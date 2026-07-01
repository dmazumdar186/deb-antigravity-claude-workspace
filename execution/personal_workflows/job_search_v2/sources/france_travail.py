"""
description: France Travail "Offres d'emploi v2" official REST API source adapter.
inputs:
  - env: FRANCE_TRAVAIL_CLIENT_ID, FRANCE_TRAVAIL_CLIENT_SECRET (OAuth2 client_credentials)
  - CLI: --query (default: "product manager"), --location (INSEE code or label, default: "Paris"),
         --max-pages (default: 3), --posted-within-days (default: 1), --fixture (offline mode)
outputs:
  - stdout: JSON-lines of SourceJob records (one per line)
  - .tmp/job_search_v2/france_travail_<run_id>.jsonl (also written for the orchestrator)

Endpoints (per https://francetravail.io docs, "Offres d'emploi v2"):
  - Token: POST https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire
  - Search: GET https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search
  - Scope: api_offresdemploiv2 o2dsoffre

Free tier rate limit at time of writing: generous (single-digit requests/sec).
We self-throttle to 1 req/sec to stay polite.

Anti-bot posture: none. This is a government API with proper credentials.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv, find_dotenv

# Local import — works when run as `py execution/personal_workflows/job_search_v2/sources/france_travail.py`
# or as `python -m execution.personal_workflows.job_search_v2.sources.france_travail`.
_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent))  # workspace root

from execution.personal_workflows.job_search_v2.contracts import JobSource, SourceJob  # noqa: E402

load_dotenv(find_dotenv(usecwd=False))
logger = logging.getLogger("france_travail")

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
TOKEN_REALM = "/partenaire"
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
SCOPE = "api_offresdemploiv2 o2dsoffre"

PROJECT_ROOT = Path(__file__).resolve().parents[4]  # workspace root
TMP_DIR = PROJECT_ROOT / ".tmp" / "job_search_v2"


class FranceTravailAuthError(RuntimeError):
    """Raised when OAuth2 credentials are missing or rejected."""


def _get_credentials() -> tuple[str, str]:
    client_id = os.environ.get("FRANCE_TRAVAIL_CLIENT_ID", "").strip()
    client_secret = os.environ.get("FRANCE_TRAVAIL_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise FranceTravailAuthError(
            "FRANCE_TRAVAIL_CLIENT_ID and FRANCE_TRAVAIL_CLIENT_SECRET must be set in .env. "
            "Register at https://francetravail.io → create app → subscribe to 'Offres d'emploi v2'."
        )
    return client_id, client_secret


def _get_access_token(client: httpx.Client) -> str:
    client_id, client_secret = _get_credentials()
    r = client.post(
        TOKEN_URL,
        params={"realm": TOKEN_REALM},
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": SCOPE,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15.0,
    )
    if r.status_code != 200:
        # 2026-07-01 security audit: prior form echoed r.text[:200] into
        # the exception, which propagated to run.py's logger.error with
        # exc_info=True — surfacing OAuth error bodies (potentially with
        # partial credential echo) into GitHub Actions run logs readable by
        # any repo collaborator. Log only the status code; write the full
        # body to .tmp/ if a human wants to forensically inspect it.
        try:
            from pathlib import Path as _P
            _P(".tmp/job_search_v2").mkdir(parents=True, exist_ok=True)
            _P(".tmp/job_search_v2/ft_auth_error.txt").write_text(
                r.text[:2000], encoding="utf-8"
            )
        except OSError:
            pass  # best-effort forensic dump
        raise FranceTravailAuthError(
            f"Token endpoint returned {r.status_code} "
            f"(body redacted from log; see .tmp/job_search_v2/ft_auth_error.txt)"
        )
    body = r.json()
    token = body.get("access_token")
    if not token:
        raise FranceTravailAuthError(f"Token endpoint returned no access_token: {body}")
    return token


def _parse_offer(offer: dict) -> SourceJob | None:
    """Map one France Travail API offer dict → SourceJob. Returns None on parse failure."""
    try:
        offer_id = str(offer["id"])
        title = offer.get("intitule") or ""
        company = (offer.get("entreprise") or {}).get("nom") or "Confidential"

        # Lieu de travail: dict {libelle, latitude, longitude, codepostal, commune}.
        lieu = offer.get("lieuTravail") or {}
        location_raw = lieu.get("libelle") or ""

        description = (offer.get("description") or "")[:2000]
        contract_raw = offer.get("typeContratLibelle") or offer.get("typeContrat") or ""
        posted_str = offer.get("dateCreation") or offer.get("dateActualisation") or ""
        posted_at = None
        if posted_str:
            try:
                # FT timestamps are ISO 8601 with a Z or offset; let fromisoformat handle Z separately.
                posted_at = datetime.fromisoformat(posted_str.replace("Z", "+00:00"))
            except ValueError:
                posted_at = None

        # Public URL: FT API offers an 'origineOffre.urlOrigine' or we construct the FT-hosted one.
        origine = offer.get("origineOffre") or {}
        url = origine.get("urlOrigine") or f"https://candidat.francetravail.fr/offres/recherche/detail/{offer_id}"

        return SourceJob(
            source=JobSource.FRANCE_TRAVAIL,
            source_id=offer_id,
            url=url,
            title=title,
            company=company,
            location_raw=location_raw,
            description_snippet=description,
            posted_at=posted_at,
            contract_type_raw=contract_raw,
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("france_travail: skip offer (parse error): %s", exc)
        return None


def fetch(
    query: str = "product manager",
    location: str = "Paris",
    max_pages: int = 3,
    posted_within_days: int = 1,
    page_size: int = 50,
    polite_delay_s: float = 1.0,
) -> list[SourceJob]:
    """Hit the France Travail search API and return list[SourceJob].

    Pagination: France Travail uses a `range=start-end` header param. We page
    in chunks of `page_size` up to `max_pages` pages.

    Date filter: `minCreationDate` ISO 8601, set to now - posted_within_days.

    Failure modes:
    - Bad creds → FranceTravailAuthError (caller decides what to do).
    - 429 → log + return what we have so far (do NOT retry blindly).
    - Other 5xx → log + return what we have so far.
    """
    now_utc = datetime.now(timezone.utc)
    # France Travail v2 requires minCreationDate + maxCreationDate as a pair.
    since = (now_utc - timedelta(days=posted_within_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    until = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    jobs: list[SourceJob] = []

    with httpx.Client(timeout=20.0) as client:
        token = _get_access_token(client)
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

        for page_num in range(max_pages):
            start = page_num * page_size
            end = start + page_size - 1
            params = {
                "motsCles": query,
                "commune": location if location.isdigit() else None,  # INSEE code if digits
                "departement": "75" if location.lower() == "paris" else None,  # 75 = Paris dept
                "range": f"{start}-{end}",
                "minCreationDate": since,
                "maxCreationDate": until,  # FT v2 requires min+max as a pair
            }
            params = {k: v for k, v in params.items() if v is not None}

            try:
                r = client.get(SEARCH_URL, params=params, headers=headers)
            except httpx.HTTPError as exc:
                logger.warning("france_travail: HTTP error on page %d: %s — stopping pagination", page_num, exc)
                break

            if r.status_code == 204:
                logger.info("france_travail: 204 No Content on page %d — end of results", page_num)
                break
            if r.status_code == 429:
                logger.warning("france_travail: 429 rate-limited on page %d — stopping (returning %d so far)", page_num, len(jobs))
                break
            if r.status_code >= 500:
                logger.warning("france_travail: %d on page %d — stopping (returning %d so far)", r.status_code, page_num, len(jobs))
                break
            if r.status_code not in (200, 206):
                logger.warning("france_travail: unexpected %d on page %d: %s", r.status_code, page_num, r.text[:200])
                break

            body = r.json()
            offers = body.get("resultats") or []
            if not offers:
                logger.info("france_travail: empty resultats on page %d — end of results", page_num)
                break

            for offer in offers:
                parsed = _parse_offer(offer)
                if parsed is not None:
                    jobs.append(parsed)

            if len(offers) < page_size:
                break  # last page

            time.sleep(polite_delay_s)

    return jobs


def fetch_from_fixture(fixture_path: Path) -> list[SourceJob]:
    """Offline mode: read recorded API response from a fixture JSON file.

    Used by the front-door synthetic and by tests so we never burn live API calls
    in CI. Fixture shape: the raw `resultats` array from the FT API response.
    """
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    offers = raw.get("resultats") if isinstance(raw, dict) else raw
    jobs: list[SourceJob] = []
    for offer in offers or []:
        parsed = _parse_offer(offer)
        if parsed is not None:
            jobs.append(parsed)
    return jobs


def _write_jsonl(jobs: list[SourceJob], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for job in jobs:
            f.write(job.model_dump_json() + "\n")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="France Travail Offres d'emploi v2 source adapter.")
    parser.add_argument("--query", default="product manager")
    parser.add_argument("--location", default="Paris", help="INSEE commune code (digits) or 'Paris'.")
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--posted-within-days", type=int, default=1)
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--fixture", type=Path, help="Read from this JSON fixture instead of live API (offline mode).")
    parser.add_argument("--out", type=Path, default=None, help="Output JSONL path (default: .tmp/job_search_v2/france_travail_<run_id>.jsonl)")
    args = parser.parse_args()

    if args.fixture:
        jobs = fetch_from_fixture(args.fixture)
        logger.info("france_travail: %d jobs from fixture %s", len(jobs), args.fixture)
    else:
        try:
            jobs = fetch(
                query=args.query,
                location=args.location,
                max_pages=args.max_pages,
                posted_within_days=args.posted_within_days,
                page_size=args.page_size,
            )
        except FranceTravailAuthError as exc:
            logger.error("france_travail: auth failure — %s", exc)
            return 2

    run_id = uuid.uuid4().hex[:8]
    out_path = args.out or (TMP_DIR / f"france_travail_{run_id}.jsonl")
    _write_jsonl(jobs, out_path)
    logger.info("france_travail: wrote %d jobs to %s", len(jobs), out_path)

    for job in jobs:
        sys.stdout.write(job.model_dump_json() + "\n")
    return 0 if jobs else 1


if __name__ == "__main__":
    sys.exit(main())
