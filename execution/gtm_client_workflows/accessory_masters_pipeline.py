#!/usr/bin/env python3
"""
accessory_masters_pipeline.py
description: End-to-end orchestration pipeline for Accessory Masters cold email system.
             Runs: source -> enrich -> verify -> personalize -> upload to Instantly.
             Also handles: reply polling, AI classification, GHL routing, notifications.
inputs: --config, --stage, --mock, --force, --poll-replies, --weekly-report; env: multiple API keys
outputs: .tmp/pipeline_state.json, .tmp/personalized_leads.json
usage:
    py execution/gtm_client_workflows/accessory_masters_pipeline.py --mock
    py execution/gtm_client_workflows/accessory_masters_pipeline.py --stage source --mock
    py execution/gtm_client_workflows/accessory_masters_pipeline.py --poll-replies --mock
    py execution/gtm_client_workflows/accessory_masters_pipeline.py --weekly-report --mock
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "execution"))

from modules.pipeline_utils import (
    export_csv,
    generate_run_id,
    load_config,
    load_leads,
    now_iso,
    save_leads,
    setup_logging,
)
from modules.outputs.instantly import (
    fetch_replies,
    normalize_replies,
    send_reply,
    upload_leads,
)
from modules.outputs.ghl import route_positive_reply, suggest_booking
from modules.outputs.slack import notify_positive_reply
from modules.outputs.telegram import notify_positive_reply as telegram_notify
from modules.outputs.auto_reply import handle_reply as auto_reply_handle
from modules.outputs.report_generator import run_weekly_report
from modules.reply_classifier import classify

load_dotenv(ROOT / ".env")
logger = setup_logging("pipeline", log_dir=ROOT / ".tmp")

TMP = ROOT / ".tmp"


# ---------------------------------------------------------------------------
# Pipeline state management
# ---------------------------------------------------------------------------

def load_pipeline_state(state_file: Path) -> dict:
    if state_file.exists():
        with open(state_file, encoding="utf-8") as f:
            return json.load(f)
    return {"stages": {}, "run_id": None}


def save_pipeline_state(state: dict, state_file: Path):
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def stage_complete(state: dict, stage_name: str) -> bool:
    return state.get("stages", {}).get(stage_name, {}).get("completed", False)


def mark_stage_complete(state: dict, stage_name: str, output_file: str):
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

    field_mapping = instantly_config.get("field_mapping")
    rate_limit = instantly_config.get("upload_rate_limit_delay", 1.0)

    result = upload_leads(
        api_url=api_url,
        api_key=api_key,
        campaign_id=campaign_id,
        leads=personalized,
        field_mapping=field_mapping,
        rate_limit_delay=rate_limit,
    )
    logger.info("Instantly upload complete: %d/%d succeeded", result["uploaded"], result["total"])

    save_leads(leads, input_file)
    return input_file


# ---------------------------------------------------------------------------
# Reply handling
# ---------------------------------------------------------------------------

def poll_replies(config: dict, mock: bool):
    instantly_config = config.get("instantly", {})
    api_url = instantly_config.get("api_url", "https://api.instantly.ai/api/v2")
    classification_config = config.get("classification", {})
    ghl_config = config.get("ghl", {})
    notif_config = config.get("notifications", {})

    if mock:
        replies = _get_mock_replies()
        logger.info("MOCK: Processing %d mock replies", len(replies))
    else:
        api_key = os.environ.get("INSTANTLY_API_KEY", "")
        if not api_key:
            logger.error("INSTANTLY_API_KEY not set.")
            return
        raw_replies = fetch_replies(api_url, api_key)
        replies = normalize_replies(raw_replies)

    if not replies:
        logger.info("No new replies found.")
        return

    for reply in replies:
        classification = classify(
            body=reply.get("body", ""),
            mock=mock,
            model=classification_config.get("model"),
            system_prompt=classification_config.get("system_prompt"),
            mock_signals=classification_config.get("mock_signals"),
        )
        reply["classification"] = classification
        logger.info(
            "Reply from %s classified as: %s",
            reply.get("from_email", "unknown"),
            classification,
        )

        if classification in ("hot_positive", "positive"):
            _handle_positive_reply(reply, ghl_config, notif_config, mock)

        def _send_fn(text):
            send_reply(
                api_url, api_key,
                reply_to_email=reply.get("from_email", ""),
                from_email=reply.get("lead_email", ""),
                reply_text=text,
            )

        ar_result = auto_reply_handle(reply, config, mock, send_fn=_send_fn)
        logger.info("Auto-reply decision for %s: %s",
                     reply.get("from_email", "unknown"), ar_result.get("action"))


def _handle_positive_reply(reply: dict, ghl_config: dict, notif_config: dict, mock: bool):
    if mock:
        logger.info(
            "MOCK: Would route + notify for %s (%s)",
            reply.get("from_name"),
            reply.get("from_email"),
        )
        return

    ghl_api_key = os.environ.get("GHL_API_KEY", "")
    if ghl_api_key:
        ghl_result = route_positive_reply(
            api_url=ghl_config.get("api_url", "https://services.leadconnectorhq.com"),
            api_key=ghl_api_key,
            location_id=ghl_config.get("location_id"),
            pipeline_id=ghl_config.get("pipeline_id"),
            stage_id=ghl_config.get("pipeline_stages", {}).get("new"),
            reply=reply,
            tags=ghl_config.get("tags"),
            source=ghl_config.get("source", "cold email pipeline"),
            api_version=ghl_config.get("api_version"),
        )
        booking = suggest_booking(
            contact_id=ghl_result.get("contact_id"),
            reply=reply,
            calendar_id=ghl_config.get("calendar_id"),
        )
        logger.info("Booking suggestion: %s", booking)
    else:
        logger.warning("GHL_API_KEY not set — skipping CRM routing.")

    if notif_config.get("telegram_enabled", False):
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        telegram_notify(
            bot_token=bot_token,
            chat_id=chat_id,
            reply=reply,
            template=notif_config.get("telegram_template"),
        )

    if notif_config.get("slack_enabled", False):
        slack_url = os.environ.get("SLACK_WEBHOOK_URL", "")
        notify_positive_reply(
            webhook_url=slack_url,
            reply=reply,
            template=notif_config.get("slack_template"),
        )


def _get_mock_replies() -> list[dict]:
    return [
        {
            "from_email": "maria.garcia@katymarina.com",
            "from_name": "Maria Garcia",
            "subject": "Re: Quick question",
            "body": "I'm ready to sell. Call me at 832-555-0199, my number is best after 5pm.",
            "company": "Katy Marina & Boat Storage",
            "industry": "marina",
            "received_at": now_iso(),
        },
        {
            "from_email": "john.miller@sparklecarwash.com",
            "from_name": "John Miller",
            "subject": "Re: Quick question",
            "body": "Yes, I've been thinking about selling. What's the process?",
            "company": "Sparkle Car Wash",
            "industry": "car wash",
            "received_at": now_iso(),
        },
        {
            "from_email": "tony.rossi@tonyspizzapalace.com",
            "from_name": "Tony Rossi",
            "subject": "Re: Quick question",
            "body": "Not interested, please remove me from your list.",
            "company": "Tony's Pizza Palace",
            "industry": "pizzeria",
            "received_at": now_iso(),
        },
        {
            "from_email": "auto-reply@cleanfreshlaundry.com",
            "from_name": "",
            "subject": "Out of Office",
            "body": "I am currently out of the office and will return on Monday.",
            "company": "Clean & Fresh Laundromat",
            "industry": "laundromat",
            "received_at": now_iso(),
        },
    ]


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def run_pipeline(config: dict, stage: str, mock: bool, force: bool):
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
    parser.add_argument("--weekly-report", action="store_true", help="Generate and send weekly report")
    args = parser.parse_args()

    TMP.mkdir(exist_ok=True)
    config = load_config(args.config)

    if args.weekly_report:
        logger.info("=== Weekly Report Mode ===")
        result = run_weekly_report(config, args.mock)
        logger.info(
            "Report generated. Email sent: %s | Slack sent: %s | Telegram sent: %s",
            result.get("html_sent"), result.get("slack_sent"), result.get("telegram_sent"),
        )
    elif args.poll_replies:
        logger.info("=== Reply Polling Mode ===")
        poll_replies(config, args.mock)
    else:
        run_pipeline(config, args.stage, args.mock, args.force)


if __name__ == "__main__":
    main()
