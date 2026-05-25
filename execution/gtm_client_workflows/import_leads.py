#!/usr/bin/env python3
"""
import_leads.py
description: Flexible CSV lead importer for the Accessory Masters pipeline.
             Auto-detects or manually maps CSV columns to the internal lead format,
             validates rows, outputs JSON, and optionally uploads to Instantly.
inputs: --csv (required), --mapping, --config, --upload, --mock, --output
outputs: .tmp/imported_leads.json (default), optional Instantly upload
usage:
    py execution/gtm_client_workflows/import_leads.py --csv leads.csv --mock
    py execution/gtm_client_workflows/import_leads.py --csv leads.csv --mapping "email=Email Address,name=Contact Name"
    py execution/gtm_client_workflows/import_leads.py --csv leads.csv --upload
"""

import argparse
import csv
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "execution"))

from modules.pipeline_utils import load_config, save_leads, setup_logging  # noqa: E402

logger = setup_logging("import_leads", log_dir=ROOT / ".tmp")

TMP = ROOT / ".tmp"

# ---------------------------------------------------------------------------
# Column auto-detection maps
# ---------------------------------------------------------------------------

# Each internal field maps to a list of common CSV header variations (lowercase).
AUTO_DETECT_MAP: dict[str, list[str]] = {
    "owner_email": [
        "email", "owner_email", "contact_email", "e-mail", "email_address",
        "email address",
    ],
    "owner_name": [
        "name", "owner_name", "contact_name", "full_name", "full name",
        "contact name", "owner name",
    ],
    "business_name": [
        "company", "business_name", "company_name", "business name",
        "company name", "business",
    ],
    "phone": [
        "phone", "phone_number", "phone number", "telephone", "tel",
    ],
    "industry": [
        "industry", "type", "category", "business_type", "business type",
    ],
    "city": ["city"],
    "state": ["state", "st"],
}

# Separate detection for first/last name columns (used to build owner_name).
FIRST_NAME_HEADERS = ["first_name", "first name", "firstname", "first"]
LAST_NAME_HEADERS = ["last_name", "last name", "lastname", "last"]

EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


# ---------------------------------------------------------------------------
# Column mapping
# ---------------------------------------------------------------------------

def _normalize_header(h: str) -> str:
    """Lowercase and strip a header for comparison."""
    return h.strip().lower()


def auto_detect_columns(headers: list[str]) -> dict[str, str]:
    """Map internal field names to actual CSV column names via fuzzy matching.

    Returns a dict like {"owner_email": "Email Address", ...} using the
    *original* CSV header casing as values.
    """
    mapping: dict[str, str] = {}
    norm_to_orig = {_normalize_header(h): h for h in headers}

    for field, candidates in AUTO_DETECT_MAP.items():
        for candidate in candidates:
            if candidate in norm_to_orig:
                mapping[field] = norm_to_orig[candidate]
                break

    # Handle first_name + last_name -> owner_name fallback
    if "owner_name" not in mapping:
        first_col = None
        last_col = None
        for fn in FIRST_NAME_HEADERS:
            if fn in norm_to_orig:
                first_col = norm_to_orig[fn]
                break
        for ln in LAST_NAME_HEADERS:
            if ln in norm_to_orig:
                last_col = norm_to_orig[ln]
                break
        if first_col:
            mapping["_first_name"] = first_col
            if last_col:
                mapping["_last_name"] = last_col

    return mapping


def parse_manual_mapping(mapping_str: str) -> dict[str, str]:
    """Parse a --mapping string like 'email=Email Address,name=Contact Name'.

    Shorthand keys are expanded to internal field names:
        email -> owner_email, name -> owner_name, company -> business_name
    """
    shorthand = {
        "email": "owner_email",
        "name": "owner_name",
        "company": "business_name",
    }
    result: dict[str, str] = {}
    for pair in mapping_str.split(","):
        pair = pair.strip()
        if "=" not in pair:
            logger.warning("Ignoring malformed mapping pair: %r", pair)
            continue
        key, value = pair.split("=", 1)
        key = key.strip()
        value = value.strip()
        internal = shorthand.get(key, key)
        result[internal] = value
    return result


# ---------------------------------------------------------------------------
# Row conversion & validation
# ---------------------------------------------------------------------------

def _build_lead(row: dict, col_map: dict[str, str]) -> dict:
    """Convert a single CSV row dict into the internal lead format."""
    lead: dict[str, str] = {
        "business_name": "",
        "owner_name": "",
        "owner_email": "",
        "phone": "",
        "industry": "",
        "city": "",
        "state": "",
        "source": "csv_import",
        "personalized_opener": "",
    }

    for field in ("owner_email", "business_name", "phone", "industry", "city", "state"):
        csv_col = col_map.get(field)
        if csv_col and csv_col in row:
            lead[field] = (row[csv_col] or "").strip()

    # Owner name — either direct column or first+last combo
    name_col = col_map.get("owner_name")
    if name_col and name_col in row:
        lead["owner_name"] = (row[name_col] or "").strip()
    else:
        first = ""
        last = ""
        fc = col_map.get("_first_name")
        lc = col_map.get("_last_name")
        if fc and fc in row:
            first = (row[fc] or "").strip()
        if lc and lc in row:
            last = (row[lc] or "").strip()
        if first or last:
            lead["owner_name"] = f"{first} {last}".strip()

    return lead


def validate_lead(lead: dict, row_num: int) -> str | None:
    """Return an error string if the lead is invalid, else None."""
    email = lead.get("owner_email", "")
    if not email:
        return f"row {row_num}: missing email"
    if not EMAIL_RE.match(email):
        return f"row {row_num}: invalid email format ({email})"
    return None


# ---------------------------------------------------------------------------
# CSV reading
# ---------------------------------------------------------------------------

def read_csv(csv_path: Path) -> tuple[list[str], list[dict]]:
    """Read a CSV and return (headers, rows). Handles BOM and common encodings."""
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with open(csv_path, newline="", encoding=encoding) as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []
                rows = list(reader)
            return headers, rows
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not decode {csv_path} with any supported encoding")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Import leads from CSV into the Accessory Masters pipeline"
    )
    parser.add_argument("--csv", required=True, help="Path to the input CSV file")
    parser.add_argument(
        "--mapping",
        default=None,
        help='Manual column mapping, e.g. "email=Email Address,name=Contact Name,company=Biz Name"',
    )
    parser.add_argument(
        "--config",
        default=str(ROOT / "config" / "accessory_masters.json"),
        help="Path to pipeline config JSON",
    )
    parser.add_argument(
        "--output",
        default=str(TMP / "imported_leads.json"),
        help="Output JSON path (default: .tmp/imported_leads.json)",
    )
    parser.add_argument("--upload", action="store_true", help="Upload imported leads to Instantly")
    parser.add_argument("--mock", action="store_true", help="Dry-run mode — no API calls")
    args = parser.parse_args()

    TMP.mkdir(parents=True, exist_ok=True)
    load_dotenv(ROOT / ".env")

    csv_path = Path(args.csv)
    if not csv_path.exists():
        logger.error("CSV file not found: %s", csv_path)
        sys.exit(1)

    # ---- Read CSV ----
    headers, rows = read_csv(csv_path)
    logger.info("Read %d rows from %s (columns: %s)", len(rows), csv_path, ", ".join(headers))

    # ---- Build column mapping ----
    if args.mapping:
        col_map = parse_manual_mapping(args.mapping)
        logger.info("Using manual mapping: %s", col_map)
    else:
        col_map = auto_detect_columns(headers)
        logger.info("Auto-detected mapping: %s", col_map)

    if "owner_email" not in col_map and "_first_name" not in col_map:
        logger.warning(
            "No email column detected. Mapped fields: %s. "
            "Use --mapping to specify columns explicitly.",
            list(col_map.keys()),
        )

    # ---- Convert & validate ----
    leads: list[dict] = []
    skipped: list[str] = []

    for i, row in enumerate(rows, start=2):  # row 1 = header
        lead = _build_lead(row, col_map)
        error = validate_lead(lead, i)
        if error:
            skipped.append(error)
            logger.debug("Skipped: %s", error)
            continue
        leads.append(lead)

    # ---- Save output ----
    output_path = Path(args.output)
    save_leads(leads, output_path)
    logger.info("Wrote %d leads to %s", len(leads), output_path)

    # ---- Log skipped rows ----
    for reason in skipped:
        logger.warning("Skipped: %s", reason)

    # ---- Upload to Instantly ----
    if args.upload:
        config = load_config(args.config)
        instantly_config = config.get("instantly", {})
        campaign_id = instantly_config.get("campaign_id")

        if not campaign_id:
            logger.error(
                "Cannot upload: instantly.campaign_id is null in %s. "
                "Set a campaign_id first.",
                args.config,
            )
            sys.exit(1)

        if args.mock:
            logger.info("MOCK: Would upload %d leads to campaign %s", len(leads), campaign_id)
        else:
            api_key = os.environ.get("INSTANTLY_API_KEY", "")
            if not api_key:
                logger.error("INSTANTLY_API_KEY not set in .env — cannot upload.")
                sys.exit(1)

            from modules.outputs.instantly import upload_leads

            api_url = instantly_config.get("api_url", "https://api.instantly.ai/api/v2")
            field_mapping = instantly_config.get("field_mapping")
            rate_limit = instantly_config.get("upload_rate_limit_delay", 1.0)

            result = upload_leads(
                api_url=api_url,
                api_key=api_key,
                campaign_id=campaign_id,
                leads=leads,
                field_mapping=field_mapping,
                rate_limit_delay=rate_limit,
            )
            logger.info(
                "Instantly upload: %d/%d succeeded",
                result["uploaded"],
                result["total"],
            )
            # Save again with upload status
            save_leads(leads, output_path)

    # ---- Summary ----
    print("\n--- Import Summary ---")
    print(f"  CSV file:   {csv_path}")
    print(f"  Total rows: {len(rows)}")
    print(f"  Imported:   {len(leads)}")
    print(f"  Skipped:    {len(skipped)}")
    print(f"  Output:     {output_path}")
    if args.upload:
        print(f"  Upload:     {'mock' if args.mock else 'live'}")


if __name__ == "__main__":
    main()
