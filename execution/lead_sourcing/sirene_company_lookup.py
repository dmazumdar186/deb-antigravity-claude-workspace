"""
description: Resolve a French company name to an INSEE SIRENE record and confirm digital-sector classification by NAF code.
inputs:
  CLI: --name <company_name> (repeatable), --output <path> (optional)
  env: INSEE_SIRENE_API_KEY (long-lived bearer token, preferred) OR
       INSEE_SIRENE_CLIENT_ID + INSEE_SIRENE_CLIENT_SECRET (OAuth2 client_credentials flow)
outputs:
  stdout: JSON list of resolution results (one dict per company name)
  file:   optional JSON file at --output path

Notes:
  - The SIRENE API (V3.11) does not reliably expose a website field; 'website' is always None.
    A downstream enrichment step (e.g. Clearbit, Firecrawl dork) should populate it.
  - Auth priority: if INSEE_SIRENE_API_KEY is present and non-empty, use it directly as a
    Bearer token. Otherwise fall back to OAuth2 client_credentials using CLIENT_ID + CLIENT_SECRET.
  - If neither auth path is configured, lookup_company() returns all-None with source='unconfigured'.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Project path bootstrap
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution.personal_workflows._jt_utils import (  # noqa: E402
    load_jt_config,
    normalize_company,
    now_iso,
    retry_with_backoff,
    save_json,
    setup_logging,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SIRENE_BASE = "https://api.insee.fr/entreprises/sirene/V3.11"
TOKEN_URL = "https://api.insee.fr/token"

logger = setup_logging("sirene_company_lookup")

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _get_static_api_key() -> str | None:
    """Return the long-lived INSEE bearer token from env, or None."""
    key = os.environ.get("INSEE_SIRENE_API_KEY", "").strip()
    return key if key else None


def _fetch_oauth_token() -> str | None:
    """Fetch a bearer token via OAuth2 client_credentials.

    Returns the access_token string, or None on failure.
    Does NOT log the raw token value.
    """
    client_id = os.environ.get("INSEE_SIRENE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("INSEE_SIRENE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return None
    try:
        resp = requests.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            timeout=15,
        )
        resp.raise_for_status()
        token = resp.json().get("access_token")
        if not token:
            logger.warning("sirene: OAuth2 token response did not contain access_token")
        return token or None
    except requests.exceptions.RequestException as exc:
        logger.warning("sirene: OAuth2 token fetch failed — %s", exc)
        return None


def _resolve_bearer_token() -> str | None:
    """Return a valid bearer token via the preferred auth path, or None."""
    token = _get_static_api_key()
    if token:
        return token
    token = _fetch_oauth_token()
    return token


def _auth_configured() -> bool:
    """Return True if at least one auth path appears to be configured."""
    has_key = bool(os.environ.get("INSEE_SIRENE_API_KEY", "").strip())
    has_oauth = bool(
        os.environ.get("INSEE_SIRENE_CLIENT_ID", "").strip()
        and os.environ.get("INSEE_SIRENE_CLIENT_SECRET", "").strip()
    )
    return has_key or has_oauth


# ---------------------------------------------------------------------------
# Null / error result factory
# ---------------------------------------------------------------------------

def _null_result(source: str = "error") -> dict:
    return {
        "siren": None,
        "naf_code": None,
        "is_digital_sector": None,
        "website": None,
        "matched_denomination": None,
        "source": source,
    }


# ---------------------------------------------------------------------------
# Core HTTP search (decorated for retry)
# ---------------------------------------------------------------------------

@retry_with_backoff(max_retries=3)
def _search_sirene(query: str, token: str) -> dict:
    """Call the SIRENE /siret endpoint and return the parsed JSON body.

    Raises requests.exceptions.HTTPError on non-2xx so retry_with_backoff can handle it.
    """
    resp = requests.get(
        f"{SIRENE_BASE}/siret",
        params={"q": query, "nombre": 5},
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Digital-sector classification
# ---------------------------------------------------------------------------

def _classify_digital(naf_code: str | None, config: dict) -> int | None:
    if naf_code is None:
        return None
    digital_list: list[str] = config.get("sirene_naf_digital", [])
    return 1 if naf_code in digital_list else 0


# ---------------------------------------------------------------------------
# Match scoring
# ---------------------------------------------------------------------------

def _pick_best_result(etablissements: list[dict], input_name: str) -> dict | None:
    """Return the single best matching etablissement dict, or None."""
    normalized_input = normalize_company(input_name)

    # Pass 1: exact normalized name match among active units
    for e in etablissements:
        ul = e.get("uniteLegale", {})
        denom = ul.get("denominationUniteLegale") or ""
        if normalize_company(denom) == normalized_input and ul.get("etatAdministratifUniteLegale") == "A":
            return e

    # Pass 2: any exact normalized match (regardless of active state)
    for e in etablissements:
        ul = e.get("uniteLegale", {})
        denom = ul.get("denominationUniteLegale") or ""
        if normalize_company(denom) == normalized_input:
            return e

    # Pass 3: first active result
    for e in etablissements:
        ul = e.get("uniteLegale", {})
        if ul.get("etatAdministratifUniteLegale") == "A":
            return e

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# In-process cache to avoid duplicate queries within one run
_cache: dict[str, dict] = {}


def lookup_company(company_name: str, config: dict | None = None) -> dict:
    """Resolve a French company name to a SIRENE record.

    Returns a dict with keys:
        siren (str|None), naf_code (str|None), is_digital_sector (int|None),
        website (str|None), matched_denomination (str|None),
        source ('sirene'|'unconfigured'|'error')
    """
    if config is None:
        try:
            config = load_jt_config()
        except Exception:
            config = {}

    if not _auth_configured():
        logger.warning(
            "sirene: no auth configured — set INSEE_SIRENE_API_KEY or "
            "INSEE_SIRENE_CLIENT_ID + INSEE_SIRENE_CLIENT_SECRET in .env"
        )
        return _null_result(source="unconfigured")

    token = _resolve_bearer_token()
    if not token:
        logger.warning("sirene: could not obtain bearer token — check auth env vars")
        return _null_result(source="unconfigured")

    def _do_lookup(query: str) -> dict | None:
        """Run a SIRENE search and return parsed body, or None on handled errors."""
        try:
            return _search_sirene(query, token)
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in (401, 403):
                logger.warning("sirene: auth failed (HTTP %s) — check INSEE_SIRENE_API_KEY", status)
                return None
            if status == 404:
                return None
            logger.warning("sirene: HTTP %s for query %r — %s", status, query, exc)
            return None
        except requests.exceptions.RequestException as exc:
            logger.warning("sirene: request failed for query %r — %s", query, exc)
            return None

    # Try exact denomination query first
    body = _do_lookup(f'denominationUniteLegale:"{company_name}"')
    etablissements = (body or {}).get("etablissements", [])

    # Fallback to simpler query if exact search returned nothing
    if not etablissements:
        logger.debug("sirene: exact query returned 0 results; trying fallback for %r", company_name)
        body = _do_lookup(company_name)
        etablissements = (body or {}).get("etablissements", [])

    if not etablissements:
        logger.info("sirene: no results found for %r", company_name)
        return _null_result(source="sirene")

    best = _pick_best_result(etablissements, company_name)
    if best is None:
        logger.info("sirene: results found but no suitable match for %r", company_name)
        return _null_result(source="sirene")

    ul = best.get("uniteLegale", {})
    siren = best.get("siren") or ul.get("siren")
    naf_code = ul.get("activitePrincipaleUniteLegale")
    matched_denomination = ul.get("denominationUniteLegale")
    is_digital = _classify_digital(naf_code, config)

    return {
        "siren": siren,
        "naf_code": naf_code,
        "is_digital_sector": is_digital,
        "website": None,  # SIRENE does not reliably expose website; enrich downstream
        "matched_denomination": matched_denomination,
        "source": "sirene",
    }


def lookup_companies(company_names: list[str], config: dict | None = None) -> dict[str, dict]:
    """Batch wrapper for lookup_company.

    Uses an in-process cache to skip duplicate queries within one run.
    Returns a dict keyed by the original input company_name string.
    """
    if config is None:
        try:
            config = load_jt_config()
        except Exception:
            config = {}

    results: dict[str, dict] = {}
    for name in company_names:
        cache_key = normalize_company(name)
        if cache_key in _cache:
            logger.debug("sirene: cache hit for %r", name)
            results[name] = _cache[cache_key]
        else:
            result = lookup_company(name, config=config)
            _cache[cache_key] = result
            results[name] = result
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resolve French company names via the INSEE SIRENE API."
    )
    parser.add_argument(
        "--name",
        dest="names",
        action="append",
        required=True,
        metavar="COMPANY_NAME",
        help="Company name to look up. Repeat --name for multiple companies.",
    )
    parser.add_argument(
        "--output",
        dest="output",
        default=None,
        metavar="PATH",
        help="Optional path to write results as JSON.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    results = lookup_companies(args.names)

    output_payload = {
        "run_at": now_iso(),
        "results": results,
    }

    json_str = json.dumps(output_payload, indent=2, ensure_ascii=False, default=str)
    print(json_str)

    if args.output:
        save_json(output_payload, Path(args.output))
        logger.info("sirene: results written to %s", args.output)


if __name__ == "__main__":
    main()
