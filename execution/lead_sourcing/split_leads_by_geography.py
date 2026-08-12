"""
description: Split a scraped-leads CSV into per-geography files and inject a personalization line column.
inputs:
  CLI: --src <csv_path> (required), --out-dir <dir> (required),
       --country-col <name> (default "Country"), --anchor-col <name> (default "Seniority"),
       --line-col <name> (default "Personal Line"), --prefix <str> (default "leads_"),
       --include-unmatched, --out-encoding <enc> (default utf-8-sig), --quiet
  env: none
outputs:
  files:  <out-dir>/<prefix><bucket>.csv, one per geography bucket that has >=1 row
  stdout: per-bucket row counts, a dropped-country summary, and a reconciliation line

Notes:
  - NEVER attach the source CSV to a Claude conversation. Pass its PATH via --src.
    A 2.3 MB lead CSV tokenizes at roughly 2.3 chars/token (emails, URLs, commas) and
    consumes ~1M tokens as an attachment, which hard-fails the request before any work
    starts. See ~/.claude/rules/no-large-file-attachments.md (Exhibit A is this script).
  - Source is read with encoding="utf-8-sig" so a BOM'd export (Apollo, Excel "Save As
    CSV UTF-8") does not corrupt the first header name and break column lookup.
  - Output defaults to utf-8-sig so Excel renders accented European names correctly.
    Pass --out-encoding utf-8 if a downstream consumer chokes on the BOM.
  - Rows whose country matches no bucket are dropped and reported by default. Pass
    --include-unmatched to write them to <prefix>other.csv instead of dropping.
  - The run hard-fails (exit 2) if rows_in != rows_kept + rows_dropped. Silent row loss
    on a lead file is the failure this gate exists to catch.
"""

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------------------
# Geography buckets
# ---------------------------------------------------------------------------
# Exact-match on the Country column value. Add a country by adding one line.
EUROPE = {
    "Germany", "Ireland", "Netherlands", "Switzerland", "Spain", "France",
    "Austria", "Greece", "Romania", "Italy", "Poland", "Belgium", "Bulgaria",
    "Hungary", "Lithuania", "Cyprus", "Czechia", "Czech Republic", "Portugal",
    "Armenia", "Bosnia and Herzegovina", "Denmark", "Croatia", "Turkey",
    "Malta", "Norway", "Sweden", "Finland", "Slovakia", "Slovenia",
    "Estonia", "Latvia", "Luxembourg", "Iceland", "Serbia", "Ukraine",
}

SINGLE_COUNTRY_BUCKETS = {
    "United States": "us",
    "United Kingdom": "uk",
    "Australia": "australia",
    "Singapore": "singapore",
}

# ---------------------------------------------------------------------------
# Company-name cleanup (used to build a natural-reading personalization line)
# ---------------------------------------------------------------------------
# Longest-first so "Pty Ltd" strips before "Ltd", "L.L.C." before "LLC", etc.
LEGAL_SUFFIXES = [
    "Pty Ltd", "Pte Ltd", "Corporation", "L.L.C.", "Ltd.", "Inc.",
    "B.V.", "S.A.", "& Co. KGaA", "& Co. KG", "& Co", "Co.", "KGaA", "KG",
    "Limited", "SARL", "GmbH",
    "PLC", "LLP", "LLC", "Ltd", "Inc", "Corp", "BV", "SA", "AB", "AS", "Oy",
]
_SUFFIX_RE = re.compile(
    r"(?:[\s,]+(?:" + "|".join(re.escape(s) for s in LEGAL_SUFFIXES) + r"))+\s*[\.,]?\s*$",
    re.IGNORECASE,
)
_DASH_TAGLINE_RE = re.compile(r"\s+[-–—]\s+.*$")   # " - Tagline", " – Tagline", " — Tagline"
_TIGHT_DASH_TAGLINE_RE = re.compile(r"[-–—]\s+.*$")  # "Ltd- Tagline" once "Ltd" is gone
_TRAILING_PAREN_RE = re.compile(r"\s*\([^()]*\)\s*$")


def strip_legal_suffix(name: str) -> str:
    """Reduce a scraped company name to the plain name a human would say out loud.

    "Wiser Partners, LLC (a ZRG Company)" -> "Wiser Partners"
    "Kingston Barnes | B Corp"            -> "Kingston Barnes"
    "Acme Ltd - We Hire Better"           -> "Acme"

    Loops to fixpoint so stacked forms ("Foo Inc, LLC") collapse fully.
    """
    head = (name or "").split("|", 1)[0]
    head = _DASH_TAGLINE_RE.sub("", head)
    prev = None
    cur = head.strip()
    while cur != prev:
        prev = cur
        cur = _TRAILING_PAREN_RE.sub("", cur)
        cur = _SUFFIX_RE.sub("", cur).rstrip(" ,.")
        cur = _TIGHT_DASH_TAGLINE_RE.sub("", cur).rstrip(" ,.")
    return cur


def bucket_for(country: str) -> str | None:
    """Map a Country cell to a bucket slug, or None if it matches nothing."""
    c = (country or "").strip()
    if c in SINGLE_COUNTRY_BUCKETS:
        return SINGLE_COUNTRY_BUCKETS[c]
    if c in EUROPE:
        return "europe"
    return None


def personal_line(first: str, title: str, company: str, industry: str) -> str:
    """Build the first-touch opener that gets injected as a new column."""
    return (
        f"Hey {(first or '').strip()}, excited to see your work as the "
        f"{(title or '').strip()} at {strip_legal_suffix(company)}, "
        f"love what you are doing in {(industry or '').strip()}."
    )


def _require_columns(header: list[str], wanted: dict[str, str]) -> dict[str, int]:
    """Resolve column names to indices, failing with a readable message.

    `header.index()` raises a bare ValueError naming only the missing column, which is
    useless when a vendor silently renames a field. This lists what IS present.
    """
    idx: dict[str, int] = {}
    missing: list[str] = []
    for key, col in wanted.items():
        if col in header:
            idx[key] = header.index(col)
        else:
            missing.append(col)
    if missing:
        print(f"ERROR: source CSV is missing required column(s): {missing}", file=sys.stderr)
        print(f"       columns present ({len(header)}): {header}", file=sys.stderr)
        print("       override names with --country-col / --anchor-col if the export renamed them.",
              file=sys.stderr)
        sys.exit(2)
    return idx


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Split a scraped-leads CSV by country into per-geography CSVs.",
    )
    ap.add_argument("--src", required=True, type=Path,
                    help="Path to the source leads CSV. Pass the PATH, never attach the file.")
    ap.add_argument("--out-dir", required=True, type=Path,
                    help="Directory to write per-geography CSVs into (created if absent).")
    ap.add_argument("--country-col", default="Country", help='Country column name (default "Country")')
    ap.add_argument("--anchor-col", default="Seniority",
                    help='Insert the personalization column immediately after this column (default "Seniority")')
    ap.add_argument("--line-col", default="Personal Line", help='Name of the injected column')
    ap.add_argument("--prefix", default="leads_", help='Output filename prefix (default "leads_")')
    ap.add_argument("--include-unmatched", action="store_true",
                    help="Write unmatched-country rows to <prefix>other.csv instead of dropping them")
    ap.add_argument("--out-encoding", default="utf-8-sig",
                    help="Output encoding (default utf-8-sig, so Excel renders accents correctly)")
    ap.add_argument("--quiet", action="store_true", help="Suppress the dropped-country breakdown")
    args = ap.parse_args()

    if not args.src.is_file():
        print(f"ERROR: source CSV not found: {args.src}", file=sys.stderr)
        return 2
    args.out_dir.mkdir(parents=True, exist_ok=True)

    # utf-8-sig transparently strips a BOM if present and behaves as utf-8 if not.
    with args.src.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            print(f"ERROR: source CSV is empty: {args.src}", file=sys.stderr)
            return 2

        idx = _require_columns(header, {
            "anchor": args.anchor_col,
            "first": "First Name",
            "title": "Title",
            "company": "Company Name",
            "industry": "Industry",
            "country": args.country_col,
        })
        anchor = idx["anchor"]
        new_header = header[:anchor + 1] + [args.line_col] + header[anchor + 1:]

        buckets: dict[str, list[list[str]]] = {}
        dropped_countries: Counter[str] = Counter()
        rows_in = 0

        for row in reader:
            rows_in += 1
            # Pad short rows so index lookups never raise on a ragged export.
            if len(row) < len(header):
                row = row + [""] * (len(header) - len(row))
            slug = bucket_for(row[idx["country"]])
            if slug is None:
                dropped_countries[(row[idx["country"]] or "").strip() or "<blank>"] += 1
                if not args.include_unmatched:
                    continue
                slug = "other"
            line = personal_line(
                row[idx["first"]], row[idx["title"]],
                row[idx["company"]], row[idx["industry"]],
            )
            buckets.setdefault(slug, []).append(row[:anchor + 1] + [line] + row[anchor + 1:])

    rows_kept = sum(len(r) for r in buckets.values())
    rows_dropped = 0 if args.include_unmatched else sum(dropped_countries.values())

    for slug in sorted(buckets):
        out = args.out_dir / f"{args.prefix}{slug}.csv"
        with out.open("w", encoding=args.out_encoding, newline="") as f:
            w = csv.writer(f)
            w.writerow(new_header)
            w.writerows(buckets[slug])
        print(f"{slug:12s} {len(buckets[slug]):5d} rows -> {out}")

    if dropped_countries and not args.quiet:
        verb = "routed to 'other'" if args.include_unmatched else "DROPPED"
        print(f"\n{sum(dropped_countries.values())} rows {verb} (country matched no bucket):")
        for country, n in dropped_countries.most_common():
            print(f"  {n:5d}  {country!r}")
        if not args.include_unmatched:
            print("  -> add these to EUROPE/SINGLE_COUNTRY_BUCKETS, or re-run with --include-unmatched")

    # Reconciliation gate: every input row must be accounted for exactly once.
    print(f"\nreconciliation: {rows_in} in = {rows_kept} kept + {rows_dropped} dropped")
    if rows_in != rows_kept + rows_dropped:
        print(f"FAIL: row accounting mismatch - {rows_in} in vs "
              f"{rows_kept + rows_dropped} accounted for. Output is NOT trustworthy.",
              file=sys.stderr)
        return 2
    print("OK: no rows lost.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
