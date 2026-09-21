"""
L4 -- identity resolution.

RADAR_CONTRACTS.md section B. Pure, deterministic, no I/O -- the same input
list of RawPersonRecords always produces the same list of PersonClusters,
which is what lets this module be fixture-tested without a network or an LLM
(SPEC.md I3: gates and identity are deterministic Python, never an LLM
judgement).

Merge rules, in priority order:
  1. EXACT -- two records share a non-empty linkedin_url, register_number or
     email. Strongest possible signal: these are keys a provider or a
     register issues once per person.
  2. STRONG -- two records normalise to the same name AND share a normalised
     employer token. Name normalisation folds fadas, the Ó/O'/O family of
     Irish patronymic spellings, Mc/Mac surname variants, and an
     initials-only forename against a fully-spelled one.
  3. WEAK -- two records normalise to the same name, NEITHER states an
     employer, and both state the same normalised location/county. Kept
     separate from every other same-named record unless a later exact key
     joins them -- which happens automatically here because exact keys are
     checked pairwise across the WHOLE input, not only within a cluster
     already formed by rule 2 or 3.

Hard invariant, checked before every prospective merge regardless of which
rule proposed it: two records that each carry a register_number, and the
numbers differ, are NEVER merged; the same is true of two differing
linkedin_urls. A name+employer match is a good reason to suspect two records
are the same person -- it is never a good enough reason to override a
register number or a LinkedIn URL that says otherwise.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Optional

from ..core.contracts import PersonCluster, RawPersonRecord

# Person is L4's downstream product -- imported lazily inside cluster_to_person
# rather than at module scope, purely for readability of "identity resolution
# feeds Person" as a one-way dependency; there is no import cycle either way.
from ..core.contracts import Person

# ---------------------------------------------------------------------------
# Name / employer / location normalisation
# ---------------------------------------------------------------------------


def _strip_accents(s: str) -> str:
    """NFKD + drop combining marks. Same technique as layers/validator.py's
    `normalize` and layers/contact.py's `_slug` -- reused here via the same
    approach rather than importing either, because both of those normalisers
    fold punctuation/whitespace choices (quote-matching, email-local-part)
    that are specific to their own callers and not appropriate for name
    matching (e.g. validator.normalize maps a lone "'" away entirely, which
    here would collapse "O'Riordain" the WRONG way -- see _normalise_name).
    """
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


_MC_MAC_RE = re.compile(r"^(mc|mac)(?=[a-z])")


def _fold_surname_token(tok: str) -> str:
    """Mc/Mac are the same patronymic prefix spelled two ways -- "mccarthy"
    and "maccarthy" fold to the same "carthy" core for comparison. Does not
    touch words that only happen to start with "mac" as themselves (there are
    none in this domain's surnames of any length worth guarding further)."""
    return _MC_MAC_RE.sub("", tok, count=1)


def _normalise_name(full_name: str) -> list[str]:
    """Tokenise a name for identity matching.

    "Seán Ó Ríordáin", "Sean O Riordain" and "S. O'Riordain" must all produce
    the same trailing token set: accents are stripped, a bare "o"/"ó" token
    (the Irish patronymic particle, with or without the apostrophe spelling)
    is fused onto the surname that follows it, and Mc/Mac is folded on every
    remaining token.
    """
    s = _strip_accents(full_name).lower()
    s = s.replace("'", "").replace("’", "").replace(".", " ")
    raw_tokens = [t for t in re.split(r"[\s-]+", s) if t]

    tokens: list[str] = []
    i = 0
    while i < len(raw_tokens):
        tok = raw_tokens[i]
        if tok == "o" and i + 1 < len(raw_tokens):
            # "O Riordain" / "O'Riordain" (apostrophe already stripped above,
            # so it already reads as "o riordain" at this point) -> one token.
            tok = "o" + raw_tokens[i + 1]
            i += 2
        else:
            i += 1
        tokens.append(_fold_surname_token(tok))
    return tokens


def _names_match(a: str, b: str) -> bool:
    """True when two full names denote the same person for merge purposes.

    Surnames (last normalised token) must match exactly. Remaining forename
    tokens are compared pairwise, leniently: a single-letter token matches
    any token starting with that letter (an initial standing in for a
    fully-spelled forename), otherwise the tokens must be equal. A record
    with no forename tokens at all (surname only) matches on surname alone.
    """
    ta, tb = _normalise_name(a), _normalise_name(b)
    if not ta or not tb or ta[-1] != tb[-1]:
        return False
    fore_a, fore_b = ta[:-1], tb[:-1]
    if not fore_a or not fore_b:
        return True
    for x, y in zip(fore_a, fore_b):
        if len(x) == 1 or len(y) == 1:
            if x[0] != y[0]:
                return False
        elif x != y:
            return False
    return True


def _normalise_token(s: Optional[str]) -> Optional[str]:
    """Loose fold for employer / location strings: accents, case, and
    non-alphanumeric characters removed, so "O'Connor Sutton Cronin" and
    "Cork" compare on their letters alone."""
    if not s:
        return None
    folded = re.sub(r"[^a-z0-9]", "", _strip_accents(s).lower())
    return folded or None


# ---------------------------------------------------------------------------
# Merge-rule evaluation
# ---------------------------------------------------------------------------

_EXACT_FIELDS = ("linkedin_url", "register_number", "email")


def _exact_key_conflict(a: RawPersonRecord, b: RawPersonRecord) -> bool:
    """True when a and b are barred from ever being merged, by any rule."""
    if a.register_number and b.register_number and a.register_number.strip() != b.register_number.strip():
        return True
    if a.linkedin_url and b.linkedin_url and _normalise_token(a.linkedin_url) != _normalise_token(b.linkedin_url):
        return True
    return False


def _exact_match(a: RawPersonRecord, b: RawPersonRecord) -> Optional[str]:
    for field in _EXACT_FIELDS:
        va, vb = getattr(a, field), getattr(b, field)
        if not va or not vb:
            continue
        norm = _normalise_token(va) if field != "register_number" else va.strip()
        norm_b = _normalise_token(vb) if field != "register_number" else vb.strip()
        if norm and norm == norm_b:
            return field
    return None


class _DSU:
    """Union-find with a conflict guard baked into `union`."""

    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: int, y: int) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx != ry:
            # Deterministic: always attach the higher root index under the
            # lower one, independent of call order.
            if rx < ry:
                self.parent[ry] = rx
            else:
                self.parent[rx] = ry


def resolve_identity(records: list[RawPersonRecord]) -> list[PersonCluster]:
    """Cluster RawPersonRecords into PersonClusters. Pure; no I/O.

    Every pair of records is evaluated once, in input order, against all
    three merge rules; a pair barred by the register_number/linkedin_url
    conflict guard is never merged under ANY rule, including a later exact
    key on a different field (an unlikely but not impossible input: two
    conflicting register numbers plus a shared email would still refuse to
    merge). A transitive chain -- A matches B by rule 2, B matches C by rule
    3/1 -- lands all three in one cluster via the union-find, with every
    basis that contributed listed on it.
    """
    n = len(records)
    dsu = _DSU(n)
    basis_by_pair: dict[tuple[int, int], str] = {}

    for i in range(n):
        for j in range(i + 1, n):
            a, b = records[i], records[j]
            if _exact_key_conflict(a, b):
                continue
            field = _exact_match(a, b)
            if field:
                dsu.union(i, j)
                basis_by_pair[(i, j)] = field
                continue
            if not _names_match(a.full_name, b.full_name):
                continue
            emp_a, emp_b = _normalise_token(a.employer), _normalise_token(b.employer)
            if emp_a and emp_b and emp_a == emp_b:
                dsu.union(i, j)
                basis_by_pair[(i, j)] = "name+employer"
                continue
            if not emp_a and not emp_b:
                loc_a, loc_b = _normalise_token(a.location), _normalise_token(b.location)
                if loc_a and loc_b and loc_a == loc_b:
                    dsu.union(i, j)
                    basis_by_pair[(i, j)] = "name+county"

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(dsu.find(i), []).append(i)

    # Post-pass: transitive merges can still land two records that DIRECTLY
    # conflict (differing register_number or linkedin_url) in the same
    # cluster, even though `_exact_key_conflict` refused to merge THAT PAIR
    # directly. A~B by name+employer, B~C by name+employer, but A and C carry
    # two different register numbers -- A-C is never checked as a union
    # candidate (only A-B and B-C ever call dsu.union), so the conflict never
    # blocks the transitive join. Split any such group here: every record
    # that would introduce a conflicting exact key against the group's
    # majority value is peeled off into its own sub-cluster instead of being
    # silently merged into a person it structurally cannot be.
    final_groups: list[list[int]] = []
    for idxs in groups.values():
        final_groups.extend(_split_on_conflicts(records, idxs))

    _RANK = {"linkedin_url": 2, "register_number": 2, "email": 2,
             "name+employer": 1, "name+county": 0}
    _CONF = {2: "exact", 1: "strong", 0: "weak"}

    clusters: list[PersonCluster] = []
    for idxs in sorted(final_groups, key=lambda g: min(g)):
        members = [records[i] for i in idxs]
        idx_set = set(idxs)
        bases: list[str] = []
        best_rank = 0  # a singleton with no merge is "weak" by default
        for (i, j), field in basis_by_pair.items():
            if i in idx_set and j in idx_set:
                if field not in bases:
                    bases.append(field)
                best_rank = max(best_rank, _RANK[field])
        clusters.append(PersonCluster(
            person_id=_cluster_person_id(members),
            members=members,
            basis=bases,
            confidence=_CONF[best_rank],
        ))
    return clusters


def _split_on_conflicts(records: list[RawPersonRecord], idxs: list[int]) -> list[list[int]]:
    """Split one union-find group so no sub-group carries two distinct
    non-empty values for register_number or linkedin_url.

    Greedy and deterministic (input order): walk the group in index order,
    keeping a running "this sub-group's register_number/linkedin_url so far"
    per bucket; a record that conflicts with a bucket's established value on
    either field starts (or joins) a different bucket instead. A record with
    neither field set never conflicts with anything and joins the first
    bucket, preserving today's behaviour for the overwhelmingly common case
    where nothing in _EXACT_FIELDS conflicts at all.
    """
    if len(idxs) <= 1:
        return [idxs]

    buckets: list[dict[str, Optional[str]]] = []  # per-bucket established keys
    bucket_members: list[list[int]] = []

    for i in idxs:
        rec = records[i]
        reg = rec.register_number.strip() if rec.register_number else None
        li = _normalise_token(rec.linkedin_url)
        placed = False
        for b, established in enumerate(buckets):
            reg_conflict = reg and established.get("register_number") and established["register_number"] != reg
            li_conflict = li and established.get("linkedin_url") and established["linkedin_url"] != li
            if reg_conflict or li_conflict:
                continue
            if reg and not established.get("register_number"):
                established["register_number"] = reg
            if li and not established.get("linkedin_url"):
                established["linkedin_url"] = li
            bucket_members[b].append(i)
            placed = True
            break
        if not placed:
            buckets.append({"register_number": reg, "linkedin_url": li})
            bucket_members.append([i])

    return bucket_members


# ---------------------------------------------------------------------------
# Canonicalisation
# ---------------------------------------------------------------------------


def _canonical_name(members: list[RawPersonRecord]) -> str:
    """The longest fully-spelled variant, fadas preserved.

    "Longest" is a proxy for "most fully spelled" -- "Seán Ó Ríordáin" (15
    chars) beats "S. O'Riordain" (13) and "Sean O Riordain" (15, ASCII-only,
    tied on length). Ties break toward the variant with more accented
    characters (a fada-bearing spelling is more fully spelled than its ASCII
    transliteration of the same length), then toward input order for
    determinism.
    """
    def accent_count(s: str) -> int:
        return sum(1 for ch in unicodedata.normalize("NFKD", s) if unicodedata.combining(ch))

    best = members[0].full_name
    best_key = (len(best), accent_count(best))
    for m in members[1:]:
        key = (len(m.full_name), accent_count(m.full_name))
        if key > best_key:
            best, best_key = m.full_name, key
    return best


def _canonical_employer(members: list[RawPersonRecord]) -> Optional[str]:
    """The most recent employer.

    RawPersonRecord carries no timestamp (RADAR_CONTRACTS.md section B does
    not give it one), so "most recent" is approximated by input order: the
    caller is expected to supply records in the order they were harvested
    (oldest first), and this returns the LAST non-empty employer seen in that
    order. Documented resolution of a spec ambiguity -- see the build report.
    """
    employer = None
    for m in members:
        if m.employer:
            employer = m.employer
    return employer


def _slugify(text: str) -> str:
    folded = re.sub(r"[^a-z0-9]+", "-", _strip_accents(text).lower()).strip("-")
    return folded or "x"


def _cluster_person_id(members: list[RawPersonRecord]) -> str:
    """Deterministic slug of canonical name + employer token.

    Two distinct clusters can legitimately share both a canonical name and
    "no employer" (two same-named people in different counties, neither
    stating an employer, correctly kept separate by resolve_identity's weak
    rule) -- a bare name+employer slug would collide for them. A short
    content hash of the member set is appended unconditionally to make the
    id unique regardless of that case, while keeping the human-legible
    name/employer prefix the spec asks for.
    """
    name_part = _slugify(_canonical_name(members))
    employer = _canonical_employer(members)
    employer_part = _slugify(employer) if employer else "unknown"
    digest = hashlib.sha1(
        "|".join(sorted(m.source + ":" + m.source_ref for m in members)).encode("utf-8")
    ).hexdigest()[:8]
    return name_part + "-" + employer_part + "-" + digest


# ---------------------------------------------------------------------------
# Identity corroboration for a fetched page / search snippet
# (2026-09-11 adversarial-audit fix, item 4).
#
# A near-miss deepening search or a discovery snippet finds a URL by matching
# on the person's NAME ALONE -- and a common name matches a page about a
# wholly different person in a wholly different profession. The exhibit: a
# Porsche sales listing for a "Shane Heffernan" got attached to a structural
# engineer of the same name. A page/snippet may be attached to a person only
# when the text NEAR the name corroborates their professional identity (their
# employer, or a discipline word) AND carries no token naming a contradicting
# profession.
# ---------------------------------------------------------------------------

# 2026-09-11 second-audit fix (item 4): bare "engineer"/"engineering" is NOT
# corroboration on its own -- a GooseChase treasure-hunt page or an
# electrical/software/mechanical bio also says "engineer" freely, and that is
# exactly how "Andrew Cross" (uwaterloo GooseChase) got attached to a
# structural engineer of the same name. Requires the DISCIPLINE to be named
# (structural/civil/consulting), not just the generic job-family word.
_DISCIPLINE_TOKEN_RE = re.compile(
    r"structural|civil|consult(?:ing|ancy)", re.I
)

# 2026-09-11 second-audit fix (item 4): widened with adjacent professions and
# generic-engineer titles a "civil/structural" page never uses for itself --
# a page naming these alongside a bare "engineer" is evidence of the WRONG
# profession, not corroboration of a structural/civil engineer.
_CONTRADICTING_PROFESSION_RE = re.compile(
    r"\bsales\b|\bmarketing\b|automotive|journalism|journalist|\bnurse\b|"
    r"\bnursing\b|\bteacher\b|solicitor|barrister|\bchef\b|pharmac|physio|"
    r"\bdentist\b|estate agent|\brecruit|founder|co-founder|\bceo\b|"
    r"chief executive|startup|mechanical engineer|\bsoftware\b|"
    r"electrical engineer|aerospace|automotive|\bprofessor\b|\blecturer\b",
    re.I,
)

_EMPLOYER_STOPWORDS = {
    "the", "and", "of", "ltd", "limited", "group", "consulting",
    "consultants", "engineers", "engineering", "co", "llp", "plc",
    "associates", "partners",
}


def _significant_employer_words(employer: Optional[str]) -> list[str]:
    """Employer words worth matching on -- generic firm-shape words like
    "Consulting" or "Group" corroborate nothing on their own."""
    if not employer:
        return []
    words = re.findall(r"[A-Za-z]{3,}", employer)
    return [w for w in words if w.lower() not in _EMPLOYER_STOPWORDS]


def has_identity_corroboration(
    window_text: Optional[str], employer: Optional[str] = None
) -> bool:
    """True when `window_text` (the text around a name occurrence) supports
    attaching this page/snippet to the named person, per the rule above.

    Corroboration: a discipline token anywhere in the window, OR at least two
    significant words of the person's current employer. Any contradicting
    profession token in the window is disqualifying regardless of
    corroboration -- a page can name both "structural" and "sales" (an
    engineering firm's careers page, say), and the contradiction still wins,
    because the failure mode this guards is exactly a plausible-looking but
    wrong page.
    """
    text = window_text or ""
    if not text.strip():
        return False
    if _CONTRADICTING_PROFESSION_RE.search(text):
        return False
    if _DISCIPLINE_TOKEN_RE.search(text):
        return True
    words = _significant_employer_words(employer)
    hits = sum(
        1 for w in words if re.search(r"\b" + re.escape(w) + r"\b", text, re.I)
    )
    return hits >= 2


def cluster_to_person(cluster: PersonCluster) -> Person:
    """The Person the pipeline downstream of L4 actually consumes."""
    members = cluster.members
    linkedin = next((m.linkedin_url for m in members if m.linkedin_url), None)
    title = next((m.title for m in reversed(members) if m.title), None)
    loc_member = next((m for m in reversed(members) if m.location), None)
    location = loc_member.location if loc_member else None
    location_source = loc_member.location_source if loc_member else None
    doc_ids: list[str] = []
    for m in members:
        for d in m.doc_ids:
            if d not in doc_ids:
                doc_ids.append(d)
    return Person(
        person_id=cluster.person_id,
        full_name=_canonical_name(members),
        current_title=title,
        current_employer=_canonical_employer(members),
        location=location,
        location_source=location_source,
        doc_ids=doc_ids,
        linkedin_url=linkedin,
    )
