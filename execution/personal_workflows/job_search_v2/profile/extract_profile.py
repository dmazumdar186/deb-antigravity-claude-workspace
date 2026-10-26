"""
description: Extract a structured operator profile from real artifacts (CV PDF +
    LinkedIn .md + brand strategy + canonical metrics + workspace project signals)
    and emit profile.json. The ranker reads profile.json so every job match is
    anchored to a verifiable skill-and-evidence set rather than a frozen prose
    rubric. Auditable: open the JSON, confirm "yes this is me / no this is wrong"
    in 60 seconds.

inputs:
    - CLI args: --cv PATH (default: workspace root "CV MAZUMDAR Debanjan EN.pdf"),
                --out PATH (default: profile/profile.json), --dry-run
    - Reads (paths resolved from workspace root):
        * CV PDF (pypdf-extracted text)
        * execution/personal_workflows/personal_brand/linkedin_profile.md
        * execution/personal_workflows/personal_brand/brand_strategy.md
        * execution/personal_workflows/personal_brand/metrics_canonical.md
        * directives/personal_workflows/*.md (project signals — shipped systems)
    - env: GEMINI_API_KEY (free tier; failure mode is hard-fail with clear msg)
    - 2026-10-26 secondary identity sources (both fail-soft, no key needed):
        * GitHub public API for user `dmazumdar186` (GITHUB_TOKEN used if set;
          GITHUB_SEED_REPOS="a,b,c" lists repos to probe when the user-level
          endpoint is blocked, e.g. in a repo-bound cloud session)
        * https://prodcraft.fyi homepage (+ /about, /services when they exist)
      `--sources-only` refreshes just these two sections into an existing
      profile.json (merge; CV/LinkedIn-derived keys are kept verbatim).

outputs:
    - profile.json with schema:
        {
          "schema_version": "1.0",
          "generated_at": ISO-8601 UTC,
          "tracks": [
            {
              "id": "A" | "B",
              "title": "AI / Senior Product Manager (CDI)" | "Product Owner / AI Product Owner (CDI)",
              "targeted_titles": [str, ...],   # exact + adjacent title forms
              "anti_titles": [str, ...],       # SKIP-on-match
              "contract_types": ["cdi"|"freelance"|"contract"|"mission"],
              "min_seniority": "senior"|"lead"|"principal"|"head",
            },
          ],
          "skills": [
            {
              "name": str, "level": "expert"|"strong"|"familiar",
              "evidence": [str, ...],        # 1-3 short proof points
              "tracks": ["A"]|["B"]|["A","B"],
            },
          ],
          "domains": [str, ...],
          "languages": [{"code": "en"|"fr", "level": "C2"|...}],
          "locations": {
            "preferred": [str, ...],         # Paris, Île-de-France, ...
            "ok_remote": [str, ...],         # remote-EU, remote-FR, ...
            "blocked_countries": [str, ...], # US, India, APAC, ...
          },
          "hard_filters": {
            "skip_title_substrings": [str, ...],
            "skip_description_substrings": [str, ...],
            "skip_seniority": ["junior", "intern", "alternance", ...],
          },
          "proof_points": [                  # for the ranker's "did they ship X?" reasoning
            {"system": str, "metric": str, "track": "A"|"B"},
          ],
          "raw_source_paths": [str, ...],    # audit trail
          "github": {                        # 2026-10-26, fail-soft
            "login", "fetched_at", "source", "public_repos",
            "languages": [str], "topics": [str],
            "commits_last_12_months": int|null,
            "repos": [{"name","description","language","languages","topics",
                       "pushed_at","commits_last_12_months"}],
          },
          "freelance_site": {                # 2026-10-26, fail-soft
            "url", "fetched_at", "pages": [str], "tagline",
            "service_lines": [str], "skills_keywords": [str],
            "visible_text_excerpt": str,
          },
        }

Notes:
    - Gemini 2.5 Flash is the judge. Strict JSON-schema output. Temperature 0.1.
    - The script does NOT call the ranker. It produces the artifact the ranker
      then reads. Decoupled so you can audit/edit profile.json by hand.
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import logging
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=False))
logger = logging.getLogger("profile.extract")

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CV = WORKSPACE_ROOT / "CV MAZUMDAR Debanjan EN.pdf"
PERSONAL_BRAND_DIR = WORKSPACE_ROOT / "execution" / "personal_workflows" / "personal_brand"
DIRECTIVES_PW_DIR = WORKSPACE_ROOT / "directives" / "personal_workflows"
DEFAULT_OUT = Path(__file__).resolve().parent / "profile.json"

GITHUB_LOGIN = "dmazumdar186"
GITHUB_API = "https://api.github.com"
FREELANCE_SITE_URL = "https://prodcraft.fyi"
FREELANCE_SITE_PAGES = ("/", "/about", "/services")
_HTTP_TIMEOUT = 20
# Repos to probe one-by-one when `users/{login}/repos` is not reachable (the
# claude.ai cloud proxy binds a session to its configured repositories and
# answers 403 on user-level paths). Override with GITHUB_SEED_REPOS.
_DEFAULT_SEED_REPOS = (
    "deb-antigravity-claude-workspace", "cv-optimizer-agent",
    "youtube-video-analyzer", "anneal", "outbound-engine", "job_search_v2",
    "humanizer", "deb-mobile-template",
)
# Skill vocabulary matched against the freelance site's visible text
# (case-insensitive, word-ish boundaries). Short on purpose: the ranker only
# needs keywords it can grep for in a job description.
_SITE_SKILL_VOCAB = (
    "AI", "GenAI", "LLM", "RAG", "Claude", "Claude Code", "GPT", "Gemini",
    "agents", "AI agents", "automation", "outbound", "cold email", "SaaS",
    "mobile", "React Native", "Expo", "Next.js", "Astro", "Python",
    "TypeScript", "JavaScript", "Supabase", "Postgres", "Modal", "Cloudflare",
    "Stripe", "Twilio", "voice agent", "video", "YouTube", "SEO",
    "data pipeline", "scraping", "API", "MVP", "product management",
    "product strategy", "roadmap", "discovery", "GTM", "go-to-market",
    "analytics", "A/B testing", "growth", "chatbot", "n8n", "Zapier", "Make",
    "HubSpot", "Instantly", "Apify", "OpenAI", "Anthropic", "vector",
    "embeddings", "fine-tuning", "prompt engineering", "evals", "Vapi",
    "Retell", "Whisper", "SmartLead", "GHL", "Playwright", "Remotion",
    "Cloudflare Workers", "MCP", "multi-agent", "copilot", "eval harness",
)


def _http_get(url: str, headers: dict[str, str] | None = None,
              timeout: int = _HTTP_TIMEOUT) -> tuple[int, bytes, dict[str, str]]:
    """GET with a UA; returns (status, body, headers). HTTP errors return their
    status instead of raising so callers can branch; network errors raise
    urllib.error.URLError / OSError."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "job-search-v2-profile-extractor",
        **(headers or {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — https only, fixed hosts
            return resp.status, resp.read(), {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return exc.code, body, {k.lower(): v for k, v in (exc.headers or {}).items()}


def _github_headers() -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _github_json(path: str) -> tuple[int, object, dict[str, str]]:
    status, body, headers = _http_get(f"{GITHUB_API}{path}", _github_headers())
    try:
        data = json.loads(body.decode("utf-8", errors="replace")) if body else None
    except json.JSONDecodeError:
        data = None
    return status, data, headers


def _github_commit_count_12m(owner: str, repo: str, since_iso: str) -> int | None:
    """Count commits since `since_iso` via per_page=1 + the Link rel="last"
    page number (one request, no pagination). None when unavailable."""
    path = (f"/repos/{owner}/{repo}/commits?since={urllib.parse.quote(since_iso)}"
            "&per_page=1")
    status, data, headers = _github_json(path)
    if status != 200 or not isinstance(data, list):
        return None
    if not data:
        return 0
    link = headers.get("link", "")
    m = re.search(r'[?&]page=(\d+)>;\s*rel="last"', link)
    return int(m.group(1)) if m else 1


def _github_repo_record(owner: str, repo: dict, since_iso: str) -> dict:
    name = repo.get("name", "")
    langs: list[str] = []
    status, data, _ = _github_json(f"/repos/{owner}/{name}/languages")
    if status == 200 and isinstance(data, dict):
        langs = [k for k, _ in sorted(data.items(), key=lambda kv: -kv[1])]
    return {
        "name": name,
        "description": (repo.get("description") or "")[:200],
        "language": repo.get("language") or "",
        "languages": langs,
        "topics": list(repo.get("topics") or []),
        "pushed_at": repo.get("pushed_at") or "",
        "fork": bool(repo.get("fork")),
        "commits_last_12_months": _github_commit_count_12m(owner, name, since_iso),
    }


def fetch_github_profile(login: str = GITHUB_LOGIN, previous: dict | None = None) -> dict | None:
    """Public GitHub evidence for `login`. Returns the section dict, or
    `previous` (may be None) on any failure — never raises.

    Path 1: users/{login}/repos (needs no token). Path 2 (when path 1 is
    blocked/forbidden): probe GITHUB_SEED_REPOS / _DEFAULT_SEED_REPOS with the
    repo-scoped endpoint and keep the ones that answer 200.
    """
    since_dt = datetime.now(timezone.utc) - timedelta(days=365)
    since_iso = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        repos: list[dict] = []
        source = "users_endpoint"
        status, data, _ = _github_json(f"/users/{login}/repos?per_page=100&sort=pushed&type=owner")
        if status == 200 and isinstance(data, list):
            repos = [r for r in data if isinstance(r, dict)]
        else:
            logger.warning("github: users/%s/repos -> HTTP %s; probing seed repos", login, status)
            source = "seed_repos"
            seeds_env = os.environ.get("GITHUB_SEED_REPOS", "").strip()
            seeds = [x.strip() for x in seeds_env.split(",") if x.strip()] or list(_DEFAULT_SEED_REPOS)
            for name in seeds:
                st, rd, _ = _github_json(f"/repos/{login}/{name}")
                if st == 200 and isinstance(rd, dict):
                    repos.append(rd)
                else:
                    logger.info("github: repo %s/%s not reachable (HTTP %s)", login, name, st)
        if not repos:
            logger.warning("github: no repos retrievable for %s — keeping previous section", login)
            return previous
        repos = [r for r in repos if not r.get("fork")] or repos
        repos.sort(key=lambda r: r.get("pushed_at") or "", reverse=True)
        records = [_github_repo_record(login, r, since_iso) for r in repos[:30]]
        lang_counts: dict[str, int] = {}
        topics: list[str] = []
        for rec in records:
            for i, lang in enumerate(rec["languages"]):
                lang_counts[lang] = lang_counts.get(lang, 0) + (3 if i == 0 else 1)
            for t in rec["topics"]:
                if t not in topics:
                    topics.append(t)
        counts = [rec["commits_last_12_months"] for rec in records]
        known = [c for c in counts if isinstance(c, int)]
        return {
            "login": login,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "public_repos": len(records),
            "languages": [k for k, _ in sorted(lang_counts.items(), key=lambda kv: -kv[1])],
            "topics": topics,
            "commits_last_12_months": sum(known) if known else None,
            "repos": records,
        }
    except (urllib.error.URLError, OSError, ValueError, TypeError) as exc:
        logger.warning("github: fetch failed (%s) — keeping previous section", exc)
        return previous


def _html_to_text(raw: bytes) -> str:
    txt = raw.decode("utf-8", errors="replace")
    txt = re.sub(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", txt, flags=re.S | re.I)
    txt = re.sub(r"<br\s*/?>|</(p|div|li|h[1-6]|section|article|header|footer)>", "\n", txt, flags=re.I)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = html_lib.unescape(txt)
    lines = [re.sub(r"[ \t\u00a0]+", " ", ln).strip() for ln in txt.splitlines()]
    return "\n".join(ln for ln in lines if ln)


_SERVICES_HEADING = re.compile(r"(what we build|services|what we do|offer(ing)?s?)\b", re.I)
_SECTION_END = re.compile(r"^\d{2}\s*[—-]\s|^(the stack|how we work|recommendations|contact)\b", re.I)
_CTA_OR_NOISE = re.compile(r"(→|↗|^\d+\s|^(book|see|hear|talk|show|scroll|keep)\b|^how it works)", re.I)


def _extract_service_lines(text: str, limit: int = 12) -> list[str]:
    """Service lines = short lines (2-10 words) inside the 'What we build' /
    'Services' section, up to the next numbered section ('05 — The stack').
    Falls back to offer-shaped lines anywhere when no such section exists."""
    lines = text.splitlines()
    out: list[str] = []
    seen: set[str] = set()

    def _take(ln: str) -> None:
        clean = ln.strip(" ·—-")
        if clean.lower() in seen or not 2 <= len(clean.split()) <= 10:
            return
        if _CTA_OR_NOISE.search(clean) or clean.endswith("."):
            return
        seen.add(clean.lower())
        out.append(clean)

    for i, ln in enumerate(lines):
        if _SERVICES_HEADING.search(ln) and len(ln.split()) <= 6:
            for nxt in lines[i + 1:]:
                if _SECTION_END.search(nxt):
                    break
                _take(nxt)
                if len(out) >= limit:
                    break
            if out:
                return out
    verbs = re.compile(r"\b(build|ship|automate|deploy|integrate|engine|agent|"
                       r"pipeline|system|copilot|chatbot|workflow|assistant)s?\b", re.I)
    for ln in lines:
        if verbs.search(ln):
            _take(ln)
        if len(out) >= limit:
            break
    return out


def _extract_skill_keywords(text: str) -> list[str]:
    low = text.lower()
    found: list[str] = []
    for kw in _SITE_SKILL_VOCAB:
        pat = r"(?<![a-z0-9])" + re.escape(kw.lower()) + r"(?![a-z0-9])"
        if re.search(pat, low) and kw not in found:
            found.append(kw)
    return found


def fetch_freelance_site(base_url: str = FREELANCE_SITE_URL,
                         previous: dict | None = None) -> dict | None:
    """Visible text of the freelance site (homepage + /about + /services when
    they exist) -> service lines + skill keywords. Returns `previous` on any
    failure — never raises."""
    pages_text: dict[str, str] = {}
    try:
        for path in FREELANCE_SITE_PAGES:
            url = base_url.rstrip("/") + path
            try:
                status, body, _ = _http_get(url)
            except (urllib.error.URLError, OSError) as exc:
                logger.warning("freelance_site: %s unreachable (%s)", url, exc)
                continue
            if status != 200 or not body:
                logger.info("freelance_site: %s -> HTTP %s (skipped)", url, status)
                continue
            pages_text[path] = _html_to_text(body)
        if not pages_text:
            logger.warning("freelance_site: nothing fetched — keeping previous section")
            return previous
        full = "\n".join(pages_text.values())
        home = pages_text.get("/", full)
        title_m = re.match(r"\s*(.+)", home)
        tagline = (title_m.group(1) if title_m else "")[:200]
        return {
            "url": base_url,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "pages": sorted(pages_text),
            "tagline": tagline,
            "service_lines": _extract_service_lines(full),
            "skills_keywords": _extract_skill_keywords(full),
            "visible_text_excerpt": full[:3000],
        }
    except (ValueError, TypeError) as exc:
        logger.warning("freelance_site: parse failed (%s) — keeping previous section", exc)
        return previous


def refresh_secondary_sources(out_path: Path) -> dict:
    """Merge fresh `github` + `freelance_site` sections into an existing
    profile.json (all other keys untouched). Missing file -> minimal dict.
    Each fetcher fails soft and keeps the previous section."""
    profile: dict = {}
    if out_path.exists():
        try:
            profile = json.loads(out_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("profile.json unreadable (%s) — starting from empty dict", exc)
            profile = {}
    gh = fetch_github_profile(previous=profile.get("github"))
    fs = fetch_freelance_site(previous=profile.get("freelance_site"))
    if gh is not None:
        profile["github"] = gh
    if fs is not None:
        profile["freelance_site"] = fs
    srcs = list(profile.get("raw_source_paths") or [])
    for tag in (f"github:{GITHUB_LOGIN}", FREELANCE_SITE_URL):
        if tag not in srcs:
            srcs.append(tag)
    profile["raw_source_paths"] = srcs
    out_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("secondary sources merged: github=%s repos, freelance_site=%s keywords",
                len((profile.get("github") or {}).get("repos", [])),
                len((profile.get("freelance_site") or {}).get("skills_keywords", [])))
    return profile


PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "schema_version": {"type": "string"},
        "generated_at": {"type": "string"},
        "tracks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "enum": ["A", "B"]},
                    "title": {"type": "string"},
                    "targeted_titles": {"type": "array", "items": {"type": "string"}},
                    "anti_titles": {"type": "array", "items": {"type": "string"}},
                    "contract_types": {"type": "array", "items": {"type": "string"}},
                    "min_seniority": {"type": "string"},
                },
                "required": ["id", "title", "targeted_titles", "anti_titles",
                             "contract_types", "min_seniority"],
            },
        },
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "level": {"type": "string", "enum": ["expert", "strong", "familiar"]},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "tracks": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "level", "evidence", "tracks"],
            },
        },
        "domains": {"type": "array", "items": {"type": "string"}},
        "languages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "level": {"type": "string"},
                },
                "required": ["code", "level"],
            },
        },
        "locations": {
            "type": "object",
            "properties": {
                "preferred": {"type": "array", "items": {"type": "string"}},
                "ok_remote": {"type": "array", "items": {"type": "string"}},
                "blocked_countries": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["preferred", "ok_remote", "blocked_countries"],
        },
        "hard_filters": {
            "type": "object",
            "properties": {
                "skip_title_substrings": {"type": "array", "items": {"type": "string"}},
                "skip_description_substrings": {"type": "array", "items": {"type": "string"}},
                "skip_seniority": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["skip_title_substrings", "skip_description_substrings",
                         "skip_seniority"],
        },
        "proof_points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "system": {"type": "string"},
                    "metric": {"type": "string"},
                    "track": {"type": "string"},
                },
                "required": ["system", "metric", "track"],
            },
        },
        "raw_source_paths": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["schema_version", "generated_at", "tracks", "skills", "domains",
                 "languages", "locations", "hard_filters", "proof_points",
                 "raw_source_paths"],
}


def _read_cv_pdf(path: Path) -> str:
    """Extract CV text via pypdf."""
    import pypdf

    reader = pypdf.PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except (ValueError, KeyError) as exc:
            # Per python-hardening rule #5: never bare except. Log specific
            # PDF-extraction failures so a corrupt page surfaces.
            logger.warning("CV PDF page extraction failed: %s", exc)
    return "\n".join(parts).strip()


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _collect_project_signals(limit_files: int = 12) -> list[tuple[str, str]]:
    """Pull short signal blurbs from directives/personal_workflows/*.md. These
    are the project descriptions you've ACTUALLY shipped — the ground truth for
    'what kind of builder are you'.

    Returns: list of (relative_path, first 1200 chars) pairs.
    """
    out: list[tuple[str, str]] = []
    if not DIRECTIVES_PW_DIR.exists():
        return out
    md_files = sorted(DIRECTIVES_PW_DIR.glob("*.md"))[:limit_files]
    for p in md_files:
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")[:1200]
            out.append((str(p.relative_to(WORKSPACE_ROOT)).replace("\\", "/"), txt))
        except OSError as exc:
            logger.warning("project signal read failed for %s: %s", p, exc)
    return out


def _build_prompt(cv_text: str, linkedin_md: str, brand_strategy_md: str,
                  metrics_md: str, project_signals: list[tuple[str, str]]) -> str:
    """Assemble the extractor user message. The system instruction lives in
    _SYSTEM and tells the model what schema to emit."""
    proj_block = "\n\n".join(
        f"### Project signal: {rel}\n{txt}" for rel, txt in project_signals
    )
    return (
        "Extract a structured operator profile by reading the artifacts below.\n\n"
        "Anchoring rules:\n"
        "- ONLY include skills/proof-points that appear (literally or paraphrased) "
        "in at least one source below. No hallucinated capabilities.\n"
        "- Two tracks already defined by the operator (2026-09-01 PM/PO-only "
        "rework): Track A = AI / Senior Product Manager (CDI), Track B = "
        "Product Owner incl. AI Product Owner (CDI). Engineering, consulting "
        "and freelance-builder roles are OUT of scope — do not emit "
        "engineer/consultant/developer targeted_titles. "
        "Map every skill to the track(s) it serves.\n"
        "- 'Level' calibration: expert = repeatedly shipped with measurable "
        "outcome cited; strong = shipped at least once with description; "
        "familiar = mentioned as adjacent / 'comfortable with'.\n"
        "- Languages: only EN + FR are valid for job-matching. Hindi/Bengali "
        "etc are personal but NOT job-relevant — include in `languages` but mark "
        "level honestly.\n"
        "- `proof_points`: extract 6-12 of the most concrete shipped-system + "
        "outcome pairs from the canonical metrics sheet.\n"
        "- `hard_filters`: derive from anti-signals across the artifacts "
        "(e.g. brand strategy says 'NOT chef de projet'; CV implies senior+; "
        "metrics rules out US/APAC).\n\n"
        f"=== CV (PDF, extracted) ===\n{cv_text}\n\n"
        f"=== LinkedIn profile ===\n{linkedin_md}\n\n"
        f"=== Brand strategy ===\n{brand_strategy_md}\n\n"
        f"=== Canonical metrics (single source of truth) ===\n{metrics_md}\n\n"
        f"=== Workspace project signals (shipped systems) ===\n{proj_block}\n\n"
        "Emit the profile JSON now. schema_version must be '1.0'."
    )


_SYSTEM = (
    "You are extracting a structured candidate profile for a job-matching ranker. "
    "Output STRICT JSON matching the response schema. No prose, no markdown, no "
    "explanations outside the schema. Every claim must be grounded in the source "
    "artifacts — if a skill is not in any artifact, do NOT invent it."
)


def extract_profile(
    cv_path: Path,
    out_path: Path,
    *,
    dry_run: bool = False,
) -> dict:
    """Run the extraction. Returns the profile dict; also writes to out_path."""
    if not cv_path.exists():
        raise FileNotFoundError(f"CV not found at {cv_path}")

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY missing from env. The extractor is one-shot — "
            "set it in .env and re-run (no Sheets-fallback for this script)."
        )

    logger.info("reading CV: %s", cv_path)
    cv_text = _read_cv_pdf(cv_path)
    logger.info("CV chars=%d", len(cv_text))

    linkedin = _read_text(PERSONAL_BRAND_DIR / "linkedin_profile.md")
    brand = _read_text(PERSONAL_BRAND_DIR / "brand_strategy.md")
    metrics = _read_text(PERSONAL_BRAND_DIR / "metrics_canonical.md")
    projects = _collect_project_signals()
    logger.info("loaded brand artifacts: linkedin=%d brand=%d metrics=%d projects=%d",
                len(linkedin), len(brand), len(metrics), len(projects))

    user_msg = _build_prompt(cv_text, linkedin, brand, metrics, projects)

    if dry_run:
        # No LLM call — emit the prompt + a stub profile so the wiring can be
        # tested without burning Gemini quota. Useful for unit tests.
        out = {
            "schema_version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tracks": [], "skills": [], "domains": [], "languages": [],
            "locations": {"preferred": [], "ok_remote": [], "blocked_countries": []},
            "hard_filters": {"skip_title_substrings": [],
                             "skip_description_substrings": [], "skip_seniority": []},
            "proof_points": [],
            "raw_source_paths": [
                str(cv_path.relative_to(WORKSPACE_ROOT)).replace("\\", "/"),
                "execution/personal_workflows/personal_brand/linkedin_profile.md",
                "execution/personal_workflows/personal_brand/brand_strategy.md",
                "execution/personal_workflows/personal_brand/metrics_canonical.md",
            ] + [rel for rel, _ in projects],
            "_dry_run": True,
            "_prompt_chars": len(user_msg),
        }
        out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False),
                            encoding="utf-8")
        logger.info("dry-run profile written: %s (prompt %d chars)",
                    out_path, len(user_msg))
        return out

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    cfg = types.GenerateContentConfig(
        system_instruction=_SYSTEM,
        response_mime_type="application/json",
        response_schema=PROFILE_SCHEMA,
        temperature=0.1,
        max_output_tokens=12000,
    )
    logger.info("calling gemini-2.5-flash (prompt %d chars)", len(user_msg))
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_msg,
        config=cfg,
    )
    raw = resp.text or "{}"
    try:
        profile = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Gemini returned invalid JSON: {exc}\n{raw[:500]}") from exc

    # Stamp post-hoc fields (override whatever the model produced).
    profile["schema_version"] = "1.0"
    profile["generated_at"] = datetime.now(timezone.utc).isoformat()
    profile["raw_source_paths"] = [
        str(cv_path.relative_to(WORKSPACE_ROOT)).replace("\\", "/"),
        "execution/personal_workflows/personal_brand/linkedin_profile.md",
        "execution/personal_workflows/personal_brand/brand_strategy.md",
        "execution/personal_workflows/personal_brand/metrics_canonical.md",
    ] + [rel for rel, _ in projects]

    out_path.write_text(
        json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info("profile written: %s (%d skills, %d proof_points)",
                out_path, len(profile.get("skills", [])),
                len(profile.get("proof_points", [])))
    # 2026-10-26: secondary identity sources (fail-soft, merged in place).
    return refresh_secondary_sources(out_path)


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1].strip())
    parser.add_argument("--cv", type=Path, default=DEFAULT_CV,
                        help=f"Path to CV PDF (default: {DEFAULT_CV})")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help=f"Output JSON path (default: {DEFAULT_OUT})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip the LLM call; write a stub profile.")
    parser.add_argument("--sources-only", action="store_true",
                        help="Only refresh github + freelance_site sections into "
                             "the existing profile.json (no CV / Gemini call).")
    args = parser.parse_args()

    try:
        if args.sources_only:
            refresh_secondary_sources(args.out)
        else:
            extract_profile(args.cv, args.out, dry_run=args.dry_run)
    except (FileNotFoundError, RuntimeError) as exc:
        logger.error("extraction failed: %s", exc)
        return 1
    print(f"OK -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
