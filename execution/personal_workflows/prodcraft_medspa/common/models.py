"""
models.py
description: Plain dataclasses mirroring db/schema.sql tables, with to_row()/from_row() round-trips.
inputs: dict rows from Store implementations (JSON for LocalStore, PostgREST JSON for SupabaseStore).
outputs: Dataclass instances; to_row() dicts ready for Store upsert/insert calls.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone


def now_iso() -> str:
    """UTC timestamp in ISO-8601 with a 'Z' suffix, matching Postgres timestamptz JSON rendering."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_id() -> str:
    return str(uuid.uuid4())


def _from_row(cls, row: dict):
    """Build a dataclass from a dict, ignoring unknown keys and filling defaults for missing ones."""
    known = {f.name for f in fields(cls)}
    kwargs = {k: v for k, v in row.items() if k in known}
    return cls(**kwargs)


@dataclass
class Business:
    id: str | None = None
    place_id: str = ""
    name: str = ""
    slug: str = ""
    address: str | None = None
    city: str | None = None
    suburb: str | None = None
    metro: str = ""
    state: str | None = None
    lat: float | None = None
    lng: float | None = None
    phone: str | None = None
    website_url: str | None = None
    final_url: str | None = None
    rating: float | None = None
    review_count: int | None = None
    primary_type: str | None = None
    business_status: str | None = None
    is_chain: bool = False
    drop_reason: str | None = None
    owner_name: str | None = None
    owner_first: str | None = None
    owner_email: str | None = None
    email_status: str | None = None
    email_source: str | None = None
    do_not_contact: bool = False
    created_at: str | None = None
    updated_at: str | None = None

    def to_row(self) -> dict:
        row = asdict(self)
        row["id"] = row["id"] or _new_id()
        row["created_at"] = row["created_at"] or now_iso()
        row["updated_at"] = row["updated_at"] or now_iso()
        return row

    @classmethod
    def from_row(cls, row: dict) -> "Business":
        return _from_row(cls, row)


@dataclass
class Audit:
    id: str | None = None
    business_id: str = ""
    audited_at: str | None = None
    score_version: str = "1.0"
    psi_mobile: int | None = None
    psi_desktop: int | None = None
    has_website: bool = True
    has_ssl: bool | None = None
    is_mobile_friendly: bool | None = None
    builder: str | None = None
    theme: str | None = None
    theme_year: int | None = None
    has_jquery_legacy: bool | None = None
    booking_widget: str | None = None
    has_cta_above_fold: bool | None = None
    has_analytics: bool | None = None
    footer_year: int | None = None
    vision_dated_score: int | None = None
    vision_rationale: str | None = None
    vision_model_id: str | None = None
    vision_prompt_sha256: str | None = None
    total_score: int = 0
    bucket: str = "skip"
    gaps: list = field(default_factory=list)
    screenshot_mobile_url: str | None = None
    screenshot_desktop_url: str | None = None
    raw: dict = field(default_factory=dict)

    def to_row(self) -> dict:
        row = asdict(self)
        row["id"] = row["id"] or _new_id()
        row["audited_at"] = row["audited_at"] or now_iso()
        return row

    @classmethod
    def from_row(cls, row: dict) -> "Audit":
        return _from_row(cls, row)


@dataclass
class Preview:
    id: str | None = None
    business_id: str = ""
    template_id: str = "medspa-v1"
    slug_suffix: str = ""
    subdomain_url: str = ""
    status: str = "review"
    content: dict = field(default_factory=dict)
    content_hash: str = ""
    deployed_at: str | None = None
    expires_at: str | None = None
    takedown: bool = False
    takedown_at: str | None = None
    created_at: str | None = None

    def to_row(self) -> dict:
        row = asdict(self)
        row["id"] = row["id"] or _new_id()
        row["created_at"] = row["created_at"] or now_iso()
        return row

    @classmethod
    def from_row(cls, row: dict) -> "Preview":
        return _from_row(cls, row)


@dataclass
class Outreach:
    id: str | None = None
    business_id: str = ""
    preview_id: str | None = None
    audit_id: str | None = None
    touch: int = 1
    status: str = "queued"
    template_variant: str | None = None
    gap_primary: str | None = None
    draft_subject: str | None = None
    draft_body: str | None = None
    gmail_draft_id: str | None = None
    gmail_thread_id: str | None = None
    sent_at: str | None = None
    replied_at: str | None = None
    reply_sentiment: str | None = None
    reply_excerpt: str | None = None
    next_touch_at: str | None = None
    notes: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_row(self) -> dict:
        row = asdict(self)
        row["id"] = row["id"] or _new_id()
        row["created_at"] = row["created_at"] or now_iso()
        row["updated_at"] = row["updated_at"] or now_iso()
        return row

    @classmethod
    def from_row(cls, row: dict) -> "Outreach":
        return _from_row(cls, row)


@dataclass
class Deal:
    id: str | None = None
    business_id: str = ""
    tier: str = "starter"
    setup_price: float = 0.0
    mrr: float = 0.0
    contract_signed_at: str | None = None
    deposit_paid_at: str | None = None
    baseline_online_bookings_30d: int | None = None
    current_booking_tool: str | None = None
    live_at: str | None = None
    bookings_60d: int | None = None
    guarantee_met: bool | None = None
    balance_paid_at: str | None = None
    care_plan_active: bool = False
    notes: str | None = None
    created_at: str | None = None

    def to_row(self) -> dict:
        row = asdict(self)
        row["id"] = row["id"] or _new_id()
        row["created_at"] = row["created_at"] or now_iso()
        return row

    @classmethod
    def from_row(cls, row: dict) -> "Deal":
        return _from_row(cls, row)


@dataclass
class MetroStats:
    id: str | None = None
    metro: str = ""
    sampled: int = 0
    qualified: int = 0
    pct_qualified: float = 0.0
    ci_low: float = 0.0
    ci_high: float = 0.0
    score_version: str = "1.0"
    measured_at: str | None = None

    def to_row(self) -> dict:
        row = asdict(self)
        row["id"] = row["id"] or _new_id()
        row["measured_at"] = row["measured_at"] or now_iso()
        return row

    @classmethod
    def from_row(cls, row: dict) -> "MetroStats":
        return _from_row(cls, row)
