"""
config.py
description: Repo-root bootstrap, .env loading, and typed Settings for the ProdCraft med-spa pipeline.
inputs: env vars listed in CONTRACTS.md ("Secrets only via env"); no CLI args (imported, not run).
outputs: Settings dataclass instance from bootstrap(); .tmp/prodcraft_medspa/ created on demand.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

# execution/personal_workflows/prodcraft_medspa/common/config.py -> repo root is 5 parents up.
REPO_ROOT = Path(__file__).resolve().parents[4]

# Env var names required (or optional-with-caveat) per pipeline stage, per CONTRACTS.md.
# Orchestrators use this to fail fast with a clear message before a stage runs live.
REQUIRED_BY_STAGE: dict[str, list[str]] = {
    "discovery": ["GOOGLE_PLACES_API_KEY"],
    # PAGESPEED_API_KEY is optional — PSI works keyless at low volume — but listed
    # here so `doctor.py`-style checks can warn (not fail) when it's unset.
    "audit": ["PAGESPEED_API_KEY", "ANTHROPIC_API_KEY"],
    "enrich": [
        "APOLLO_API_KEY",
        "FINDYMAIL_API_KEY|HUNTER_API_KEY",
        "MILLION_VERIFIER_API_KEY",
    ],
    "preview": ["CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID", "R2_BUCKET"],
    "outreach": ["GMAIL_CREDENTIALS_JSON", "GMAIL_TOKEN_JSON", "ANTHROPIC_API_KEY"],
    "store": ["SUPABASE_URL", "SUPABASE_SERVICE_KEY"],
    "notify": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
}

# Every env var named anywhere in CONTRACTS.md's "Secrets only via env" list,
# mirrored 1:1 as Settings fields below.
_ENV_VAR_NAMES = [
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "SUPABASE_DB_URL",
    "GOOGLE_PLACES_API_KEY",
    "PAGESPEED_API_KEY",
    "ANTHROPIC_API_KEY",
    "APOLLO_API_KEY",
    "FINDYMAIL_API_KEY",
    "HUNTER_API_KEY",
    "MILLION_VERIFIER_API_KEY",
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_ACCOUNT_ID",
    "R2_BUCKET",
    "PREVIEW_BASE_DOMAIN",
    "GMAIL_CREDENTIALS_JSON",
    "GMAIL_TOKEN_JSON",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "GOOGLE_SHEETS_MIRROR_ID",
    "DASHBOARD_USER",
    "DASHBOARD_PASS",
    "PRODCRAFT_STORE",
    "PRODCRAFT_ENV",
]

_DEFAULTS = {
    "R2_BUCKET": "prodcraft-previews",
    "PREVIEW_BASE_DOMAIN": "preview.prodcraft.fyi",
}


@dataclass
class Settings:
    """Typed view over the env vars the pipeline reads. Unset vars are None."""

    SUPABASE_URL: str | None = None
    SUPABASE_SERVICE_KEY: str | None = None
    SUPABASE_DB_URL: str | None = None
    GOOGLE_PLACES_API_KEY: str | None = None
    PAGESPEED_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    APOLLO_API_KEY: str | None = None
    FINDYMAIL_API_KEY: str | None = None
    HUNTER_API_KEY: str | None = None
    MILLION_VERIFIER_API_KEY: str | None = None
    CLOUDFLARE_API_TOKEN: str | None = None
    CLOUDFLARE_ACCOUNT_ID: str | None = None
    R2_BUCKET: str | None = "prodcraft-previews"
    PREVIEW_BASE_DOMAIN: str | None = "preview.prodcraft.fyi"
    GMAIL_CREDENTIALS_JSON: str | None = None
    GMAIL_TOKEN_JSON: str | None = None
    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_CHAT_ID: str | None = None
    GOOGLE_SHEETS_MIRROR_ID: str | None = None
    DASHBOARD_USER: str | None = None
    DASHBOARD_PASS: str | None = None
    PRODCRAFT_STORE: str | None = None
    PRODCRAFT_ENV: str | None = None

    REPO_ROOT: Path = field(default_factory=lambda: REPO_ROOT)
    TMP: Path = field(default_factory=lambda: REPO_ROOT / ".tmp" / "prodcraft_medspa")

    @property
    def is_mock(self) -> bool:
        """True when no live credentials are configured at all (best-effort heuristic).

        Individual scripts should prefer their own explicit --mock flag; this
        property is a convenience for code paths without direct CLI access.
        """
        return not any(
            [
                self.GOOGLE_PLACES_API_KEY,
                self.ANTHROPIC_API_KEY,
                self.APOLLO_API_KEY,
                self.MILLION_VERIFIER_API_KEY,
            ]
        )

    @property
    def store_kind(self) -> str:
        """'local' or 'supabase', from PRODCRAFT_STORE env, default 'local'."""
        kind = (self.PRODCRAFT_STORE or "local").strip().lower()
        return kind if kind in ("local", "supabase") else "local"

    def missing_for_stage(self, stage: str) -> list[str]:
        """Return the subset of REQUIRED_BY_STAGE[stage] that resolve to nothing.

        Entries containing '|' are OR-groups (e.g. FINDYMAIL_API_KEY|HUNTER_API_KEY);
        the group is "missing" only if every alternative is unset.
        """
        missing: list[str] = []
        for name in REQUIRED_BY_STAGE.get(stage, []):
            alts = name.split("|")
            if not any(getattr(self, alt, None) for alt in alts):
                missing.append(name)
        return missing


def bootstrap() -> Settings:
    """Add repo root to sys.path, load .env, return populated Settings.

    Safe to call multiple times (idempotent path insert, dotenv reload).
    """
    root_str = str(REPO_ROOT)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    try:
        from dotenv import load_dotenv  # type: ignore[import-untyped]

        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass  # python-dotenv not installed; env vars must already be set (e.g. cloud sessions)

    import os

    values: dict = {}
    for name in _ENV_VAR_NAMES:
        raw = os.environ.get(name)
        values[name] = raw if raw not in (None, "") else _DEFAULTS.get(name)

    settings = Settings(**values)
    settings.TMP.mkdir(parents=True, exist_ok=True)
    return settings
