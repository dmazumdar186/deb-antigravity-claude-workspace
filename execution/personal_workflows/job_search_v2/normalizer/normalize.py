"""
description: SourceJob -> NormalizedJob mapper. One pure function per source.
inputs: list[SourceJob]
outputs: list[NormalizedJob] with content_hash + canonical_url filled in.

This module is the boundary between "what the source gave us" and "what the rest
of the pipeline operates on." Adding a new source = adding one mapper here.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent))

from execution.personal_workflows.job_search_v2.contracts import (  # noqa: E402
    ContractType,
    NormalizedJob,
    RemoteMode,
    SourceJob,
    canonicalize_url,
    compute_content_hash,
)


_PARIS_RE = re.compile(r"\bparis\b", re.IGNORECASE)
_IDF_RE = re.compile(r"\bile[- ]?de[- ]?france\b|\b(?:75|77|78|91|92|93|94|95)\d{3}\b", re.IGNORECASE)


def _normalize_location(raw: str) -> str:
    if not raw:
        return "Unknown"
    if _PARIS_RE.search(raw):
        return "Paris"
    if _IDF_RE.search(raw):
        return "Île-de-France"
    return raw.strip()


def _normalize_contract(raw: str) -> ContractType:
    s = (raw or "").strip().lower()
    if not s:
        return ContractType.UNKNOWN
    if "cdi" in s or "permanent" in s or "indéterminée" in s or "indeterminee" in s or "full_time" in s or "full-time" in s:
        return ContractType.CDI
    if "cdd" in s or "fixed-term" in s or "déterminée" in s or "determinee" in s:
        return ContractType.CDD
    if "freelance" in s or "indep" in s or "contract" in s or "mission" in s:
        return ContractType.FREELANCE
    if "stage" in s or "intern" in s or "alternance" in s:
        return ContractType.INTERNSHIP
    return ContractType.UNKNOWN


def _detect_remote(location_raw: str, description_snippet: str) -> RemoteMode:
    s = f"{location_raw} {description_snippet}".lower()
    if "full remote" in s or "100% remote" in s or "télétravail total" in s or "télétravail complet" in s:
        return RemoteMode.REMOTE
    if "hybrid" in s or "hybride" in s or "télétravail partiel" in s:
        return RemoteMode.HYBRID
    if "on site" in s or "on-site" in s or "présentiel" in s:
        return RemoteMode.ONSITE
    if "remote" in s or "télétravail" in s:
        return RemoteMode.HYBRID  # default when the word appears but not qualified
    return RemoteMode.UNKNOWN


def to_normalized(src: SourceJob) -> NormalizedJob:
    canonical = canonicalize_url(str(src.url))
    return NormalizedJob(
        source=src.source,
        source_id=src.source_id,
        url=src.url,
        canonical_url=canonical,
        title=src.title,
        company=src.company,
        location=_normalize_location(src.location_raw),
        description_snippet=src.description_snippet,
        posted_at=src.posted_at,
        contract_type=_normalize_contract(src.contract_type_raw),
        remote_mode=_detect_remote(src.location_raw, src.description_snippet),
        fetched_at=src.fetched_at,
        content_hash=compute_content_hash(src.title, src.company, canonical),
    )


def batch_normalize(jobs: list[SourceJob]) -> list[NormalizedJob]:
    """Map a batch of SourceJobs to NormalizedJobs. Merges in-batch cross-source dupes
    via content_hash, populating `also_seen_on` on the surviving job.
    """
    by_hash: dict[str, NormalizedJob] = {}
    for src in jobs:
        nj = to_normalized(src)
        if nj.content_hash in by_hash:
            existing = by_hash[nj.content_hash]
            if nj.source != existing.source and nj.source not in existing.also_seen_on:
                merged = existing.model_copy(update={"also_seen_on": [*existing.also_seen_on, nj.source]})
                by_hash[nj.content_hash] = merged
        else:
            by_hash[nj.content_hash] = nj
    return list(by_hash.values())


def main() -> int:
    """CLI: read SourceJob JSONL from stdin, write NormalizedJob JSONL to stdout."""
    import json

    src_jobs: list[SourceJob] = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            src_jobs.append(SourceJob.model_validate_json(line))
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"normalize: skip line (parse error): {exc}", file=sys.stderr)

    normalized = batch_normalize(src_jobs)
    for nj in normalized:
        sys.stdout.write(nj.model_dump_json() + "\n")
    print(f"normalize: {len(src_jobs)} src → {len(normalized)} normalized (in-run dedup applied)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
