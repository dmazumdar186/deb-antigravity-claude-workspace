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
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from .core.cache import fetch_rendered
from .core.config import CONFIG, PKG_ROOT
from .core.providers import (
    CostCeilingExceeded,
    autoselect_plan,
    set_plan,
    spend_eur,
)
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
from .sources import acp, company_bios, oral_hearing_web, technical_evidence

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
            except CostCeilingExceeded:
                # The one failure that must NOT be contained. Degrading by one
                # item is right for a bad document; for a budget breach it
                # would spend the rest of the stage one contained failure at a
                # time, which is the opposite of what a ceiling is for.
                for pending in futures:
                    pending.cancel()
                raise
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


# ---------------------------------------------------------------------------
# One run at a time
# ---------------------------------------------------------------------------


def _lock_path() -> Path:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    return RUN_DIR / ".run.lock"


def acquire_run_lock(force: bool = False) -> Optional[Path]:
    """Refuse to start while another run of this campaign is live.

    Two overlapping runs do not merely race on a file -- the older process is
    running OLDER CODE, because Python read its modules at import time. On
    2026-08-19 a background extract started before a fix to the chartership
    gate, finished after it, and wrote its own gate.json over the corrected
    one. The pipeline reported a smaller shortlist with no error anywhere, and
    the candidate that the fix had just recovered silently vanished again.
    That is the same shape as the stale-pool bug this project already fixed
    once: a cheap stage downstream of a changing one, quietly out of date.
    """
    lock = _lock_path()
    if lock.exists() and not force:
        try:
            held = lock.read_text(encoding="utf-8").strip()
        except Exception:
            held = "unknown"
        raise SystemExit(
            "Another run of campaign '" + CONFIG.campaign_id + "' holds the "
            "lock (" + held + ").\n"
            "Two runs overlapping is not a race on a file: the older process "
            "is running older code\nand will overwrite this one's stage "
            "output with results computed from it.\n"
            "Wait for it to finish, or pass --force-lock if you are certain "
            "it is dead."
        )
    lock.write_text(
        "pid=" + str(os.getpid()) + " started=" + time.strftime("%Y-%m-%d %H:%M:%S"),
        encoding="utf-8",
    )
    return lock


def release_run_lock(lock: Optional[Path]) -> None:
    if lock is None:
        return
    try:
        lock.unlink()
    except FileNotFoundError:
        pass  # already gone; nothing to release and nothing to warn about


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
# Stage 1c -- Role 2 breadth: oral-hearing evidence on scheme and authority sites
# ---------------------------------------------------------------------------


def stage_harvest_r2_web(force: bool = False) -> None:
    """Briefs of evidence published outside An Coimisiun Pleanala.

    acp.py gives DEPTH on cases we already know about; this gives BREADTH.
    Major Irish schemes run their own public consent sites and publish the
    whole oral-hearing bundle -- n6galwaycityringroad.ie, ringaskiddyrrc.ie,
    sligococo.ie's N4 hearing pages, corkcity.ie, kildarecoco.ie's M7 pages.

    This matters because roughly half the witness statements on the older ACP
    cases are image-only scans with no text layer, so ACP alone cannot fill
    Role 2. The scheme sites host the same documents, often as born-digital
    PDFs.
    """
    if done("harvest_r2_web") and not force:
        log("harvest_r2_web: cached, skipping")
        return
    log("harvest_r2_web: discovering oral-hearing evidence across scheme sites")

    try:
        found = oral_hearing_web.harvest()
    except Exception as exc:
        log("  discovery FAILED: " + repr(exc)[:140])
        found = []

    records: list[dict] = []
    docs: list[RawDocument] = []
    for wdoc, rdoc in found:
        docs.append(rdoc)
        records.append(
            {
                "case_no": "web",
                "url": wdoc.url,
                "doc_id": rdoc.doc_id,
                "person_hint": wdoc.person_hint,
                "party": None,
                "chars": len(rdoc.content_text),
            }
        )
        log("  " + str(wdoc.person_hint) + " <- " + wdoc.url[:78])

    save_docs(docs)
    save("harvest_r2_web", records)
    log("harvest_r2_web: " + str(len(records)) + " documents")


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
    if done("harvest_r2_web"):
        seen_urls = {r["url"] for r in r2}
        r2 = r2 + [r for r in load("harvest_r2_web") if r["url"] not in seen_urls]
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

    # Exact-match dedup above is not enough. The model frequently quotes the
    # SAME sentence at two different lengths -- "Eddie has over 25 years of
    # experience in structural and civil engineering in Ireland" and "Eddie
    # has over 25 years of experience in structural and civil engineering in
    # Ireland on private and public developments" -- and the shorter span is
    # wholly contained in the longer one. Two bullets, one fact.
    #
    # It reads as padding on the card, and it is worse than cosmetic: the
    # primary-signal count decides A/B/C, so one piece of evidence quoted at
    # two lengths could promote someone to Tier A on its own. That is the same
    # failure the exact-match dedup was added for, one step less obvious.
    #
    # The longest quote wins, because it is the one carrying the most context
    # for a reader who clicks through to check it.
    by_key: dict[tuple, list] = {}
    for c in deduped:
        by_key.setdefault((c.subject_person_id, c.dimension), []).append(c)
    nested: set[str] = set()
    for group in by_key.values():
        ordered = sorted(group, key=lambda c: -len(_norm_quote(c.evidence_quote)))
        kept_quotes: list[str] = []
        for c in ordered:
            q = _norm_quote(c.evidence_quote)
            if any(q in longer for longer in kept_quotes):
                nested.add(c.claim_id)
            else:
                kept_quotes.append(q)
    if nested:
        deduped = [c for c in deduped if c.claim_id not in nested]
        log("  collapsed " + str(len(nested)) + " claims whose quote was "
            "contained in a longer quote of the same fact")

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
    sources: dict[str, str] = {}
    for pid, rec in data["persons"].items():
        rec = dict(rec)
        roles[pid] = rec.pop("role_id")
        sources[pid] = rec.pop("source", "")
        persons[pid] = Person(**rec)
    by_person: dict[str, list[ValidatedClaim]] = {}
    for c in vd["claims"]:
        vc = ValidatedClaim(**c)
        by_person.setdefault(vc.subject_person_id, []).append(vc)

    # Whose word counts for "employer" depends on where the person came from.
    #
    # An oral-hearing document is named for the PARTY that submitted it
    # ("No.02 - TII - Witness Statement of Aidan Foley"), but the witness is
    # usually that party's consultant, not its employee -- Susie Coyle's
    # statement opens "I am an Associate Director in Jacobs" while sitting
    # under a TII filename. There, the witness's own words must win, or half
    # the transport pool gets filed as client-side and dropped for being the
    # wrong kind of right person.
    #
    # A staff directory is the opposite case: the page belongs to the firm, so
    # the firm IS the employer, and a stray sentence like "based in the Dublin
    # office" must never overwrite it. Applying the oral-hearing rule here
    # replaced "Barrett Mahony Consulting Engineers" with "Dublin office" on a
    # delivered card.
    for pid, person in persons.items():
        if sources.get(pid) == "company_directory" and person.current_employer:
            continue
        stated = [
            c for c in by_person.get(pid, [])
            if c.dimension == "employer" and c.confidence == "direct"
        ]
        # EVERY employer claim is tried, not just the first. The first is
        # often the one that names a city or a past employer ("Currently
        # leader of the Arup maritime engineering team in Dublin"), and
        # stopping there fell back to the unvalidated model hint -- which is
        # how "Dublin" reached the employer field on a delivered pool map.
        resolved = None
        for claim in stated:
            resolved = _employer_from_claim(claim.assertion)
            if resolved:
                break
        # The fallback is the model's freeform hint from L5. It is a guess
        # with no evidence contract behind it, so it goes through the same
        # rejection rules as a parsed claim rather than straight onto a card.
        # Unfiltered, it supplied "Environment", "Tunnels and Underground
        # Infrastructure" and "Dublin" as employers.
        person.current_employer = (
            resolved
            or _clean_employer_name(person.current_employer or "")
            or None
        )

    return persons, by_person, roles


# "Susie Coyle is an Associate Director at Jacobs." -> "Jacobs"
# The leading .* is greedy on purpose, so the LAST preposition wins.
# "Senior Associate Director of Highways in Jacobs" must yield "Jacobs", not
# "Highways in Jacobs" -- with a lazy prefix the engine takes the first "of"
# and the character class happily swallows the rest of the sentence.
# Parentheses are part of the character class because Irish firms are
# routinely written with their initialism attached -- "Archaeological
# Management Solutions (AMS)", "Transport Infrastructure Ireland (TII)".
# Without them the capture stopped dead at the bracket and the whole claim
# yielded nothing.
_EMPLOYER_TAIL_RE = re.compile(
    r"^.*\b(?:at|with|for|in|of)\s+([A-Z][\w'’&.\-() ]{2,60}?)\s*\.?$"
)

# Captures that are a place or an org-chart position rather than an employer.
# "...is based in the Dublin office" yields "Dublin office", which then
# OVERWRITES a perfectly good employer taken from the staff directory --
# Rouslan Taskov's card read "Dublin office" instead of "Barrett Mahony
# Consulting Engineers" until this guard existed.
_NOT_AN_EMPLOYER_RE = re.compile(
    r"\b(office|team|division|department|group|practice|branch|region|"
    r"sector|unit|project|scheme|programme|role|position|capacity)\b",
    re.I,
)

# An employer named by an explicit employment verb. This is the STRONGEST cue
# and it is tried FIRST, because the "last preposition wins" rule below is
# right only for the shape it was written for.
#
# "Employed by Jacobs as Senior Associate Director of Environment" ends in a
# DIVISION, not an employer, and the last preposition yields "Environment".
# Four of the eighteen Role 2 candidates carried a division or a city in the
# employer field on the delivered pool map for exactly this reason: "Dublin"
# (from "leader of the Arup maritime engineering team in Dublin"), "Land &
# Property Services", "Tunnels and Underground Infrastructure", "MetroLink".
# The employer is what follows the employment verb, and it STOPS at the
# clause that starts describing the job.
# The verb is case-folded with a scoped group; the capture is NOT, because a
# capitalised word is what marks an organisation. A blanket re.I here would
# case-fold [A-Z] too and "employed by the same team as" would capture "the
# same team as". Claims routinely open the sentence -- "Employed by Jacobs
# as ..." -- so a lowercase-only literal matches almost none of them.
_EMPLOYED_BY_RE = re.compile(
    r"\b(?i:employed\s+(?:by|at|with)|works?\s+for|working\s+(?:for|at)|"
    r"joined|is\s+with|am\s+with)\s+"
    r"([A-Z][\w'’&.\-]*(?:\s+[A-Z(][\w'’&.\-)]*){0,5})"
)

# "Employed as TII's Project Director for MetroLink" -- the possessive names
# the employer and the tail names the scheme, so the last preposition picks
# the scheme. A scheme is not an employer.
_EMPLOYER_POSSESSIVE_RE = re.compile(
    r"\b([A-Z][\w&.\-]*(?:\s+[A-Z][\w&.\-]*){0,4})['’]s\s+[A-Za-z]"
)

# Where an employer name ends and the job description begins.
_CLAUSE_BREAK_RE = re.compile(
    r"\s+(?:as|in|on|since|and|where|which|to|for|from|responsible)\b", re.I
)

# A possessive division tail: "Jacobs' Transport Planning team" is Jacobs.
_POSSESSIVE_DIVISION_RE = re.compile(
    r"^(.*?)['’]s?\s+(?:[\w&.\-]+\s+){0,3}"
    r"(?:team|division|department|group|practice|unit|office|branch|business)$",
    re.I,
)

# A capture that is only a place. "Dublin" is where someone works, not who
# they work for, and it overwrote a real employer on a delivered card.
_PLACE_ONLY = {
    "dublin", "cork", "limerick", "galway", "waterford", "sligo", "athlone",
    "kilkenny", "ennis", "tralee", "wexford", "drogheda", "dundalk", "belfast",
    "london", "ireland", "the netherlands", "netherlands", "uk",
    "united kingdom", "northern ireland", "republic of ireland", "europe",
}

# Several places joined by "and" is still just places. "Ireland and the
# Netherlands" -- from "worked on projects around the coast of Ireland and the
# Netherlands" -- reached a delivered card as an employer.
_PLACE_CONJUNCTION_RE = re.compile(r"\s+(?:and|&|/|,)\s+")


def _clean_employer_name(name: str) -> Optional[str]:
    """Reduce a captured span to an employer, or reject it."""
    name = name.strip().strip(" .,;:")
    # "Jacobs' Transport Planning team" -> "Jacobs"
    m = _POSSESSIVE_DIVISION_RE.match(name)
    if m and m.group(1).strip():
        name = m.group(1).strip()
    name = name.strip().strip(" .,;:'’")
    if len(name) < 3 or len(name.split()) > 6:
        return None
    low = name.lower()
    if low in _PLACE_ONLY:
        return None
    parts = [p.strip() for p in _PLACE_CONJUNCTION_RE.split(low) if p.strip()]
    if len(parts) > 1 and all(p in _PLACE_ONLY for p in parts):
        return None
    if _NOT_AN_EMPLOYER_RE.search(name):
        return None
    return name


def _employer_from_claim(assertion: str) -> Optional[str]:
    """Read the employer out of an evidenced employer claim.

    Tried in descending order of how strongly the phrasing commits to an
    employer, because the weakest cue -- a trailing preposition -- is also
    the one most often pointing at a division, a scheme or a city.
    """
    text = assertion.strip()

    for pattern in (_EMPLOYED_BY_RE, _EMPLOYER_POSSESSIVE_RE):
        m = pattern.search(text)
        if not m:
            continue
        span = _CLAUSE_BREAK_RE.split(m.group(1))[0]
        cleaned = _clean_employer_name(span)
        if cleaned:
            return cleaned

    # Weakest cue, kept for "Senior Associate Director of Highways in Jacobs",
    # where the employer genuinely is last.
    m = _EMPLOYER_TAIL_RE.search(text)
    if m:
        return _clean_employer_name(m.group(1))
    return None


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
    # Write the corrected identity back to extract.json. _persons_and_claims
    # derives employer/title from the person's own evidenced words, and the
    # gates and contact lookup both use that corrected value -- but the
    # renderer reads extract.json directly, so without this write-back the
    # dossier printed a blank employer for every oral-hearing candidate while
    # the pipeline behind it knew perfectly well who they worked for.
    data = load("extract")
    for pid, person in persons.items():
        rec = data["persons"].get(pid)
        if rec is None:
            continue
        for field in ("current_title", "current_employer", "location"):
            value = getattr(person, field, None)
            if value:
                rec[field] = value
    save("extract", data)

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
        # Candidates that failed exactly ONE hard gate. When a role comes up
        # short, "we found nobody" is much less useful to the client than
        # "we found these four, and here is the single thing each was missing"
        # -- that is a list they can act on, by widening the brief or by
        # asking us to verify the one open point.
        near_misses: list[str] = []
        for pid in pids:
            g = gate_out.get(pid)
            if g is None or g["tier"] != "EXCLUDED" or g["client_side"]:
                continue
            failed = [gr for gr in g["gates"] if not gr["passed"]]
            if len(failed) != 1:
                continue
            person = persons[pid]
            near_misses.append(
                person.full_name
                + (" -- " + person.current_employer if person.current_employer else "")
                + " -- missing only: " + failed[0]["gate_id"]
            )

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
            "near_misses": sorted(near_misses),
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
    "harvest_r2_web": stage_harvest_r2_web,
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
    ap.add_argument(
        "--force-lock", action="store_true",
        help="start even if another run holds the lock (only if it is dead)",
    )
    ap.add_argument(
        "--plan", default=None,
        help="force a provider plan (free/hybrid/openrouter/anthropic/budget) "
             "instead of auto-selecting by what the credentials can pay for",
    )
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
    if args.plan:
        set_plan(args.plan)
        plan = args.plan
        log("provider plan: " + plan + " (forced)")
    else:
        plan = autoselect_plan(verbose=True)
    log("provider plan: " + plan)

    t0 = time.time()
    lock = acquire_run_lock(force=args.force_lock)
    try:
        for name in names:
            fn = STAGES.get(name)
            if fn is None:
                raise SystemExit("Unknown stage: " + name)
            log("")
            log("=== " + name + " ===")
            fn(force=args.force)
    finally:
        release_run_lock(lock)
    log("")
    log("done in " + format(time.time() - t0, ".1f") + "s")
    # The operator reads this number, so it is in EUR per ~/.claude/rules/
    # currency-eur.md. It was previously computed per call and discarded.
    log("LLM spend this run: EUR " + format(spend_eur(), ".2f")
        + " of a EUR " + format(CONFIG.max_cost_eur, ".2f") + " ceiling")
    return 0


if __name__ == "__main__":
    sys.exit(main())
