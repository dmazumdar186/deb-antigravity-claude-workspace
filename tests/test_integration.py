"""
test_integration.py — System Integration Tests
Verify all modules import, config loads correctly, components wire together.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "execution"))


class TestModuleImports:
    """Every execution module must import without errors."""

    def test_import_pipeline_utils(self):
        import modules.pipeline_utils

    def test_import_reply_classifier(self):
        import modules.reply_classifier

    def test_import_llm_client(self):
        import modules.llm_client

    def test_import_instantly(self):
        import modules.outputs.instantly

    def test_import_ghl(self):
        import modules.outputs.ghl

    def test_import_slack(self):
        import modules.outputs.slack

    def test_import_telegram(self):
        import modules.outputs.telegram

    def test_import_auto_reply(self):
        import modules.outputs.auto_reply

    def test_import_report_generator(self):
        import modules.outputs.report_generator

    def test_import_serper_maps_scraper(self):
        import lead_sourcing.serper_maps_scraper

    def test_import_prospeo_leads(self):
        import lead_sourcing.prospeo_leads

    def test_import_anymailfinder_lookup(self):
        import enrichment.anymailfinder_lookup

    def test_import_million_verifier(self):
        import enrichment.million_verifier

    def test_import_ai_opener_generator(self):
        import personalization.ai_opener_generator

    def test_import_accessory_masters_pipeline(self):
        import gtm_client_workflows.accessory_masters_pipeline


class TestConfigLoading:
    """Config files must be valid and contain required keys."""

    @pytest.fixture
    def am_config(self):
        with open(ROOT / "config" / "accessory_masters.json", encoding="utf-8") as f:
            return json.load(f)

    @pytest.fixture
    def tone_config(self):
        with open(ROOT / "config" / "tone.json", encoding="utf-8") as f:
            return json.load(f)

    def test_am_config_has_12_industries(self, am_config):
        industries = am_config["icp"]["industries"]
        assert len(industries) == 12

    def test_am_config_includes_manufacturing(self, am_config):
        assert "manufacturing" in am_config["icp"]["industries"]

    def test_am_config_includes_professional_services(self, am_config):
        assert "professional services" in am_config["icp"]["industries"]

    def test_am_config_required_top_level_keys(self, am_config):
        required = ["icp", "sourcing", "enrichment", "personalization",
                     "instantly", "ghl", "classification", "auto_reply", "reporting"]
        for key in required:
            assert key in am_config, f"Missing config key: {key}"

    def test_am_config_use_prospeo_for_empty(self, am_config):
        assert am_config["sourcing"]["use_prospeo_for"] == []

    def test_tone_config_has_voice(self, tone_config):
        assert "voice" in tone_config

    def test_tone_config_has_never_say(self, tone_config):
        assert "never_say" in tone_config

    def test_tone_config_has_example_openers(self, tone_config):
        assert "example_openers" in tone_config


class TestPipelineUtilsFunctions:
    """Verify pipeline_utils exports expected functions."""

    def test_retry_with_backoff_exists(self):
        from modules.pipeline_utils import retry_with_backoff
        assert callable(retry_with_backoff)

    def test_deduplicate_exists(self):
        from modules.pipeline_utils import deduplicate
        assert callable(deduplicate)

    def test_load_config_exists(self):
        from modules.pipeline_utils import load_config
        assert callable(load_config)

    def test_save_leads_exists(self):
        from modules.pipeline_utils import save_leads
        assert callable(save_leads)

    def test_load_leads_exists(self):
        from modules.pipeline_utils import load_leads
        assert callable(load_leads)

    def test_normalize_domain_exists(self):
        from modules.pipeline_utils import normalize_domain
        assert callable(normalize_domain)

    def test_compute_dedup_key_exists(self):
        from modules.pipeline_utils import compute_dedup_key
        assert callable(compute_dedup_key)

    def test_load_config_returns_dict(self):
        from modules.pipeline_utils import load_config
        config = load_config(str(ROOT / "config" / "accessory_masters.json"))
        assert isinstance(config, dict)
        assert "icp" in config
