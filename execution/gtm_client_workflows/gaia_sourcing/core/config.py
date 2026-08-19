"""Config, secrets and run-manifest handling for the Gaia sourcing pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Workspace root = five levels up from this file
# (gaia_sourcing/core/config.py -> gaia_sourcing -> gtm_client_workflows
#  -> execution -> workspace root)
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
PKG_ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path | None = None) -> dict[str, str]:
    """Minimal .env reader. Does NOT mutate os.environ by default.

    We deliberately avoid python-dotenv's override semantics: a blank value
    already present in os.environ must not shadow the .env value.
    See ~/.claude/rules/environ-not-copy-copy.md for the related hazard.
    """
    path = path or (WORKSPACE_ROOT / ".env")
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


_ENV = load_dotenv()


def secret(name: str, required: bool = True) -> str:
    """Fetch a secret from .env first, then os.environ.

    Empty strings are treated as absent (the load_dotenv override=False trap).
    """
    val = (_ENV.get(name) or os.environ.get(name) or "").strip()
    if not val and required:
        raise RuntimeError(
            f"{name} missing. Add it to {WORKSPACE_ROOT / '.env'} and re-run."
        )
    return val


# ---------------------------------------------------------------------------
# Models -- full names pinned per ~/.claude/rules/model-tier.md.
# Never use bare aliases; they drift across providers and CLI versions.
# Verified live against GET /v1/models on 2026-08-19.
# ---------------------------------------------------------------------------

MODEL_EXTRACT = "claude-sonnet-5"   # L5 evidence extraction (high volume)
MODEL_PARSE = "claude-sonnet-5"     # L1 requisition parsing
MODEL_JUDGE = "claude-opus-5"       # L8 adversarial + tiering (judgement)
MODEL_MOVABILITY = "claude-opus-5"  # L10
MODEL_MESSAGE = "claude-opus-5"     # L11 -- goes out under Gaia's name

# Pricing per MTok (USD), from ~/.claude/rules/model-tier.md, verified
# 2026-08-12. Converted to EUR for all operator-facing output.
USD_TO_EUR = 0.92
PRICING: dict[str, dict[str, float]] = {
    "claude-opus-5": {
        "input": 5.00, "cache_write": 6.25, "cache_read": 0.50, "output": 25.00
    },
    "claude-sonnet-5": {
        "input": 2.00, "cache_write": 2.50, "cache_read": 0.20, "output": 10.00
    },
}


@dataclass
class RunConfig:
    campaign_id: str = "gaia-2026-08-20"
    # Hard cost ceiling. The run aborts rather than silently overspending
    # (SPEC.md section 14 "Cost ceiling").
    max_cost_eur: float = 30.0
    # L6 drop-rate alarm. Above this, the L5 prompt is wrong -- see section 7.
    max_drop_rate: float = 0.15
    request_timeout_s: int = 60
    max_concurrency: int = 6
    per_host_delay_s: float = 0.4
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
    off_limits: list[str] = field(
        default_factory=lambda: ["tobin", "atkinsrealis", "atkinsréalis", "atkins realis"]
    )

    @property
    def run_dir(self) -> Path:
        return PKG_ROOT / "run" / self.campaign_id

    def layer_dir(self, name: str) -> Path:
        d = self.run_dir / name
        d.mkdir(parents=True, exist_ok=True)
        return d


CONFIG = RunConfig()

# ---------------------------------------------------------------------------
# GDPR strings. INJECTED VERBATIM -- never LLM-generated (SPEC.md I6, s12).
# The URL is a placeholder until the Cloudflare Pages notice is deployed;
# render.py hard-fails if it is still the placeholder at delivery time.
# ---------------------------------------------------------------------------

PRIVACY_NOTICE_URL = "https://privacy.prodcraft.fyi/gaia-candidate-notice"

GDPR_ART14_NOTICE = (
    "How we got your details: Gaia Talent Ltd sourced your professional "
    "information from publicly available sources (including public planning "
    "records and your employer's published team pages). We process it under "
    "legitimate interest (GDPR Art. 6(1)(f)) to contact you about a relevant "
    "engineering role. Full privacy notice, including your rights and our "
    "retention period: " + PRIVACY_NOTICE_URL
)

OPT_OUT_LINE = (
    "If you would rather not hear from us, reply with the word STOP and we "
    "will erase your details and not contact you again."
)
