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
  poolmap      the honest denominator, per role                     (free)
  scorecard    eval/scorecard.py's six ship numbers                 (free)
  render       L13 dossier.html + candidates.csv + pool maps        (free)
  console      L14 operator console (deliverables/<c>/console/)     (free)
  sync_crm     push the delivered shortlist to Recruit CRM           (paid,
               dry-run/audit-only by default -- see --live-crm and
               --allow-stale)

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
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from .core import alerts
from .core.cache import fetch_rendered
from .core.config import CONFIG, PKG_ROOT, WORKSPACE_ROOT, secret
from .core.providers import (
    CostCeilingExceeded,
    autoselect_plan,
    cumulative_spend_eur,
    set_plan,
    spend_eur,
)
from .core.contracts import (
    CandidateCard,
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
from .eval import scorecard as eval_scorecard
from .eval.labels import build_worksheet_row, cohen_kappa, load_labels
from .integrations.recruit_crm import RecruitCRMClient, sync_delivery
from .layers import adversarial, contact, gates, linkcheck, messages, movability, optout
from .layers.extract import extract_directory, extract_from_document
from .layers.icp_check import icp_check_from_gate_json
from .layers.replies import classify_reply
from .layers.validator import validate_all
from .render import render as render_module
from .render.console import render_console
from .roles import ROLE1, ROLE2, ROLES, is_client_side
from .sources import (
    acp,
    company_bios,
    linkedin_lookup,
    oral_hearing_web,
    technical_evidence,
)

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
        except Exception as exc:
            print("[load_docs] skipping malformed line in " + str(DOCS)
                  + ": " + repr(exc)[:160])
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

    # Per-role one-liner naming the two client-feedback gates specifically
    # (seniority_ceiling / located_ie), so a re-run on a call shows the effect
    # of --max-grade/--counties etc. without reading gate.json by hand.
    per_role: dict[str, dict[str, int]] = {}
    for rec in out.values():
        bucket = per_role.setdefault(
            rec["role_id"], {"passed": 0, "seniority_ceiling": 0, "located_ie": 0}
        )
        if rec["tier"] != "EXCLUDED":
            bucket["passed"] += 1
        for g in rec["gates"]:
            if not g["passed"] and g["gate_id"] in ("seniority_ceiling", "located_ie"):
                bucket[g["gate_id"]] += 1
    for role_id, bucket in per_role.items():
        log("  " + role_id + ": " + str(bucket["passed"]) + " passed / "
            + str(bucket["seniority_ceiling"]) + " excluded by seniority_ceiling / "
            + str(bucket["located_ie"]) + " by located_ie")


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
    """The candidates that actually ship, post-adversarial, best tier first.

    Also computes, logs, and returns `out["overflow"][role_id]` -- the
    qualifying person_ids CUT by the target_count truncation. Before this,
    a role that qualified 14 people against a target_count of 10 silently
    dropped 4 with no record anywhere of who they were or that they existed
    -- indistinguishable, from delivery.json alone, from a role that only
    ever qualified 10.
    """
    gate_out = load("gate")
    adv = load("adversarial") if done("adversarial") else {}
    persons, by_person, _ = _persons_and_claims()
    order = {"A": 0, "B": 1, "C": 2}
    out: dict[str, list[str]] = {}
    overflow: dict[str, list[str]] = {}
    for role_id, spec in ((ROLE1.role_id, ROLE1), (ROLE2.role_id, ROLE2)):
        rows = []
        for pid, g in gate_out.items():
            if g["role_id"] != role_id or g["tier"] == "EXCLUDED" or g["client_side"]:
                continue
            t = _final_tier(pid, gate_out, adv)
            if t == "EXCLUDED":
                continue
            # pid is the final key on purpose. Without it two candidates tied
            # on (tier, n_claims) are ordered by whatever the upstream
            # iteration happened to produce, and the renderer -- which walked
            # a different structure -- resolved the same tie the other way.
            # The delivered dossier shipped two people the contact stage had
            # never enriched, so their cards carried no email, no LinkedIn and
            # no way to reach them at all, while two candidates that HAD been
            # enriched were dropped. Nothing errored; the two lists simply
            # disagreed.
            rows.append((order.get(t, 3), -g["n_claims"], pid))
        rows.sort()
        ranked = [pid for _, _, pid in rows]
        out[role_id] = ranked[: spec.target_count]
        cut = ranked[spec.target_count:]
        overflow[role_id] = cut
        if cut:
            log("delivery: " + role_id + " qualified " + str(len(ranked))
                + " but target_count is " + str(spec.target_count) + " -- "
                + str(len(cut)) + " cut: " + ", ".join(cut))
    out["overflow"] = overflow
    return out


def stage_contact(force: bool = False) -> None:
    if done("contact") and not force:
        log("contact: cached, skipping")
        return
    persons, by_person, _ = _persons_and_claims()
    corpus = load_docs()
    delivery = _delivery_set()
    targets = delivery[ROLE1.role_id] + delivery[ROLE2.role_id]
    log("contact: enriching " + str(len(targets)) + " candidates via Prospeo")

    out: dict[str, dict] = {}
    for pid in targets:
        # RADAR_CONTRACTS.md section E "Stale evidence": evidence_age_days is
        # computed from this person's employer-dimension source documents.
        # The claims carry only source_doc_id, so the actual RawDocument
        # metadata is loaded from the cached doc store the same way
        # stage_validate/stage_linkcheck do -- claims never carry the full
        # document themselves.
        employer_doc_ids = {
            c.source_doc_id for c in by_person.get(pid, []) if c.dimension == "employer"
        }
        employer_docs = [corpus[d] for d in employer_doc_ids if d in corpus]
        try:
            rec = contact.enrich(persons[pid], employer_docs=employer_docs)
        except Exception as exc:
            log("  " + pid + " enrich FAILED: " + repr(exc)[:120])
            continue
        rec_d = rec.model_dump()
        # Prospeo returns a profile URL for some people and not others. For the
        # ones it misses the card fell back to handing the reader a LinkedIn
        # SEARCH, which is honest but is not a contact route -- and the
        # profiles turn out to be findable in one query. Resolved here rather
        # than at render time so the URL is checked by L12 like any other link.
        if not rec_d.get("linkedin_url"):
            found = linkedin_lookup.resolve(
                persons[pid].full_name, persons[pid].current_employer
            )
            if found:
                rec_d["linkedin_url"] = found
                log("    resolved LinkedIn: " + found)
        out[pid] = rec_d
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
    contacts_raw = load("contact") if done("contact") else {}
    out: dict[str, dict] = {}
    lock = threading.Lock()

    def one(pid: str) -> None:
        spec = ROLES[roles[pid]]
        contact_record: Optional[ContactRecord] = None
        contact_raw = contacts_raw.get(pid)
        if contact_raw:
            try:
                contact_record = ContactRecord(**contact_raw)
            except Exception as exc:
                log("  " + pid + " could not parse cached contact record for "
                    "opt-out check: " + repr(exc)[:120])
        optout_hit = optout.is_opted_out(person=persons[pid], contact=contact_record,
                                          person_id=pid)
        if optout_hit is not None:
            log("  " + pid + " draft_blocked_optout")
            return
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
# Stage 11 -- Recruit CRM sync (client promise 2026-09-10: "sourced candidates
# land in the CRM so consultants and Maddie take over"). Runs LAST in STAGES
# -- after console -- so a CRM sync always reflects whatever the render/
# console stages just produced for this run, per the actual STAGES dict
# ordering below (this comment previously said "Stage 8", duplicating
# scorecard's own "Stage 8" label and disagreeing with the real order).
# ---------------------------------------------------------------------------

# Set from --live-crm / --allow-stale in main() before the stage loop runs.
# Module globals rather than stage_sync_crm(force, live, allow_stale)
# parameters because every stage in STAGES is called uniformly as
# fn(force=args.force) by the loop in main().
_LIVE_CRM = False
_ALLOW_STALE = False


def _build_delivered_cards() -> tuple[
    list[CandidateCard], dict[str, ContactRecord], dict[str, MovabilitySignal]
]:
    """Assemble CandidateCard/ContactRecord/MovabilitySignal for everyone in
    the delivered set, from the same stage files the renderer reads.

    render.py builds its rows straight from raw dicts; this goes through the
    pydantic contracts instead, because integrations.recruit_crm's public API
    is typed against them (CandidateCard, ContactRecord, MovabilitySignal) --
    a deliberate boundary so a malformed stage file fails loudly here rather
    than reaching a live CRM write.
    """
    persons, by_person, roles = _persons_and_claims()
    gate_out = load("gate")
    adv = load("adversarial") if done("adversarial") else {}
    contacts_raw = load("contact") if done("contact") else {}
    movs_raw = load("movability") if done("movability") else {}
    delivery = load("delivery") if done("poolmap") else _delivery_set()

    cards: list[CandidateCard] = []
    contact_map: dict[str, ContactRecord] = {}
    mov_map: dict[str, MovabilitySignal] = {}

    for role_id in (ROLE1.role_id, ROLE2.role_id):
        for pid in delivery.get(role_id, []):
            person = persons.get(pid)
            g = gate_out.get(pid)
            if person is None or g is None:
                continue

            ev_raw = dict(adv.get(pid) or {})
            ev_raw.setdefault("gates", g["gates"])
            tier = ev_raw.get("tier") or g["tier"]
            if tier == "EXCLUDED":
                # Should not reach the delivered set at all (_delivery_set
                # already filters EXCLUDED), but CandidateCard's tier field
                # only accepts A/B/C -- refuse to fabricate a tier rather than
                # crash the whole sync over one bad record.
                log("  sync_crm: " + pid + " has tier EXCLUDED in a delivered "
                    "slot -- skipped")
                continue
            ev_raw["person_id"] = pid
            ev_raw["role_id"] = role_id
            ev_raw["tier"] = tier
            evaluation = Evaluation(**ev_raw)

            contact_raw = dict(contacts_raw.get(pid) or {})
            contact_raw["person_id"] = pid
            contact_record = ContactRecord(**contact_raw)

            mov_raw = dict(movs_raw.get(pid) or {})
            mov_raw["person_id"] = pid
            mov_signal = MovabilitySignal(**mov_raw)

            card = CandidateCard(
                person_id=pid,
                full_name=person.full_name,
                current_title=person.current_title or "not stated",
                current_employer=person.current_employer or "not stated",
                location=person.location or "not stated",
                role_id=role_id,
                tier=tier,
                claims=by_person.get(pid, []),
                evaluation=evaluation,
                contact=contact_record,
                movability=mov_signal,
                outreach=None,
            )
            cards.append(card)
            contact_map[pid] = contact_record
            mov_map[pid] = mov_signal

    return cards, contact_map, mov_map


def stage_sync_crm(force: bool = False) -> None:
    """Push the delivered shortlist to Recruit CRM.

    Dry-run (audit-only) unless `--live-crm` was passed to main(). Must never
    run ahead of `contact`: without it there is no email/LinkedIn to dedupe
    on, and RecruitCRMClient.upsert_candidate refuses a live write with
    neither -- but that refusal is per-candidate (NoDedupeKey, contained by
    sync_delivery), so gate the whole stage here instead of discovering it
    one contained failure at a time.
    """
    if not done("contact"):
        log("sync_crm: skipped -- the 'contact' stage has not run yet "
            "(nothing to dedupe candidates on)")
        return
    if done("sync_crm") and not force:
        log("sync_crm: cached, skipping")
        return

    if not CONFIG.recruit_crm_job_ids:
        log("sync_crm: CONFIG.recruit_crm_job_ids is empty -- "
            "attach_to_job will be skipped for every candidate this run")

    cards, contact_map, mov_map = _build_delivered_cards()
    log("sync_crm: syncing " + str(len(cards)) + " delivered candidates "
        + ("[LIVE]" if _LIVE_CRM else "[DRY RUN -- audited only, nothing sent]"))

    client = RecruitCRMClient(live=_LIVE_CRM)
    report = sync_delivery(
        cards, contact_map, mov_map, client, CONFIG.recruit_crm_job_ids,
        allow_stale=_ALLOW_STALE,
    )

    save("sync_crm", {
        "live": _LIVE_CRM,
        "allow_stale": _ALLOW_STALE,
        "created": report.created,
        "updated": report.updated,
        "would_create": report.would_create,
        "would_update": report.would_update,
        "skipped": report.skipped,
        "errors": report.errors,
        "lines": report.lines,
    })
    log("sync_crm: created=" + str(report.created) + " updated=" + str(report.updated)
        + " would_create=" + str(report.would_create)
        + " would_update=" + str(report.would_update)
        + " skipped=" + str(report.skipped) + " errors=" + str(report.errors))
    for line in report.lines:
        log("  " + line)


# ---------------------------------------------------------------------------
# Operator-console health snapshot (RADAR_CONTRACTS.md section G / this
# package's HANDOFF.md 2026-09-10). Written at the end of stage_poolmap
# rather than as its own registered stage: it is cheap, pure, and derived
# entirely from state stage_poolmap already has in hand (the doc store) or
# can check in a line (which secrets are configured) -- a whole extra STAGES
# entry (and the cache-skip bookkeeping that comes with one) would be
# ceremony for something this small.
# ---------------------------------------------------------------------------


def stage_health() -> None:
    """Write run/<campaign_id>/health.json -- console.py's health banner and
    its integrations-configured note read this shape (adapted minimally to
    match: see render/console.py's `_health_banner` docstring).
    """
    corpus = load_docs()
    fetched_dates = [d.fetched_at for d in corpus.values() if getattr(d, "fetched_at", None)]
    newest = max(fetched_dates) if fetched_dates else None
    stale_days = (date.today() - newest).days if newest else None

    health = {
        "campaign_id": CONFIG.campaign_id,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pool_last_refreshed": newest.isoformat() if newest else None,
        "stale_days": stale_days,
        "integrations": {
            "recruit_crm": (
                "configured" if secret("RECRUIT_CRM_API_KEY", required=False) else "missing"
            ),
            "alert_webhook": (
                "configured" if secret(CONFIG.alert_webhook_env, required=False) else "missing"
            ),
            "modal_radar": (
                "configured" if secret("MODAL_RADAR_URL", required=False) else "missing"
            ),
        },
    }
    save("health", health)
    log("health: pool last refreshed " + (health["pool_last_refreshed"] or "never")
        + (" (" + str(stale_days) + "d ago)" if stale_days is not None else ""))


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
    # The delivered shortlist, written down rather than recomputed.
    #
    # Every stage downstream of the gates derived this list for itself, and the
    # renderer's copy applied a slightly different filter and resolved ties
    # differently. The result was a dossier containing two people the contact
    # stage had never seen -- cards with no email, no LinkedIn and no route --
    # while two enriched candidates were silently dropped. One list, saved
    # once, read by everyone.
    save("delivery", delivery)

    save("poolmap", out)
    for role_id, m in out.items():
        log("poolmap " + role_id + ": assessed=" + str(m["profiles_assessed"])
            + " gates_passed=" + str(m["passed_all_gates"])
            + " delivered=" + str(m["delivered"]))

    # Delivery composition guard. The per-candidate gates decide who passes;
    # this is the last look at what actually shipped, on the exact fields the
    # client reads off the card -- title and location -- independent of
    # whatever evidence got a candidate through the gate. It exists because
    # the 2026-08-20 delivered CSV had every single Role 1 row titled Director
    # or Associate Director, and nothing before render time said so out loud.
    contacts = load("contact") if done("contact") else {}
    for role_id, spec in ((ROLE1.role_id, ROLE1), (ROLE2.role_id, ROLE2)):
        cards = [
            {
                "full_name": persons[pid].full_name,
                "current_title": persons[pid].current_title,
                "location": persons[pid].location,
                "email_status": contacts.get(pid, {}).get("email_status"),
            }
            for pid in delivery.get(role_id, [])
        ]
        violations = gates.composition_violations(cards, spec)
        if violations:
            log("  *** DELIVERY COMPOSITION VIOLATIONS for " + role_id
                + " (" + str(len(violations)) + " of " + str(len(cards)) + " delivered) ***")
            for v in violations:
                log("    - " + v)

    stage_health()


# ---------------------------------------------------------------------------
# Stage 8 -- eval/scorecard.py's six numbers (RADAR_CONTRACTS.md section F)
# ---------------------------------------------------------------------------


def stage_scorecard(force: bool = False) -> None:
    """Compute and save the ship scorecard for this run.

    Depends on `poolmap` (for delivery.json / poolmap.json) and `validate`/
    `gate`/`extract` (already required by poolmap itself), so it is
    registered directly after `poolmap` in STAGES. Never fabricates the two
    label-derived precision numbers: with no `eval/labels.jsonl` yet they
    print "n/a (no labels)" via eval.scorecard.render_table, not a false
    100%.
    """
    if not done("poolmap"):
        log("scorecard: skipped -- the 'poolmap' stage has not run yet")
        return
    if done("scorecard") and not force:
        log("scorecard: cached, skipping")
        return

    sc = eval_scorecard.compute_scorecard(RUN_DIR)
    save("scorecard", sc)
    for line in eval_scorecard.render_table(sc):
        log(line)


# ---------------------------------------------------------------------------
# Stage 10 -- L14 operator console (render/console.py). Always re-rendered:
# it is a cheap, pure read of whatever stage JSON already exists under
# RUN_DIR, so there is nothing to "cache" against -- unlike the paid/slow
# stages above, staleness here is a correctness bug, not a cost saving.
# ---------------------------------------------------------------------------


def stage_console(force: bool = False) -> None:
    out_dir = WORKSPACE_ROOT / "deliverables" / CONFIG.campaign_id / "console"
    render_console(CONFIG.campaign_id, out_dir, run_dir=RUN_DIR)
    log("console: rendered -> " + str(out_dir))


# ---------------------------------------------------------------------------
# Stage 9 -- L13 the client-facing renderer (render/render.py): dossier.html,
# candidates.csv, pool_map_role1.md/role2.md. Registered here, BEFORE
# console, so the console's own links to those artifacts point at files that
# already exist by the time it renders; same "always re-rendered, nothing to
# cache" rationale as stage_console -- it is a pure read of RUN_DIR's already
# -computed stage JSON.
# ---------------------------------------------------------------------------

# Set from --allow-placeholder-notice in main() before the stage loop runs.
# Module global for the same reason as _LIVE_CRM/_ALLOW_STALE above: every
# stage in STAGES is called uniformly as fn(force=args.force).
_ALLOW_PLACEHOLDER_NOTICE = False


def stage_render(force: bool = False) -> None:
    """render.render.build() raises SystemExit if the Art. 14 privacy
    notice URL is not live and --allow-placeholder-notice was not passed --
    a deliberate hard stop (every outreach draft cites that URL), not
    something this stage should swallow into a silent skip.
    """
    render_module.build(allow_placeholder_notice=_ALLOW_PLACEHOLDER_NOTICE)
    log("render: rendered -> " + str(render_module.OUT_DIR))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# --coverage-test -- RADAR_CONTRACTS.md section A. Licensed source providers
# (pdl/crustdata/apollo) are owned by a separate build from the rest of
# run.py and are imported ONLY inside run_coverage_test, never at module
# level -- a missing or broken licensed-provider module must never break any
# other run.py flag (--stage, --classify-reply, brief overrides, ...).
# ---------------------------------------------------------------------------

_NICHE_TERMS: dict[str, list[str]] = {
    "structural": ["structural engineer", "structural design", "structural"],
    "transport": ["transport engineer", "transportation planning", "highways", "transport"],
}

# ROI counties for a coverage-test location filter. Not exhaustive (roles.py
# has no single master list to reuse -- Role 2's brief scopes to ["Cork"]
# specifically) -- broad enough to exercise a provider's Ireland filter
# across the counties Role 1/Role 2 candidates have actually come from.
_IE_COUNTIES = [
    "Dublin", "Cork", "Galway", "Limerick", "Waterford", "Kildare",
    "Meath", "Wicklow", "Kilkenny", "Louth",
]

_LICENSED_PROVIDER_MODULES = {
    "pdl": "gtm_client_workflows.gaia_sourcing.sources.pdl",
    "crustdata": "gtm_client_workflows.gaia_sourcing.sources.crustdata",
    "apollo": "gtm_client_workflows.gaia_sourcing.sources.apollo",
    # Free, not licensed, but --coverage-test drives it the same way -- see
    # sources/serper_people.py.
    "serper_people": "gtm_client_workflows.gaia_sourcing.sources.serper_people",
}

# go/no-go threshold per RADAR_CONTRACTS.md section A: "40 matched with
# title+employer+dates per niche" out of a 50-record page.
_COVERAGE_GO_THRESHOLD = 40


def run_coverage_test(provider_name: str, niche: str) -> int:
    """`run.py --coverage-test <provider> --niche structural|transport`.

    Builds a SourceQuery ("chartered engineer" + niche terms, ROI counties),
    fetches ONE page (limit 50) from the named provider, and prints matched /
    with title / with employer / with dates / with city / cost, plus the
    go/no-go line. Fails loudly with the provider's own
    ProviderNotConfigured message (never a silent empty result) when its API
    key is absent -- see sources/licensed_common.py.
    """
    import importlib

    module_path = _LICENSED_PROVIDER_MODULES.get(provider_name)
    if module_path is None:
        log("--coverage-test: unknown provider " + repr(provider_name)
            + "; known: " + ", ".join(sorted(_LICENSED_PROVIDER_MODULES)))
        return 1
    try:
        importlib.import_module(module_path)  # self-registers into sources.registry
    except ImportError as exc:
        log("--coverage-test: could not import " + module_path + ": " + repr(exc)[:200])
        return 1

    from .core.contracts import SourceQuery
    from .sources.licensed_common import ProviderNotConfigured
    from .sources.registry import get_provider

    provider = get_provider(provider_name)
    terms = ["chartered engineer"] + _NICHE_TERMS.get(niche, [niche])
    query = SourceQuery(
        role_id="coverage_test", niche=niche, terms=terms,
        locations=list(_IE_COUNTIES), limit=50,
    )

    try:
        result = provider.fetch(query)
    except ProviderNotConfigured as exc:
        log("--coverage-test " + provider_name + ": " + str(exc))
        return 1

    if result.error:
        # A non-200 (e.g. an expired/unauthorized key) used to fall straight
        # through to "matched: 0" and print "NO-GO: 0/50" -- indistinguishable
        # from a query that genuinely matched nobody. Surfaced here instead,
        # with a non-zero exit so a CI/cron invocation of --coverage-test
        # actually fails on a broken credential rather than reporting a
        # misleading go/no-go verdict.
        log("--coverage-test " + provider_name + ": provider returned " + result.error)
        return 1

    records = result.provider_records
    matched = result.fetched
    with_title = sum(1 for r in records if r.current_title)
    with_employer = sum(1 for r in records if r.current_employer)
    with_dates = sum(1 for r in records if any(js.start or js.end for js in r.job_history))
    with_city = sum(1 for r in records if r.city)
    qualifying = sum(
        1 for r in records
        if r.current_title and r.current_employer
        and any(js.start or js.end for js in r.job_history)
    )

    log("coverage-test " + provider_name + " / niche=" + niche + ":")
    log("  matched:       " + str(matched))
    log("  with title:    " + str(with_title))
    log("  with employer: " + str(with_employer))
    log("  with dates:    " + str(with_dates))
    log("  with city:     " + str(with_city))
    # Every licensed provider's cost_eur rests on an UNVERIFIED placeholder
    # per-record/credit rate (see each module's docstring "UNVERIFIED"
    # section) -- labelled here so this number is never mistaken for a real
    # invoiced figure.
    log("  cost:          EUR " + format(result.cost_eur, ".4f")
        + " (estimated, placeholder rate)")
    verdict = "GO" if qualifying >= _COVERAGE_GO_THRESHOLD else "NO-GO"
    log("  " + verdict + ": " + str(qualifying) + "/50 with title+employer+dates "
        + "(threshold " + str(_COVERAGE_GO_THRESHOLD) + ")")
    return 0


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
    "scorecard": stage_scorecard,
    "render": stage_render,
    "console": stage_console,
    "sync_crm": stage_sync_crm,
}

ORDER = list(STAGES.keys())


def _apply_brief_overrides(args: argparse.Namespace) -> None:
    """Apply --max-grade/--max-years/--min-years/--counties/--*-location.

    Mutates ROLE1/ROLE2's HardGate.params in place -- the same objects
    stage_gate reads via ROLES -- so a client-call correction needs no code
    edit and no re-harvest: `--from-stage gate` re-derives tiers from the
    already-cached extract.json/validate.json, offline.
    """
    touched = any([
        args.max_grade, args.max_years is not None, args.min_years is not None,
        args.counties is not None, args.strict_location, args.lenient_location,
    ])
    if not touched:
        return
    counties = (
        [c.strip() for c in args.counties.split(",") if c.strip()]
        if args.counties is not None else None
    )
    for spec in (ROLE1, ROLE2):
        for gate in spec.hard_gates:
            if gate.check == "seniority_ceiling":
                if args.max_grade:
                    gate.params["max_grade"] = args.max_grade
                if args.max_years is not None:
                    gate.params["max_years"] = args.max_years
            elif gate.check == "seniority_years":
                if args.min_years is not None:
                    gate.params["min_years"] = args.min_years
            elif gate.check == "located_ie":
                if counties is not None:
                    gate.params["counties"] = counties
                if args.strict_location:
                    gate.params["require_direct_evidence"] = True
                    gate.params["treat_unknown_as"] = "fail"
                if args.lenient_location:
                    gate.params["require_direct_evidence"] = False

        # Keep spec.seniority_band / spec.location_rule in lockstep with the
        # hard_gates params just mutated above -- layers.gates.
        # composition_violations and eval/scorecard's post-hoc judge of the
        # delivered set read those two fields directly, not the gate params,
        # so leaving them on the old brief would judge the delivered set
        # against a brief the gates never actually enforced this run. Same
        # fix as layers/recut.py's `_apply_overrides` (RADAR_CONTRACTS.md).
        if spec.seniority_band is not None:
            band_updates: dict = {}
            if args.max_grade:
                band_updates["max_grade"] = args.max_grade
            if args.max_years is not None:
                band_updates["max_years"] = args.max_years
            if args.min_years is not None:
                band_updates["min_years"] = args.min_years
            if band_updates:
                spec.seniority_band = spec.seniority_band.model_copy(update=band_updates)
        if spec.location_rule is not None:
            loc_updates: dict = {}
            if counties is not None:
                loc_updates["counties"] = counties
            if args.strict_location:
                loc_updates["require_direct_evidence"] = True
                loc_updates["treat_unknown_as"] = "fail"
            if args.lenient_location:
                loc_updates["require_direct_evidence"] = False
            if loc_updates:
                spec.location_rule = spec.location_rule.model_copy(update=loc_updates)

        log("brief override applied to " + spec.role_id + ": "
            + json.dumps({g.gate_id: g.params for g in spec.hard_gates
                          if g.check in ("seniority_ceiling", "seniority_years",
                                         "located_ie")}))


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
    # Brief-level knobs (client feedback 2026-09-10) settable on a call
    # without editing roles.py. Applied to BOTH ROLE1 and ROLE2's matching
    # hard_gates before any stage runs -- offline, re-runs the gate stage
    # from cached extract.json/validate.json only.
    ap.add_argument(
        "--max-grade", default=None,
        choices=["senior_engineer", "principal_or_associate",
                 "associate_director", "director"],
        help="override seniority_ceiling's max_grade for both roles",
    )
    ap.add_argument(
        "--max-years", type=int, default=None,
        help="override seniority_ceiling's max_years for both roles",
    )
    ap.add_argument(
        "--min-years", type=int, default=None,
        help="override the seniority FLOOR gate's min_years for both roles",
    )
    ap.add_argument(
        "--counties", default=None,
        help="comma list overriding located_ie's counties for both roles "
             "(empty string means any Republic of Ireland location)",
    )
    loc_group = ap.add_mutually_exclusive_group()
    loc_group.add_argument(
        "--strict-location", action="store_true",
        help="located_ie requires direct residence evidence; Irish scheme/"
             "employer work alone fails (require_direct_evidence=True, "
             "treat_unknown_as=fail)",
    )
    loc_group.add_argument(
        "--lenient-location", action="store_true",
        help="located_ie accepts Irish scheme/employer evidence as residence "
             "evidence (the pre-2026-09-10 default; require_direct_evidence=False)",
    )
    ap.add_argument(
        "--live-crm", action="store_true",
        help="sync_crm actually writes to Recruit CRM (RECRUIT_CRM_API_KEY "
             "required). Without this flag sync_crm is dry-run: every "
             "intended write is logged to logs/recruit_crm_audit.jsonl and "
             "nothing is sent.",
    )
    ap.add_argument(
        "--allow-stale", action="store_true",
        help="sync_crm proceeds for a candidate whose evidence is stale "
             "(evidence_age_days > CONFIG.max_evidence_age_days) instead of "
             "skipping them (RADAR_CONTRACTS.md section E). Threaded into "
             "integrations.recruit_crm.sync_delivery(allow_stale=...).",
    )
    ap.add_argument(
        "--allow-placeholder-notice", action="store_true",
        help="the 'render' stage proceeds even if the Art. 14 privacy "
             "notice URL is not live, omitting outreach drafts and showing "
             "a warning banner instead of refusing to render entirely. "
             "Threaded into render.render.build(allow_placeholder_notice=...).",
    )
    ap.add_argument(
        "--icp-check", action="store_true",
        help="run layers.icp_check.icp_check_from_gate_json against "
             "run/<campaign_id>/gate.json, print one 'round N: ...' line "
             "per round, then exit. Requires the 'gate' stage to have run.",
    )
    ap.add_argument(
        "--alert-test", action="store_true",
        help="call core.alerts.alert('gaia_sourcing', CONFIG.campaign_id, "
             "'test alert', 1) and print whether the configured "
             "ALERT_WEBHOOK_URL accepted it, then exit -- does not touch a "
             "run directory.",
    )
    ap.add_argument(
        "--purge-failed-cache", default=None, metavar="ERROR_SUBSTRING",
        help="delete _httpcache entries whose failure error contains this "
             "substring (e.g. empty_after_parse, fitz) so a later run with the "
             "missing key/library re-fetches them; prints the count and exits",
    )
    ap.add_argument(
        "--spend", action="store_true",
        help="print this run's in-memory spend total (core.providers."
             "spend_eur(), zero if nothing has been spent yet this process) "
             "and the persistent cumulative total across every run "
             "(core.providers.cumulative_spend_eur(), from logs/"
             "spend_ledger.jsonl), then exit -- does not touch a run "
             "directory or make any paid call.",
    )
    ap.add_argument(
        "--classify-reply", default=None, metavar="TEXT",
        help="classify one candidate reply, print the ReplyVerdict as JSON, "
             "and exit -- a quick demo, does not touch a run directory",
    )
    ap.add_argument(
        "--label-export", action="store_true",
        help="write run/<campaign_id>/label_export.jsonl -- a BLIND "
             "labelling worksheet (source excerpts only, no extractor "
             "verdict) for every person in gate.json, then exit. See "
             "eval/blind_label_prompt.md. Requires 'gate' to have run.",
    )
    ap.add_argument(
        "--kappa", nargs=2, default=None, metavar=("LABELS_A", "LABELS_B"),
        help="print Cohen's kappa (grade / location_country / chartered) "
             "between two labeller JSONL files, then exit -- does not touch "
             "a run directory",
    )
    ap.add_argument(
        "--coverage-test", default=None, metavar="PROVIDER",
        help="fetch one page (limit 50) from a source provider "
             "(pdl/crustdata/apollo/serper_people) and print matched/title/"
             "employer/dates/city/cost plus a go/no-go line, then exit -- "
             "does not touch a run directory. Requires the provider's own "
             "API key (PDL_API_KEY/CRUSTDATA_API_KEY/APOLLO_API_KEY/"
             "SERPER_API_KEY); see deliverables/gaia_2026-09-10/"
             "KEY_INSTRUCTIONS.md. Combine with --niche.",
    )
    ap.add_argument(
        "--niche", default="structural", choices=sorted(_NICHE_TERMS),
        help="niche terms for --coverage-test (default: structural)",
    )
    args = ap.parse_args()

    if args.coverage_test is not None:
        return run_coverage_test(args.coverage_test, args.niche)

    if args.classify_reply is not None:
        verdict = classify_reply(args.classify_reply)
        print(json.dumps(verdict.model_dump(), indent=2, default=str))
        return 0

    if args.kappa is not None:
        path_a, path_b = Path(args.kappa[0]), Path(args.kappa[1])
        labels_a = {lbl.person_id: lbl for lbl in load_labels(path_a)}
        labels_b = {lbl.person_id: lbl for lbl in load_labels(path_b)}
        common = sorted(set(labels_a) & set(labels_b))
        if not common:
            print("no person_id is labelled in both files -- nothing to score")
            return 0
        print("Cohen's kappa over " + str(len(common)) + " person(s) labelled in both files:")
        for field in ("grade", "location_country", "chartered"):
            a_vals = [getattr(labels_a[pid], field) for pid in common]
            b_vals = [getattr(labels_b[pid], field) for pid in common]
            k = cohen_kappa(a_vals, b_vals)
            print("  " + field + ": " + format(k, ".3f"))
        return 0

    if args.label_export:
        if not done("gate"):
            raise SystemExit("--label-export needs the 'gate' stage to have run first")
        gate_out = load("gate")
        persons = load("extract")["persons"]
        docs = load_docs()
        rows = []
        for pid in gate_out:
            rec = persons.get(pid)
            if rec is None:
                continue
            doc_ids = rec.get("doc_ids") or []
            person_docs = [docs[d].model_dump() for d in doc_ids if d in docs]
            rows.append(build_worksheet_row(pid, rec.get("full_name", pid), person_docs))
        out_path = RUN_DIR / "label_export.jsonl"
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        log("label_export: wrote " + str(len(rows)) + " rows to " + str(out_path))
        return 0

    if args.icp_check:
        gate_path = RUN_DIR / "gate.json"
        if not gate_path.exists():
            raise SystemExit(
                "--icp-check needs the 'gate' stage to have run first ("
                + str(gate_path) + " missing)."
            )
        icp_check_from_gate_json(gate_path, log=log)
        return 0

    if args.alert_test:
        posted = alerts.alert("gaia_sourcing", CONFIG.campaign_id, "test alert", 1)
        log("alert-test: " + ("posted" if posted else "NOT posted (see the "
            "[alerts] log line above -- either no ALERT_WEBHOOK_URL is "
            "configured or the webhook rejected it)"))
        return 0

    if args.purge_failed_cache is not None:
        from .core.cache import CACHE_DIR
        needle = args.purge_failed_cache
        purged = 0
        for meta_p in CACHE_DIR.glob("*.meta.json"):
            try:
                meta = json.loads(meta_p.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                log("  skipping unreadable cache meta " + meta_p.name + ": " + repr(exc)[:80])
                continue
            if meta.get("ok"):
                continue
            if needle and needle not in str(meta.get("error", "")):
                continue
            body_p = meta_p.with_name(meta_p.name.replace(".meta.json", ".body"))
            meta_p.unlink()
            if body_p.exists():
                body_p.unlink()
            purged += 1
        log("purged " + str(purged) + " failed cache entries matching '" + needle + "'")
        return 0

    if args.spend:
        run_total = spend_eur()
        cumulative = cumulative_spend_eur()
        log("spend: this run EUR " + format(run_total, ".2f")
            + " (ceiling EUR " + format(CONFIG.max_cost_eur, ".2f") + ")")
        log("spend: cumulative EUR " + format(cumulative, ".2f")
            + " (ceiling EUR " + format(CONFIG.max_cost_eur_total, ".2f") + ")")
        return 0

    global _LIVE_CRM, _ALLOW_STALE, _ALLOW_PLACEHOLDER_NOTICE
    _LIVE_CRM = args.live_crm
    _ALLOW_STALE = args.allow_stale
    _ALLOW_PLACEHOLDER_NOTICE = args.allow_placeholder_notice

    _apply_brief_overrides(args)

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
