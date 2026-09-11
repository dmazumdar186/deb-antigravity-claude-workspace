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
# Sonnet 5 verified live against GET /v1/models on 2026-08-19. Judgement roles
# moved to Fable 5 on 2026-08-27 (operator rule: everything that is not mundane
# execution is Fable 5). L10 stays on Sonnet 5: it is a per-candidate rubric
# pass, which model-tier.md Exhibit D classes as bulk execution. Cost of the
# move, for a 38-candidate shortlist (run.py: 24 + 14): L8 + L11 = ~76 Fable 5
# calls at ~3k in / ~2k out each = ~$0.13 per call = ~$10 (~EUR 9) per full run,
# vs ~EUR 4.5 on Opus 5. The RunConfig ceiling is unchanged and trips earlier.
# ---------------------------------------------------------------------------

MODEL_EXTRACT = "claude-sonnet-5"   # L5 evidence extraction (high volume)
MODEL_PARSE = "claude-sonnet-5"     # L1 requisition parsing
MODEL_JUDGE = "claude-fable-5-1"    # L8 adversarial + tiering (judgement)
MODEL_MOVABILITY = "claude-sonnet-5"  # L10 per-candidate rubric scoring = bulk execution (model-tier.md Exhibit D)
MODEL_MESSAGE = "claude-fable-5-1"  # L11 -- goes out under Gaia's name (judgement)
# 2026-09-01: MODEL_JUDGE / MODEL_MESSAGE moved claude-fable-5 -> claude-fable-5-1.

# Pricing per MTok (USD), from ~/.claude/rules/model-tier.md, verified
# 2026-08-27. Converted to EUR for all operator-facing output.
USD_TO_EUR = 0.92
PRICING: dict[str, dict[str, float]] = {
    # Kept: superseded by claude-fable-5-1 on 2026-09-01, but historical run
    # records still cost-resolve against this row.
    "claude-fable-5": {
        "input": 10.00, "cache_write": 12.50, "cache_read": 1.00, "output": 50.00
    },
    # verified 2026-09-01: same input/output as fable-5; cache_read dropped to
    # 0.25 (0.025x input, not the usual 0.1x).
    "claude-fable-5-1": {
        "input": 10.00, "cache_write": 12.50, "cache_read": 0.25, "output": 50.00
    },
    "claude-opus-5": {
        "input": 5.00, "cache_write": 6.25, "cache_read": 0.50, "output": 25.00
    },
    "claude-sonnet-5": {
        "input": 2.00, "cache_write": 2.50, "cache_read": 0.20, "output": 10.00
    },
}


@dataclass
class RunConfig:
    # 2026-09-11: env override so a new run never writes over a delivered
    # campaign's deliverables/ folder (the render stage clobbered the 20 Aug
    # dossier once). Set GAIA_CAMPAIGN_ID=gaia-2026-09-14 for the Monday run.
    campaign_id: str = field(default_factory=lambda: (os.environ.get("GAIA_CAMPAIGN_ID") or "gaia-2026-08-20").strip())
    # Hard ceiling on LLM SPEND ONLY. The run aborts rather than silently
    # overspending (SPEC.md section 14 "Cost ceiling").
    #
    # Scope, stated so nobody reads more into this number than it carries:
    # it covers every call through providers.call_role plus the OCR
    # transcription path. It does NOT cover Firecrawl renders (core/cache.py),
    # Prospeo enrichment (layers/contact.py) or Serper searches (sources/*) --
    # those are paid too, and each is bounded only by its own provider-side
    # quota. Prospeo at least reports its remaining credits via
    # contact.account_credits(); the other two do not.
    #
    # This ceiling spent its first three sessions being enforced nowhere at
    # all, so the failure mode it guards against is a real one: a declared
    # limit that quietly does nothing is worse than no limit, because it stops
    # anyone from looking.
    max_cost_eur: float = 12.0
    # Cumulative, cross-run ceiling (execution/core/providers.py's persistent
    # logs/spend_ledger.jsonl). The operator has exactly $30 of Anthropic
    # credit, period -- a per-run ceiling resets every run and cannot protect
    # a fixed lifetime balance. 22.0 EUR ~= $24 at the USD_TO_EUR rate below,
    # leaving headroom for FX drift and any spend this ledger does not see
    # (Firecrawl, Prospeo, Serper -- see the max_cost_eur docstring above).
    # Enforced in the same place as max_cost_eur: core.providers.call_role
    # and core.ocr's Anthropic transcription path.
    # 2026-09-11: operator holds $30 of credit; the Console spend limit is
    # the hard stop; cumulative EUR 15.68 after the first full runs, deepen
    # round 2 windowed.
    max_cost_eur_total: float = 25.0
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
    # 2026-09-10 -- client promise on the call: sourced candidates land in
    # Recruit CRM so consultants and Maddie (their inbound screening agent)
    # take over. role_id -> Recruit CRM job slug/id. Empty by default: an
    # empty mapping means run.py's sync_crm stage still creates/updates
    # candidate records but SKIPS attach_to_job for every candidate (logged,
    # not silently dropped), because a wrong job id would be a live write to
    # the wrong requisition and there is no way to detect that from here.
    # Fill in after `run.py --stage sync_crm` (dry-run) or
    # RecruitCRMClient.list_jobs() confirms the correct slugs.
    recruit_crm_job_ids: dict[str, str] = field(default_factory=dict)
    # 2026-09-10 -- RADAR_CONTRACTS.md section E. A ContactRecord's evidence
    # is "stale" once it is older than this many days (layers/contact.py sets
    # ContactRecord.evidence_age_days / .stale from it); integrations.
    # recruit_crm.sync_delivery blocks a stale record from CRM sync unless
    # called with allow_stale=True (wired to a future --allow-stale CLI flag).
    max_evidence_age_days: int = 30
    # Env var name (looked up via core.config.secret, required=False) holding
    # the Slack/WhatsApp-compatible webhook URL core/alerts.py posts to. A
    # name rather than the URL itself so ops can repoint it without a code
    # change; core/alerts.alert() no-ops with a log line when it is unset.
    alert_webhook_env: str = "ALERT_WEBHOOK_URL"
    # 2026-09-11 -- core/ocr.py's free local OCR path (rapidocr-onnxruntime)
    # caps how many pages of one scanned PDF it will rasterise and read; a
    # runaway page count on a mis-sized bundle should not stall a run for
    # minutes on CPU-only inference. Independent of _MAX_PAGES (the paid
    # path's hard cap on what is even sent).
    ocr_max_pages: int = 40
    # 2026-09-11 -- when True, core.ocr.transcribe_pdf never falls through to
    # a paid model (Anthropic or Gemini) if the free local OCR path fails or
    # is unavailable; the document is simply left unrecovered. For a fixed,
    # near-exhausted Anthropic balance where the operator wants OCR spend at
    # zero, full stop, rather than falling back to the paid readers.
    ocr_local_only: bool = False
    # 2026-09-11 -- core.cache.fetch_rendered's middle rung: when no
    # FIRECRAWL_API_KEY is present, render JS pages locally with Playwright +
    # Chromium (core/render_local.py) before falling back to raw HTTP. Set
    # False to skip straight to the raw-HTTP fallback (e.g. a sandbox with no
    # Chromium binary at all).
    render_local: bool = True
    # 2026-09-11 -- stage_harvest_discovery (run.py), RADAR_CONTRACTS.md
    # section A. Free/cheap people-discovery via sources.registry providers,
    # ahead of the paid r1/r2 harvests. Per-query result cap passed straight
    # through as SourceQuery.limit.
    discovery_limit: int = 60
    # Provider names run for stage_harvest_discovery, looked up via
    # sources.registry.get_provider (imported first if not yet registered --
    # see run.py's _LICENSED_PROVIDER_MODULES). A provider that raises
    # ProviderNotConfigured (missing API key) is skipped with a log line, not
    # a stage failure -- same contract as run_coverage_test.
    discovery_providers: list[str] = field(default_factory=lambda: ["serper_people"])
    # Total query budget across the whole stage_harvest_discovery run, summed
    # across every role x provider combination. serper_people alone issues 3
    # queries per (term, location) pair, so this is the knob that actually
    # bounds spend/rate-limit exposure when ROLES x terms x locations grows.
    discovery_max_queries: int = 120
    # 2026-09-11 -- run.py's stage_deepen_near_misses. Gate ids that count as
    # an "evidence gap" rather than a real disqualification: a person whose
    # SET of failed gates is a subset of this list is a near-miss worth a
    # second, targeted search. Chartership and years-of-experience are both
    # things a search snippet routinely omits even for a genuinely qualified
    # person (RADAR scope update 2026-09-11: 45 Role 1 + 10 Role 2 candidates
    # failed exactly this pair together). Never add "discipline",
    # "seniority_ceiling", "not_client" or "located_ie" here -- those are
    # real exclusions, not evidence gaps, and deepening them would spend
    # search budget trying to explain away a correct rejection.
    deepen_gates: list[str] = field(
        default_factory=lambda: ["chartered", "seniority"]
    )
    # Cap on how many near-miss candidates stage_deepen_near_misses will
    # spend search budget on, richest-evidence-first (same shape as
    # stage_deepen_r1's cap of 30 gate-passers).
    # 2026-09-11: raised 60 -> 200 now that fetched-page extraction is
    # windowed (see deepen_window_chars) rather than sending whole pages to
    # the LLM -- the EUR 5.98-for-60-people run that justified the old cap
    # was paying for full-page extraction, not for the search itself.
    deepen_near_miss_cap: int = 200
    # Total Serper query budget for stage_deepen_near_misses, summed across
    # every near-miss candidate (up to 3 queries each -- see
    # stage_deepen_near_misses' docstring). Serper is free but rate-limited;
    # this is a sanity ceiling, not a cost control.
    # 2026-09-11: raised 150 -> 500 alongside deepen_near_miss_cap -- Serper's
    # free tier is 2,500 queries/month and ~370 had been used so far, leaving
    # ample headroom for the larger near-miss pool.
    deepen_max_queries: int = 500
    # 2026-09-11 -- stage_deepen_near_misses windows a fetched page to this
    # many characters either side of the first co-occurrence of the person's
    # forename+surname (layers.extract.window_around_names) before it is sent
    # to the L5 extractor, instead of the whole page. The full page stays in
    # docs.jsonl untouched -- L6's quote validator still checks every claim
    # against the complete cached text, so a quote just outside the window
    # still validates; only the (paid) extraction INPUT shrinks. Sized well
    # above the 12-400 char quote range so a real answer near either name is
    # never cut off mid-sentence.
    deepen_window_chars: int = 2500

    @property
    def deliverables_dir(self):
        """deliverables/<campaign> -- 'gaia-2026-09-14' maps to the folder
        convention 'gaia_2026-09-14'. Derived from campaign_id so a new run can
        never write over a delivered campaign (2026-09-11 clobber)."""
        slug = self.campaign_id.replace("gaia-", "gaia_", 1)
        return WORKSPACE_ROOT / "deliverables" / slug

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

# Deployed and verified live 2026-08-19 (Cloudflare Pages project
# "gaia-privacy"). Every outreach draft cites this URL and render.py refuses
# to emit outreach if it does not return 200, so it must be the address that
# actually resolves today rather than the one we would prefer.
#
# privacy.prodcraft.fyi IS bound to the same project and is the intended
# address, but it sits at status "pending": the Pages custom-domain binding
# needs a CNAME in the prodcraft.fyi zone, and the API token in use has Pages
# permissions but not Zone:Edit. Once that record exists and the domain goes
# active, change this one line back and re-run `--stage messages --force`
# plus the renderer.
PRIVACY_NOTICE_URL = "https://gaia-privacy.pages.dev/gaia-candidate-notice"

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
