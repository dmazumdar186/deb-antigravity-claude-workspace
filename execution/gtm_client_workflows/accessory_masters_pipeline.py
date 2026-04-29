#!/usr/bin/env python3
"""
accessory_masters_pipeline.py
description: End-to-end orchestration pipeline for Accessory Masters cold email system.
             Runs: source -> enrich -> verify -> personalize -> upload to Instantly.
             Also handles: reply polling, AI classification, GHL routing, notifications.
inputs: --config, --stage, --mock, --force, --poll-replies; env: multiple API keys
outputs: .tmp/pipeline_state.json, .tmp/personalized_leads.json
usage:
    py execution/gtm_client_workflows/accessory_masters_pipeline.py --mock
    py execution/gtm_client_workflows/accessory_masters_pipeline.py --stage source --mock
    py execution/gtm_client_workflows/accessory_masters_pipeline.py --poll-replies --mock
"""

import argparse
import importlib
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "execution"))

from modules.pipeline_utils import (
    export_csv,
    generate_run_id,
    load_config,
    load_leads,
    now_iso,
    retry_with_backoff,
    save_leads,
    setup_logging,
)

load_dotenv(ROOT / ".env")
logger = setup_logging("pipeline", log_dir=ROOT / ".tmp")

TMP = ROOT / ".tmp"


# ---------------------------------------------------------------------------
# Pipeline state management
# ---------------------------------------------------------------------------

def load_pipeline_state(state_file: Path) -> dict:
    """Load pipeline checkpoint state from JSON file."""
    if state_file.exists():
        with open(state_file, encoding="utf-8") as f:
            return json.load(f)
    return {"stages": {}, "run_id": None}


def save_pipeline_state(state: dict, state_file: Path):
    """Save pipeline checkpoint state."""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def stage_complete(state: dict, stage_name: str) -> bool:
    """Check if a stage has been completed."""
    return state.get("stages", {}).get(stage_name, {}).get("completed", False)


def mark_stage_complete(state: dict, stage_name: str, output_file: str):
    """Mark a stage as completed with its output path."""
    if "stages" not in state:
        state["stages"] = {}
    state["stages"][stage_name] = {
        "completed": True,
        "output_file": output_file,
        "completed_at": now_iso(),
    }


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

def stage_source(config: dict, mock: bool, run_id: str) -> str:
    """Run lead sourcing (Serper Maps + Prospeo). Returns output file path."""
    output = str(TMP / "serper_leads.json")

    serper_args = [
        "--config", str(ROOT / "config" / "accessory_masters.json"),
        "--output", output,
    ]
    if mock:
        serper_args.append("--mock")

    from lead_sourcing.serper_maps_scraper import main as serper_main
    sys.argv = ["serper_maps_scraper.py"] + serper_args
    serper_main()

    prospeo_output = str(TMP / "prospeo_leads.json")
    prospeo_args = [
        "--config", str(ROOT / "config" / "accessory_masters.json"),
        "--output", prospeo_output,
    ]
    if mock:
        prospeo_args.append("--mock")

    from lead_sourcing.prospeo_leads import main as prospeo_main
    sys.argv = ["prospeo_leads.py"] + prospeo_args
    prospeo_main()

    serper_leads = load_leads(output)
    if Path(prospeo_output).exists():
        prospeo_leads = load_leads(prospeo_output)
        if prospeo_leads:
            from modules.pipeline_utils import deduplicate
            merged = deduplicate(serper_leads + prospeo_leads)
            save_leads(merged, output)
            logger.info("Merged: %d Serper + %d Prospeo = %d unique leads",
                        len(serper_leads), len(prospeo_leads), len(merged))

    return output


def stage_enrich(config: dict, input_file: str, mock: bool) -> str:
    """Run email enrichment (AnymailFinder). Returns output file path."""
    output = str(TMP / "enriched_leads.json")

    enrich_args = [
        "--input", input_file,
        "--output", output,
    ]
    min_conf = config.get("enrichment", {}).get("anymailfinder_min_confidence", 50)
    enrich_args.extend(["--min-confidence", str(min_conf)])
    if mock:
        enrich_args.append("--mock")

    from enrichment.anymailfinder_lookup import main as enrich_main
    sys.argv = ["anymailfinder_lookup.py"] + enrich_args
    enrich_main()

    return output


def stage_verify(config: dict, input_file: str, mock: bool) -> str:
    """Run email verification (Million Verifier). Returns output file path."""
    output = str(TMP / "verified_leads.json")

    accept = config.get("enrichment", {}).get("million_verifier_accept", ["ok", "catch_all"])
    verify_args = [
        "--input", input_file,
        "--output", output,
        "--accept", ",".join(accept),
    ]
    if mock:
        verify_args.append("--mock")

    from enrichment.million_verifier import main as verify_main
    sys.argv = ["million_verifier.py"] + verify_args
    verify_main()

    return output


def stage_personalize(config: dict, input_file: str, mock: bool) -> str:
    """Run AI opener generation. Returns output file path."""
    output = str(TMP / "personalized_leads.json")

    pers_config = config.get("personalization", {})
    pers_args = [
        "--input", input_file,
        "--output", output,
        "--tone-config", str(ROOT / pers_config.get("tone_config", "config/tone.json")),
        "--batch-size", str(pers_config.get("batch_size", 50)),
        "--model", pers_config.get("model", "claude-haiku-4-5-20251001"),
    ]
    if mock:
        pers_args.append("--mock")

    from personalization.ai_opener_generator import main as pers_main
    sys.argv = ["ai_opener_generator.py"] + pers_args
    pers_main()

    return output


def stage_upload_instantly(config: dict, input_file: str, mock: bool) -> str:
    """Upload personalized leads to Instantly.ai via API."""
    instantly_config = config.get("instantly", {})
    campaign_id = instantly_config.get("campaign_id")
    api_url = instantly_config.get("api_url", "https://api.instantly.ai/api/v2")

    leads = load_leads(input_file)
    personalized = [l for l in leads if l.get("status") == "personalized"]

    if not personalized:
        logger.warning("No personalized leads to upload.")
        return input_file

    if not campaign_id:
        logger.warning("No campaign_id configured — skipping Instantly upload. "
                       "Set 'instantly.campaign_id' in config.")
        return input_file

    if mock:
        logger.info("MOCK: Would upload %d leads to campaign %s", len(personalized), campaign_id)
        for lead in personalized:
            lead["uploaded_to_instantly"] = True
            lead["campaign_id"] = campaign_id
            lead["status"] = "uploaded"
        save_leads(leads, input_file)
        return input_file

    api_key = os.environ.get("INSTANTLY_API_KEY", "")
    if not api_key:
        logger.error("INSTANTLY_API_KEY not set — cannot upload.")
        return input_file

    uploaded = 0
    for lead in personalized:
        try:
            payload = {
                "campaign": campaign_id,
                "email": lead.get("owner_email", ""),
                "first_name": (lead.get("owner_name", "") or "").split()[0] if lead.get("owner_name") else "",
                "last_name": " ".join((lead.get("owner_name", "") or "").split()[1:]) if lead.get("owner_name") else "",
                "company_name": lead.get("business_name", ""),
                "custom_variables": {
                    "opener": lead.get("personalized_opener", ""),
                    "industry": lead.get("industry", ""),
                    "city": lead.get("city", ""),
                },
            }
            resp = requests.post(
                f"{api_url}/leads",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()

            lead["uploaded_to_instantly"] = True
            lead["campaign_id"] = campaign_id
            lead["instantly_lead_id"] = resp.json().get("id")
            lead["status"] = "uploaded"
            uploaded += 1
        except Exception:
            logger.exception("Failed to upload lead %s", lead.get("owner_email"))
            lead["status"] = "error"
            lead["error_message"] = "Instantly upload failed"

    save_leads(leads, input_file)
    logger.info("Uploaded %d/%d leads to Instantly", uploaded, len(personalized))
    return input_file


# ---------------------------------------------------------------------------
# Reply handling
# ---------------------------------------------------------------------------

def poll_replies(config: dict, mock: bool):
    """Poll Instantly for new replies, classify, route to GHL, notify."""
    instantly_config = config.get("instantly", {})
    api_url = instantly_config.get("api_url", "https://api.instantly.ai/api/v2")

    if mock:
        replies = _get_mock_replies()
        logger.info("MOCK: Processing %d mock replies", len(replies))
    else:
        api_key = os.environ.get("INSTANTLY_API_KEY", "")
        if not api_key:
            logger.error("INSTANTLY_API_KEY not set.")
            return
        replies = _fetch_replies(api_url, api_key)

    if not replies:
        logger.info("No new replies found.")
        return

    for reply in replies:
        classification = classify_reply(reply, mock)
        logger.info(
            "Reply from %s classified as: %s",
            reply.get("from_email", "unknown"),
            classification,
        )

        if classification == "positive":
            route_to_ghl(reply, config, mock)
            send_notification(reply, config, mock)


def _get_mock_replies() -> list[dict]:
    """Return mock replies for testing."""
    return [
        {
            "from_email": "john.miller@sparklecarwash.com",
            "from_name": "John Miller",
            "subject": "Re: Quick question",
            "body": "Yes, I've been thinking about selling. What's the process?",
            "company": "Sparkle Car Wash",
            "received_at": now_iso(),
        },
        {
            "from_email": "tony.rossi@tonyspizzapalace.com",
            "from_name": "Tony Rossi",
            "subject": "Re: Quick question",
            "body": "Not interested, please remove me from your list.",
            "company": "Tony's Pizza Palace",
            "received_at": now_iso(),
        },
        {
            "from_email": "auto-reply@cleanfreshlaundry.com",
            "from_name": "",
            "subject": "Out of Office",
            "body": "I am currently out of the office and will return on Monday.",
            "company": "Clean & Fresh Laundromat",
            "received_at": now_iso(),
        },
    ]


@retry_with_backoff(max_retries=3, base_delay=2.0)
def _fetch_replies(api_url: str, api_key: str) -> list[dict]:
    """Fetch new replies from Instantly Unibox API."""
    resp = requests.get(
        f"{api_url}/unibox/emails",
        headers={"Authorization": f"Bearer {api_key}"},
        params={"email_type": "received", "limit": 50},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", [])


def classify_reply(reply: dict, mock: bool) -> str:
    """Classify a reply as positive, negative, or neutral."""
    body = (reply.get("body", "") or "").lower()

    if mock:
        negative_signals = ["not interested", "remove", "stop", "unsubscribe", "no thanks", "don't", "no longer"]
        neutral_signals = ["out of office", "auto-reply", "vacation", "will return"]
        positive_signals = ["interested", "sell", "process", "tell me more", "call me", "yes"]

        for signal in negative_signals:
            if signal in body:
                return "negative"
        for signal in neutral_signals:
            if signal in body:
                return "neutral"
        for signal in positive_signals:
            if signal in body:
                return "positive"
        return "neutral"

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not set for reply classification.")
        return "neutral"

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            system=(
                "Classify this cold email reply as exactly one of: positive, negative, neutral.\n"
                "positive = interested in selling their business, wants to talk, asks about the process\n"
                "negative = not interested, asks to be removed, hostile\n"
                "neutral = out of office, auto-reply, bounce, unclear\n"
                "Reply with exactly one word: positive, negative, or neutral."
            ),
            messages=[{"role": "user", "content": body}],
        )
        result = resp.content[0].text.strip().lower()
        if result in ("positive", "negative", "neutral"):
            return result
        return "neutral"
    except Exception:
        logger.exception("Reply classification failed, defaulting to neutral")
        return "neutral"


def route_to_ghl(reply: dict, config: dict, mock: bool):
    """Create a contact and opportunity in GoHighLevel for a positive reply."""
    ghl_config = config.get("ghl", {})
    api_url = ghl_config.get("api_url", "https://services.leadconnectorhq.com")
    pipeline_id = ghl_config.get("pipeline_id")
    stages = ghl_config.get("pipeline_stages", {})
    new_stage_id = stages.get("new")

    if mock:
        logger.info(
            "MOCK: Would create GHL contact + opportunity for %s (%s)",
            reply.get("from_name"),
            reply.get("from_email"),
        )
        return

    api_key = os.environ.get("GHL_API_KEY", "")
    if not api_key:
        logger.error("GHL_API_KEY not set — cannot route to GHL.")
        return

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Version": "2021-07-28",
    }

    name_parts = (reply.get("from_name", "") or "").split()
    first_name = name_parts[0] if name_parts else ""
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

    try:
        contact_resp = requests.post(
            f"{api_url}/contacts/",
            headers=headers,
            json={
                "firstName": first_name,
                "lastName": last_name,
                "email": reply.get("from_email", ""),
                "companyName": reply.get("company", ""),
                "tags": ["cold email", "positive reply"],
                "source": "cold email pipeline",
                "customFields": [
                    {"key": "reply_text", "value": reply.get("body", "")[:500]},
                ],
            },
            timeout=30,
        )
        contact_resp.raise_for_status()
        contact_id = contact_resp.json().get("contact", {}).get("id")
        logger.info("Created GHL contact: %s", contact_id)

        if pipeline_id and new_stage_id and contact_id:
            opp_resp = requests.post(
                f"{api_url}/opportunities/",
                headers=headers,
                json={
                    "pipelineId": pipeline_id,
                    "stageId": new_stage_id,
                    "contactId": contact_id,
                    "name": f"{reply.get('from_name', 'Unknown')} — {reply.get('company', 'Unknown')}",
                    "status": "open",
                },
                timeout=30,
            )
            opp_resp.raise_for_status()
            logger.info("Created GHL opportunity for contact %s", contact_id)
    except Exception:
        logger.exception("GHL routing failed for %s", reply.get("from_email"))


def send_notification(reply: dict, config: dict, mock: bool):
    """Send a Slack notification for a positive reply."""
    if mock:
        logger.info(
            "MOCK: Would send Slack notification — Positive reply from %s (%s): %s",
            reply.get("from_name"),
            reply.get("company"),
            (reply.get("body", "")[:100]),
        )
        return

    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL not set — skipping notification.")
        return

    try:
        message = {
            "text": (
                f":white_check_mark: *Positive Reply Detected*\n"
                f"*From:* {reply.get('from_name', 'Unknown')} ({reply.get('from_email', '')})\n"
                f"*Company:* {reply.get('company', 'Unknown')}\n"
                f"*Reply:* {reply.get('body', '')[:200]}\n"
                f"*Time:* {reply.get('received_at', now_iso())}"
            )
        }
        resp = requests.post(webhook_url, json=message, timeout=10)
        resp.raise_for_status()
        logger.info("Slack notification sent for %s", reply.get("from_email"))
    except Exception:
        logger.exception("Slack notification failed")


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def run_pipeline(config: dict, stage: str, mock: bool, force: bool):
    """Run the pipeline stages with checkpoint resume."""
    state_file = Path(config.get("pipeline", {}).get("state_file", str(TMP / "pipeline_state.json")))
    state = load_pipeline_state(state_file) if not force else {"stages": {}}

    run_id = state.get("run_id") or generate_run_id()
    state["run_id"] = run_id
    logger.info("Pipeline run: %s (force=%s, stage=%s)", run_id, force, stage)

    stages_to_run = ["source", "enrich", "verify", "personalize", "upload"]

    if stage != "all":
        if stage not in stages_to_run:
            logger.error("Unknown stage: %s. Choose from: %s", stage, ", ".join(stages_to_run))
            return
        stages_to_run = [stage]

    for stage_name in stages_to_run:
        if not force and stage_complete(state, stage_name):
            output = state["stages"][stage_name].get("output_file", "")
            logger.info("Skipping %s (already complete) -> %s", stage_name, output)
            continue

        logger.info("=== Running stage: %s ===", stage_name)

        if stage_name == "source":
            output = stage_source(config, mock, run_id)
        elif stage_name == "enrich":
            prev_output = state["stages"].get("source", {}).get("output_file", str(TMP / "serper_leads.json"))
            output = stage_enrich(config, prev_output, mock)
        elif stage_name == "verify":
            prev_output = state["stages"].get("enrich", {}).get("output_file", str(TMP / "enriched_leads.json"))
            output = stage_verify(config, prev_output, mock)
        elif stage_name == "personalize":
            prev_output = state["stages"].get("verify", {}).get("output_file", str(TMP / "verified_leads.json"))
            output = stage_personalize(config, prev_output, mock)
        elif stage_name == "upload":
            prev_output = state["stages"].get("personalize", {}).get("output_file", str(TMP / "personalized_leads.json"))
            output = stage_upload_instantly(config, prev_output, mock)

        mark_stage_complete(state, stage_name, output)
        save_pipeline_state(state, state_file)
        logger.info("Stage %s complete -> %s", stage_name, output)

    logger.info("Pipeline run %s finished.", run_id)

    final_output = state["stages"].get("personalize", {}).get("output_file")
    if final_output and Path(final_output).exists():
        leads = load_leads(final_output)
        csv_path = TMP / "instantly_upload.csv"
        personalized = [l for l in leads if l.get("status") in ("personalized", "uploaded")]
        if personalized:
            export_csv(
                personalized,
                csv_path,
                ["owner_email", "owner_name", "business_name", "industry", "city", "state", "personalized_opener"],
            )
            logger.info("CSV export for Instantly: %s (%d leads)", csv_path, len(personalized))


def main():
    parser = argparse.ArgumentParser(
        description="Accessory Masters end-to-end cold email pipeline"
    )
    parser.add_argument("--config", default=str(ROOT / "config" / "accessory_masters.json"))
    parser.add_argument(
        "--stage",
        default="all",
        choices=["all", "source", "enrich", "verify", "personalize", "upload"],
        help="Run a specific stage or all stages",
    )
    parser.add_argument("--mock", action="store_true", help="Use mock data for all stages")
    parser.add_argument("--force", action="store_true", help="Ignore checkpoint state, re-run all")
    parser.add_argument("--poll-replies", action="store_true", help="Run reply polling instead of pipeline")
    args = parser.parse_args()

    TMP.mkdir(exist_ok=True)
    config = load_config(args.config)

    if args.poll_replies:
        logger.info("=== Reply Polling Mode ===")
        poll_replies(config, args.mock)
    else:
        run_pipeline(config, args.stage, args.mock, args.force)


if __name__ == "__main__":
    main()
