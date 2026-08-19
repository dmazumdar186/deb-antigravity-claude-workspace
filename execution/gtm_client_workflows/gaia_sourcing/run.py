"""
L0 -- the orchestrator.

Runs the pipeline in named, resumable stages. Every stage writes its output to
`run/<campaign_id>/<stage>.json` and every later stage reads that file rather
than recomputing. This matters more here than in most pipelines: the expensive
steps are paid API calls (Firecrawl renders, Claude extractions, Prospeo
lookups), so a crash in stage 7 must not re-buy stages 1-6.

Stage order:

  harvest_r1   Firecrawl-render every firm's staff directory        (paid)
  harvest_r2   An Coimisiun Pleanala oral-hearing witness statements (free)
  extract      L5  evidence extraction, both roles                  (paid)
  validate     L6  quote validation -- THE PRODUCT                  (free)
  gate         L7  deterministic gates + tiering                    (free)
  deepen_r1    Re-render the individual profile pages of candidates
               that already passed the gates, and extract again.
               Aimed only at gate-passers, because the directory blurb
               establishes chartership but rarely Eurocode/Tekla, and
               that gap is what holds Role 1 at Tier C.              (paid)
  adversarial  L8  blind second pass + deterministic demotion        (paid)
  contact      L9  Prospeo enrichment                               (paid)
  movability   L10                                                  (paid)
  messages     L11 outreach drafting                                (paid)
  linkcheck    L12 liveness + name match                            (free)
  render       L13 dossier.html + candidates.csv + pool maps        (free)

Usage:
    py -m gtm_client_workflows.gaia_sourcing.run --stage all
    py -m gtm_client_workflows.gaia_sourcing.run --stage extract --force
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from .core.cache import fetch_rendered
from .core.config import CONFIG, PKG_ROOT
from .core.providers import autoselect_plan
from .core.contracts import (
    Claim,
    ContactRecord,
    Evaluation,
    GateResult,
    MovabilitySignal,
    OutreachSequence,
    Person,
    RawDocument,
    ValidatedClaim,
)
from .layers import adversarial, contact, gates, linkcheck, messages, movability
from .layers.extract import extract_directory, extract_from_document
from .layers.validator import validate_all
from .roles import ROLE1, ROLE2, ROLES, is_client_side
from .sources import acp, company_bios, technical_evidence

RUN_DIR = PKG_ROOT / "run" / CONFIG.campaign_id
LOG_DIR = PKG_ROOT / "logs"

_PRINT_LOCK = threading.Lock()


def log(msg: str) -> None:
    with _PRINT_LOCK:
        print(msg, flush=True)


def run_all(fn, items, workers: int = 4, label: str = "") -> int:
    """Run `fn` over `items` concurrently, surviving per-item failures.

    `ThreadPoolExecutor.map` re-raises the first exception when its result
    iterator is consumed, which kills the whole stage. On this pipeline's
    first full run that cost roughly 190 already-extracted Role 1 people to a
    single unpacking error in the Role 2 branch -- the stage saves only at the
    end, so everything in memory went with it.

    A stage is a batch of independent work. One bad item degrades coverage by
    one item; it must never cost the batch.
    """
    failures = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(fn, item): item for item in items}
        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception as exc:
                failures += 1
                log("  [" + (label or "worker") + "] item failed: " + repr(exc)[:140])
    if failures:
        log("  [" + (label or "worker") + "] " + str(failures) + " of "
            + str(len(items)) + " items failed; the rest were kept")
    return failures


# ---------------------------------------------------------------------------
# Stage persistence
# ---------------------------------------------------------------------------


def _path(stage: str) -> Path:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    return RUN_DIR / (stage + ".json")


def save(stage: str, obj) -> None:
    _path(stage).write_text(
        json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )
    log("  [saved] " + stage + ".json")


def load(stage: str):
    p = _path(stage)
    if not p.exists():
        raise SystemExit(
            "Stage '" + stage + "' has not run yet (" + str(p) + " missing)."
        )
    return json.loads(p.read_text(encoding="utf-8"))


def done(stage: str) -> bool:
    return _path(stage).exists()


# Documents live in their own append-only store keyed by doc_id, because the
# validator needs the full source text of every document any claim cites and
# the adversarial layer needs excerpts from the same set.
DOCS = RUN_DIR / "docs.jsonl"


def save_docs(docs: list[RawDocument]) -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    existing = {d.doc_id for d in load_docs().values()} if DOCS.exists() else set()
    with DOCS.open("a", encoding="utf-8") as fh:
        for d in docs:
            if d.doc_id in existing:
                continue
            existing.add(d.doc_id)
            fh.write(json.dumps(d.model_dump(), ensure_ascii=False, default=str) + "\n")


def load_docs() -> dict[str, RawDocument]:
    if not DOCS.exists():
        return {}
    out: dict[str, RawDocument] = {}
    for line in DOCS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            d = RawDocument(**json.loads(line))
        except Exception:
            continue
        out[d.doc_id] = d
    return out


# ---------------------------------------------------------------------------
# Stage 1a -- Role 1 staff directories, Firecrawl-rendered
# ---------------------------------------------------------------------------

# Firms domiciled in Ireland. Their staff directory lists Irish staff, so a
# person with no stated office is in Ireland by default. The global firms
# (RPS / Arup / Jacobs) list worldwide staff on the same page, so they get no
# default and must evidence location per-person or fail located_ie.
_IRISH_DOMICILED = {
    "rod", "punch", "dbfl", "oconnor_sutton", "mwp", "nodwyer",
    "barrett_mahony", "horganlynch", "kilgallen", "tjoc", "cora",
    "downes", "axis",
}


def stage_harvest_r1(force: bool = False) -> None:
    if done("harvest_r1") and not force:
        log("harvest_r1: cached, skipping")
        return
    log("harvest_r1: discovering + rendering staff directories for "
        + str(len(company_bios.FIRMS)) + " firms")

    records: list[dict] = []
    docs: list[RawDocument] = []
    lock = threading.Lock()

    def one(firm) -> None:
        try:
            indexes = company_bios.find_people_indexes(firm, limit=3)
            guessed = ["https://www." + firm.domain + p for p in firm.people_paths]
            for url in list(dict.fromkeys(indexes + guessed))[:4]:
                doc = fetch_rendered(url, source_type="company_bio")
                if doc is None or len(doc.content_text) < 800:
                    continue
                with lock:
                    docs.append(doc)
                    records.append(
                        {
                            "firm_slug": firm.slug,
                            "firm_name": firm.name,
                            "url": url,
                            "doc_id": doc.doc_id,
                            "chars": len(doc.content_text),
                            "default_location": (
                                "Ireland" if firm.slug in _IRISH_DOMICILED else None
                            ),
                        }
                    )
                log("  " + firm.slug + ": " + str(len(doc.content_text)) + " chars <- " + url)
        except Exception as exc:
            log("  " + firm.slug + " FAILED: " + repr(exc)[:120])

    run_all(one, company_bios.FIRMS, workers=4, label="harvest_r1")

    save_docs(docs)
    save("harvest_r1", records)
    log("harvest_r1: " + str(len(records)) + " directory pages from "
        + str(len({r["firm_slug"] for r in records})) + " firms")


# ---------------------------------------------------------------------------
# Stage 1b -- Role 2 oral-hearing witness statements
# ---------------------------------------------------------------------------

# Cases seeded by hand plus whatever discovery finds. Hand-seeding matters:
# Serper cannot reach ACP's /publicaccess/ tree (HANDOFF correction 5), so the
# case numbers come from the scheme names a transport recruiter already knows.
SEED_CASES = [
    # Verified real case references (checked against pleanala.ie, 2026-08-19).
    # An earlier pass in this file carried INVENTED case numbers; 9 of 10
    # returned nothing, which is the correct behaviour for a number that does
    # not exist but wasted a harvest cycle. Every entry below was confirmed
    # from a published document or case page before being added.
    "314724",  # MetroLink -- oral hearing Feb-Mar 2024, the largest in the set
    "314232",  # DART+ West Railway Order -- oral hearing Sept-Oct 2023
    "320164",  # DART+ Coastal North Railway Order -- oral hearing 2025
    "302885",  # N6 Galway City Ring Road -- oral hearing 2020
    "317742",  # BusConnects Bray to City Centre Core Bus Corridor
    "317679",  # BusConnects core bus corridor
    "316828",  # BusConnects core bus corridor
    "314942",  # BusConnects core bus corridor
    "314597",  # BusConnects core bus corridor
    "313509",  # BusConnects core bus corridor
    "316119",  # DART+ programme
    "318220",  # N6 Galway City Ring Road -- further information
    "302848",  # N6 Galway City Ring Road -- associated
    "310286",  # Dublin Port MP2 -- already harvested, kept for completeness
]


def stage_harvest_r2(force: bool = False) -> None:
    if done("harvest_r2") and not force:
        log("harvest_r2: cached, skipping")
        return
    log("harvest_r2: harvesting ACP oral-hearing documents")

    cases = list(dict.fromkeys(SEED_CASES))
    try:
        cases += [c for c in acp.discover_cases_serper(acp.DISCOVERY_QUERIES) if c not in cases]
    except Exception as exc:
        log("  case discovery failed (continuing with seeds): " + repr(exc)[:120])

    records: list[dict] = []
    docs: list[RawDocument] = []
    lock = threading.Lock()

    def one(case_no: str) -> None:
        try:
            harvested = acp.harvest(case_no, verify_text=True)
        except Exception as exc:
            log("  case " + case_no + " FAILED: " + repr(exc)[:120])
            return
        if not harvested:
            return
        with lock:
            for adoc, rdoc in harvested:
                docs.append(rdoc)
                records.append(
                    {
                        "case_no": case_no,
                        "url": adoc.url,
                        "doc_id": rdoc.doc_id,
                        "person_hint": adoc.person_hint,
                        "party": adoc.party,
                        "chars": len(rdoc.content_text),
                    }
                )
        log("  case " + case_no + ": " + str(len(harvested)) + " witness documents")

    run_all(one, cases[:40], workers=4, label="harvest_r2")

    save_docs(docs)
    save("harvest_r2", records)
    log("harvest_r2: " + str(len(records)) + " documents across "
        + str(len({r["case_no"] for r in records})) + " cases")


# ---------------------------------------------------------------------------
# Stage 2 -- L5 extraction
# ---------------------------------------------------------------------------


def stage_extract(force: bool = False) -> None:
    """Extract from every harvested document not already extracted.

    Incremental by doc_id rather than all-or-nothing. Harvesting more firms
    is the main lever on pool size, so this stage gets re-run often; paying
    again for the documents already processed would make each new firm cost
    the price of every previous one.
    """
    corpus = load_docs()
    persons: dict[str, dict] = {}
    claims: list[dict] = []
    seen_docs: set[str] = set()
    if done("extract") and not force:
        prev = load("extract")
        persons = prev.get("persons", {})
        claims = prev.get("claims", [])
        seen_docs = set(prev.get("extracted_doc_ids", []))
        log("extract: resuming, " + str(len(seen_docs)) + " documents already done")
    lock = threading.Lock()

    # -- Role 1: one directory page yields many people ----------------------
    r1 = load("harvest_r1")
    log("extract: Role 1 across " + str(len(r1)) + " directory pages")

    def do_dir(rec: dict) -> None:
        doc = corpus.get(rec["doc_id"])
        if doc is None or doc.doc_id in seen_docs:
            return
        try:
            found = extract_directory(
                doc,
                employer=rec["firm_name"],
                default_location=rec.get("default_location"),
            )
        except Exception as exc:
            log("  " + rec["firm_slug"] + " extract FAILED: " + repr(exc)[:120])
            return
        with lock:
            for person, pclaims in found:
                slot = persons.setdefault(
                    person.person_id,
                    {**person.model_dump(), "role_id": ROLE1.role_id,
                     "source": "company_directory"},
                )
                slot.setdefault("doc_ids", [])
                if doc.doc_id not in slot["doc_ids"]:
                    slot["doc_ids"].append(doc.doc_id)
                claims.extend(c.model_dump() for c in pclaims)
            seen_docs.add(doc.doc_id)
        log("  " + rec["firm_slug"] + ": " + str(len(found)) + " people")

    run_all(do_dir, r1, workers=3, label="extract_r1")

    # -- Role 2: one witness statement is one person ------------------------
    r2 = load("harvest_r2")
    log("extract: Role 2 across " + str(len(r2)) + " witness documents")

    def do_witness(rec: dict) -> None:
        doc = corpus.get(rec["doc_id"])
        if doc is None or doc.doc_id in seen_docs or not rec.get("person_hint"):
            return
        name = rec["person_hint"]
        pid = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        person = Person(
            person_id=pid,
            full_name=name,
            current_employer=rec.get("party"),
            doc_ids=[doc.doc_id],
        )
        try:
            found, hints = extract_from_document(person, doc)
        except Exception as exc:
            # One unreadable witness statement must not end the stage. The
            # first run of this pipeline lost ~190 extracted Role 1 people to
            # an unhandled error raised inside a worker thread.
            log("  " + pid + " extract FAILED: " + repr(exc)[:120])
            return
        if not found:
            return
        # The document's own reading of title/employer/location beats the
        # filename, which names the submitting party rather than the witness.
        for field in ("current_title", "current_employer", "location"):
            if (hints or {}).get(field):
                setattr(person, field, hints[field])
        with lock:
            slot = persons.setdefault(
                pid,
                {**person.model_dump(), "role_id": ROLE2.role_id,
                 "source": "acp_witness_statement"},
            )
            for field in ("current_title", "current_employer", "location"):
                if (hints or {}).get(field) and not slot.get(field):
                    slot[field] = hints[field]
            slot.setdefault("doc_ids", [])
            if doc.doc_id not in slot["doc_ids"]:
                slot["doc_ids"].append(doc.doc_id)
            claims.extend(c.model_dump() for c in found)
            seen_docs.add(doc.doc_id)

    run_all(do_witness, r2, workers=3, label="extract_r2")

    save("extract", {
        "persons": persons,
        "claims": claims,
        "extracted_doc_ids": sorted(seen_docs),
    })
    log("extract: " + str(len(persons)) + " persons, " + str(len(claims)) + " raw claims")


# ---------------------------------------------------------------------------
# Stage 3 -- L6 validation. The product.
# ---------------------------------------------------------------------------


def _norm_quote(q: str) -> str:
    """Whitespace- and case-insensitive key for duplicate detection."""
    return " ".join(q.split()).lower()


def stage_validate(force: bool = False) -> None:
    # Deliberately NOT cached. Validation and gating are pure functions of
    # extract.json and cost nothing, while extract.json changes every time
    # another firm or another case is harvested. Skipping them as "already
    # done" silently gated a stale pool: a run that had just extracted 174
    # people re-used a gate built from 158, so the sixteen newest -- the whole
    # of Role 2 -- never reached the shortlist. A cheap deterministic stage
    # downstream of a changing one should always recompute.
    data = load("extract")
    corpus = load_docs()
    raw = [Claim(**c) for c in data["claims"]]
    kept, stats = validate_all(raw, corpus, drops_log=LOG_DIR / "drops.jsonl")

    # Deduplicate across sources. The same staff page fetched as ocsc.ie/people
    # and www.ocsc.ie/people renders twice, and Firecrawl output varies enough
    # between renders that the two get different doc_ids -- so claim_id, which
    # hashes (person, doc, quote), does not collapse them. Left alone this
    # prints every bullet on a card twice AND inflates the primary-signal count
    # that decides the tier, which could promote someone to Tier A on one piece
    # of evidence counted twice.
    seen: set[tuple] = set()
    deduped: list = []
    for c in kept:
        key = (c.subject_person_id, c.dimension, _norm_quote(c.evidence_quote))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)
    dropped_dupes = len(kept) - len(deduped)
    stats["duplicates_collapsed"] = dropped_dupes
    if dropped_dupes:
        log("  collapsed " + str(dropped_dupes) + " duplicate claims "
            "(same quote for the same person from a re-rendered page)")

    save("validate", {
        "claims": [c.model_dump() for c in deduped],
        "stats": stats,
    })
    kept = deduped
    log("validate: " + str(stats["claims_kept"]) + " kept / "
        + str(stats["claims_in"]) + " in, drop rate "
        + format(stats["drop_rate"] * 100, ".1f") + "%")
    if stats["drop_rate"] > CONFIG.max_drop_rate:
        log("  *** DROP RATE ABOVE CEILING (" +
            format(CONFIG.max_drop_rate * 100, ".0f") + "%) -- investigate before shipping")


# ---------------------------------------------------------------------------
# Stage 4 -- L7 gates + tiering
# ---------------------------------------------------------------------------


def _persons_and_claims() -> tuple[dict[str, Person], dict[str, list[ValidatedClaim]], dict[str, str]]:
    data = load("extract")
    vd = load("validate")
    persons: dict[str, Person] = {}
    roles: dict[str, str] = {}
    for pid, rec in data["persons"].items():
        rec = dict(rec)
        roles[pid] = rec.pop("role_id")
        rec.pop("source", None)
        persons[pid] = Person(**rec)
    by_person: dict[str, list[ValidatedClaim]] = {}
    for c in vd["claims"]:
        vc = ValidatedClaim(**c)
        by_person.setdefault(vc.subject_person_id, []).append(vc)

    # The witness's own words outrank the filename. An oral-hearing document
    # is named for the PARTY that submitted it ("No.02 - TII - Witness
    # Statement of Aidan Foley"), but the witness is usually that party's
    # consultant, not its employee -- Susie Coyle's statement opens "I am an
    # Associate Director in Jacobs" while sitting under a TII filename.
    # Taking the party as the employer would file half the transport pool as
    # client-side and drop them from the shortlist for being the wrong kind of
    # right person.
    for pid, person in persons.items():
        stated = [
            c for c in by_person.get(pid, [])
            if c.dimension == "employer" and c.confidence == "direct"
        ]
        if stated:
            person.current_employer = _employer_from_claim(stated[0].assertion)                 or person.current_employer

    return persons, by_person, roles


# "Susie Coyle is an Associate Director at Jacobs." -> "Jacobs"
_EMPLOYER_TAIL_RE = re.compile(
    r"\b(?:at|with|for|in|of)\s+([A-Z][\w'&.\- ]{2,60}?)\s*\.?$"
)


def _employer_from_claim(assertion: str) -> Optional[str]:
    m = _EMPLOYER_TAIL_RE.search(assertion.strip())
    if not m:
        return None
    name = m.group(1).strip(" .")
    # Guard against swallowing a sentence tail that is not a company.
    if len(name.split()) > 6 or len(name) < 3:
        return None
    return name


def stage_gate(force: bool = False) -> None:
    # Not cached, for the same reason as stage_validate above.
    persons, by_person, roles = _persons_and_claims()
    out: dict[str, dict] = {}
    counts = {"A": 0, "B": 0, "C": 0, "EXCLUDED": 0}
    for pid, person in persons.items():
        spec = ROLES[roles[pid]]
        pclaims = by_person.get(pid, [])
        results = gates.run_gates(person, pclaims, spec)
        tier = gates.assign_tier(pclaims, results, spec)
        counts[tier] += 1
        out[pid] = {
            "role_id": spec.role_id,
            "tier": tier,
            "gates": [g.model_dump() for g in results],
            "n_claims": len(pclaims),
            "client_side": is_client_side(person.current_employer),
        }
    save("gate", out)
    log("gate: A=" + str(counts["A"]) + " B=" + str(counts["B"])
        + " C=" + str(counts["C"]) + " EXCLUDED=" + str(counts["EXCLUDED"]))


# ---------------------------------------------------------------------------
# Stage 5 -- deepen Role 1 on gate-passers only
# ---------------------------------------------------------------------------

_SLUG_SPLIT_RE = re.compile(r"[^a-z0-9]+")


def _slug_tokens(s: str) -> set[str]:
    return {t for t in _SLUG_SPLIT_RE.split(s.lower()) if len(t) >= 3}


def stage_deepen_r1(force: bool = False) -> None:
    """Fetch the individual profile page of every Role 1 gate-passer.

    A staff-directory blurb establishes chartership, grade and discipline --
    enough for the gates. It rarely names a design code or a project, which is
    what the Role 1 primary signal (`technical_skill`) needs. The individual
    profile page usually does. Spending the render + extraction budget only on
    people who already passed the gates is what makes this affordable.
    """
    if done("deepen_r1") and not force:
        log("deepen_r1: cached, skipping")
        return
    persons, _, roles = _persons_and_claims()
    gate_out = load("gate")

    # Gate-passers only, richest-evidence first, capped. The cap bounds the
    # search + extraction spend; the ordering means the cap falls on the
    # thinnest candidates, who were never going to reach Tier A anyway.
    ranked = sorted(
        (
            (-g["n_claims"], pid) for pid, g in gate_out.items()
            if g["role_id"] == ROLE1.role_id and g["tier"] != "EXCLUDED"
            and not g["client_side"]
        )
    )
    targets = [pid for _, pid in ranked][:30]
    log("deepen_r1: " + str(len(targets)) + " of " + str(len(ranked))
        + " gate-passing Role 1 candidates (capped)")

    firm_by_name = {f.name: f for f in company_bios.FIRMS}
    profile_index: dict[str, list[str]] = {}
    for pid in targets:
        emp = persons[pid].current_employer
        if not emp or emp in profile_index:
            continue
        firm = firm_by_name.get(emp)
        if firm is None:
            continue
        try:
            profile_index[emp] = [b.url for b in company_bios.crawl_people_index(firm, limit=80)]
            log("  " + firm.slug + ": " + str(len(profile_index[emp])) + " profile URLs")
        except Exception as exc:
            log("  " + firm.slug + " index FAILED: " + repr(exc)[:120])
            profile_index[emp] = []

    new_claims: list[dict] = []
    matched: dict[str, str] = {}
    docs: list[RawDocument] = []
    lock = threading.Lock()

    def one(pid: str) -> None:
        person = persons[pid]
        urls = profile_index.get(person.current_employer or "", [])
        want = _slug_tokens(person.full_name)
        hit = None
        for u in urls:
            if len(want & _slug_tokens(u.rsplit("/", 2)[-1] or u)) >= 2:
                hit = u
                break
        if hit is None:
            return
        doc = fetch_rendered(hit, source_type="company_bio")
        if doc is None or len(doc.content_text) < 300:
            return
        try:
            found, _hints = extract_from_document(person, doc)
        except Exception as exc:
            log("  " + pid + " deepen extract FAILED: " + repr(exc)[:120])
            return
        with lock:
            docs.append(doc)
            matched[pid] = hit
            new_claims.extend(c.model_dump() for c in found)
        log("  " + pid + ": +" + str(len(found)) + " claims from " + hit)

    run_all(one, targets, workers=4, label="deepen_profile")

    # -- Channel 2: per-candidate technical-evidence search -----------------
    # The directory pages carry zero occurrences of Eurocode / Tekla / ETABS
    # (measured across all 16 of them), so channel 1 alone caps Role 1 at
    # Tier C. See sources/technical_evidence.py for the numbers.
    tech_urls: dict[str, list[str]] = {}

    def tech(pid: str) -> None:
        person = persons[pid]
        try:
            found = technical_evidence.discover_for(
                pid, person.full_name, person.current_employer
            )
            harvested = technical_evidence.harvest(found)
        except Exception as exc:
            log("  " + pid + " tech search FAILED: " + repr(exc)[:120])
            return
        if not harvested:
            return
        for tdoc, rdoc in harvested[:3]:
            try:
                claims, _h = extract_from_document(person, rdoc)
            except Exception as exc:
                log("  " + pid + " tech extract FAILED: " + repr(exc)[:120])
                continue
            if not claims:
                continue
            with lock:
                docs.append(rdoc)
                tech_urls.setdefault(pid, []).append(tdoc.url)
                new_claims.extend(c.model_dump() for c in claims)
            log("  " + pid + ": +" + str(len(claims)) + " technical claims from "
                + tdoc.url[:70])

    log("deepen_r1: technical-evidence search across " + str(len(targets)))
    run_all(tech, targets, workers=4, label="deepen_tech")

    save_docs(docs)
    save("deepen_r1", {
        "profile_urls": matched,
        "technical_urls": tech_urls,
        "claims": new_claims,
    })
    log("deepen_r1: " + str(len(matched)) + " profiles deepened, "
        + str(len(tech_urls)) + " candidates with technical evidence, "
        + str(len(new_claims)) + " new raw claims")

    # Fold the new claims back through L5 -> L6 -> L7 so tiering reflects them.
    if new_claims:
        data = load("extract")
        have = {c["claim_id"] for c in data["claims"]}
        data["claims"].extend(c for c in new_claims if c["claim_id"] not in have)
        for pid, url in matched.items():
            data["persons"][pid]["profile_url"] = url
        save("extract", data)
        stage_validate(force=True)
        stage_gate(force=True)


# ---------------------------------------------------------------------------
# Stage 6 -- L8 adversarial (blind)
# ---------------------------------------------------------------------------


def _shortlist(limit_per_role: Optional[dict[str, int]] = None) -> dict[str, list[str]]:
    """Gate-passing candidates per role, best tier first.

    Client-side employees are held out of the 15 per SPEC 2.3 and surface in
    the dossier sidebar instead.
    """
    gate_out = load("gate")
    persons, by_person, _ = _persons_and_claims()
    order = {"A": 0, "B": 1, "C": 2}
    out: dict[str, list[str]] = {}
    for role_id in (ROLE1.role_id, ROLE2.role_id):
        rows = [
            (order[g["tier"]], -g["n_claims"], pid)
            for pid, g in gate_out.items()
            if g["role_id"] == role_id
            and g["tier"] != "EXCLUDED"
            and not g["client_side"]
        ]
        rows.sort()
        pids = [pid for _, _, pid in rows]
        if limit_per_role:
            pids = pids[: limit_per_role.get(role_id, len(pids))]
        out[role_id] = pids
    return out


def stage_adversarial(force: bool = False) -> None:
    if done("adversarial") and not force:
        log("adversarial: cached, skipping")
        return
    persons, by_person, _ = _persons_and_claims()
    gate_out = load("gate")
    corpus = load_docs()

    short = _shortlist({ROLE1.role_id: 24, ROLE2.role_id: 14})
    targets = short[ROLE1.role_id] + short[ROLE2.role_id]
    log("adversarial: reviewing " + str(len(targets)) + " candidates (blind)")

    out: dict[str, dict] = {}
    lock = threading.Lock()

    def one(pid: str) -> None:
        g = gate_out[pid]
        spec = ROLES[g["role_id"]]
        results = [GateResult(**r) for r in g["gates"]]
        try:
            rec = adversarial.critique(
                persons[pid], by_person.get(pid, []), spec, corpus, results, g["tier"]
            )
        except Exception as exc:
            log("  " + pid + " critique FAILED: " + repr(exc)[:120])
            return
        with lock:
            out[pid] = rec.model_dump()
        log("  " + pid + ": " + g["tier"] + " -> " + rec.tier)

    run_all(one, targets, workers=4, label="adversarial")

    save("adversarial", out)


# ---------------------------------------------------------------------------
# Stage 7 -- L9 contact / L10 movability / L11 messages / L12 linkcheck
# ---------------------------------------------------------------------------


def _final_tier(pid: str, gate_out: dict, adv: dict) -> str:
    rec = adv.get(pid)
    if rec and rec.get("tier"):
        return str(rec["tier"])
    return gate_out[pid]["tier"]


def _delivery_set() -> dict[str, list[str]]:
    """The candidates that actually ship, post-adversarial, best tier first."""
    gate_out = load("gate")
    adv = load("adversarial") if done("adversarial") else {}
    persons, by_person, _ = _persons_and_claims()
    order = {"A": 0, "B": 1, "C": 2}
    out: dict[str, list[str]] = {}
    for role_id, spec in ((ROLE1.role_id, ROLE1), (ROLE2.role_id, ROLE2)):
        rows = []
        for pid, g in gate_out.items():
            if g["role_id"] != role_id or g["tier"] == "EXCLUDED" or g["client_side"]:
                continue
            t = _final_tier(pid, gate_out, adv)
            if t == "EXCLUDED":
                continue
            rows.append((order.get(t, 3), -g["n_claims"], pid))
        rows.sort()
        out[role_id] = [pid for _, _, pid in rows][: spec.target_count]
    return out


def stage_contact(force: bool = False) -> None:
    if done("contact") and not force:
        log("contact: cached, skipping")
        return
    persons, _, _ = _persons_and_claims()
    delivery = _delivery_set()
    targets = delivery[ROLE1.role_id] + delivery[ROLE2.role_id]
    log("contact: enriching " + str(len(targets)) + " candidates via Prospeo")

    out: dict[str, dict] = {}
    for pid in targets:
        try:
            rec = contact.enrich(persons[pid])
        except Exception as exc:
            log("  " + pid + " enrich FAILED: " + repr(exc)[:120])
            continue
        out[pid] = rec.model_dump()
        log("  " + pid + ": " + str(rec.email or "-") + " [" + rec.email_status + "]")
    save("contact", out)
    log("contact: prospeo stats " + json.dumps(contact.run_stats()))


def stage_movability(force: bool = False) -> None:
    if done("movability") and not force:
        log("movability: cached, skipping")
        return
    persons, by_person, roles = _persons_and_claims()
    delivery = _delivery_set()
    out: dict[str, dict] = {}
    lock = threading.Lock()

    def one(pid: str) -> None:
        spec = ROLES[roles[pid]]
        try:
            sig = movability.assess(persons[pid], by_person.get(pid, []), spec)
        except Exception as exc:
            log("  " + pid + " movability FAILED: " + repr(exc)[:120])
            return
        with lock:
            out[pid] = sig.model_dump()

    targets = delivery[ROLE1.role_id] + delivery[ROLE2.role_id]
    log("movability: assessing " + str(len(targets)))
    run_all(one, targets, workers=4, label="movability")
    save("movability", out)


def stage_messages(force: bool = False) -> None:
    if done("messages") and not force:
        log("messages: cached, skipping")
        return
    persons, by_person, roles = _persons_and_claims()
    delivery = _delivery_set()
    out: dict[str, dict] = {}
    lock = threading.Lock()

    def one(pid: str) -> None:
        spec = ROLES[roles[pid]]
        try:
            seq = messages.draft(persons[pid], by_person.get(pid, []), spec)
        except Exception as exc:
            log("  " + pid + " draft FAILED: " + repr(exc)[:120])
            return
        if seq is None:
            return
        ok, problems = messages.compliance_ok(seq)
        if not ok:
            # I6 is a hard gate: a non-compliant draft is dropped, never
            # patched, because a patched legal notice is the failure mode the
            # invariant exists to prevent.
            log("  " + pid + " draft dropped, compliance: " + "; ".join(problems))
            return
        with lock:
            out[pid] = seq.model_dump()

    targets = delivery[ROLE1.role_id] + delivery[ROLE2.role_id]
    log("messages: drafting " + str(len(targets)))
    run_all(one, targets, workers=4, label="messages")
    save("messages", out)


def stage_linkcheck(force: bool = False) -> None:
    if done("linkcheck") and not force:
        log("linkcheck: cached, skipping")
        return
    persons, by_person, _ = _persons_and_claims()
    data = load("extract")
    contacts = load("contact") if done("contact") else {}
    delivery = _delivery_set()
    targets = delivery[ROLE1.role_id] + delivery[ROLE2.role_id]
    log("linkcheck: checking " + str(len(targets)) + " candidates")

    out: dict[str, dict] = {}
    lock = threading.Lock()

    def one(pid: str) -> None:
        profile = data["persons"].get(pid, {}).get("profile_url")
        if not profile:
            c = contacts.get(pid) or {}
            profile = c.get("linkedin_url")
        evidence = list(dict.fromkeys(
            str(c.source_url) for c in by_person.get(pid, [])
        ))[:6]
        try:
            rep = linkcheck.check_person(pid, persons[pid].full_name, profile, evidence)
        except Exception as exc:
            log("  " + pid + " linkcheck FAILED: " + repr(exc)[:120])
            return
        with lock:
            out[pid] = {
                "person_id": pid,
                "all_alive": rep.all_alive,
                "checks": [vars(c) for c in rep.checks],
            }

    run_all(one, targets, workers=6, label="linkcheck")
    save("linkcheck", out)


# ---------------------------------------------------------------------------
# Pool map (SPEC 2.2) -- the honest denominator
# ---------------------------------------------------------------------------


def stage_poolmap(force: bool = False) -> None:
    persons, by_person, roles = _persons_and_claims()
    gate_out = load("gate")
    adv = load("adversarial") if done("adversarial") else {}
    delivery = _delivery_set()
    raw = load("extract")

    out: dict[str, dict] = {}
    for role_id in (ROLE1.role_id, ROLE2.role_id):
        pids = [p for p, r in roles.items() if r == role_id]
        reasons: dict[str, int] = {}
        client_side: list[str] = []
        for pid in pids:
            g = gate_out.get(pid)
            if g is None:
                continue
            if g["client_side"]:
                client_side.append(
                    persons[pid].full_name + " -- " + (persons[pid].current_employer or "")
                )
            for gr in g["gates"]:
                if not gr["passed"]:
                    reasons[gr["gate_id"]] = reasons.get(gr["gate_id"], 0) + 1
        n_raw = len([c for c in raw["claims"] if c["subject_person_id"] in set(pids)])
        out[role_id] = {
            "role_id": role_id,
            "profiles_assessed": len(pids),
            "raw_claims": n_raw,
            "evidence_validated": sum(len(by_person.get(p, [])) for p in pids),
            "passed_all_gates": sum(
                1 for p in pids if gate_out.get(p, {}).get("tier") not in (None, "EXCLUDED")
            ),
            "delivered": len(delivery[role_id]),
            "exclusions": [{"reason": k, "count": v} for k, v in
                           sorted(reasons.items(), key=lambda kv: -kv[1])],
            "client_side_sidebar": sorted(set(client_side)),
        }
    save("poolmap", out)
    for role_id, m in out.items():
        log("poolmap " + role_id + ": assessed=" + str(m["profiles_assessed"])
            + " gates_passed=" + str(m["passed_all_gates"])
            + " delivered=" + str(m["delivered"]))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

STAGES = {
    "harvest_r1": stage_harvest_r1,
    "harvest_r2": stage_harvest_r2,
    "extract": stage_extract,
    "validate": stage_validate,
    "gate": stage_gate,
    "deepen_r1": stage_deepen_r1,
    "adversarial": stage_adversarial,
    "contact": stage_contact,
    "movability": stage_movability,
    "messages": stage_messages,
    "linkcheck": stage_linkcheck,
    "poolmap": stage_poolmap,
}

ORDER = list(STAGES.keys())


def main() -> int:
    ap = argparse.ArgumentParser(description="Gaia sourcing pipeline")
    ap.add_argument("--stage", default="all", help="stage name, comma list, or 'all'")
    ap.add_argument("--force", action="store_true", help="re-run even if cached")
    ap.add_argument("--from-stage", default=None, help="run this stage and everything after")
    args = ap.parse_args()

    if args.from_stage:
        if args.from_stage not in ORDER:
            raise SystemExit("Unknown stage: " + args.from_stage)
        names = ORDER[ORDER.index(args.from_stage):]
    elif args.stage == "all":
        names = ORDER
    else:
        names = [s.strip() for s in args.stage.split(",") if s.strip()]

    # Pick the provider plan before any stage runs. Without this the module
    # default applies, which routes extraction to free-tier Gemini at ~6.5s of
    # enforced spacing per call -- correct when the Anthropic balance is zero,
    # and roughly twenty times slower than necessary when it is not.
    plan = autoselect_plan(verbose=True)
    log("provider plan: " + plan)

    t0 = time.time()
    for name in names:
        fn = STAGES.get(name)
        if fn is None:
            raise SystemExit("Unknown stage: " + name)
        log("")
        log("=== " + name + " ===")
        fn(force=args.force)
    log("")
    log("done in " + format(time.time() - t0, ".1f") + "s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
