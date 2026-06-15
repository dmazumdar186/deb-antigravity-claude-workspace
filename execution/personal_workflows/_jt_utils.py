"""
_jt_utils.py
description: Standalone utility helpers (retry, hashing, normalization, JSON I/O, logging) for the French PM/PO Job Tracker. Imported by other job-tracker modules; not run directly.
inputs: None — utility module.
outputs: N/A.
"""

import functools
import hashlib
import json
import logging
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------

def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator that retries on HTTP 429/5xx and ConnectionError with exponential backoff.

    - 429: respects Retry-After header if present; otherwise uses exponential backoff.
    - 5xx: exponential backoff (base_delay * 2^attempt).
    - ConnectionError: exponential backoff.
    - Other HTTPError: re-raised immediately without retry.
    - After exhausting retries, raises the last exception.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.HTTPError as exc:
                    status = exc.response.status_code if exc.response is not None else None
                    if status == 429:
                        retry_after = exc.response.headers.get("Retry-After") if exc.response is not None else None
                        if retry_after is not None:
                            try:
                                delay = float(retry_after)
                            except ValueError:
                                delay = base_delay * (2 ** attempt)
                        else:
                            delay = base_delay * (2 ** attempt)
                        last_exc = exc
                        if attempt < max_retries:
                            logging.warning(
                                "retry_with_backoff: 429 rate-limited on attempt %d/%d; sleeping %.1fs",
                                attempt + 1, max_retries, delay,
                            )
                            time.sleep(delay)
                            continue
                        raise
                    elif status is not None and status >= 500:
                        delay = base_delay * (2 ** attempt)
                        last_exc = exc
                        if attempt < max_retries:
                            logging.warning(
                                "retry_with_backoff: HTTP %d on attempt %d/%d; sleeping %.1fs",
                                status, attempt + 1, max_retries, delay,
                            )
                            time.sleep(delay)
                            continue
                        raise
                    else:
                        # Non-retriable HTTP error — re-raise immediately
                        raise
                except requests.exceptions.ConnectionError as exc:
                    delay = base_delay * (2 ** attempt)
                    last_exc = exc
                    if attempt < max_retries:
                        logging.warning(
                            "retry_with_backoff: ConnectionError on attempt %d/%d; sleeping %.1fs",
                            attempt + 1, max_retries, delay,
                        )
                        time.sleep(delay)
                        continue
                    raise
            # Should be unreachable, but raise last_exc for safety
            if last_exc is not None:
                raise last_exc
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging(name: str, log_path: Path | None = None) -> logging.Logger:
    """Configure and return a logger with a stream handler (INFO) and optional file handler (DEBUG).

    Guards against adding duplicate handlers if called more than once for the same logger name.
    """
    logger = logging.getLogger(name)
    # Avoid adding duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)

    if log_path is not None:
        log_path = Path(log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    return logger


# ---------------------------------------------------------------------------
# String normalization
# ---------------------------------------------------------------------------

def normalize_title(title: str) -> str:
    """NFKD-normalize, strip combining (accent) marks, lowercase, collapse whitespace."""
    nfkd = unicodedata.normalize("NFKD", title)
    stripped = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    lowered = stripped.lower()
    return re.sub(r"\s+", " ", lowered).strip()


def normalize_company(name: str) -> str:
    """Lowercase, strip leading/trailing whitespace, collapse internal whitespace,
    strip leading/trailing non-alphanumeric characters.
    Accents are preserved (company names use them as distinguishing chars).
    """
    lowered = name.lower().strip()
    collapsed = re.sub(r"\s+", " ", lowered)
    # Strip leading/trailing non-alphanumeric (handles punctuation like quotes, dashes)
    stripped = re.sub(r"^[^\w]+|[^\w]+$", "", collapsed, flags=re.UNICODE)
    return stripped


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def compute_job_hash(company_normalized: str, title_normalized: str, location) -> str:
    """SHA-1 hexdigest of '{company_normalized}|{title_normalized}|{location_lower}'.

    `location` is typed loose because upstream boards return inconsistent
    shapes: france_travail returns ``{"libelle": "Paris (75)"}`` while most
    others return a plain string. The synthetic surfaced this as an
    AttributeError on dict.strip(); we now coerce defensively here so a
    contract change on one board never breaks dedup for the whole pipeline.
    """
    if isinstance(location, dict):
        # Common keys across boards: libelle (france_travail), name, display.
        for key in ("libelle", "name", "display"):
            v = location.get(key)
            if isinstance(v, str) and v.strip():
                location = v
                break
        else:
            location = ""
    elif not isinstance(location, (str, type(None))):
        # Last-ditch coerce: numbers, lists — stringify rather than crash.
        location = str(location)
    loc = (location or "").strip().lower()
    payload = f"{company_normalized}|{title_normalized}|{loc}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Date/time helpers
# ---------------------------------------------------------------------------

def now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def generate_run_id() -> str:
    """Return a unique run identifier like 'run_20260514_143022'."""
    return "run_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_jt_config(path: Path | str | None = None) -> dict:
    """Load config/job_tracker.json.

    Defaults to <project_root>/config/job_tracker.json where project_root is
    two levels above this file (execution/personal_workflows/ → execution/ → project_root/).
    """
    if path is None:
        project_root = Path(__file__).resolve().parents[2]
        path = project_root / "config" / "job_tracker.json"
    return load_json(path)


# ---------------------------------------------------------------------------
# JSON I/O
# ---------------------------------------------------------------------------

def save_json(data, path: Path | str) -> None:
    """Write *data* to *path* as indented JSON (UTF-8, no ASCII escaping).

    Creates parent directories as needed.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, default=str)


def load_json(path: Path | str) -> dict:
    """Load JSON from *path*; raises FileNotFoundError with a helpful message if missing."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"load_json: file not found at {path.resolve()}. "
            "Check that the path is correct and the file has been created."
        )
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)
