"""CV Optimizer — local CLI using `claude --print` (operator's Claude subscription).

See directives/personal_workflows/cv_optimizer_local.md for full design.

Usage:
    py cli.py --cv /path/to/cv.pdf --jd-text "..." --out-dir .tmp/out/
    py cli.py --cv-text-file cv.txt --jd-url https://... --out-dir .tmp/out/

Outputs in --out-dir:
    cvspec.json   raw CVSpec JSON from Claude
    cv.html       rendered CV (cv-template.html substitution)
    cv.pdf        A4 PDF via Playwright headless Chromium
    cv.png        snapshot PNG for quick visual review
    run.log       per-step timing breakdown
    claude_raw.txt  raw Claude output if JSON parse fails (debugging)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from html import escape as html_escape
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_PROMPT_PATH = REPO_ROOT / "execution" / "personal_workflows" / "cv_optimizer_v2" / "prompts" / "system_prompt.md"
SHARED_SCHEMA_PATH = REPO_ROOT / "execution" / "personal_workflows" / "cv_optimizer_v2" / "prompts" / "cv_response_schema.json"
SHARED_TEMPLATE_PATH = REPO_ROOT / "execution" / "personal_workflows" / "cv_optimizer_v2" / "web" / "cv-template.html"

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_OUT_BASE = REPO_ROOT / ".tmp" / "cv_optimizer_local"


# ---------------------------------------------------------------------------
# PDF + JD extraction
# ---------------------------------------------------------------------------

def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from a PDF using pypdf. Returns concatenated text across pages."""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError("pypdf not installed. Run: py -m pip install pypdf")

    if not pdf_path.exists():
        raise FileNotFoundError(f"CV PDF not found: {pdf_path}")
    if pdf_path.stat().st_size == 0:
        raise ValueError(f"CV PDF is empty: {pdf_path}")

    reader = PdfReader(str(pdf_path))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception as exc:
            pages.append("")
            print(f"WARN: page extract failed: {exc}", file=sys.stderr)

    text = "\n\n".join(pages).strip()
    if len(text) < 100:
        raise ValueError(f"PDF extract produced suspiciously little text ({len(text)} chars); is it a scanned/image PDF?")
    return text


def scrape_jd_url(url: str, firecrawl_key: str | None = None) -> str:
    """Scrape JD URL. Uses Firecrawl if key present, else plain fetch + naive HTML strip."""
    if firecrawl_key:
        return _scrape_firecrawl(url, firecrawl_key)
    return _scrape_plain(url)


def _scrape_firecrawl(url: str, api_key: str) -> str:
    body = json.dumps({
        "url": url,
        "formats": ["markdown"],
        "onlyMainContent": True,
        "maxAge": 86_400_000,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.firecrawl.dev/v1/scrape",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"firecrawl HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}")
    except Exception as e:
        raise RuntimeError(f"firecrawl request failed: {e}")

    markdown = (data.get("data") or {}).get("markdown", "")
    if len(markdown) < 200:
        raise RuntimeError(f"firecrawl returned thin content ({len(markdown)} chars)")

    login_keywords = ["sign in to view", "sign in to apply", "join linkedin", "join to apply"]
    low = markdown.lower()
    for kw in login_keywords:
        if kw in low:
            raise RuntimeError(f"login_wall detected: {kw!r}; use --jd-text-file instead")

    # Strip pre-H2 chrome, cap at 3500 chars (matches Worker behavior).
    import re
    h2 = re.search(r"\n##\s+\S", markdown)
    body = markdown[h2.start() + 1:] if h2 else markdown
    return body[:3500]


def _scrape_plain(url: str) -> str:
    """Plain fetch fallback for when Firecrawl key isn't available.

    Limited: won't handle JS-rendered pages (WTTJ, Greenhouse, Lever often fail here).
    Adequate for static company career pages and most blog-style JDs.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (cv-optimizer-local)"})
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        raise RuntimeError(f"plain fetch failed: {e}")

    # Very naive HTML strip: drop scripts/styles, then strip tags.
    import re
    html = re.sub(r"<script.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < 200:
        raise RuntimeError(f"plain scrape produced thin content ({len(text)} chars); use --jd-text-file")
    return text[:3500]


# ---------------------------------------------------------------------------
# Claude call
# ---------------------------------------------------------------------------

def call_claude_print(prompt: str, model: str = DEFAULT_MODEL, timeout: int = 360, retries: int = 1) -> str:
    """Call `claude --print` using the operator's authenticated session.

    Returns stdout. Raises on non-zero exit. One automatic retry on subprocess
    timeout (Sonnet 4.6 latency variance is wide — p50 ~150s, p99 ~280s with
    a full CVSpec prompt). Total wall budget = timeout * (retries + 1).
    """
    last_err = ""
    for attempt in range(retries + 1):
        try:
            r = subprocess.run(
                ["claude", "--print", "--model", model],
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=True,
                timeout=timeout,
            )
            if r.returncode != 0:
                last_err = f"exit {r.returncode}: {(r.stderr or '')[:200]}"
                continue  # retry on non-zero too
            return r.stdout
        except subprocess.TimeoutExpired:
            last_err = f"subprocess.TimeoutExpired after {timeout}s (attempt {attempt+1})"
            continue
    raise RuntimeError(f"claude --print failed after {retries+1} attempts: {last_err}")


def extract_json_object(raw: str) -> dict:
    """Robust extraction of one JSON object from Claude output (handles code fences, prose)."""
    first = raw.find("{")
    last = raw.rfind("}")
    if first < 0 or last < first:
        raise ValueError(f"no JSON braces in claude output (first 200 chars: {raw[:200]})")
    text = raw[first:last + 1]
    return json.loads(text)


REQUIRED_FIELDS = (
    "language_detected", "ats_score", "name", "title", "contact",
    "summary", "summary_kpis", "experience", "skills", "education",
    "languages", "recommendations",
)


def validate_cvspec(spec: dict) -> list[str]:
    """Return list of error strings. Empty = valid enough to render."""
    errs = []
    for f in REQUIRED_FIELDS:
        if f not in spec:
            errs.append(f"missing field: {f}")
    if "language_detected" in spec and spec["language_detected"] not in ("en", "fr", "es", "de"):
        errs.append(f"invalid language_detected: {spec['language_detected']!r}")
    if "ats_score" in spec:
        s = spec["ats_score"]
        if not isinstance(s, int) or s < 0 or s > 100:
            errs.append(f"invalid ats_score: {s!r}")
    if "experience" in spec and not isinstance(spec["experience"], list):
        errs.append("experience must be a list")
    return errs


# ---------------------------------------------------------------------------
# Rendering: JSON -> HTML -> PDF/PNG
# ---------------------------------------------------------------------------

def render_html(spec: dict, template: str) -> str:
    """Replicate the web/app.js renderPreview() in Python. Same template, same fields."""

    def esc(s):
        return html_escape(str(s) if s is not None else "")

    out = template
    out = out.replace("{{name}}", esc(spec.get("name", "")))
    out = out.replace("{{title}}", esc(spec.get("title", "")))
    out = out.replace("{{ats_score}}", esc(spec.get("ats_score", "")))
    out = out.replace("{{language_detected}}", esc(spec.get("language_detected", "")))
    out = out.replace("{{summary}}", esc(spec.get("summary", "")))
    out = out.replace("{{summary_kpis}}", esc(spec.get("summary_kpis", "")))

    c = spec.get("contact") or {}
    out = out.replace("{{contact_email}}", esc(c.get("email", "")))
    out = out.replace("{{contact_phone}}", esc(c.get("phone", "")))
    out = out.replace("{{contact_location}}", esc(c.get("location", "")))
    out = out.replace("{{contact_linkedin}}", esc(c.get("linkedin", "")))
    out = out.replace("{{contact_github}}", esc(c.get("github", "")))

    exp_html = "".join(
        f'<div class="exp">'
        f'<div class="exp-role">{esc(e.get("role",""))}</div>'
        f'<div class="exp-company">{esc(e.get("company_line",""))}</div>'
        f'<ul class="exp-bullets">{"".join(f"<li>{esc(b)}</li>" for b in (e.get("bullets") or []))}</ul>'
        f'</div>'
        for e in (spec.get("experience") or [])
    )
    out = out.replace("{{experience_block}}", exp_html)

    skills_html = "".join(
        f'<div class="skill-row"><span class="skill-cat">{esc(s.get("category",""))}</span>'
        f'<span class="skill-val">{esc(s.get("value",""))}</span></div>'
        for s in (spec.get("skills") or [])
    )
    out = out.replace("{{skills_block}}", skills_html)

    edu_html = "".join(
        f'<div class="edu"><div class="edu-degree">{esc(e.get("degree",""))}</div>'
        f'<div class="edu-inst">{esc(e.get("institution_line",""))}</div></div>'
        for e in (spec.get("education") or [])
    )
    out = out.replace("{{education_block}}", edu_html)

    langs_html = esc(" · ".join(spec.get("languages") or []))
    out = out.replace("{{languages}}", langs_html)

    certs = spec.get("certifications") or []
    certs_html = f"<ul>{''.join(f'<li>{esc(c)}</li>' for c in certs)}</ul>" if certs else ""
    out = out.replace("{{certifications_block}}", certs_html)

    projs = spec.get("projects") or []
    projs_html = f"<ul>{''.join(f'<li>{esc(p)}</li>' for p in projs)}</ul>" if projs else ""
    out = out.replace("{{projects_block}}", projs_html)

    recs = spec.get("recommendations") or []
    recs_html = "".join(f"<li>{esc(r)}</li>" for r in recs)
    out = out.replace("{{recommendations_block}}", recs_html)
    return out


def render_pdf_and_png(html_text: str, pdf_path: Path, png_path: Path) -> dict:
    """Use Playwright headless Chromium to render HTML to A4 PDF + PNG snapshot."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 794, "height": 1123})
        page = context.new_page()
        page.set_content(html_text, wait_until="load")

        page.pdf(
            path=str(pdf_path),
            format="A4",
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            print_background=True,
            prefer_css_page_size=True,
        )
        page.screenshot(path=str(png_path), full_page=True)
        dims = page.evaluate("() => ({w: document.documentElement.scrollWidth, h: document.documentElement.scrollHeight})")
        browser.close()
        return dims


# ---------------------------------------------------------------------------
# CLI orchestration
# ---------------------------------------------------------------------------

def assemble_prompt(cv_text: str, jd_text: str, system_prompt: str, schema: dict) -> str:
    """Build the prompt sent to claude --print. Mirrors the Worker's body shape."""
    schema_instruction = (
        "\n\nYou MUST respond ONLY with a JSON object matching this exact schema. "
        "No prose, no markdown code fences, no preamble. Just the raw JSON object:\n\n"
        + json.dumps(schema)
    )
    user_block = (
        f"CV (original):\n{cv_text}\n\n---\n\nJD (target):\n{jd_text}\n\n"
        f"Return the optimized CV JSON now."
    )
    return f"{system_prompt}{schema_instruction}\n\n---\n\n{user_block}"


def resolve_cv_text(args) -> str:
    if args.cv:
        return extract_pdf_text(Path(args.cv))
    if args.cv_text_file:
        return Path(args.cv_text_file).read_text(encoding="utf-8")
    if args.cv_text:
        return args.cv_text
    raise SystemExit("Provide one of: --cv path/to/cv.pdf, --cv-text, --cv-text-file")


def resolve_jd_text(args) -> str:
    if args.jd_text_file:
        return Path(args.jd_text_file).read_text(encoding="utf-8")
    if args.jd_text:
        return args.jd_text
    if args.jd_url:
        firecrawl_key = os.environ.get("FIRECRAWL_API_KEY", "").strip() or None
        return scrape_jd_url(args.jd_url, firecrawl_key)
    raise SystemExit("Provide one of: --jd-url, --jd-text, --jd-text-file")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CV Optimizer (local, uses Claude subscription)")
    parser.add_argument("--cv", help="Path to CV PDF (extracted via pypdf)")
    parser.add_argument("--cv-text", help="CV text directly (alternative to --cv)")
    parser.add_argument("--cv-text-file", help="Path to a .txt file with CV text")
    parser.add_argument("--jd-url", help="JD URL (Firecrawl if FIRECRAWL_API_KEY set, else plain fetch)")
    parser.add_argument("--jd-text", help="JD text directly")
    parser.add_argument("--jd-text-file", help="Path to a .txt file with JD text")
    parser.add_argument("--out-dir", help="Output directory (default .tmp/cv_optimizer_local/<ts>/)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude model (default {DEFAULT_MODEL})")
    parser.add_argument("--no-render", action="store_true", help="Skip PDF/PNG render (faster CI/synthetic check)")
    args = parser.parse_args(argv)

    # Set up output dir.
    ts = time.strftime("%Y%m%d-%H%M%S")
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT_BASE / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    log_lines = [f"# cv_optimizer_local run @ {ts}", f"model: {args.model}"]

    def log(msg):
        log_lines.append(msg)
        print(msg, flush=True)

    t_total = time.time()
    try:
        t0 = time.time()
        cv_text = resolve_cv_text(args)
        log(f"[step] cv_extract: {len(cv_text)} chars in {int((time.time()-t0)*1000)}ms")

        t0 = time.time()
        jd_text = resolve_jd_text(args)
        log(f"[step] jd_resolve: {len(jd_text)} chars in {int((time.time()-t0)*1000)}ms")

        if not SHARED_PROMPT_PATH.exists():
            raise SystemExit(f"system prompt source missing: {SHARED_PROMPT_PATH}")
        if not SHARED_SCHEMA_PATH.exists():
            raise SystemExit(f"schema source missing: {SHARED_SCHEMA_PATH}")
        system_prompt = SHARED_PROMPT_PATH.read_text(encoding="utf-8")
        schema = json.loads(SHARED_SCHEMA_PATH.read_text(encoding="utf-8"))

        prompt = assemble_prompt(cv_text, jd_text, system_prompt, schema)
        log(f"[step] prompt assembled: {len(prompt)} chars")

        t0 = time.time()
        raw = call_claude_print(prompt, model=args.model)
        log(f"[step] claude --print: {len(raw)} chars in {int((time.time()-t0)*1000)}ms")

        # Save raw for debugging regardless of parse outcome.
        (out_dir / "claude_raw.txt").write_text(raw, encoding="utf-8")

        try:
            spec = extract_json_object(raw)
        except Exception as exc:
            log(f"[fail] JSON extraction: {exc}")
            (out_dir / "run.log").write_text("\n".join(log_lines), encoding="utf-8")
            return 2

        errs = validate_cvspec(spec)
        if errs:
            log(f"[fail] CVSpec validation: {errs}")
            (out_dir / "cvspec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
            (out_dir / "run.log").write_text("\n".join(log_lines), encoding="utf-8")
            return 3

        (out_dir / "cvspec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"[step] cvspec.json written: lang={spec['language_detected']} ats={spec['ats_score']}")

        if args.no_render:
            log(f"[done] --no-render set; total {int((time.time()-t_total)*1000)}ms")
            (out_dir / "run.log").write_text("\n".join(log_lines), encoding="utf-8")
            return 0

        if not SHARED_TEMPLATE_PATH.exists():
            raise SystemExit(f"template missing: {SHARED_TEMPLATE_PATH}")
        template = SHARED_TEMPLATE_PATH.read_text(encoding="utf-8")
        html = render_html(spec, template)
        (out_dir / "cv.html").write_text(html, encoding="utf-8")
        log(f"[step] cv.html written: {len(html)} chars")

        t0 = time.time()
        dims = render_pdf_and_png(html, out_dir / "cv.pdf", out_dir / "cv.png")
        log(f"[step] cv.pdf + cv.png rendered ({dims['w']}x{dims['h']}) in {int((time.time()-t0)*1000)}ms")

        log(f"[done] total {int((time.time()-t_total)*1000)}ms; output -> {out_dir}")
        (out_dir / "run.log").write_text("\n".join(log_lines), encoding="utf-8")
        return 0

    except SystemExit:
        raise
    except Exception as exc:
        log(f"[fail] unhandled: {type(exc).__name__}: {exc}")
        (out_dir / "run.log").write_text("\n".join(log_lines), encoding="utf-8")
        return 1


if __name__ == "__main__":
    sys.exit(main())
