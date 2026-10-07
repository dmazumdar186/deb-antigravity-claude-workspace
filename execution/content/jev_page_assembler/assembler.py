"""Assemble a per-visitor landing page from a component library using ONE Jev call.

description: Builds a visitor+brand state, asks Jev one `choice` question per page slot
             (criteria = variant descriptions) plus a `noul` buyer-vs-researcher question,
             fills page_shell.html with the chosen fragments and theme. Fails open to
             DEFAULT_CHOICES on any Jev error. Deterministic cache keyed on a hash of the
             visitor context (in-memory + optional JSON file) so repeat contexts are free.
inputs: visitor dict (referrer, utm_source, utm_campaign, device, locale, hour_local,
        returning, pages_seen, query_terms), brand dict (name, product, audience),
        library dict (load_library()). env OPENROUTER_API_KEY (or alias).
outputs: assemble() -> {html, choices, buyer_stage, cost, latency_ms, cached, error}.
"""
from __future__ import annotations

import hashlib
import html as html_lib
import json
import logging
import sys
import threading
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from execution.modules import jev_client  # noqa: E402

log = logging.getLogger("jev_page_assembler")

PKG_DIR = Path(__file__).resolve().parent
LIBRARY_PATH = PKG_DIR / "library.json"
PERSONAS_PATH = PKG_DIR / "personas.json"
SHELL_PATH = PKG_DIR / "page_shell.html"
DEFAULT_CACHE_FILE = _ROOT / ".tmp" / "jev_pages_cache.json"

SLOTS = ["theme", "hero", "primary_cta", "proof", "form", "faq", "footer"]
DEFAULT_CHOICES: dict[str, str] = {
    "theme": "calm-light", "hero": "outcome-stat", "primary_cta": "start-trial",
    "proof": "logos", "form": "email-only", "faq": "pricing-objections", "footer": "minimal",
}
DEFAULT_BRAND: dict[str, str] = {
    "name": "Flowly", "product": "Flowly Autopilot",
    "audience": "operations teams at 10-500 person B2B companies",
}
VISITOR_KEYS = ["referrer", "utm_source", "utm_campaign", "device", "locale",
                "hour_local", "returning", "pages_seen", "query_terms"]

SLOT_INSTRUCTIONS = {
    "theme": "Pick the visual theme that best suits this visitor.",
    "hero": "Pick the hero section most likely to keep this visitor reading.",
    "primary_cta": "Pick the primary call to action matching this visitor's intent stage.",
    "proof": "Pick the proof block this visitor will find most convincing.",
    "form": "Pick the lead form that matches the chosen intent; fewer fields for researchers.",
    "faq": "Pick the FAQ that answers this visitor's most likely objection.",
    "footer": "Pick the footer that fits this visitor's device and context.",
}

_cache: dict[str, dict[str, Any]] = {}
_cache_lock = threading.Lock()


def load_library(path: Path = LIBRARY_PATH) -> dict[str, dict[str, dict[str, str]]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_personas(path: Path = PERSONAS_PATH) -> dict[str, dict[str, Any]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalize_visitor(visitor: dict[str, Any]) -> dict[str, Any]:
    """Keep only known keys with stable types (so the cache key is deterministic)."""
    out: dict[str, Any] = {}
    for k in VISITOR_KEYS:
        v = visitor.get(k)
        if k == "returning":
            out[k] = bool(v)
        elif k == "hour_local":
            try:
                out[k] = int(v) % 24
            except (TypeError, ValueError):
                out[k] = 12
        elif k == "pages_seen":
            out[k] = [str(p)[:100] for p in (v or [])][:20]
        else:
            out[k] = str(v or "")[:300]
    return out


def cache_key(visitor: dict[str, Any], brand: dict[str, Any]) -> str:
    blob = json.dumps({"v": normalize_visitor(visitor), "b": brand}, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def build_questions(library: dict[str, Any]) -> dict[str, dict[str, Any]]:
    qs: dict[str, dict[str, Any]] = {}
    for slot in SLOTS:
        opts = {name: f"{v['description']} (good for: {v.get('when', '')})"
                for name, v in library[slot].items()}
        qs[slot] = jev_client.choice(SLOT_INSTRUCTIONS[slot], opts)
    qs["buyer_stage"] = jev_client.noul(
        "Is this visitor likely a buyer-stage visitor rather than an early researcher?",
        "buyer-stage: ready to evaluate, compare pricing or talk to sales",
        "researcher: learning about the problem, not ready to buy")
    return qs


def _fill(fragment: str, brand: dict[str, Any]) -> str:
    return (fragment.replace("{{brand}}", html_lib.escape(str(brand.get("name", ""))))
            .replace("{{product}}", html_lib.escape(str(brand.get("product", "")))))


def render(choices: dict[str, str], brand: dict[str, Any], library: dict[str, Any],
           locale: str = "en", debug_html: str = "") -> str:
    shell = SHELL_PATH.read_text(encoding="utf-8")
    page = shell.replace("{{theme_css}}", library["theme"][choices["theme"]]["css"])
    for slot in SLOTS[1:]:
        page = page.replace("{{" + slot + "}}", _fill(library[slot][choices[slot]]["html"], brand))
    lang = (locale or "en").split(",")[0].split(";")[0].strip()[:12] or "en"
    page = page.replace("{{lang}}", html_lib.escape(lang)).replace("{{debug}}", debug_html)
    return _fill(page, brand)


def debug_ribbon(result: dict[str, Any]) -> str:
    parts = " | ".join(f"{k}={v}" for k, v in result["choices"].items())
    txt = (f"Jev: {parts} | buyer={result['buyer_stage']:.2f} | {result['latency_ms']} ms | "
           f"${result['cost']:.5f}{' | cached' if result['cached'] else ''}"
           f"{' | FALLBACK: ' + result['error'] if result['error'] else ''}")
    return f'<div class="jev-debug" role="status">{html_lib.escape(txt)}</div>'


def _load_file_cache(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        log.warning("cache file unreadable (%s); starting empty", exc)
        return {}


def _save_file_cache(path: Path, key: str, entry: dict[str, Any]) -> None:
    with _cache_lock:
        data = _load_file_cache(path)
        data[key] = entry
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
        tmp.replace(path)


def choose(visitor: dict[str, Any], brand: dict[str, Any], library: dict[str, Any],
           cache_file: Path | None = None) -> dict[str, Any]:
    """Return {choices, buyer_stage, cost, latency_ms, cached, error} (no HTML)."""
    key = cache_key(visitor, brand)
    with _cache_lock:
        hit = _cache.get(key)
    if hit is None and cache_file is not None:
        hit = _load_file_cache(cache_file).get(key)
        if hit:
            with _cache_lock:
                _cache[key] = hit
    if hit:
        return {**hit, "cost": 0.0, "latency_ms": 0, "cached": True, "error": None}

    state = {"visitor": normalize_visitor(visitor),
             "brand": {k: brand.get(k, "") for k in ("name", "product", "audience")}}
    t0 = time.perf_counter()
    try:
        res = jev_client.decide(state, build_questions(library))
        err = res.error
    except Exception as exc:  # fail-open: page must always render; logged below
        res, err = None, f"{exc.__class__.__name__}: {exc}"
    latency = int((time.perf_counter() - t0) * 1000)
    choices = dict(DEFAULT_CHOICES)
    buyer = 0.0
    if res is not None and not err:
        for slot in SLOTS:
            pick = res.choice(slot, "")
            if pick in library[slot]:
                choices[slot] = pick
        buyer = res.noul("buyer_stage", 0.0)
    else:
        log.warning("Jev failed, using DEFAULT_CHOICES: %s", err)
    out = {"choices": choices, "buyer_stage": buyer,
           "cost": (res.cost_usd if res is not None else 0.0), "latency_ms": latency,
           "cached": False, "error": err}
    if not err:  # only cache real decisions; errors should retry next time
        entry = {"choices": choices, "buyer_stage": buyer}
        with _cache_lock:
            _cache[key] = entry
        if cache_file is not None:
            _save_file_cache(cache_file, key, entry)
    return out


def assemble(visitor: dict[str, Any], brand: dict[str, Any] | None = None,
             library: dict[str, Any] | None = None, *, debug: bool = False,
             cache_file: Path | None = None) -> dict[str, Any]:
    brand = brand or DEFAULT_BRAND
    library = library or load_library()
    result = choose(visitor, brand, library, cache_file=cache_file)
    ribbon = debug_ribbon(result) if debug else ""
    result["html"] = render(result["choices"], brand, library,
                            locale=str(visitor.get("locale", "en")), debug_html=ribbon)
    return result


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()
