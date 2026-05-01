"""
test_e2e.py — End-to-End Tests (Mock Mode)
Run full pipeline stages in mock mode, verify outputs and data flow.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "execution"))


@pytest.fixture
def am_config():
    with open(ROOT / "config" / "accessory_masters.json", encoding="utf-8") as f:
        return json.load(f)


class TestFullPipelineMock:
    """End-to-end pipeline run in mock mode."""

    def test_full_pipeline_completes(self, am_config, tmp_path):
        from gtm_client_workflows.accessory_masters_pipeline import run_pipeline

        config = am_config.copy()
        config["pipeline"] = {
            "state_file": str(tmp_path / "pipeline_state.json"),
            "output_dir": str(tmp_path),
        }
        run_pipeline(config, stage="all", mock=True, force=True)

    def test_state_file_created(self, am_config, tmp_path):
        from gtm_client_workflows.accessory_masters_pipeline import run_pipeline

        config = am_config.copy()
        config["pipeline"] = {
            "state_file": str(tmp_path / "pipeline_state.json"),
            "output_dir": str(tmp_path),
        }
        run_pipeline(config, stage="all", mock=True, force=True)
        assert (tmp_path / "pipeline_state.json").exists()

    def test_state_file_is_valid_json(self, am_config, tmp_path):
        from gtm_client_workflows.accessory_masters_pipeline import run_pipeline

        config = am_config.copy()
        config["pipeline"] = {
            "state_file": str(tmp_path / "pipeline_state.json"),
            "output_dir": str(tmp_path),
        }
        run_pipeline(config, stage="all", mock=True, force=True)
        with open(tmp_path / "pipeline_state.json") as f:
            state = json.load(f)
        assert isinstance(state, dict)

    def test_poll_replies_completes(self, am_config):
        from gtm_client_workflows.accessory_masters_pipeline import poll_replies
        poll_replies(am_config, mock=True)


class TestSerperMock:
    """Serper Maps scraper mock data and parsing."""

    def test_mock_data_returns_list(self):
        from lead_sourcing.serper_maps_scraper import get_mock_data
        data = get_mock_data()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_mock_data_has_lead_fields(self):
        from lead_sourcing.serper_maps_scraper import get_mock_data
        data = get_mock_data()
        assert "business_name" in data[0]

    def test_mock_leads_have_required_fields(self):
        from lead_sourcing.serper_maps_scraper import get_mock_data
        data = get_mock_data()
        required = {"business_name", "address", "phone", "domain"}
        for lead in data:
            missing = required - set(lead.keys())
            assert not missing, f"Lead missing fields: {missing}"

    def test_parse_serper_results_with_raw_places(self):
        from lead_sourcing.serper_maps_scraper import parse_serper_results
        raw_places = [{"title": "Test Car Wash", "address": "123 Main St",
                       "phone": "555-1234", "website": "https://test.com",
                       "ratingCount": 42, "rating": 4.5}]
        leads = parse_serper_results(raw_places, "test query", "car wash", "test-run", "2026-05-01")
        assert len(leads) == 1
        assert leads[0]["business_name"] == "Test Car Wash"


class TestProspeoMock:
    """Prospeo leads mock data and parsing."""

    def test_mock_data_returns_list(self):
        from lead_sourcing.prospeo_leads import get_mock_data
        data = get_mock_data()
        assert isinstance(data, list)

    def test_mock_data_has_entries(self):
        from lead_sourcing.prospeo_leads import get_mock_data
        data = get_mock_data()
        assert len(data) > 0

    def test_mock_data_has_lead_fields(self):
        from lead_sourcing.prospeo_leads import get_mock_data
        data = get_mock_data()
        for lead in data:
            assert "business_name" in lead or "first_name" in lead

    def test_parse_prospeo_v2_with_synthetic_data(self):
        from lead_sourcing.prospeo_leads import parse_prospeo_results
        v2_data = [{
            "person": {
                "first_name": "Alice", "last_name": "Smith",
                "email": {"email": "alice@test.com", "revealed": True},
                "current_job_title": "Owner",
                "location": {"city": "Houston", "state": "TX"},
            },
            "company": {"name": "Test Mfg", "domain": "testmfg.com"},
        }]
        leads = parse_prospeo_results(v2_data, "manufacturing", "test-run", "2026-05-01")
        assert len(leads) == 1
        assert leads[0]["owner_email"] == "alice@test.com"


class TestOpenerMock:
    """AI opener generator mock mode."""

    def test_mock_opener_returns_string(self):
        from personalization.ai_opener_generator import get_mock_opener
        lead = {"business_name": "Test Biz", "industry": "car wash", "address": "Houston TX"}
        opener = get_mock_opener(lead)
        assert isinstance(opener, str)
        assert len(opener) > 0

    def test_mock_opener_is_nonempty_for_minimal_lead(self):
        from personalization.ai_opener_generator import get_mock_opener
        opener = get_mock_opener({})
        assert isinstance(opener, str)
        assert len(opener) > 0
