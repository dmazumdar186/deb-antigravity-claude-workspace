"""Rosy Origami test suite — LLM-free.

Run: py tests/content/rosy_origami/test_composer.py
Exit 0 on all-pass, 1 on any failure.

All Gemini and Tavily API calls are mocked out. Real LLM/API verification is
covered by manual end-to-end runs (see plan file).
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import tracemalloc
from datetime import datetime
from pathlib import Path

# Force UTF-8 stdout on Windows so PASS/FAIL prints with Unicode don't crash
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
COMPOSER_DIR = ROOT / "execution" / "content" / "rosy_origami"
SCRIPT = COMPOSER_DIR / "generate_demo.py"

# Add composer dir to sys.path so we can import composer.py + generate_demo.py
sys.path.insert(0, str(COMPOSER_DIR))


# ─────────────────────────────────────────────────────────────────────────
# Test harness
# ─────────────────────────────────────────────────────────────────────────

class Results:
    def __init__(self) -> None:
        self.tiers: dict[str, list[tuple[bool, str]]] = {
            "Unit": [], "Integration": [], "E2E": [],
            "Sanity": [], "Performance": [], "Monkey": [],
        }

    def add(self, tier: str, ok: bool, label: str) -> None:
        self.tiers[tier].append((ok, label))
        prefix = "PASS " if ok else "FAIL "
        print(f"  {prefix} {label}")

    def report(self) -> int:
        print("\n" + "=" * 60)
        print("          FULL TEST SUMMARY")
        print("=" * 60)
        total_pass, total_fail = 0, 0
        for tier, results in self.tiers.items():
            p = sum(1 for ok, _ in results if ok)
            f = sum(1 for ok, _ in results if not ok)
            total_pass += p
            total_fail += f
            print(f"  {tier:13s}: {p} passed, {f} failed")
        print("  " + "─" * 40)
        print(f"  TOTAL        : {total_pass} passed, {total_fail} failed")
        verdict = "ALL PASS" if total_fail == 0 else f"{total_fail} FAILURES"
        print(f"  VERDICT      : {verdict}")
        return 0 if total_fail == 0 else 1


R = Results()


def check(tier: str, label: str, fn):
    """Wrap a test body — capture exceptions as FAIL, otherwise PASS on truthy return."""
    try:
        result = fn()
        if result is False:
            R.add(tier, False, f"{label} — assertion returned False")
        else:
            R.add(tier, True, label)
    except AssertionError as e:
        R.add(tier, False, f"{label} — {e}")
    except Exception as e:
        R.add(tier, False, f"{label} — {type(e).__name__}: {e}")


# ─────────────────────────────────────────────────────────────────────────
# Tier 1: UNIT TESTS — composer.py helpers (LLM-free)
# ─────────────────────────────────────────────────────────────────────────

print("\n=== TIER 1: UNIT TESTS ===")

import composer as cmp  # noqa: E402

def t_strip_signoff_simple():
    txt = "Hello world.\n-GIO Team"
    assert cmp._strip_signoff_lines(txt) == "Hello world."

def t_strip_signoff_emoji():
    txt = "Body text.\n💜 -GIO Team"
    assert cmp._strip_signoff_lines(txt) == "Body text."

def t_strip_signoff_bare_emoji_line():
    txt = "Real content.\n✨"
    assert cmp._strip_signoff_lines(txt) == "Real content."

def t_strip_signoff_keeps_non_signoff():
    txt = "Para 1.\n\nPara 2 mentions GIO inline naturally."
    out = cmp._strip_signoff_lines(txt)
    assert "Para 2 mentions GIO inline naturally." in out
    assert "Para 1." in out

def t_strip_hashtag_block_trailing():
    txt = "Real content here.\n#tag1 #tag2 #tag3"
    out = cmp._strip_signoff_lines(txt)
    assert "#tag1" not in out and "Real content here." in out

def t_strip_hashtag_block_anywhere():
    txt = "Para 1.\n#foo #bar\nPara 2."
    out = cmp._strip_signoff_lines(txt)
    assert "#foo" not in out and "Para 1." in out and "Para 2." in out

def t_strip_single_hashtag_kept():
    # one #tag inside a sentence is NOT a hashtag block — should NOT be stripped
    txt = "Join us at #HoliAuJardin this weekend."
    out = cmp._strip_signoff_lines(txt)
    assert "#HoliAuJardin" in out

def t_classify_all_teasers():
    chunks = ["### Save the Date: Holi\nBody.", "### Coming up: Diwali\nBody."]
    assert cmp.classify_event_section(chunks) == "What's Coming Up"

def t_classify_all_recaps():
    chunks = ["### Harvest Festival\nBody.", "### Women's Day Panel\nBody."]
    assert cmp.classify_event_section(chunks) == "Event Recap"

def t_classify_mixed():
    chunks = ["### Harvest Festival\nBody.", "### Save the Date: Holi\nBody."]
    assert cmp.classify_event_section(chunks) == "Community Updates"

def t_classify_empty():
    assert cmp.classify_event_section([]) == "Community Updates"

def t_hallucinated_dates_finds_invented_year():
    gen = "The event was held in 2099."
    sources = ["The event was held in 2026."]
    flags = cmp.find_hallucinated_dates(gen, sources)
    assert "2099" in flags

def t_hallucinated_dates_no_false_positive():
    gen = "The event was held in 2026."
    sources = ["The event was held in 2026."]
    flags = cmp.find_hallucinated_dates(gen, sources)
    assert "2026" not in flags

def t_hallucinated_dates_month_pattern():
    gen = "Join us on December 25."
    sources = ["Join us on November 5."]
    flags = cmp.find_hallucinated_dates(gen, sources)
    assert any("december" in f.lower() for f in flags)

def t_voice_block_loads_real_profile():
    block = cmp._voice_block("gio_paris")
    assert "Global Indian Organization Paris" in block
    assert "Sample" in block
    assert len(block) > 500  # has substantive content

def t_voice_block_missing_voice_fails():
    raised = False
    try:
        cmp._voice_block("nonexistent_voice_xyz")
    except Exception:
        raised = True
    assert raised

for fn in [t_strip_signoff_simple, t_strip_signoff_emoji, t_strip_signoff_bare_emoji_line,
           t_strip_signoff_keeps_non_signoff, t_strip_hashtag_block_trailing,
           t_strip_hashtag_block_anywhere, t_strip_single_hashtag_kept,
           t_classify_all_teasers, t_classify_all_recaps, t_classify_mixed,
           t_classify_empty, t_hallucinated_dates_finds_invented_year,
           t_hallucinated_dates_no_false_positive, t_hallucinated_dates_month_pattern,
           t_voice_block_loads_real_profile, t_voice_block_missing_voice_fails]:
    check("Unit", fn.__name__.replace("t_", ""), fn)


# ─────────────────────────────────────────────────────────────────────────
# Tier 2: INTEGRATION TESTS — module-to-module, real filesystem
# ─────────────────────────────────────────────────────────────────────────

print("\n=== TIER 2: INTEGRATION TESTS ===")

import generate_demo as gd  # noqa: E402


def t_tenant_config_loads():
    cfg = gd.load_tenant("gio_paris")
    assert cfg["slug"] == "gio_paris"
    assert cfg["voice_profile"] == "gio_paris"
    assert cfg["archetype"] == "cultural_community"

def t_template_loads():
    tpl = gd.load_template("cultural_community")
    assert tpl["archetype"] == "cultural_community"
    assert len(tpl["sections"]) == 6
    ids = [s["id"] for s in tpl["sections"]]
    assert "intro" in ids and "event_recap" in ids and "closing" in ids

def t_voice_validates():
    path = gd.validate_voice("gio_paris")
    assert path.exists()

def t_ig_manual_returns_captions():
    pool = gd.fetch_ig_manual("gio_paris")
    assert len(pool) >= 7
    assert all(hasattr(p, "body") and p.body for p in pool)

def t_news_fetcher_no_query_returns_empty():
    assert gd.fetch_news("", 30) == []

def t_news_fetcher_no_key_returns_empty():
    # Set empty string to defeat both the .env reloader (which only sets if absent)
    # and the truthy check inside fetch_news (which treats "" as falsy → returns []).
    saved = os.environ.get("TAVILY_API_KEY")
    os.environ["TAVILY_API_KEY"] = ""
    try:
        assert gd.fetch_news("test", 30) == []
    finally:
        if saved is not None:
            os.environ["TAVILY_API_KEY"] = saved
        else:
            os.environ.pop("TAVILY_API_KEY", None)

def t_compose_sections_dry_run_returns_tuple():
    tpl = gd.load_template("cultural_community")
    pool = gd.fetch_ig_manual("gio_paris")
    sections, flags = gd.compose_sections(pool, tpl, "test theme", None, dry_run=True)
    assert isinstance(sections, list)
    assert isinstance(flags, list)
    assert flags == []  # no LLM calls in dry-run → no flags
    assert len(sections) >= 2  # intro + event_recap + closing minimum

def t_compose_sections_omits_empty():
    tpl = gd.load_template("cultural_community")
    sections, _ = gd.compose_sections([], tpl, "x", None, dry_run=True)
    omit_if_empty_ids = {s["id"] for s in tpl["sections"] if s.get("omit_if_empty")}
    emitted_ids = {s.id for s in sections}
    # None of the omit_if_empty sections should be in output when pool is empty
    assert not (omit_if_empty_ids & emitted_ids)

def t_render_markdown_includes_title_and_sections():
    tpl = gd.load_template("cultural_community")
    cfg = gd.load_tenant("gio_paris")
    sections, _ = gd.compose_sections([], tpl, "x", None, dry_run=True)
    md = gd.render_markdown(sections, cfg)
    assert "Global Indian Organization Paris" in md
    assert "##" in md  # at least one section heading

def t_render_html_produces_real_tags():
    md = "# Title\n\n## Section\n\nParagraph with [link](https://example.com)."
    html = gd.render_html(md)
    assert "<h1>" in html and "<h2>" in html and "<p>" in html
    assert "<a href" in html
    assert "<pre>" not in html  # not the fallback path
    assert "<style>" in html  # styled output

def t_recency_sort_works():
    tpl = gd.load_template("cultural_community")
    pool = gd.fetch_ig_manual("gio_paris")
    # All ig_event by default — should sort by timestamp descending
    event_spec = next(s for s in tpl["sections"] if s["id"] == "event_recap")
    items = gd._select_items(pool, event_spec, None)
    assert len(items) >= 2
    # Most-recent first
    for i in range(len(items) - 1):
        assert items[i].timestamp >= items[i + 1].timestamp


for fn in [t_tenant_config_loads, t_template_loads, t_voice_validates,
           t_ig_manual_returns_captions, t_news_fetcher_no_query_returns_empty,
           t_news_fetcher_no_key_returns_empty, t_compose_sections_dry_run_returns_tuple,
           t_compose_sections_omits_empty, t_render_markdown_includes_title_and_sections,
           t_render_html_produces_real_tags, t_recency_sort_works]:
    check("Integration", fn.__name__.replace("t_", ""), fn)


# ─────────────────────────────────────────────────────────────────────────
# Tier 3: E2E TESTS — full script in dry-run mode
# ─────────────────────────────────────────────────────────────────────────

print("\n=== TIER 3: E2E TESTS ===")


def _run_script(*args, timeout=60):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout, check=False,
        cwd=str(ROOT),
    )

def t_e2e_dry_run_exits_zero():
    r = _run_script("--tenant", "gio_paris", "--ig-source", "manual",
                    "--theme", "Test theme", "--dry-run")
    assert r.returncode == 0, f"stderr: {r.stderr[:500]}"

def t_e2e_dry_run_writes_three_files():
    out_dir = ROOT / ".tmp" / "rosy_origami" / "gio_paris"
    stamp = datetime.now().strftime("%Y-%m-%d")
    files = [
        out_dir / f"newsletter_{stamp}.html",
        out_dir / f"newsletter_{stamp}.md",
        out_dir / f"newsletter_{stamp}.meta.json",
    ]
    r = _run_script("--tenant", "gio_paris", "--ig-source", "manual",
                    "--theme", "Test theme", "--dry-run")
    assert r.returncode == 0
    for f in files:
        assert f.exists(), f"missing: {f}"

def t_e2e_meta_json_has_required_fields():
    stamp = datetime.now().strftime("%Y-%m-%d")
    meta_path = ROOT / ".tmp" / "rosy_origami" / "gio_paris" / f"newsletter_{stamp}.meta.json"
    _run_script("--tenant", "gio_paris", "--ig-source", "manual",
                "--theme", "Test theme", "--dry-run")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    for k in ["tenant", "generated_at", "dry_run", "pool_size",
              "sections_emitted", "hallucination_flags"]:
        assert k in meta, f"missing key: {k}"

def t_e2e_help_flag_works():
    r = _run_script("--help")
    assert r.returncode == 0
    assert "tenant" in r.stdout.lower()


for fn in [t_e2e_dry_run_exits_zero, t_e2e_dry_run_writes_three_files,
           t_e2e_meta_json_has_required_fields, t_e2e_help_flag_works]:
    check("E2E", fn.__name__.replace("t_e2e_", ""), fn)


# ─────────────────────────────────────────────────────────────────────────
# Tier 4: SANITY TESTS — smoke
# ─────────────────────────────────────────────────────────────────────────

print("\n=== TIER 4: SANITY TESTS ===")


def t_required_files_present():
    expected = [
        ROOT / "directives" / "content" / "rosy_origami_composer.md",
        COMPOSER_DIR / "generate_demo.py",
        COMPOSER_DIR / "composer.py",
        COMPOSER_DIR / "requirements.txt",
        COMPOSER_DIR / "templates" / "cultural_community.yaml",
        COMPOSER_DIR / "tenants" / "gio_paris.yaml",
        ROOT / "execution" / "content" / "voices" / "gio_paris.json",
    ]
    missing = [str(p) for p in expected if not p.exists()]
    assert not missing, f"missing files: {missing}"

def t_imports_resolve():
    for mod in ["composer", "generate_demo"]:
        spec = importlib.util.find_spec(mod)
        assert spec is not None, f"cannot import {mod}"

def t_voice_profile_has_real_examples():
    voice = json.loads((ROOT / "execution" / "content" / "voices" /
                        "gio_paris.json").read_text(encoding="utf-8"))
    assert len(voice["examples"]) >= 5, f"only {len(voice['examples'])} examples"
    assert not any("PLACEHOLDER" in e for e in voice["examples"]), "still has placeholder"

def t_template_section_word_ranges_valid():
    tpl = gd.load_template("cultural_community")
    for s in tpl["sections"]:
        if "word_range" in s:
            lo, hi = s["word_range"]
            assert 10 <= lo < hi <= 250, f"{s['id']} word_range invalid: {[lo, hi]}"

def t_captions_json_is_valid():
    p = ROOT / ".tmp" / "rosy_origami" / "gio_paris" / "ig_export" / "captions.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert isinstance(data, list) and len(data) >= 7
    for item in data:
        assert "caption" in item and "timestamp" in item

def t_env_keys_documented():
    # not testing presence, just that the directive describes them
    directive = (ROOT / "directives" / "content" / "rosy_origami_composer.md").read_text(encoding="utf-8")
    for k in ["GEMINI_API_KEY", "META_ACCESS_TOKEN", "TAVILY_API_KEY"]:
        assert k in directive, f"{k} not documented in directive"


for fn in [t_required_files_present, t_imports_resolve, t_voice_profile_has_real_examples,
           t_template_section_word_ranges_valid, t_captions_json_is_valid,
           t_env_keys_documented]:
    check("Sanity", fn.__name__.replace("t_", ""), fn)


# ─────────────────────────────────────────────────────────────────────────
# Tier 5: PERFORMANCE TESTS — wall-clock + size + memory
# ─────────────────────────────────────────────────────────────────────────

print("\n=== TIER 5: PERFORMANCE TESTS ===")


def t_perf_dry_run_under_5s():
    t0 = time.monotonic()
    r = _run_script("--tenant", "gio_paris", "--ig-source", "manual",
                    "--theme", "Test", "--dry-run")
    elapsed = time.monotonic() - t0
    assert r.returncode == 0
    print(f"      ->{elapsed:.2f}s (threshold: <5s)")
    assert elapsed < 5.0

def t_perf_html_under_50kb():
    stamp = datetime.now().strftime("%Y-%m-%d")
    html_path = ROOT / ".tmp" / "rosy_origami" / "gio_paris" / f"newsletter_{stamp}.html"
    _run_script("--tenant", "gio_paris", "--ig-source", "manual",
                "--theme", "Test", "--dry-run")
    size_kb = html_path.stat().st_size / 1024
    print(f"      ->{size_kb:.1f}KB (threshold: <50KB)")
    assert size_kb < 50

def t_perf_memory_dry_run_under_100mb():
    tracemalloc.start()
    tpl = gd.load_template("cultural_community")
    pool = gd.fetch_ig_manual("gio_paris")
    sections, _ = gd.compose_sections(pool, tpl, "x", None, dry_run=True)
    md = gd.render_markdown(sections, gd.load_tenant("gio_paris"))
    _ = gd.render_html(md)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_mb = peak / (1024 * 1024)
    print(f"      ->peak {peak_mb:.1f}MB (threshold: <100MB)")
    assert peak_mb < 100

def t_perf_voice_block_load_fast():
    t0 = time.monotonic()
    for _ in range(50):
        cmp._voice_block("gio_paris")
    elapsed = time.monotonic() - t0
    print(f"      ->50 loads in {elapsed*1000:.0f}ms (threshold: <500ms)")
    assert elapsed < 0.5


for fn in [t_perf_dry_run_under_5s, t_perf_html_under_50kb,
           t_perf_memory_dry_run_under_100mb, t_perf_voice_block_load_fast]:
    check("Performance", fn.__name__.replace("t_perf_", ""), fn)


# ─────────────────────────────────────────────────────────────────────────
# Tier 6: MONKEY TESTS — adversarial / malformed inputs
# ─────────────────────────────────────────────────────────────────────────

print("\n=== TIER 6: MONKEY TESTS ===")


def t_monkey_missing_tenant_exits_cleanly():
    r = _run_script("--tenant", "nonexistent_tenant_xyz", "--ig-source", "manual",
                    "--theme", "x", "--dry-run")
    assert r.returncode != 0
    assert "tenant" in (r.stderr + r.stdout).lower()

def t_monkey_missing_archetype_exits_cleanly():
    r = _run_script("--tenant", "gio_paris", "--archetype", "nonexistent",
                    "--ig-source", "manual", "--theme", "x", "--dry-run")
    assert r.returncode != 0
    assert "template" in (r.stderr + r.stdout).lower()

def t_monkey_extremely_long_theme_ok():
    long_theme = "spring " * 500  # ~3.5KB theme string
    r = _run_script("--tenant", "gio_paris", "--ig-source", "manual",
                    "--theme", long_theme, "--dry-run")
    assert r.returncode == 0

def t_monkey_empty_theme_ok():
    r = _run_script("--tenant", "gio_paris", "--ig-source", "manual",
                    "--theme", "", "--dry-run")
    # Empty theme should still work in dry-run; theme defaults to "TBD"
    assert r.returncode == 0

def t_monkey_unicode_emoji_theme_ok():
    r = _run_script("--tenant", "gio_paris", "--ig-source", "manual",
                    "--theme", "🎉 测试 हिंदी العربية ✨", "--dry-run")
    assert r.returncode == 0

def t_monkey_strip_signoff_handles_long_input():
    big = ("Paragraph. " * 1000) + "\n-GIO Team"
    out = cmp._strip_signoff_lines(big)
    assert "-GIO Team" not in out
    assert "Paragraph." in out

def t_monkey_strip_signoff_handles_empty():
    assert cmp._strip_signoff_lines("") == ""

def t_monkey_strip_signoff_handles_only_signoff():
    assert cmp._strip_signoff_lines("-GIO Team") == ""

def t_monkey_strip_signoff_handles_null_bytes():
    txt = "Content\x00with null.\n-GIO Team"
    out = cmp._strip_signoff_lines(txt)
    assert "Content" in out and "-GIO Team" not in out

def t_monkey_hallucinated_dates_on_garbage_input():
    # Should not crash on weird non-text input
    flags = cmp.find_hallucinated_dates("", [""])
    assert flags == []

def t_monkey_classify_garbage_chunks():
    chunks = ["", "garbage no heading", "###", "### "]
    title = cmp.classify_event_section(chunks)
    assert title in ("Event Recap", "What's Coming Up", "Community Updates")

def t_monkey_malformed_tenant_yaml():
    # Create a malformed tenant file in a temp location, point script at it
    bad_tenant = COMPOSER_DIR / "tenants" / "_test_bad.yaml"
    backup = None
    if bad_tenant.exists():
        backup = bad_tenant.read_text(encoding="utf-8")
    try:
        bad_tenant.write_text("not: valid: yaml: ::: !!!", encoding="utf-8")
        r = _run_script("--tenant", "_test_bad", "--ig-source", "manual",
                        "--theme", "x", "--dry-run")
        # Should exit non-zero (parse error) — not silently succeed
        assert r.returncode != 0
    finally:
        if backup is not None:
            bad_tenant.write_text(backup, encoding="utf-8")
        else:
            bad_tenant.unlink(missing_ok=True)

def t_monkey_missing_captions_json_graceful():
    # Move captions.json out, run, restore — should warn but not crash
    captions = ROOT / ".tmp" / "rosy_origami" / "gio_paris" / "ig_export" / "captions.json"
    backup = captions.with_suffix(".json.bak")
    moved = False
    if captions.exists():
        shutil.move(captions, backup)
        moved = True
    try:
        r = _run_script("--tenant", "gio_paris", "--ig-source", "manual",
                        "--theme", "x", "--dry-run")
        # Should still succeed in dry-run with empty pool
        assert r.returncode == 0
    finally:
        if moved:
            shutil.move(backup, captions)


for fn in [t_monkey_missing_tenant_exits_cleanly, t_monkey_missing_archetype_exits_cleanly,
           t_monkey_extremely_long_theme_ok, t_monkey_empty_theme_ok,
           t_monkey_unicode_emoji_theme_ok, t_monkey_strip_signoff_handles_long_input,
           t_monkey_strip_signoff_handles_empty, t_monkey_strip_signoff_handles_only_signoff,
           t_monkey_strip_signoff_handles_null_bytes, t_monkey_hallucinated_dates_on_garbage_input,
           t_monkey_classify_garbage_chunks, t_monkey_malformed_tenant_yaml,
           t_monkey_missing_captions_json_graceful]:
    check("Monkey", fn.__name__.replace("t_monkey_", ""), fn)


# ─────────────────────────────────────────────────────────────────────────
# Final report
# ─────────────────────────────────────────────────────────────────────────

# 2026-07-01: guarded behind __name__ == "__main__" because a bare
# sys.exit() at module-load-time crashed pytest's collector on the whole
# tests/ tree (INTERNALERROR: SystemExit: 0). This is a standalone script,
# not a pytest module; running it directly still exits with the R.report()
# code as before.
if __name__ == "__main__":
    sys.exit(R.report())
