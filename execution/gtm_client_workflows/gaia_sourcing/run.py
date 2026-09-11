"""
L0 -- the orchestrator.

Runs the pipeline in named, resumable stages. Every stage writes its output to
`run/<campaign_id>/<stage>.json` and every later stage reads that file rather
than recomputing. This matters more here than in most pipelines: the expensive
steps are paid API calls (Firecrawl renders, Claude extractions, Prospeo
lookups), so a crash in stage 7 must not re-buy stages 1-6.

Stage order:

  harvest_r1       Firecrawl-render every firm's staff directory        (paid)
  harvest_r2       An Coimisiun Pleanala oral-hearing witness statements (free)
  harvest_r2_web   oral-hearing evidence on scheme/authority sites       (free)
  harvest_discovery  sources.registry providers (serper_people etc.)     (free)
  extract          L5  evidence extraction, both roles                  (paid)
  locate       cheap no-LLM Role 1 location backfill from Firm.domicile (free)
  validate     L6  quote validation -- THE PRODUCT                  (free)
  gate         L7  deterministic gates + tiering                    (free)
  deepen_r1    Re-render the individual profile pages of candidates
               that already passed the gates, and extract again.
               Aimed only at gate-passers, because the directory blurb
               establishes chartership but rarely Eurocode/Tekla, and
               that gap is what holds Role 1 at Tier C.              (paid)
  deepen_near_misses  Targeted search for candidates who fail ONLY an
               evidence-gap gate (CONFIG.deepen_gates, default chartered +
               seniority) -- a search snippet rarely shows "CEng MIEI" or
               "12 years" even for a genuinely qualified person, and the
               chartership registers themselves are not automatable
               (WAF/Cloudflare). Public bio pages, Engineers Journal
               articles, conference bios and award citations often state it
               plainly.                                    (Serper free,
                                                              extraction paid)
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
from .core.cache import fetch as cache_fetch
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
from .layers.identity import has_identity_corroboration
from .layers.extract import (
    _claim_id as _extract_claim_id,
    _find_location_quote,
    employer_from_own_text,
    strip_postnominals,
    extract_directory,
    extract_from_document,
    window_around_names,
)
from .layers.icp_check import icp_check_from_gate_json
from .layers.replies import classify_reply
from .layers.validator import validate_all
from .render import render as render_module
from .render.console import render_console
from .roles import (
    ACCEPT_TITLES_FOR_FLOOR_DEFAULT, ROLE1, ROLE2, ROLES, is_client_side,
)
from .sources import (
    acp,
    company_bios,
    linkedin_lookup,
    oral_hearing_web,
    technical_evidence,
)
from .sources.licensed_common import raw_hash
from .sources.registers import fragment_with_both_names

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

# Deprecated 2026-09-11: superseded by Firm.domicile/office_cities
# (sources/company_bios.py) and _default_location_for_firm below, which cover
# all 59 firms instead of only the original 13. Kept as a frozen historical
# reference only -- nothing in this module reads it any more.
_IRISH_DOMICILED = {
    "rod", "punch", "dbfl", "oconnor_sutton", "mwp", "nodwyer",
    "barrett_mahony", "horganlynch", "kilgallen", "tjoc", "cora",
    "downes", "axis",
}


# 2026-09-11 adversarial-audit fix: office-city names that mean this firm is
# NOT confined to the Republic. If Firm.office_cities names one of these, the
# "several offices" default below must never fire for that firm.
_NON_IE_OFFICE_CITY_RE = re.compile(
    r"\b(belfast|derry|londonderry|antrim|armagh|newry|lisburn|"
    r"london|birmingham|manchester|glasgow|edinburgh|leeds|bristol)\b",
    re.I,
)


def _default_location_for_firm(firm) -> Optional[str]:
    """The location a firm's directory implies for a person with no stated office.

    2026-09-11 adversarial-audit fix: a firm's default location now counts
    only when its offices are ALL in the Republic -- domicile "IE", AND
    office_cities actually named (not empty/unknown), AND none of them is a
    Northern Ireland or Great Britain city. O'Connor Sutton Cronin is the
    exhibit: domicile "IE" but ALSO Belfast/Birmingham/London, which is why
    Firm.multi_country exists and is checked first. A firm with `office_cities
    == []` (office count not confidently known) no longer gets a bare
    "Ireland" default on the strength of domicile alone -- the widening this
    used to provide traded away exactly the residence-evidence hygiene this
    fix restores; such a firm's people must evidence Ireland individually or
    fail located_ie, same as any UK/INTL firm always has.

    IE-domiciled firms with exactly one known, Irish office city ->
    "<City>, Ireland" (the strongest default: it also lets the located_ie
    gate's `counties` param match a specific county straight away). An IE
    firm with several known, all-Irish cities gets the generic "Ireland" --
    still enough to pass located_ie's Republic-wide check. UK/INTL firms, and
    any multi-country IE firm, get no default at all.
    """
    if firm.domicile != "IE":
        return None
    if firm.multi_country:
        return None
    if not firm.office_cities:
        return None
    if any(_NON_IE_OFFICE_CITY_RE.search(c) for c in firm.office_cities):
        return None
    if len(firm.office_cities) == 1:
        return firm.office_cities[0] + ", Ireland"
    return "Ireland"


# 2026-09-11 adversarial-audit fix: a firm's people-directory page sometimes
# lists NI/GB offices that Firm.office_cities does not (yet) know about --
# scanned at stage_locate time, from the already-cached page text, so a
# default location that _default_location_for_firm would otherwise grant
# never gets handed out where the page itself contradicts it.
_PAGE_NI_UK_OFFICE_RE = re.compile(
    r"\b(belfast|derry|londonderry|antrim|armagh|newry|lisburn|"
    r"london|birmingham|manchester|glasgow|edinburgh|leeds|bristol)\b"
    r"[^.\n]{0,20}\boffice\b"
    r"|\boffice\b[^.\n]{0,20}\b(belfast|derry|londonderry|antrim|armagh|newry|"
    r"lisburn|london|birmingham|manchester|glasgow|edinburgh|leeds|bristol)\b",
    re.I,
)


def _page_lists_ni_or_uk_office(text: str) -> bool:
    """True when `text` (a firm's cached directory page) names an office in
    Northern Ireland or Great Britain near the word "office" -- see
    _PAGE_NI_UK_OFFICE_RE. Used by stage_locate to void a firm default that
    Firm.office_cities alone did not catch."""
    return bool(text) and bool(_PAGE_NI_UK_OFFICE_RE.search(text))


def stage_harvest_r1(force: bool = False) -> None:
    if done("harvest_r1") and not force:
        log("harvest_r1: cached, skipping")
        return
    log("harvest_r1: discovering + rendering staff directories for "
        + str(len(company_bios.FIRMS)) + " firms")

    records: list[dict] = []
    docs: list[RawDocument] = []
    no_page_firms: list[str] = []
    lock = threading.Lock()

    def one(firm) -> None:
        try:
            urls = company_bios.discover_people_urls(firm, limit=4)
            found_any = False
            for url in urls:
                doc = fetch_rendered(url, source_type="company_bio")
                if doc is None or len(doc.content_text) < 800:
                    continue
                found_any = True
                with lock:
                    docs.append(doc)
                    records.append(
                        {
                            "firm_slug": firm.slug,
                            "firm_name": firm.name,
                            "url": url,
                            "doc_id": doc.doc_id,
                            "chars": len(doc.content_text),
                            "default_location": _default_location_for_firm(firm),
                        }
                    )
                log("  " + firm.slug + ": " + str(len(doc.content_text)) + " chars <- " + url)
            if not found_any:
                with lock:
                    no_page_firms.append(firm.slug)
                log("  " + firm.slug + ": no people page found (tried "
                    + str(len(urls)) + " urls)")
        except Exception as exc:
            with lock:
                no_page_firms.append(firm.slug)
            log("  " + firm.slug + " FAILED: " + repr(exc)[:120])

    run_all(one, company_bios.FIRMS, workers=4, label="harvest_r1")

    save_docs(docs)
    save("harvest_r1", records)
    log("harvest_r1: " + str(len(records)) + " directory pages from "
        + str(len({r["firm_slug"] for r in records})) + " firms ("
        + str(len(no_page_firms)) + " firms with no people page found)")


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
# Stage 1d -- free/cheap people-discovery via sources.registry providers
# (RADAR_CONTRACTS.md section A). Runs before the paid r1/r2 harvests widen
# the pool with cost-free candidates first.
# ---------------------------------------------------------------------------

# Default counties for a role whose location_rule sets no specific counties
# (Role 1's brief is "any ROI" -- roles.py's LocationRule(counties=[])).
# Not exhaustive of every Irish county; the four the pipeline's candidates
# have actually come from (see sources/serper_people.py's own _IE_COUNTIES
# for the exhaustive list used at query-build time).
_DISCOVERY_DEFAULT_LOCATIONS = ["Cork", "Dublin", "Limerick", "Galway"]


def _title_like_discipline_terms(spec, limit: int = 3) -> list[str]:
    """The discipline hard gate's `include` terms that read as a searchable
    job title/role phrase rather than a bare discipline noun.

    "structural engineer" is a LinkedIn-searchable job title; "structural"
    alone matches a structural biology PhD as readily as a structural
    engineer. Heuristic: a multi-word phrase is treated as title-like, a
    single bare word is not. Falls back to the first `limit` include terms
    verbatim if the gate's include list happens to be all single words, so
    this never returns nothing for a role whose gate is written differently.
    """
    discipline_gate = next(
        (g for g in spec.hard_gates if g.check == "discipline"), None
    )
    include = list((discipline_gate.params.get("include") if discipline_gate else []) or [])
    title_like = [t for t in include if " " in t]
    return (title_like or include)[:limit]


def stage_harvest_discovery(force: bool = False) -> None:
    """Free/cheap people-discovery ahead of the paid r1/r2 harvests.

    For each role in ROLES, builds one SourceQuery (title + top job-title-
    like discipline terms, the role's counties or a default Irish spread)
    and runs it through every provider named in CONFIG.discovery_providers,
    resolved via sources.registry.get_provider. A provider missing its API
    key raises ProviderNotConfigured (sources/licensed_common.py) and is
    skipped with a log line rather than failing the stage -- same contract
    as run_coverage_test below.

    CONFIG.discovery_max_queries caps the TOTAL query budget across every
    role x provider combination in this one stage run, tracked here rather
    than inside any one provider, because a provider's fetch() has no way to
    know how many sibling calls this stage is about to make -- serper_people
    alone issues 3 queries per (term, location) pair (sources/
    serper_people.py's _build_queries), so an unwatched multi-role,
    multi-provider stage could burn a free-tier quota or rate limit in one
    run. The per-call estimate (len(terms) * len(locations)) is a query
    COUNT ESTIMATE for budgeting, not necessarily each provider's own exact
    internal query count -- see this function's inline comment.
    """
    if done("harvest_discovery") and not force:
        log("harvest_discovery: cached, skipping")
        return
    log("harvest_discovery: discovering people via "
        + ", ".join(CONFIG.discovery_providers))

    import importlib

    from .core.contracts import SourceQuery
    from .sources.licensed_common import ProviderNotConfigured
    from .sources.registry import get_provider

    records: list[dict] = []
    docs: list[RawDocument] = []
    queries_used = 0
    budget = CONFIG.discovery_max_queries

    for role_id, spec in ROLES.items():
        niche = "structural" if role_id == ROLE1.role_id else "transport"
        terms = [spec.title.lower()] + _title_like_discipline_terms(spec)
        locations = (
            (spec.location_rule.counties if spec.location_rule else None)
            or _DISCOVERY_DEFAULT_LOCATIONS
        )
        query = SourceQuery(
            role_id=role_id, niche=niche, terms=terms, locations=locations,
            limit=CONFIG.discovery_limit,
        )
        # Budgeting estimate only -- see docstring above. Each provider's own
        # fetch() decides its real query shape; this is what this STAGE
        # charges against the shared budget for one role x provider call.
        query_cost_estimate = len(terms) * len(locations)

        for provider_name in CONFIG.discovery_providers:
            if queries_used + query_cost_estimate > budget:
                log("  " + role_id + "/" + provider_name + ": skipped -- "
                    "discovery_max_queries budget (" + str(budget) + ") would "
                    "be exceeded (" + str(queries_used) + " used, "
                    + str(query_cost_estimate) + " needed)")
                continue

            # serper_people (and any other free/registry provider that is
            # not one of the three chartership-register plugins registry.py
            # imports at module level) must be imported at least once for
            # its module-level `register_provider(...)` call to have run --
            # same registration hook run_coverage_test below uses.
            module_path = _LICENSED_PROVIDER_MODULES.get(provider_name)
            if module_path is not None:
                try:
                    importlib.import_module(module_path)
                except ImportError as exc:
                    log("  " + role_id + "/" + provider_name + ": could not "
                        "import " + module_path + ": " + repr(exc)[:160])
                    continue
            try:
                provider = get_provider(provider_name)
            except KeyError as exc:
                log("  " + role_id + "/" + provider_name + ": not registered "
                    "-- " + repr(exc)[:160])
                continue

            try:
                result = provider.fetch(query)
            except ProviderNotConfigured as exc:
                log("  " + role_id + "/" + provider_name + ": skipped, not "
                    "configured -- " + str(exc))
                continue
            except Exception as exc:
                log("  " + role_id + "/" + provider_name + " FAILED: "
                    + repr(exc)[:160])
                continue

            queries_used += query_cost_estimate
            if result.error:
                log("  " + role_id + "/" + provider_name + ": provider "
                    "returned " + result.error)
                continue

            # documents/provider_records are built in lockstep by every
            # provider that emits both (see sources/serper_people.py's
            # fetch()) -- one appended for every kept organic result, in the
            # same order -- so zipping them by position is exact, not a
            # best-effort join.
            for doc, pr in zip(result.documents, result.provider_records):
                # 2026-09-11 adversarial-audit fix (item 4): a search_snippet
                # document is kept only when its title carries a discipline
                # token -- the same identity-corroboration rule deepen_near_
                # misses applies to a fetched page, applied here to the
                # title text this stage actually has (see
                # layers.identity.has_identity_corroboration).
                if doc.source_type == "search_snippet" and not has_identity_corroboration(
                    doc.title or pr.current_title or "", pr.current_employer
                ):
                    log("  identity: " + role_id + " skipped " + _url_tail(str(doc.url))
                        + ": no corroboration")
                    continue
                docs.append(doc)
                records.append({
                    "role_id": role_id,
                    "provider": provider_name,
                    "url": str(doc.url),
                    "doc_id": doc.doc_id,
                    "full_name": pr.full_name,
                    "current_title": pr.current_title,
                    "current_employer": pr.current_employer,
                    "city": pr.city,
                })
            # A provider that returns documents with no paired provider
            # records (a fixture, or a future provider shaped differently)
            # still gets its documents harvested -- just with no parsed
            # identity fields, same as any doc extract.py cannot pre-fill.
            for doc in result.documents[len(result.provider_records):]:
                docs.append(doc)
                records.append({
                    "role_id": role_id,
                    "provider": provider_name,
                    "url": str(doc.url),
                    "doc_id": doc.doc_id,
                    "full_name": None,
                    "current_title": None,
                    "current_employer": None,
                    "city": None,
                })

            log("  harvest_discovery: " + role_id + ": " + str(result.fetched)
                + " people from " + provider_name + " ("
                + str(query_cost_estimate) + " queries, EUR "
                + format(result.cost_eur, ".4f") + ")")

    save_docs(docs)
    save("harvest_discovery", records)
    log("harvest_discovery: " + str(len(records)) + " people across "
        + str(len({r["provider"] for r in records})) + " provider(s), "
        + str(queries_used) + "/" + str(budget) + " queries used")


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

    # -- Discovery: one search-snippet is one person -------------------------
    # search_snippet documents already carry a parsed name/title/employer/
    # city (sources/serper_people.py's title/snippet parsing, done at harvest
    # time with no LLM call) -- extract_from_document is still run so every
    # claim on the card is quote-verified by L6 like any other source, but
    # the record's own parsed fields win over the model's hints below,
    # because they came from the SAME text with no chance of the model
    # reading a different person into the snippet.
    if done("harvest_discovery"):
        r3 = load("harvest_discovery")
        log("extract: discovery snippets across " + str(len(r3)) + " documents")

        def do_discovery(rec: dict) -> None:
            doc = corpus.get(rec["doc_id"])
            if doc is None or doc.doc_id in seen_docs:
                return
            name = (rec.get("full_name") or "").strip()
            if not name:
                return
            pid = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
            person = Person(
                person_id=pid,
                full_name=name,
                current_title=rec.get("current_title"),
                current_employer=rec.get("current_employer"),
                location=rec.get("city"),
                doc_ids=[doc.doc_id],
            )
            try:
                found, hints = extract_from_document(person, doc)
            except Exception as exc:
                log("  " + pid + " discovery extract FAILED: " + repr(exc)[:120])
                return
            with lock:
                slot = persons.setdefault(
                    pid,
                    {**person.model_dump(), "role_id": rec["role_id"],
                     "source": "search_snippet"},
                )
                for field in ("current_title", "current_employer", "location"):
                    if not slot.get(field) and (hints or {}).get(field):
                        slot[field] = hints[field]
                slot.setdefault("doc_ids", [])
                if doc.doc_id not in slot["doc_ids"]:
                    slot["doc_ids"].append(doc.doc_id)
                if found:
                    claims.extend(c.model_dump() for c in found)
                seen_docs.add(doc.doc_id)

        run_all(do_discovery, r3, workers=3, label="extract_discovery")

    save("extract", {
        "persons": persons,
        "claims": claims,
        "extracted_doc_ids": sorted(seen_docs),
    })
    log("extract: " + str(len(persons)) + " persons, " + str(len(claims)) + " raw claims")


# ---------------------------------------------------------------------------
# Stage 2b -- cheap, no-LLM location backfill
# ---------------------------------------------------------------------------


def stage_locate(force: bool = False) -> None:
    """Re-derive Role 1 Person.location from Firm.domicile without any LLM call.

    Exists so a change to sources.company_bios.Firm's domicile/office_cities
    -- like this widening, which gave the 42 firms added 2026-09-11 a
    default location for the first time -- can be picked up by every
    already-extracted person WITHOUT re-running stage_harvest_r1 (a paid
    Firecrawl render) or stage_extract's L5 calls (paid, and the very
    directory pages that would be re-fetched are already cached in
    docs.jsonl). Everything this stage touches is already on disk:
    harvest_r1.json for the firm_slug each directory page came from,
    docs.jsonl for the cached page text, and extract.json for the persons
    to backfill.

    Only fills a company_directory person's location when it is currently
    EMPTY -- an existing location (however it got there) is never
    overwritten, so this is safe to re-run after any future firm-list edit.
    Mirrors extract_directory's own default-location behaviour exactly:
    Person.location is set from Firm's default AND, when the cached page
    states the office city or "Ireland" near the person's name (or anywhere
    on the page), a quoted `location` Claim is added too
    (layers.extract._find_location_quote) -- a bare default is not evidence
    on its own.

    Provenance: whenever a location is set from a firm default here,
    `Person.location_source` is stamped "firm_default" (2026-09-11). A
    location that came from extraction itself or from an on-page quote
    carries no such stamp and this stage never touches it.

    On `force`, every person currently stamped "firm_default" has that
    location CLEARED first (location and location_source both reset to
    None), then the normal fill-if-empty pass below re-derives it under the
    CURRENT firm data. Without this, `--force` after a firm is newly marked
    `multi_country` (i.e. _default_location_for_firm now correctly returns
    None for it) would leave that firm's people holding a stale "Ireland" --
    the "only fills when empty" rule above would see the old value still
    sitting there and skip them forever. A person whose location came from
    extraction or an on-page quote has no location_source stamp and is never
    cleared by this.
    """
    if not done("extract"):
        log("locate: extract.json missing -- run stage_extract first, skipping")
        return
    if done("locate") and not force:
        log("locate: cached, skipping")
        return

    data = load("extract")
    persons: dict = data.get("persons", {})
    claims: list[dict] = data.get("claims", [])
    have_claim_ids = {c["claim_id"] for c in claims}

    r1 = load("harvest_r1") if done("harvest_r1") else []
    rec_by_doc_id = {r["doc_id"]: r for r in r1}
    firm_by_slug = {f.slug: f for f in company_bios.FIRMS}
    corpus = load_docs()

    loc_claims_by_pid: dict[str, list[dict]] = {}
    for c in claims:
        if c.get("dimension") == "location":
            loc_claims_by_pid.setdefault(
                c.get("subject_person_id"), []
            ).append(c)

    def _has_real_location_evidence(pid: str) -> bool:
        for c in loc_claims_by_pid.get(pid, []):
            cleaned = gates._clean_residence_haystack(c.get("evidence_quote") or "")
            if gates._RESIDENCE_SHAPE_RE.search(cleaned) or gates._IE_RE.search(cleaned):
                return True
        return False

    if force:
        cleared = 0
        for prec in persons.values():
            if prec.get("location_source") == "firm_default":
                prec["location"] = None
                prec["location_source"] = None
                cleared += 1
        if cleared:
            log("locate: --force cleared " + str(cleared)
                + " stale firm_default location(s) for recompute")

        # 2026-09-11 second-audit fix (item 1): persons extracted BEFORE
        # location_source existed (e.g. O'Connor Sutton Cronin, extracted
        # pre-fix) carry a firm-default location with NO stamp at all -- the
        # pass above can never see them, so --force never clears the stale
        # value and it survives forever. Detected by shape instead: a
        # company_directory person whose location is exactly "Ireland" or
        # "<city>, Ireland", unstamped, AND with no location-dimension claim
        # whose quote is real residence evidence (survives
        # gates._clean_residence_haystack and matches a residence-shaped
        # phrase or an Irish county/city token). Such a person's location is
        # cleared; if the CURRENT _default_location_for_firm still grants a
        # default for their firm, it is reapplied WITH the provenance stamp
        # so it is tracked correctly from here on.

        legacy_cleared = 0
        legacy_restamped = 0
        for pid, prec in persons.items():
            if prec.get("role_id") != ROLE1.role_id:
                continue
            if prec.get("source") != "company_directory":
                continue
            if prec.get("location_source"):
                continue  # already provenance-tracked, handled above
            loc = prec.get("location")
            if not loc or not (loc == "Ireland" or loc.endswith(", Ireland")):
                continue

            if _has_real_location_evidence(pid):
                continue

            rec = None
            for did in prec.get("doc_ids", []) or []:
                rec = rec_by_doc_id.get(did)
                if rec is not None:
                    break
            firm = firm_by_slug.get(rec.get("firm_slug")) if rec else None

            prec["location"] = None
            prec["location_source"] = None
            legacy_cleared += 1
            if firm is not None:
                new_default = _default_location_for_firm(firm)
                if new_default:
                    prec["location"] = new_default
                    prec["location_source"] = "firm_default"
                    legacy_restamped += 1
        if legacy_cleared:
            log("locate: --force cleared " + str(legacy_cleared)
                + " legacy (pre-provenance) firm-default location(s)"
                + (", " + str(legacy_restamped)
                   + " re-stamped under current firm data" if legacy_restamped else ""))

    # Employer recovery for every role: a person with no current_employer
    # whose own document states one in a recognisable shape gets it, with a
    # quoted direct employer claim (third audit 2026-09-11: Alcaras, Clyne).
    employers_recovered = 0
    for pid, prec in persons.items():
        if (prec.get("current_employer") or "").strip():
            continue
        name_parts = strip_postnominals(prec.get("full_name") or "").split()
        if len(name_parts) < 2:
            continue
        for did in prec.get("doc_ids", []) or []:
            doc = corpus.get(did)
            if doc is None:
                continue
            # Name-anchored: only the text around this person's own name is
            # searched, so a team page or a post listing several people
            # cannot hand one person another's employer (code review).
            window = window_around_names(
                doc.content_text, name_parts[0], name_parts[-1], 300
            )
            if not window or name_parts[-1].lower() not in window.lower():
                continue
            hit = employer_from_own_text(window)
            if not hit:
                continue
            firm, quote = hit
            cid = _extract_claim_id(pid, did, quote)
            if cid not in have_claim_ids:
                claims.append({
                    "claim_id": cid, "subject_person_id": pid,
                    "dimension": "employer",
                    "assertion": prec.get("full_name", pid) + " works at " + firm,
                    "evidence_quote": quote, "source_doc_id": did,
                    "source_url": str(doc.url), "confidence": "direct",
                })
                have_claim_ids.add(cid)
            prec["current_employer"] = firm
            employers_recovered += 1
            log("locate: " + pid + " employer recovered from own text: " + firm)
            break

    relocated = 0
    backfilled = 0
    new_location_claims = 0
    for pid, prec in persons.items():
        if prec.get("role_id") != ROLE1.role_id:
            continue
        if prec.get("source") != "company_directory":
            continue

        rec = None
        for did in prec.get("doc_ids", []) or []:
            rec = rec_by_doc_id.get(did)
            if rec is not None:
                break
        if rec is None:
            continue
        firm = firm_by_slug.get(rec.get("firm_slug"))
        if firm is None:
            continue
        default_location = _default_location_for_firm(firm)

        if prec.get("location"):
            # Back-fill provenance for a location that IS the current firm
            # default but was set unstamped (extract runs before 2026-09-11
            # stamped at source). Same datum, same stamp.
            # A person with a real quoted residence keeps extraction's
            # provenance (None) -- the claim carries the gate for them.
            if (default_location and not prec.get("location_source")
                    and prec.get("location") == default_location
                    and not _has_real_location_evidence(pid)):
                prec["location_source"] = "firm_default"
                backfilled += 1
            continue
        if not default_location:
            continue

        doc = corpus.get(rec["doc_id"])
        # 2026-09-11 adversarial-audit fix: the firm's own cached page can
        # name an NI/UK office that Firm.office_cities does not yet know
        # about -- void the default rather than hand out a wrong "Ireland".
        if doc is not None and _page_lists_ni_or_uk_office(doc.content_text):
            continue

        prec["location"] = default_location
        prec["location_source"] = "firm_default"
        relocated += 1

        if doc is None:
            continue
        city = None
        if default_location != "Ireland" and default_location.endswith(", Ireland"):
            city = default_location.rsplit(",", 1)[0].strip()
        quote = _find_location_quote(doc.content_text, prec.get("full_name", ""), city)
        if not quote:
            continue
        cid = _extract_claim_id(pid, doc.doc_id, quote)
        if cid in have_claim_ids:
            continue
        have_claim_ids.add(cid)
        claims.append(
            Claim(
                claim_id=cid,
                subject_person_id=pid,
                dimension="location",
                assertion=prec.get("full_name", "") + " is based in " + default_location,
                evidence_quote=quote,
                source_doc_id=doc.doc_id,
                source_url=doc.url,
                confidence="direct",
            ).model_dump()
        )
        new_location_claims += 1

    data["persons"] = persons
    data["claims"] = claims
    save("extract", data)
    save("locate", {"relocated": relocated, "new_location_claims": new_location_claims,
                    "employers_recovered": employers_recovered,
                    "provenance_backfilled": backfilled})
    log("locate: " + str(relocated) + " persons given a location, "
        + str(employers_recovered) + " employers recovered from own text, "
        + str(backfilled) + " unstamped firm defaults given provenance, "
        + str(new_location_claims) + " location claims quoted from cached pages")

    if relocated or employers_recovered or backfilled:
        stage_validate(force=True)
        stage_gate(force=True)


# ---------------------------------------------------------------------------
# Stage 4c -- identity hygiene (offline, no LLM). 2026-09-11: the adversarial
# audit found delivered cards whose claims came from OTHER people with the same
# name (a Mayo structural engineer merged with a Missouri car salesman), all
# attached by the earlier near-miss deepening before its corroboration rule
# existed. Re-extraction is not affordable; the same corroboration rule applied
# to the cached page text removes the wrong-person claims for free.
# ---------------------------------------------------------------------------

_HYGIENE_SOURCE_TYPES = {"other", "search_snippet", "technical_evidence"}


def stage_identity_hygiene(force: bool = False) -> None:
    if not done("extract"):
        log("identity_hygiene: extract.json missing -- run stage_extract first, skipping")
        return
    if done("identity_hygiene") and not force:
        log("identity_hygiene: cached, skipping")
        return
    from .layers.identity import has_identity_corroboration
    from .sources.registers import fragment_with_both_names

    data = load("extract")
    persons = data.get("persons", {})
    claims = data.get("claims", [])
    corpus = load_docs()
    dropped_total = 0
    per_person: dict[str, int] = {}
    kept: list[dict] = []
    for c in claims:
        pid = c.get("subject_person_id")
        prec = persons.get(pid)
        doc = corpus.get(c.get("source_doc_id"))
        if prec is None or doc is None or doc.source_type not in _HYGIENE_SOURCE_TYPES:
            kept.append(c)
            continue
        parts = (prec.get("full_name") or "").split()
        forename, surname = (parts[0], parts[-1]) if len(parts) >= 2 else ("", "")
        window = fragment_with_both_names(doc.content_text, forename, surname) if forename else None
        if window is None:
            # the name never co-occurs on the page: the quote may still be
            # verbatim, but nothing ties the page to this person
            reason = "name not on page together"
        elif not has_identity_corroboration(window, prec.get("current_employer")):
            reason = "no corroboration or contradicting profession"
        else:
            kept.append(c)
            continue
        dropped_total += 1
        per_person[pid] = per_person.get(pid, 0) + 1
        log("identity_hygiene: " + str(pid) + " dropped claim from "
            + str(c.get("source_url", ""))[-60:] + ": " + reason)
    # a person keeps a doc_id only while some kept claim still cites it
    cited: dict[str, set] = {}
    for c in kept:
        cited.setdefault(c["subject_person_id"], set()).add(c["source_doc_id"])
    for pid, prec in persons.items():
        ids = prec.get("doc_ids") or []
        prec["doc_ids"] = [
            d for d in ids
            if (corpus.get(d) is None or corpus[d].source_type not in _HYGIENE_SOURCE_TYPES
                or d in cited.get(pid, set()))
        ]
    data["claims"] = kept
    save("extract", data)
    save("identity_hygiene", {"dropped": dropped_total, "per_person": per_person})
    log("identity_hygiene: dropped " + str(dropped_total) + " claims across "
        + str(len(per_person)) + " persons; " + str(len(kept)) + " claims kept")
    if dropped_total:
        stage_validate(force=True)
        stage_gate(force=True)



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
# Stage 5b -- targeted search for near-miss candidates (evidence-gap gates)
# ---------------------------------------------------------------------------

# The registers themselves (Engineers Ireland/IStructE/ICE) cannot be
# scraped -- they sit behind WAF/Cloudflare (sources/registers.py) -- so a
# person's chartership is only ever recoverable from a public page that
# QUOTES it: a firm bio page, an Engineers Journal/Engineers Ireland
# article, a conference bio, an award citation, or the search snippet's own
# headline text. Reusing gates._CHARTERED_RE keeps "does this text evidence
# chartership" defined in exactly one place in the whole pipeline.
_CHARTER_TOKEN_RE = gates._CHARTERED_RE

# Never fetch a LinkedIn URL here: linkedin_lookup.py and sources/
# serper_people.py already establish that a LinkedIn RESULT (not a fetched
# page) is a search_snippet; the page itself requires a login wall this
# pipeline has no session for, and fetching it would just cache a login
# page as if it were evidence.
_LINKEDIN_HOST_RE = re.compile(r"linkedin\.com", re.I)


def _url_tail(url: str) -> str:
    """The last path segment of a URL, for a compact log line."""
    return (url or "").rstrip("/").rsplit("/", 1)[-1][:80] or url


def _near_miss_queries(full_name: str, employer: Optional[str]) -> list[str]:
    """Up to two employer-scoped queries plus one years-of-experience query.

    Quoted on the full name throughout -- an unquoted Irish name returns the
    whole country, same rationale as sources/technical_evidence.py.
    """
    q = '"' + full_name + '"'
    emp = employer or ""
    out = [
        q + ' (CEng OR MIEI OR "Chartered Engineer") ' + emp,
        q + ' "' + emp + '" engineer',
        q + ' engineer "years" (experience OR chartered)',
    ]
    return out


def _snippet_doc(title: str, snippet: str, link: str) -> RawDocument:
    """A Serper organic result as its own RawDocument.

    Exact content_text shape as sources/serper_people.py's `_to_document` --
    the quote validator (layers/validator.py) checks a claim's
    evidence_quote against this text verbatim, so the three lines and their
    order are load-bearing, not cosmetic.
    """
    content_text = "title: " + title + "\nsnippet: " + snippet + "\nurl: " + link
    return RawDocument(
        doc_id=raw_hash({"title": title, "snippet": snippet, "url": link}),
        url=link,
        source_type="search_snippet",
        fetched_at=date.today(),
        content_text=content_text,
        http_status=200,
        title=title or None,
    )


def stage_deepen_near_misses(force: bool = False) -> None:
    """Targeted search for candidates who fail ONLY an evidence-gap gate.

    A search snippet establishes a person's name, title and employer but
    rarely their chartership post-nominals or a stated years-of-experience
    figure -- CONFIG.deepen_gates (default ["chartered", "seniority"]) names
    the gates where "no public evidence found" plausibly means "the evidence
    exists but the harvested source never showed it" rather than "this
    person genuinely does not qualify". A near-miss is anyone whose FAILED
    gates are a subset of that list; failing any other gate (discipline,
    seniority_ceiling, not_client, located_ie) is a real exclusion and is
    never deepened.

    For each near-miss (capped at CONFIG.deepen_near_miss_cap,
    richest-evidence-first), up to three Serper queries look for a page that
    states it explicitly. The Serper result's own title+snippet is kept as a
    search_snippet document when it already carries a chartership token --
    the snippet is public text and L6's validator checks a claim's quote
    against it like any other source. Every non-LinkedIn organic result is
    also fetched; the fetched page is kept as evidence only when the
    person's forename and surname co-occur within a tight fragment of it
    (sources/registers.fragment_with_both_names) -- the same "no claim ships
    without a verbatim quote naming this person" rule the register plugins
    use, because a page merely containing "Chartered Engineer" somewhere
    proves nothing about THIS candidate.

    New documents are extracted and their claims folded back into
    extract.json, then validate + gate re-run exactly as stage_deepen_r1
    does, so tiering reflects them before the next stage runs.
    """
    if not done("gate"):
        log("deepen_near_misses: gate.json missing -- run stage_gate first, skipping")
        return
    if done("deepen_near_misses") and not force:
        log("deepen_near_misses: cached, skipping")
        return

    persons, _, _ = _persons_and_claims()
    # `source` is popped off each person record by _persons_and_claims and
    # not returned; read it from extract.json directly (code review
    # 2026-09-11: the third tuple element is roles, not sources).
    sources = {
        pid: rec.get("source", "") for pid, rec in load("extract")["persons"].items()
    }
    gate_out = load("gate")
    deepen_gates = set(CONFIG.deepen_gates)

    def _eligible(pid: str, failed: set[str]) -> bool:
        if not failed or not failed <= deepen_gates:
            return False
        # located_ie is a real exclusion for a company-directory person (the
        # firm's own page says where its offices are) but an EVIDENCE GAP for
        # a search-snippet person: a 300-character snippet routinely omits
        # the profile's location line. Deepening it is allowed only for the
        # latter (2026-09-11 third cut: Kate FitzGerald, Seckin Cetinkaya).
        if "located_ie" in failed and sources.get(pid) != "search_snippet":
            return False
        return True

    ranked = sorted(
        (-g["n_claims"], pid) for pid, g in gate_out.items()
        if g["tier"] == "EXCLUDED" and not g["client_side"]
        and _eligible(pid, {gr["gate_id"] for gr in g["gates"] if not gr["passed"]})
    )
    targets = [pid for _, pid in ranked][: CONFIG.deepen_near_miss_cap]
    log("deepen_near_misses: " + str(len(targets)) + " near-miss candidates "
        + "(gates " + ", ".join(sorted(deepen_gates)) + "), cap "
        + str(CONFIG.deepen_near_miss_cap))

    lock = threading.Lock()
    query_count = 0
    query_budget_hit = False
    docs: list[RawDocument] = []
    docs_by_pid: dict[str, int] = {}
    new_claims: list[dict] = []

    def one(pid: str) -> None:
        nonlocal query_count, query_budget_hit
        person = persons[pid]
        name_parts = [p for p in person.full_name.split() if p]
        if len(name_parts) < 2:
            return
        forename, surname = name_parts[0], name_parts[-1]
        person_docs: list[RawDocument] = []
        seen_urls: set[str] = set()

        for query in _near_miss_queries(person.full_name, person.current_employer):
            with lock:
                if query_count >= CONFIG.deepen_max_queries:
                    query_budget_hit = True
                    break
                query_count += 1
            try:
                results = oral_hearing_web.serper_search(query, num=10)
            except Exception as exc:
                log("  " + pid + " near-miss query FAILED: " + repr(exc)[:120])
                continue
            for item in results:
                link = (item.get("link") or "").strip()
                if not link or link in seen_urls:
                    continue
                seen_urls.add(link)
                title = item.get("title") or ""
                snippet = item.get("snippet") or ""
                # The two checks below are independent, not either/or: a
                # LinkedIn headline snippet can carry "CEng MIEI" in its own
                # right (kept here) even though its page is never fetched
                # (below), and a firm-bio result can supply BOTH its own
                # snippet-as-evidence and its fetched page as a second,
                # richer document.
                if _CHARTER_TOKEN_RE.search(title + " " + snippet):
                    # 2026-09-11 adversarial-audit fix (item 4): a snippet
                    # carrying a charter token still needs corroboration --
                    # the name alone is not enough to attach it to this
                    # person. See layers.identity.has_identity_corroboration.
                    if has_identity_corroboration(
                        title + " " + snippet, person.current_employer
                    ):
                        person_docs.append(_snippet_doc(title, snippet, link))
                    else:
                        log("  identity: " + pid + " skipped " + _url_tail(link)
                            + ": no corroboration")
                if _LINKEDIN_HOST_RE.search(link):
                    continue
                try:
                    page = cache_fetch(link, source_type="other")
                except Exception as exc:
                    log("  " + pid + " near-miss fetch FAILED: " + repr(exc)[:120])
                    continue
                if page is None or len(page.content_text) < 300:
                    continue
                fragment = fragment_with_both_names(page.content_text, forename, surname)
                if fragment is None:
                    continue
                # 2026-09-11 adversarial-audit fix (item 4): a fetched page
                # may only be attached to this person when the text around
                # their name corroborates their professional identity (their
                # employer, or a discipline word) and carries no contradicting
                # profession token -- a Porsche sales page for "Shane
                # Heffernan" must never be attached to a structural engineer
                # of the same name.
                if not has_identity_corroboration(fragment, person.current_employer):
                    log("  identity: " + pid + " skipped " + _url_tail(link)
                        + ": no corroboration")
                    continue
                person_docs.append(page)

        if not person_docs:
            return
        found_claims: list[Claim] = []
        for doc in person_docs:
            # Window the extraction INPUT to CONFIG.deepen_window_chars either
            # side of the first co-occurrence of the person's names -- the
            # full page is still what gets cached (docs.extend below) and
            # what the L6 validator checks quotes against, so a quote just
            # outside the window still validates. See
            # layers.extract.window_around_names and CONFIG.deepen_window_chars.
            windowed_text = window_around_names(
                doc.content_text, forename, surname, CONFIG.deepen_window_chars
            )
            log("  " + pid + ": windowed " + doc.doc_id + " to "
                + str(len(windowed_text)) + " chars (full "
                + str(len(doc.content_text)) + ")")
            extract_doc = doc.model_copy(update={"content_text": windowed_text})
            try:
                claims, _hints = extract_from_document(person, extract_doc)
            except Exception as exc:
                log("  " + pid + " near-miss extract FAILED: " + repr(exc)[:120])
                continue
            found_claims.extend(claims)
        with lock:
            docs.extend(person_docs)
            docs_by_pid[pid] = docs_by_pid.get(pid, 0) + len(person_docs)
            new_claims.extend(c.model_dump() for c in found_claims)

    run_all(one, targets, workers=4, label="deepen_near_miss")
    if query_budget_hit:
        log("  deepen_near_misses: query budget (" + str(CONFIG.deepen_max_queries)
            + ") reached -- remaining candidates got fewer than 3 queries")

    save_docs(docs)
    save("deepen_near_misses", {
        "targets": targets,
        "docs_by_pid": docs_by_pid,
        "claims": new_claims,
        "queries_used": query_count,
    })

    if new_claims:
        data = load("extract")
        have = {c["claim_id"] for c in data["claims"]}
        data["claims"].extend(c for c in new_claims if c["claim_id"] not in have)
        save("extract", data)
        stage_validate(force=True)
        stage_gate(force=True)

    new_gate = load("gate") if new_claims else gate_out
    now_passing = 0
    for pid in targets:
        n = docs_by_pid.get(pid, 0)
        rec = new_gate.get(pid, {})
        chartered_passed = any(
            g["gate_id"] == "chartered" and g["passed"] for g in rec.get("gates", [])
        )
        if chartered_passed:
            now_passing += 1
        log("  " + pid + ": +" + str(n) + " docs, chartered="
            + ("pass" if chartered_passed else "fail"))

    log("deepen_near_misses: " + str(now_passing) + " of " + str(len(targets))
        + " near-misses now pass chartered; " + str(query_count) + " queries")


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


def _is_review_incomplete(rec: Optional[dict]) -> bool:
    """True when the adversarial second pass errored or returned nothing
    parseable -- layers.adversarial.critique's "REVIEW INCOMPLETE" findings."""
    if not rec:
        return False
    return any(
        "REVIEW INCOMPLETE" in str(f)
        for f in (rec.get("adversarial_findings") or [])
    )


def _final_tier(pid: str, gate_out: dict, adv: dict) -> str:
    rec = adv.get(pid)
    # 2026-09-11 adversarial-audit fix (item 6): a card that only ever had
    # ONE reviewer (the second pass errored or returned nothing parseable)
    # must never ship at the confidence of a card that had two. Capped at
    # tier C regardless of what the first pass's own tier was.
    if _is_review_incomplete(rec):
        return "C"
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

    Also computes and returns `out["held_back"][role_id]` -- a list of
    {"person_id", "reason"} records for people who passed every hard gate but
    are withheld for a reason short of exclusion (currently: no named
    employer). 2026-09-11: this used to be smuggled into `overflow` under a
    synthetic key `role_id + ":no_employer"` -- a key that is not a real role
    id. Two things read delivery.json's keys as if every key were a role id:
    the renderer's per-role lookup (harmless, since it only reads real role
    ids) and the acceptance suite's enrichment check, which iterated ALL of
    delivery.json's top-level values including that synthetic key, so a
    held-back person's id ended up compared against contact.json as if they
    were a delivered candidate. `out["overflow"]` and `out["held_back"]` are
    now the only non-role keys, and both are dicts keyed by the real role id,
    never by a role id with a suffix appended.
    """
    gate_out = load("gate")
    adv = load("adversarial") if done("adversarial") else {}
    persons, by_person, _ = _persons_and_claims()
    order = {"A": 0, "B": 1, "C": 2}
    out: dict[str, list[str]] = {}
    overflow: dict[str, list[str]] = {}
    held_back: dict[str, list[dict[str, str]]] = {}
    for role_id, spec in ((ROLE1.role_id, ROLE1), (ROLE2.role_id, ROLE2)):
        rows = []
        for pid, g in gate_out.items():
            if g["role_id"] != role_id or g["tier"] == "EXCLUDED" or g["client_side"]:
                continue
            t = _final_tier(pid, gate_out, adv)
            if t == "EXCLUDED":
                continue
            # 2026-09-11: a card with no named employer failed the acceptance
            # gate ("every candidate has a named employer") after passing every
            # hard gate. Held back by name, never silently -- recorded under
            # out["held_back"][role_id], never as an extra key inside
            # `overflow` or at the top level of `out` (see docstring above).
            if not (persons.get(pid) and (persons[pid].current_employer or "").strip()):
                log("delivery: " + pid + " held back: employer not captured from any source")
                held_back.setdefault(role_id, []).append(
                    {"person_id": pid,
                     "reason": "employer not captured from any source text"}
                )
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
        held_back.setdefault(role_id, [])
        if cut:
            log("delivery: " + role_id + " qualified " + str(len(ranked))
                + " but target_count is " + str(spec.target_count) + " -- "
                + str(len(cut)) + " cut: " + ", ".join(cut))
    out["overflow"] = overflow
    out["held_back"] = held_back
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
            # Fourth audit 2026-09-11 (Alcaras): the person's own cited
            # source was already a linkedin.com/in/ profile, yet the card
            # offered a search URL. Take the cited profile first.
            for did in persons[pid].doc_ids or []:
                d = corpus.get(did)
                u = str(d.url) if d is not None else ""
                if re.search(r"linkedin\.com/in/[^/?#\s]+", u):
                    rec_d["linkedin_url"] = u.split("?")[0]
                    log("    LinkedIn from cited source: " + rec_d["linkedin_url"])
                    break
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
            with lock:
                out[pid] = {"dropped": "opted out"}
            return
        try:
            seq = messages.draft(persons[pid], by_person.get(pid, []), spec)
        except Exception as exc:
            reason = "draft generation failed: " + repr(exc)[:120]
            log("  " + pid + " draft FAILED: " + repr(exc)[:120])
            with lock:
                out[pid] = {"dropped": reason}
            return
        if seq is None:
            # 2026-09-11 second-audit fix (item 7): record why so render.py's
            # message column can show the real reason instead of implying the
            # privacy notice is not live when it is.
            log("  " + pid + " draft: model returned nothing")
            with lock:
                out[pid] = {"dropped": "model returned nothing"}
            return
        ok, problems = messages.compliance_ok(seq)
        if not ok:
            # I6 is a hard gate: a non-compliant draft is dropped, never
            # patched, because a patched legal notice is the failure mode the
            # invariant exists to prevent.
            reason = "; ".join(problems)
            log("  " + pid + " draft dropped, compliance: " + reason)
            with lock:
                out[pid] = {"dropped": reason}
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
            "held_back": [
                (persons[h["person_id"]].full_name if h["person_id"] in persons
                 else h["person_id"]) + " -- " + h["reason"]
                for h in (delivery.get("held_back", {}) or {}).get(role_id, [])
            ],
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
                "current_employer": persons[pid].current_employer,
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
    out_dir = CONFIG.deliverables_dir / "console"
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
    "harvest_discovery": stage_harvest_discovery,
    "extract": stage_extract,
    "locate": stage_locate,
    "identity_hygiene": stage_identity_hygiene,
    "validate": stage_validate,
    "gate": stage_gate,
    "deepen_r1": stage_deepen_r1,
    "deepen_near_misses": stage_deepen_near_misses,
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
    accept_senior_titles = getattr(args, "accept_senior_titles", None)
    accept_senior_titles_role2 = getattr(args, "accept_senior_titles_role2", None)
    touched = any([
        args.max_grade, args.max_years is not None, args.min_years is not None,
        args.counties is not None, args.strict_location, args.lenient_location,
        accept_senior_titles is not None, accept_senior_titles_role2 is not None,
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
                # 2026-09-11 adversarial-audit fix (item 5): the blanket
                # --accept-senior-titles flag used to apply to BOTH roles
                # unconditionally, which silently gave Role 2 (deliberately
                # strict -- accept_titles_for_floor=[] in roles.py, because
                # witness statements state years explicitly) the same
                # title-floor override as Role 1. It now applies only to a
                # role that ALREADY carries a non-empty accept_titles_for_
                # floor of its own -- Role 1 -- and Role 2 needs the
                # explicit, separate --accept-senior-titles-role2 opt-in.
                if accept_senior_titles is True and gate.params.get("accept_titles_for_floor"):
                    gate.params["accept_titles_for_floor"] = list(
                        ACCEPT_TITLES_FOR_FLOOR_DEFAULT
                    )
                elif accept_senior_titles is False:
                    gate.params["accept_titles_for_floor"] = []
                if spec is ROLE2 and accept_senior_titles_role2 is True:
                    gate.params["accept_titles_for_floor"] = list(
                        ACCEPT_TITLES_FOR_FLOOR_DEFAULT
                    )
                elif spec is ROLE2 and accept_senior_titles_role2 is False:
                    gate.params["accept_titles_for_floor"] = []
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
        help="force a provider plan (free/hybrid/openrouter/anthropic/anthropic_budget/budget) "
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
    ap.add_argument(
        "--accept-senior-titles", action=argparse.BooleanOptionalAction, default=None,
        help="override the seniority FLOOR gate's accept_titles_for_floor "
             "for any role that ALREADY carries a non-empty list of its own "
             "(Role 1) -- --accept-senior-titles sets it to "
             + repr(ACCEPT_TITLES_FOR_FLOOR_DEFAULT) + " (pass with a note "
             "when no years figure is stated but the title itself names the "
             "target grade, e.g. 'Senior Structural Engineer'); "
             "--no-accept-senior-titles clears it back to [] for every role "
             "(strict). 2026-09-11: no longer applies to Role 2, which never "
             "opts in on its own -- use --accept-senior-titles-role2 for an "
             "explicit, separate opt-in there. Omit to leave each role's own "
             "roles.py default untouched.",
    )
    ap.add_argument(
        "--accept-senior-titles-role2", action=argparse.BooleanOptionalAction, default=None,
        help="explicit, Role-2-only opt-in/out for the seniority FLOOR "
             "gate's title-based acceptance (2026-09-11: split out from "
             "--accept-senior-titles, which never applies to Role 2 on its "
             "own -- see that flag's help). --accept-senior-titles-role2 "
             "sets Role 2's accept_titles_for_floor to "
             + repr(ACCEPT_TITLES_FOR_FLOOR_DEFAULT) + "; "
             "--no-accept-senior-titles-role2 clears it back to [] (the "
             "default). Omit to leave Role 2 untouched by this flag.",
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
             "missing key/library re-fetches them; an EMPTY string ('') purges "
             "only entries with no explicit error at all -- i.e. a rendered/"
             "fetched 404 or other non-200 status, the shape a guessed team-page "
             "path leaves behind -- and never touches empty_after_parse or any "
             "other named error unless you pass that substring explicitly; "
             "prints the count and exits",
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
    ap.add_argument(
        "--deepen-gates", default=None,
        help="comma-separated gate ids stage_deepen_near_misses may target "
             "(overrides CONFIG.deepen_gates for this run). located_ie is "
             "honoured only for search-snippet persons -- a directory "
             "person's residence miss is a real exclusion, not an evidence "
             "gap.",
    )
    args = ap.parse_args()

    if args.deepen_gates:
        CONFIG.deepen_gates = [
            g.strip() for g in args.deepen_gates.split(",") if g.strip()
        ]

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
            error = str(meta.get("error") or "")
            if needle:
                if needle not in error:
                    continue
            elif error:
                # Empty needle purges only entries with NO explicit error --
                # a rendered/fetched non-200 (the 108 guessed team-page 404s
                # this flag was added for). empty_after_parse and other named
                # errors are left alone unless the operator names them.
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
