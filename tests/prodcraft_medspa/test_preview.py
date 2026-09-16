"""
test_preview.py
description: Tests for the preview package — business.json assembly, content_lint, extract_services
             fallback, R2 SigV4/MockR2, publish/extend/takedown, and a mock end-to-end build_preview run.
inputs: N/A (pytest); uses local_store/fixtures_root from conftest.py and this file's own fixtures.
outputs: N/A (pytest).
"""

from __future__ import annotations

import json

import pytest

from execution.personal_workflows.prodcraft_medspa.common import slug as slug_module
from execution.personal_workflows.prodcraft_medspa.preview import (
    build_preview,
    content_lint,
    extract_services,
    publish,
    r2,
    takedown,
)
from tests.prodcraft_medspa.conftest import PKG_ROOT

PROMPTS_FIXTURES_ROOT = PKG_ROOT / "prompts" / "fixtures"
PREVIEW_FIXTURES = PKG_ROOT / "preview" / "fixtures"


# ---------------------------------------------------------------------------
# Shared seed data
# ---------------------------------------------------------------------------


def _seed_glow(store):
    business = store.upsert_business(
        {
            "place_id": "place-glow-1",
            "name": "Glow Aesthetics",
            "slug": "glow-aesthetics",
            "metro": "Chicago North Shore",
            "city": "Winnetka",
            "state": "IL",
            "address": "123 Green Bay Rd, Winnetka, IL 60093",
            "phone": "(847) 555-0100",
            "rating": 4.8,
            "review_count": 132,
            "primary_type": "spa",
            "is_chain": False,
            "do_not_contact": False,
            "email_status": "deliverable",
        }
    )
    audit = store.insert_audit(
        {
            "business_id": business["id"],
            "bucket": "qualified",
            "total_score": 60,
            "raw": {
                "site_text": (
                    "Glow Aesthetics offers Botox, dermal fillers, HydraFacial, laser hair removal, "
                    "and chemical peels in a calm space."
                ),
                "regularOpeningHours": {
                    "weekdayDescriptions": [
                        "Monday: 9:00 AM – 6:00 PM",
                        "Tuesday: 9:00 AM – 6:00 PM",
                        "Wednesday: 9:00 AM – 6:00 PM",
                        "Thursday: 9:00 AM – 7:00 PM",
                        "Friday: 9:00 AM – 5:00 PM",
                        "Saturday: 10:00 AM – 3:00 PM",
                        "Sunday: Closed",
                    ]
                },
            },
        }
    )
    return business, audit


def _run_build(store, business, tmp_path, *, force=False, email_policy="deliverable_only"):
    stats = {
        "llm_cost_usd": 0.0,
        "built": 0,
        "uploaded": 0,
        "published": 0,
        "lint_failed": 0,
        "skipped_unchanged": 0,
    }
    build_preview._process_business(
        business,
        store=store,
        mock=True,
        skip_build=True,
        force=force,
        template_dir=build_preview.TEMPLATE_DIR,
        base_domain="preview.prodcraft.fyi",
        tmp_root=tmp_path,
        stats=stats,
        email_policy=email_policy,
    )
    return stats


def _valid_business() -> dict:
    return {
        "name": "Glow Aesthetics",
        "google_maps_url": "https://maps.google.com/?cid=123",
        "tagline": "Book your next treatment in under a minute",
        "phone": "(847) 555-0100",
        "services": [
            {"name": "Botox", "blurb": "Schedule a consultation.", "icon": "syringe"},
            {"name": "Facials", "blurb": "Book a visit.", "icon": "sparkle"},
            {"name": "Peels", "blurb": "Come in for a look.", "icon": "leaf"},
        ],
        "hours": [
            {"day": d, "open": "9:00 AM", "close": "5:00 PM"}
            for d in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
        ],
        "preview": {
            "remove_url": "https://x.preview.prodcraft.fyi/remove",
            "watermark": content_lint.watermark_for("Glow Aesthetics"),
        },
    }


# ---------------------------------------------------------------------------
# business.json assembly
# ---------------------------------------------------------------------------


def test_assemble_business_json_matches_expected_fixture(local_store):
    business, audit = _seed_glow(local_store)
    services_result = extract_services.extract_services(
        business, audit, mock=True, fixtures_root=PROMPTS_FIXTURES_ROOT
    )
    slug_suffix = slug_module.random_suffix()
    host = slug_module.preview_host(business["slug"], slug_suffix, "preview.prodcraft.fyi")

    actual = build_preview.assemble_business_json(
        business,
        audit,
        services_result,
        slug=business["slug"],
        slug_suffix=slug_suffix,
        host=host,
        expires_at="2026-10-10",
    )

    expected = json.loads((PREVIEW_FIXTURES / "business_expected_glow.json").read_text(encoding="utf-8"))
    expected = {k: v for k, v in expected.items() if not k.startswith("_")}
    expected["preview"] = {k: v for k, v in expected["preview"].items() if not k.startswith("_")}

    actual_comparable = dict(actual)
    actual_comparable.pop("slug_suffix", None)
    actual_preview = dict(actual_comparable["preview"])
    actual_preview.pop("expires_at", None)
    actual_preview.pop("remove_url", None)
    actual_comparable["preview"] = actual_preview

    assert actual_comparable == expected
    assert actual["slug_suffix"] == slug_suffix
    assert actual["preview"]["expires_at"] == "2026-10-10"
    assert actual["preview"]["remove_url"] == f"https://{host}/remove"


def test_slug_suffix_reused_from_existing_preview(local_store):
    business, _audit = _seed_glow(local_store)
    local_store.upsert_preview(
        {
            "business_id": business["id"],
            "content_hash": "hash1",
            "slug_suffix": "abc123",
            "created_at": "2026-01-01T00:00:00Z",
        }
    )
    existing = build_preview.find_previews_for_business(local_store, business["id"])
    existing_sorted = sorted(existing, key=lambda p: p.get("created_at") or "")
    reused = existing_sorted[-1]["slug_suffix"]
    assert reused == "abc123"


def test_content_hash_ignores_expires_at_but_not_other_fields():
    base = {
        "schema_version": "1.0",
        "name": "X",
        "preview": {"expires_at": "2026-01-01", "remove_url": "u", "watermark": "w"},
    }
    changed_expiry = json.loads(json.dumps(base))
    changed_expiry["preview"]["expires_at"] = "2099-12-31"
    changed_name = json.loads(json.dumps(base))
    changed_name["name"] = "Y"

    h1 = build_preview.content_hash(base)
    h2 = build_preview.content_hash(changed_expiry)
    h3 = build_preview.content_hash(changed_name)

    assert h1 == h2
    assert h1 != h3


# ---------------------------------------------------------------------------
# Hours parsing
# ---------------------------------------------------------------------------


def test_hours_examples_fixture():
    examples = json.loads((PREVIEW_FIXTURES / "hours_examples.json").read_text(encoding="utf-8"))
    for name, case in examples.items():
        got = build_preview.parse_weekday_descriptions(case["weekday_descriptions"])
        assert got == case["expected"], name


# ---------------------------------------------------------------------------
# content_lint — one rule at a time
# ---------------------------------------------------------------------------


def test_lint_passes_clean_business():
    assert content_lint.lint(_valid_business()) == []


def test_lint_catches_forbidden_term():
    b = _valid_business()
    b["tagline"] = "Guaranteed results in one visit"
    assert any("forbidden term" in v for v in content_lint.lint(b))


def test_lint_catches_dollar_amount():
    b = _valid_business()
    b["services"][0]["blurb"] = "Only $99 today"
    assert any("dollar amount" in v for v in content_lint.lint(b))


def test_lint_catches_logo_word():
    b = _valid_business()
    b["tagline"] = "See our logo design"
    assert any("logo" in v for v in content_lint.lint(b))


def test_lint_catches_disallowed_url():
    b = _valid_business()
    b["tagline"] = "Visit https://evil.example.com now"
    assert any("disallowed URL" in v for v in content_lint.lint(b))


def test_lint_catches_services_count():
    b = _valid_business()
    b["services"] = b["services"][:2]
    assert any("services count" in v for v in content_lint.lint(b))


def test_lint_catches_tagline_too_long():
    b = _valid_business()
    b["tagline"] = " ".join(["word"] * 10)
    assert any("tagline word count" in v for v in content_lint.lint(b))


def test_lint_catches_phone_format():
    b = _valid_business()
    b["phone"] = "847-555-0100"
    assert any("phone format" in v for v in content_lint.lint(b))


def test_lint_catches_hours_count():
    b = _valid_business()
    b["hours"] = b["hours"][:5]
    assert any("hours has" in v for v in content_lint.lint(b))


def test_lint_catches_watermark_mismatch():
    b = _valid_business()
    b["preview"]["watermark"] = "not the right watermark"
    assert any("watermark" in v for v in content_lint.lint(b))


# ---------------------------------------------------------------------------
# extract_services fallback
# ---------------------------------------------------------------------------


def test_extract_services_fallback_when_too_few_valid(tmp_path):
    fixtures_root = tmp_path / "fixtures"
    (fixtures_root / "llm").mkdir(parents=True)
    (fixtures_root / "llm" / "extract_services.txt").write_text(
        json.dumps(
            {
                "services": [
                    {
                        "name": "Botox / Neuromodulators",
                        "blurb": "Schedule a consultation to see if it's right for you.",
                        "icon": "syringe",
                    }
                ],
                "tagline": "Book now.",
            }
        ),
        encoding="utf-8",
    )
    business = {"name": "Test Spa", "primary_type": "spa"}
    result = extract_services.extract_services(business, None, mock=True, fixtures_root=fixtures_root)

    assert result["used_fallback"] is True
    assert 3 <= len(result["services"]) <= 8
    assert {s["name"] for s in result["services"]}.issubset(extract_services.ALLOWED_SERVICES)
    assert {s["icon"] for s in result["services"]}.issubset(extract_services.ALLOWED_ICONS)


def test_extract_services_fallback_on_malformed_json(tmp_path):
    fixtures_root = tmp_path / "fixtures"
    (fixtures_root / "llm").mkdir(parents=True)
    (fixtures_root / "llm" / "extract_services.txt").write_text("not json at all", encoding="utf-8")
    business = {"name": "Test Salon", "primary_type": "beauty_salon"}
    result = extract_services.extract_services(business, None, mock=True, fixtures_root=fixtures_root)

    assert result["used_fallback"] is True
    assert len(result["services"]) == 4
    assert result["tagline"] == extract_services._DEFAULT_TAGLINE


def test_extract_services_uses_llm_output_when_valid():
    business = {"name": "Glow Aesthetics", "primary_type": "spa"}
    result = extract_services.extract_services(
        business, None, mock=True, fixtures_root=PROMPTS_FIXTURES_ROOT
    )
    assert result["used_fallback"] is False
    assert len(result["services"]) == 5
    assert result["tagline"] == "Book your next Glow visit in under a minute."


# ---------------------------------------------------------------------------
# R2 SigV4 + MockR2
# ---------------------------------------------------------------------------


def test_sigv4_selftest_deterministic_and_headers():
    result = r2._sigv4_selftest()
    assert result["deterministic"] is True
    assert result["has_expected_headers"] is True
    assert result["authorization"].startswith(
        "AWS4-HMAC-SHA256 Credential=AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request"
    )


def test_mock_r2_upload_list_delete(tmp_path):
    client = r2.MockR2(root=tmp_path / "bucket")
    client.upload_bytes("previews/abc/index.html", b"<html></html>")
    client.upload_bytes("previews/abc/robots.txt", b"User-agent: *")

    keys = client.list_objects("previews/abc")
    assert len(keys) == 2

    deleted = client.delete_prefix("previews/abc")
    assert deleted == 2
    assert client.list_objects("previews/abc") == []


def test_mock_r2_blocks_path_traversal(tmp_path):
    client = r2.MockR2(root=tmp_path / "bucket")
    with pytest.raises(ValueError):
        client.upload_bytes("../../etc/passwd", b"x")


# ---------------------------------------------------------------------------
# Mock end-to-end build_preview
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# email_policy eligibility (build instructions item 2)
# ---------------------------------------------------------------------------


def test_eligibility_deliverable_only_rejects_unverified():
    business = {"do_not_contact": False, "email_status": "unverified"}
    audit = {"bucket": "qualified"}
    assert build_preview.eligibility_reason(business, audit) == "email_not_deliverable"
    assert build_preview.eligibility_reason(business, audit, email_policy="deliverable_only") == "email_not_deliverable"


def test_eligibility_allow_unverified_accepts_unverified_but_not_undeliverable():
    audit = {"bucket": "qualified"}
    unverified = {"do_not_contact": False, "email_status": "unverified"}
    assert build_preview.eligibility_reason(unverified, audit, email_policy="allow_unverified") is None

    undeliverable = {"do_not_contact": False, "email_status": "undeliverable"}
    assert build_preview.eligibility_reason(undeliverable, audit, email_policy="allow_unverified") == "email_not_deliverable"

    deliverable = {"do_not_contact": False, "email_status": "deliverable"}
    assert build_preview.eligibility_reason(deliverable, audit, email_policy="allow_unverified") is None


def test_build_preview_allow_unverified_builds_an_unverified_email_row(local_store, tmp_path):
    business, _audit = _seed_glow(local_store)
    local_store.upsert_business({"id": business["id"], "place_id": business["place_id"], "email_status": "unverified"})
    business = local_store.get_business(business["id"])

    stats_default = _run_build(local_store, business, tmp_path, email_policy="deliverable_only")
    assert stats_default["built"] == 0  # deliverable_only still rejects it

    stats_allow = _run_build(local_store, business, tmp_path, email_policy="allow_unverified")
    assert stats_allow["built"] == 1

    preview = build_preview.find_previews_for_business(local_store, business["id"])[0]
    assert preview["email_policy"] == "allow_unverified"
    assert "email_policy" not in preview["content"]  # never leaks into the customer-visible business.json


def test_build_preview_mock_end_to_end_creates_review_preview(local_store, tmp_path):
    business, _audit = _seed_glow(local_store)
    stats = _run_build(local_store, business, tmp_path)

    assert stats["built"] == 1
    assert stats["uploaded"] == 1
    assert stats["published"] == 1
    assert stats["lint_failed"] == 0

    previews = build_preview.find_previews_for_business(local_store, business["id"])
    assert len(previews) == 1
    preview = previews[0]
    assert preview["status"] == "review"
    assert preview["takedown"] is False
    assert preview["content"]["schema_version"] == "1.0"

    host = preview["subdomain_url"].split("//", 1)[-1]
    prefix_label = host.split(".")[0]
    r2_dir = tmp_path / "r2" / "previews" / prefix_label
    assert r2_dir.exists()
    assert any(p.is_file() for p in r2_dir.rglob("*"))

    kv_file = tmp_path / "kv" / f"{host}.json"
    assert kv_file.exists()
    kv_data = json.loads(kv_file.read_text(encoding="utf-8"))
    assert kv_data["takedown"] is False
    assert kv_data["business_id"] == business["id"]


def test_unchanged_content_skipped_on_rerun(local_store, tmp_path):
    business, _audit = _seed_glow(local_store)
    stats1 = _run_build(local_store, business, tmp_path)
    assert stats1["built"] == 1

    stats2 = _run_build(local_store, business, tmp_path)
    assert stats2["built"] == 0
    assert stats2["skipped_unchanged"] == 1

    previews = build_preview.find_previews_for_business(local_store, business["id"])
    assert len(previews) == 1


def test_force_rebuilds_even_when_unchanged(local_store, tmp_path):
    business, _audit = _seed_glow(local_store)
    _run_build(local_store, business, tmp_path)
    stats2 = _run_build(local_store, business, tmp_path, force=True)
    assert stats2["built"] == 1
    assert stats2["skipped_unchanged"] == 0


# ---------------------------------------------------------------------------
# Takedown
# ---------------------------------------------------------------------------


def test_takedown_flips_flags_and_deletes_r2_prefix(local_store, tmp_path):
    business, _audit = _seed_glow(local_store)
    local_store.upsert_outreach({"business_id": business["id"], "touch": 1, "status": "sent"})
    _run_build(local_store, business, tmp_path)
    preview = build_preview.find_previews_for_business(local_store, business["id"])[0]

    host = preview["subdomain_url"].split("//", 1)[-1]
    prefix_label = host.split(".")[0]
    r2_dir = tmp_path / "r2" / "previews" / prefix_label
    assert r2_dir.exists()

    result = takedown.take_down_preview(local_store, preview, mock=True, tmp_root=tmp_path)

    assert result["r2_objects_deleted"] > 0
    assert not r2_dir.exists()

    updated_preview = build_preview.find_previews_for_business(local_store, business["id"])[0]
    assert updated_preview["status"] == "takedown"
    assert updated_preview["takedown"] is True
    assert updated_preview["takedown_at"] is not None

    updated_business = local_store.get_business(business["id"])
    assert updated_business["do_not_contact"] is True

    outreach_rows = takedown._find_outreach_for_business(local_store, business["id"])
    assert len(outreach_rows) == 1
    assert outreach_rows[0]["status"] == "dnc"

    kv_data = json.loads((tmp_path / "kv" / f"{host}.json").read_text(encoding="utf-8"))
    assert kv_data["takedown"] is True
    assert kv_data["status"] == "takedown"


def test_takedown_uses_update_row_not_upsert_business(local_store, tmp_path, monkeypatch):
    """code-reviewer C4/M1: do_not_contact is patched via store.update_row (patch-by-id), never
    a read-modify-upsert_business round trip, which would lose a concurrent write to the same
    business row between takedown's read and its write."""
    business, _audit = _seed_glow(local_store)
    _run_build(local_store, business, tmp_path)
    preview = build_preview.find_previews_for_business(local_store, business["id"])[0]

    calls = {"upsert_business": 0, "update_row": 0}
    orig_upsert = local_store.upsert_business
    orig_update_row = local_store.update_row

    def _tracked_upsert(row):
        calls["upsert_business"] += 1
        return orig_upsert(row)

    def _tracked_update_row(table, row_id, patch):
        if table == "businesses":
            calls["update_row"] += 1
        return orig_update_row(table, row_id, patch)

    monkeypatch.setattr(local_store, "upsert_business", _tracked_upsert)
    monkeypatch.setattr(local_store, "update_row", _tracked_update_row)

    takedown.take_down_preview(local_store, preview, mock=True, tmp_root=tmp_path)

    assert calls["update_row"] == 1
    assert calls["upsert_business"] == 0
    assert local_store.get_business(business["id"])["do_not_contact"] is True


# ---------------------------------------------------------------------------
# takedown.py CLI — --mock/--store supabase guard (item 1)
# ---------------------------------------------------------------------------


def test_takedown_cli_mock_with_store_supabase_exits_2():
    import subprocess
    import sys as _sys

    proc = subprocess.run(
        [_sys.executable, "-m", "execution.personal_workflows.prodcraft_medspa.preview.takedown",
         "--business-id", "x", "--mock", "--store", "supabase"],
        cwd=str(PKG_ROOT.parents[2]), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 2
    assert "--mock cannot be combined with --store supabase" in proc.stderr


# ---------------------------------------------------------------------------
# build_preview.py CLI — --mock/--store supabase guard (item 1)
# ---------------------------------------------------------------------------


def test_build_preview_cli_mock_with_store_supabase_exits_2():
    import subprocess
    import sys as _sys

    proc = subprocess.run(
        [_sys.executable, "-m", "execution.personal_workflows.prodcraft_medspa.preview.build_preview",
         "--business-id", "x", "--mock", "--store", "supabase"],
        cwd=str(PKG_ROOT.parents[2]), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 2
    assert "--mock cannot be combined with --store supabase" in proc.stderr


def test_resolve_target_previews_by_host_and_preview_id(local_store, tmp_path):
    business, _audit = _seed_glow(local_store)
    _run_build(local_store, business, tmp_path)
    preview = build_preview.find_previews_for_business(local_store, business["id"])[0]
    host = preview["subdomain_url"].split("//", 1)[-1]

    by_host = takedown.resolve_target_previews(local_store, business_id=None, preview_id=None, host=host)
    assert len(by_host) == 1 and by_host[0]["id"] == preview["id"]

    by_preview_id = takedown.resolve_target_previews(
        local_store, business_id=None, preview_id=preview["id"], host=None
    )
    assert len(by_preview_id) == 1 and by_preview_id[0]["id"] == preview["id"]

    by_business = takedown.resolve_target_previews(
        local_store, business_id=business["id"], preview_id=None, host=None
    )
    assert len(by_business) == 1 and by_business[0]["id"] == preview["id"]


# ---------------------------------------------------------------------------
# Extend
# ---------------------------------------------------------------------------


def test_extend_updates_store_and_mock_kv(local_store, tmp_path):
    business, _audit = _seed_glow(local_store)
    _run_build(local_store, business, tmp_path)
    preview = build_preview.find_previews_for_business(local_store, business["id"])[0]
    host = preview["subdomain_url"].split("//", 1)[-1]

    new_expires = "2099-01-01"
    result = publish.extend(host, new_expires, mock=True, meta_dir=tmp_path / "kv")
    assert result["meta"]["expires_at"] == new_expires
    assert result["meta"]["takedown"] is False

    updated = local_store.update_preview(preview["id"], {"expires_at": new_expires, "status": "active"})
    assert updated["expires_at"] == new_expires

    kv_data = json.loads((tmp_path / "kv" / f"{host}.json").read_text(encoding="utf-8"))
    assert kv_data["expires_at"] == new_expires


# ---------------------------------------------------------------------------
# preview/approve.py — CLI counterpart of the dashboard approve button
# ---------------------------------------------------------------------------


def _seed_preview(store, business_id: str, status: str = "review", takedown: bool = False) -> dict:
    return store.upsert_preview(
        {
            "business_id": business_id,
            "template_id": "medspa-v1",
            "slug_suffix": "abc123",
            "subdomain_url": f"https://x-{status}.preview.prodcraft.fyi",
            "status": status,
            "content": {"name": "x"},
            "content_hash": f"hash-{status}-{takedown}",
            "takedown": takedown,
        }
    )


def test_approve_moves_review_to_approved_and_logs_event(local_store):
    from execution.personal_workflows.prodcraft_medspa.preview import approve

    business, _audit = _seed_glow(local_store)
    preview = _seed_preview(local_store, business["id"])
    stat = approve.run(local_store, preview_id=preview["id"], metro=None, actor="test")
    assert stat["out"] == 1 and stat["dropped"] == {}
    assert local_store.get_row("previews", preview["id"])["status"] == "approved"
    events = local_store.list_rows("events", entity="preview", entity_id=preview["id"])
    assert any(e["event"] == "status:review->approved" for e in events)


def test_approve_metro_skips_non_review_takedown_and_dnc(local_store):
    from execution.personal_workflows.prodcraft_medspa.preview import approve

    business, _audit = _seed_glow(local_store)
    _seed_preview(local_store, business["id"], status="review")
    _seed_preview(local_store, business["id"], status="live")
    _seed_preview(local_store, business["id"], status="review", takedown=True)
    stat = approve.run(local_store, preview_id=None, metro=business["metro"], actor="test")
    assert stat["out"] == 1
    assert stat["dropped"] == {"takedown": 1}  # live rows are never candidates; takedown rows are reported

    # second run is idempotent: nothing approvable left; the takedown row is still reported, not hidden
    again = approve.run(local_store, preview_id=None, metro=business["metro"], actor="test")
    assert again["out"] == 0 and again["dropped"] == {"takedown": 1}

    # do_not_contact business: approve refuses
    dnc = local_store.upsert_business({**business, "id": None, "place_id": "p-dnc", "slug": "dnc-spa", "do_not_contact": True})
    p = _seed_preview(local_store, dnc["id"])
    stat = approve.run(local_store, preview_id=p["id"], metro=None, actor="test")
    assert stat["dropped"] == {"do_not_contact": 1}


def test_approve_unknown_preview_id_is_a_reported_drop(local_store):
    from execution.personal_workflows.prodcraft_medspa.preview import approve

    stat = approve.run(local_store, preview_id="nope", metro=None, actor="test")
    assert stat == {"script": "approve", "in": 0, "out": 0, "dropped": {"not_found": 1}, "preview_ids": []}


# ---------------------------------------------------------------------------
# preview/approve.py CLI — --mock/--store supabase guard + live-bulk-approve guard (item 1, 4)
# ---------------------------------------------------------------------------


def _run_approve_cli(args, cwd):
    import subprocess
    import sys as _sys

    return subprocess.run(
        [_sys.executable, "-m", "execution.personal_workflows.prodcraft_medspa.preview.approve", *args],
        cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def test_approve_cli_mock_with_store_supabase_exits_2(tmp_path):
    proc = _run_approve_cli(
        ["--preview-id", "x", "--mock", "--store", "supabase"], PKG_ROOT.parents[2]
    )
    assert proc.returncode == 2
    assert "--mock cannot be combined with --store supabase" in proc.stderr


def test_approve_cli_live_bulk_approve_requires_yes_i_reviewed_them(tmp_path):
    """A live bulk approve (--metro against --store supabase) must refuse without
    --yes-i-reviewed-them — run_metro.py's own --auto-approve is local-store only and never
    passes this flag, so this path is reachable only by a deliberate manual invocation."""
    proc = _run_approve_cli(
        ["--metro", "chicago_north_shore", "--all-review", "--store", "supabase"], PKG_ROOT.parents[2]
    )
    assert proc.returncode == 2
    assert "--yes-i-reviewed-them" in proc.stderr


def test_approve_cli_local_bulk_approve_does_not_require_yes_i_reviewed_them(local_store, tmp_path):
    """The extra confirmation flag is Supabase/live-only; a local (e.g. --mock) bulk approve
    (exactly what run_metro.py's --auto-approve invokes) keeps working exactly as before, with
    no --yes-i-reviewed-them needed."""
    business, _audit = _seed_glow(local_store)
    _seed_preview(local_store, business["id"], status="review")
    proc = _run_approve_cli(
        [
            "--metro", business["metro"], "--all-review", "--actor", "run_metro",
            "--mock", "--store-root", str(local_store.root),
        ],
        PKG_ROOT.parents[2],
    )
    assert proc.returncode == 0, proc.stderr
    stat = json.loads(proc.stdout.strip().splitlines()[-1])
    assert stat["out"] == 1


# ---------------------------------------------------------------------------
# build isolation: inter-process lock + output sanity check
# ---------------------------------------------------------------------------


def test_process_lock_is_exclusive_across_processes(tmp_path):
    """A second process must wait (and time out) while the first holds template/.build.lock."""
    import subprocess as sp
    import sys as _sys

    from execution.personal_workflows.prodcraft_medspa.preview import build_preview

    lock_path = tmp_path / ".build.lock"
    with build_preview._ProcessLock(lock_path):
        code = (
            "import sys; sys.path.insert(0, %r)\n"
            "from execution.personal_workflows.prodcraft_medspa.preview.build_preview import _ProcessLock\n"
            "from pathlib import Path\n"
            "try:\n"
            "    with _ProcessLock(Path(%r), wait_s=1.5): print('ACQUIRED')\n"
            "except TimeoutError: print('TIMEOUT')\n"
        ) % (str(PKG_ROOT.parents[2]), str(lock_path))
        proc = sp.run([_sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    assert proc.stdout.strip() == "TIMEOUT", proc.stderr
    # released: a fresh acquire succeeds immediately
    with build_preview._ProcessLock(lock_path, wait_s=1):
        pass


def test_assert_build_matches_rejects_foreign_output(tmp_path):
    from execution.personal_workflows.prodcraft_medspa.preview import build_preview

    out = tmp_path / "out"
    out.mkdir()
    (out / "index.html").write_text("<title>Other Spa &amp; Co</title>", encoding="utf-8")
    with pytest.raises(RuntimeError):
        build_preview._assert_build_matches(out, {"name": "Glow Aesthetics"})
    build_preview._assert_build_matches(out, {"name": "Other Spa & Co"})  # escaped form is accepted


def test_touch4_already_sent_detects_deadline_email(local_store):
    from execution.personal_workflows.prodcraft_medspa.preview import publish

    business, _audit = _seed_glow(local_store)
    assert publish.touch4_already_sent(local_store, business["id"]) is False
    local_store.upsert_outreach({"business_id": business["id"], "touch": 4, "status": "drafted", "next_touch_at": "2026-09-01"})
    assert publish.touch4_already_sent(local_store, business["id"]) is False  # drafted, not sent
    local_store.update_outreach(
        local_store.list_outreach(business["id"])[0]["id"], {"status": "sent"}
    )
    assert publish.touch4_already_sent(local_store, business["id"]) is True
    assert publish.touch4_already_sent(local_store, None) is False


def test_google_maps_url_falls_back_to_search_for_imported_rows():
    from execution.personal_workflows.prodcraft_medspa.preview import build_preview

    url = build_preview.google_maps_url({"place_id": "import:abc123", "name": "Glow Spa", "address": "1 Main St, Winnetka, IL"})
    assert url.startswith("https://www.google.com/maps/search/?api=1&query=Glow+Spa+1+Main+St")
    assert build_preview.google_maps_url({"place_id": "ChIJ123"}).endswith("place_id:ChIJ123")
