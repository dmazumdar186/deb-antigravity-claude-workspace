"""
test_sanity.py — Sanity Tests
Quick checks that the system is in a valid, deployable state.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


class TestFileExistence:
    """Critical files must exist."""

    def test_env_file_exists(self):
        assert (ROOT / ".env").exists()

    def test_am_config_exists(self):
        assert (ROOT / "config" / "accessory_masters.json").exists()

    def test_tone_config_exists(self):
        assert (ROOT / "config" / "tone.json").exists()

    def test_redirects_file_exists(self):
        assert (ROOT / "website" / "_redirects").exists()

    def test_vercel_json_exists(self):
        assert (ROOT / "website" / "vercel.json").exists()

    def test_wrangler_toml_exists(self):
        assert (ROOT / "execution" / "infrastructure" / "api-proxy" / "wrangler.toml").exists()

    def test_gtm_directive_exists(self):
        assert (ROOT / "directives" / "gtm_client_workflows" / "accessory_masters_gtm.md").exists()

    def test_prd_exists(self):
        assert (ROOT / "directives" / "gtm_client_workflows" / "accessory_masters_prd.md").exists()

    def test_gitignore_exists(self):
        assert (ROOT / ".gitignore").exists()


class TestExecutionScripts:
    """Registered execution scripts must exist on disk.

    Retired 2026-06-15 (sundown):
      - content/wedding_card_generator.py (one-time artifact, event past)
      - personal_workflows/cv_optimizer_agent.py (Streamlit prototype superseded
        by cv_optimizer_v2 Cloudflare Worker)
    AM-coupled entries below remain (the AM project is frozen, not retired).
    """

    SCRIPTS = [
        "enrichment/anymailfinder_lookup.py",
        "enrichment/million_verifier.py",
        "gtm_client_workflows/accessory_masters_pipeline.py",
        "lead_sourcing/prospeo_leads.py",
        "lead_sourcing/serper_maps_scraper.py",
        "personal_workflows/cv_builder.py",
        "personalization/ai_opener_generator.py",
        "personalization/variant_generator.py",
    ]

    @pytest.mark.parametrize("script", SCRIPTS)
    def test_script_exists(self, script):
        assert (ROOT / "execution" / script).exists(), f"Missing: execution/{script}"


class TestConfigValidity:
    """Config files must be valid JSON with expected content."""

    def test_am_config_valid_json(self):
        with open(ROOT / "config" / "accessory_masters.json", encoding="utf-8") as f:
            config = json.load(f)
        assert isinstance(config, dict)

    def test_tone_config_valid_json(self):
        with open(ROOT / "config" / "tone.json", encoding="utf-8") as f:
            config = json.load(f)
        assert isinstance(config, dict)

    def test_vercel_json_valid(self):
        with open(ROOT / "website" / "vercel.json", encoding="utf-8") as f:
            config = json.load(f)
        assert "rewrites" in config


class TestDeploymentConfig:
    """Deployment config files must reference correct URLs."""

    def test_redirects_has_worker_url(self):
        text = (ROOT / "website" / "_redirects").read_text(encoding="utf-8")
        assert "accessory-masters-api.accessory-masters.workers.dev" in text

    def test_vercel_json_has_worker_url(self):
        text = (ROOT / "website" / "vercel.json").read_text(encoding="utf-8")
        assert "accessory-masters-api.accessory-masters.workers.dev" in text
        assert "SUBDOMAIN" not in text

    def test_wrangler_has_account_id(self):
        text = (ROOT / "execution" / "infrastructure" / "api-proxy" / "wrangler.toml").read_text(encoding="utf-8")
        assert "26e5b8612be35e5d23a9186fcf5288d0" in text

    def test_wrangler_has_pages_origin(self):
        text = (ROOT / "execution" / "infrastructure" / "api-proxy" / "wrangler.toml").read_text(encoding="utf-8")
        assert "accessory-masters-site.pages.dev" in text


class TestGitignore:
    """Gitignore must protect secrets and build artifacts."""

    @pytest.fixture
    def gitignore(self):
        return (ROOT / ".gitignore").read_text(encoding="utf-8")

    def test_env_is_ignored(self, gitignore):
        assert ".env" in gitignore

    def test_wrangler_is_ignored(self, gitignore):
        assert ".wrangler/" in gitignore

    def test_credentials_ignored(self, gitignore):
        assert "credentials.json" in gitignore

    def test_tmp_ignored(self, gitignore):
        assert ".tmp/" in gitignore


class TestNoHardcodedSecrets:
    """No API keys should be hardcoded in Python source files.

    Patterns require enough trailing key-shape characters that bare prefix
    references in redaction/detection logic (e.g. `if "sk-ant-" in msg`) do
    not false-positive.
    """

    @pytest.fixture
    def all_py_sources(self):
        sources = []
        for py_file in (ROOT / "execution").rglob("*.py"):
            sources.append((py_file.relative_to(ROOT), py_file.read_text(encoding="utf-8", errors="ignore")))
        return sources

    import re as _re
    FORBIDDEN_PATTERNS = [
        _re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
        _re.compile(r"sk-or-v1-[A-Za-z0-9_-]{20,}"),
        _re.compile(r"AIza[A-Za-z0-9_-]{30,}"),
        _re.compile(r"pk_690ab[A-Za-z0-9]+"),
        _re.compile(r"cfat_H3o[A-Za-z0-9]+"),
        _re.compile(r"NDU3MzA4[A-Za-z0-9]+"),
    ]

    @pytest.mark.parametrize("pattern", FORBIDDEN_PATTERNS, ids=lambda p: p.pattern)
    def test_no_hardcoded_key(self, pattern, all_py_sources):
        for rel_path, content in all_py_sources:
            match = pattern.search(content)
            assert match is None, f"Hardcoded key pattern '{pattern.pattern}' found in {rel_path}: {match.group(0)[:32]}..."
