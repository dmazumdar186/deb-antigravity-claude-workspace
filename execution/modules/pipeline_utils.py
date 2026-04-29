"""
pipeline_utils.py
description: Shared utilities for the Accessory Masters cold email pipeline.
             Provides retry logic, lead I/O, deduplication, config loading, and logging.
inputs: Imported by pipeline scripts — not run directly.
outputs: N/A (utility module)
"""

import csv
import functools
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests


class PipelineAPIError(Exception):
    """Raised when an API call fails after all retries."""

    def __init__(self, endpoint: str, status_code: int, response_body: str):
        self.endpoint = endpoint
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(
            f"API error: {endpoint} returned {status_code}: {response_body[:200]}"
        )


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator that retries a function on transient HTTP errors with exponential backoff."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.HTTPError as e:
                    last_exception = e
                    status = e.response.status_code if e.response is not None else 0
                    if status == 429:
                        retry_after = e.response.headers.get("Retry-After")
                        delay = (
                            float(retry_after)
                            if retry_after
                            else base_delay * (2**attempt)
                        )
                        logging.warning(
                            "Rate limited on %s, waiting %.1fs (attempt %d/%d)",
                            func.__name__,
                            delay,
                            attempt + 1,
                            max_retries,
                        )
                        time.sleep(delay)
                    elif status >= 500:
                        delay = base_delay * (2**attempt)
                        logging.warning(
                            "Server error %d on %s, retrying in %.1fs (attempt %d/%d)",
                            status,
                            func.__name__,
                            delay,
                            attempt + 1,
                            max_retries,
                        )
                        time.sleep(delay)
                    else:
                        raise
                except requests.exceptions.ConnectionError as e:
                    last_exception = e
                    delay = base_delay * (2**attempt)
                    logging.warning(
                        "Connection error on %s, retrying in %.1fs (attempt %d/%d)",
                        func.__name__,
                        delay,
                        attempt + 1,
                        max_retries,
                    )
                    time.sleep(delay)
            raise last_exception

        return wrapper

    return decorator


def load_config(config_path: str | Path) -> dict:
    """Read and return a JSON config file."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_leads(filepath: str | Path) -> list[dict]:
    """Read a JSON lead file and return the list of lead dicts."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(
            f"Lead file not found: {path}. Run the previous pipeline stage first."
        )
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {path}, got {type(data).__name__}")
    return data


def save_leads(leads: list[dict], filepath: str | Path) -> Path:
    """Write a list of lead dicts to a JSON file. Creates parent dirs if needed."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(leads, f, indent=2, ensure_ascii=False, default=str)
    return path


def export_csv(leads: list[dict], filepath: str | Path, columns: list[str]) -> Path:
    """Export selected columns from leads to a CSV file (e.g. for Instantly upload)."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(leads)
    return path


def normalize_domain(url_or_domain: str) -> str:
    """Extract and normalize a domain from a URL or bare domain string."""
    if not url_or_domain:
        return ""
    s = url_or_domain.strip().lower()
    if "://" not in s:
        s = "http://" + s
    parsed = urlparse(s)
    domain = parsed.hostname or ""
    domain = re.sub(r"^www\.", "", domain)
    return domain


def normalize_name(name: str) -> str:
    """Normalize a business name for dedup comparison."""
    if not name:
        return ""
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def compute_dedup_key(lead: dict) -> str:
    """Generate a dedup key from domain + business name, or name + city + state."""
    domain = normalize_domain(lead.get("website", "") or lead.get("domain", ""))
    name = normalize_name(lead.get("business_name", ""))
    if domain:
        return f"{domain}|{name}"
    city = (lead.get("city", "") or "").strip().lower()
    state = (lead.get("state", "") or "").strip().lower()
    return f"{name}|{city}|{state}"


def deduplicate(leads: list[dict]) -> list[dict]:
    """Remove duplicate leads by dedup_key, keeping the first occurrence."""
    seen = set()
    unique = []
    for lead in leads:
        key = lead.get("dedup_key") or compute_dedup_key(lead)
        lead["dedup_key"] = key
        if key not in seen:
            seen.add(key)
            unique.append(lead)
    removed = len(leads) - len(unique)
    if removed:
        logging.info("Deduplication: removed %d duplicates, %d unique remain", removed, len(unique))
    return unique


def setup_logging(name: str, log_dir: str | Path | None = None) -> logging.Logger:
    """Configure and return a logger with console (INFO) and optional file (DEBUG) handlers."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(levelname)s | %(message)s"))
    logger.addHandler(console)

    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_path / f"{name}.log", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        )
        logger.addHandler(fh)

    return logger


def generate_run_id() -> str:
    """Return a timestamped run ID like 'run_20260429_103000'."""
    return datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S")


def now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()
