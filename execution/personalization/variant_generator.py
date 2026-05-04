#!/usr/bin/env python3
"""
variant_generator.py
description: Generate AI challenger email variants and analyze per-variant performance for A/B testing.
inputs: --action (generate|analyze|recommend|report), --config, --mock; env: OPENROUTER_API_KEY, INSTANTLY_API_KEY
outputs: Updated config/email_variants.json, .tmp/variant_report.json
usage:
    py execution/personalization/variant_generator.py --action generate --mock
    py execution/personalization/variant_generator.py --action analyze --mock
    py execution/personalization/variant_generator.py --action recommend --mock
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "execution"))

from modules.pipeline_utils import load_config, now_iso, setup_logging

load_dotenv(ROOT / ".env")
logger = setup_logging("variant_generator", log_dir=ROOT / ".tmp")

DEFAULT_MODEL = "anthropic/claude-haiku-4.5"


def load_variants(variants_file: str) -> dict:
    path = Path(variants_file)
    if not path.is_absolute():
        path = ROOT / path
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_variants(variants_data: dict, variants_file: str) -> Path:
    path = Path(variants_file)
    if not path.is_absolute():
        path = ROOT / path
    with open(path, "w", encoding="utf-8") as f:
        json.dump(variants_data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path


def build_variant_system_prompt(tone_config: dict, human_variants: list[dict]) -> str:
    sender = tone_config.get("sender_name", "Aleksandar")
    company = tone_config.get("company_name", "Accessory Masters")
    backing = tone_config.get("backing", "Hedgestone Capital Group")
    tone_desc = tone_config.get("tone_description", "Direct and blunt.")
    copy_phil = tone_config.get("copy_philosophy", "")
    never_say = tone_config.get("never_say", [])

    prompt = f"""You write cold email variants for {sender} at {company}, backed by {backing}.

TONE: {tone_desc}

COPY PHILOSOPHY: {copy_phil}

GUARD RAILS:
- Never promise specific valuations or dollar amounts
- Never mention AI, automation, or algorithms
- Maximum 3 sentences
- No exclamation marks
- No sales-y or corporate language ("exciting opportunity", "game-changing", "transform", "synergy")
- Use template variables: {{{{opener}}}}, {{{{industry}}}}, {{{{city}}}}, {{{{business_name}}}}
- Sound like a real person texting, not a marketer

EXISTING HUMAN VARIANTS (match this style):
"""
    for v in human_variants:
        prompt += f"\n[{v['label']}]\nSubject: {v['subject']}\nBody: {v['body']}\n"

    if never_say:
        prompt += "\nNEVER SAY: " + ", ".join(f'"{w}"' for w in never_say)

    prompt += """

YOUR TASK: Generate a new email variant that could outperform the existing ones. Return a JSON object with exactly two fields: "subject" and "body". No markdown, no code fences, just raw JSON."""

    return prompt


def validate_variant(body: str, constraints: dict) -> bool:
    if not body:
        return False
    words = body.split()
    max_words = constraints.get("max_words", 60)
    if len(words) > max_words:
        return False
    sentences = [s.strip() for s in body.replace("?", ".").replace("...", ".").split(".") if s.strip()]
    max_sentences = constraints.get("max_sentences", 3)
    if len(sentences) > max_sentences:
        return False
    if constraints.get("no_exclamation_marks", True) and "!" in body:
        return False
    return True


def generate_mock_variant(human_variants: list[dict]) -> dict:
    return {
        "variant_id": f"ai_{now_iso()[:10].replace('-', '')}",
        "type": "ai",
        "label": "AI Challenger",
        "subject": "Thought about selling?",
        "body": "{{opener}} Business owners in {{city}} are getting serious offers right now. Worth a conversation?",
        "created_at": now_iso(),
        "created_by": "claude-haiku-4.5",
        "active": False,
        "instantly_step_id": None,
    }


def generate_challenger_variant(
    human_variants: list[dict],
    tone_config: dict,
    constraints: dict,
    model: str,
    mock: bool,
) -> dict:
    if mock:
        return generate_mock_variant(human_variants)

    from modules.llm_client import chat_completion

    system_prompt = build_variant_system_prompt(tone_config, human_variants)
    user_prompt = "Generate one new cold email variant as JSON with \"subject\" and \"body\" fields."

    for attempt in range(2):
        try:
            raw = chat_completion(
                system=system_prompt,
                user_message=user_prompt,
                model=model,
                max_tokens=300,
            )
            raw = raw.strip("`").removeprefix("json").strip()
            parsed = json.loads(raw)
            subject = parsed.get("subject", "")
            body = parsed.get("body", "")

            if not subject or not body:
                logger.debug("Missing subject or body (attempt %d)", attempt + 1)
                continue

            if validate_variant(body, constraints):
                return {
                    "variant_id": f"ai_{now_iso()[:10].replace('-', '')}",
                    "type": "ai",
                    "label": "AI Challenger",
                    "subject": subject,
                    "body": body,
                    "created_at": now_iso(),
                    "created_by": model,
                    "active": False,
                    "instantly_step_id": None,
                }

            if attempt == 0:
                logger.debug("Variant validation failed, retrying")
        except (json.JSONDecodeError, KeyError):
            logger.debug("Failed to parse Claude response (attempt %d)", attempt + 1)
        except Exception:
            logger.exception("Claude API error (attempt %d)", attempt + 1)

    logger.warning("Falling back to mock variant after failed generation")
    return generate_mock_variant(human_variants)


def generate_mock_performance(variants: list[dict]) -> list[dict]:
    active = [v for v in variants if v.get("active")]
    results = []
    for idx, v in enumerate(active):
        sent = 150 + idx * 50
        replies = 3 + idx * 2
        positive = 1 + idx
        negative = idx % 2
        rate = round((replies / sent) * 100, 2) if sent > 0 else 0.0
        results.append({
            "variant_id": v["variant_id"],
            "emails_sent": sent,
            "replies": replies,
            "positive_replies": positive,
            "negative_replies": negative,
            "response_rate_pct": rate,
        })
    return results


def fetch_variant_performance(
    api_url: str,
    api_key: str,
    campaign_id: str,
    variants: list[dict],
    mock: bool,
) -> list[dict]:
    if mock:
        return generate_mock_performance(variants)

    from modules.outputs.instantly import fetch_step_analytics

    step_list = fetch_step_analytics(api_url, api_key, campaign_id)
    step_map = {s["step_id"]: s for s in step_list}
    results = []
    for v in variants:
        if not v.get("active") or not v.get("instantly_step_id"):
            continue
        step_id = v["instantly_step_id"]
        stats = step_map.get(step_id, {})
        sent = stats.get("emails_sent", 0)
        replies = stats.get("replies", 0)
        rate = round((replies / sent) * 100, 2) if sent > 0 else 0.0
        results.append({
            "variant_id": v["variant_id"],
            "emails_sent": sent,
            "replies": replies,
            "positive_replies": stats.get("positive_replies", 0),
            "negative_replies": stats.get("negative_replies", 0),
            "response_rate_pct": rate,
        })
    return results


def recommend_replacement(
    variants: list[dict],
    performance: list[dict],
    config: dict,
) -> dict:
    min_sends = config.get("min_sends_for_comparison", 100)
    threshold = config.get("replacement_threshold_pct", 0.5)

    perf_map = {p["variant_id"]: p for p in performance}

    human_perfs = []
    for v in variants:
        if v.get("type") != "human" or not v.get("active"):
            continue
        p = perf_map.get(v["variant_id"])
        if p and p["emails_sent"] >= min_sends:
            human_perfs.append({"variant": v, "perf": p})

    ai_perfs = []
    for v in variants:
        if v.get("type") != "ai" or not v.get("active"):
            continue
        p = perf_map.get(v["variant_id"])
        if p and p["emails_sent"] >= min_sends:
            ai_perfs.append({"variant": v, "perf": p})

    if not human_perfs:
        return {
            "action": "insufficient_data",
            "worst_human": None,
            "ai_variant": None,
            "reason": "Not enough human variant data (need at least {0} sends).".format(min_sends),
        }

    if not ai_perfs:
        return {
            "action": "insufficient_data",
            "worst_human": None,
            "ai_variant": None,
            "reason": "No AI variant has enough sends for comparison (need at least {0}).".format(min_sends),
        }

    worst = min(human_perfs, key=lambda x: x["perf"]["response_rate_pct"])
    best_ai = max(ai_perfs, key=lambda x: x["perf"]["response_rate_pct"])

    worst_rate = worst["perf"]["response_rate_pct"]
    ai_rate = best_ai["perf"]["response_rate_pct"]
    delta = ai_rate - worst_rate

    worst_label = worst["variant"].get("label", worst["variant"]["variant_id"])

    if delta >= threshold:
        return {
            "action": "replace",
            "worst_human": worst["variant"],
            "ai_variant": best_ai["variant"],
            "reason": (
                f"AI variant ({ai_rate}% response rate) outperforms "
                f"worst human variant '{worst_label}' ({worst_rate}%) "
                f"by {delta:.2f}pp, exceeding {threshold}pp threshold."
            ),
        }

    return {
        "action": "keep",
        "worst_human": worst["variant"],
        "ai_variant": best_ai["variant"],
        "reason": (
            f"AI variant ({ai_rate}%) does not outperform worst human variant "
            f"'{worst_label}' ({worst_rate}%) by enough "
            f"({delta:.2f}pp < {threshold}pp threshold)."
        ),
    }


def format_variant_report(
    variants: list[dict],
    performance: list[dict],
    recommendation: dict,
) -> str:
    lines = ["VARIANT PERFORMANCE REPORT", "=" * 40, ""]

    perf_map = {p["variant_id"]: p for p in performance}

    lines.append("ACTIVE VARIANTS:")
    lines.append("-" * 40)
    for v in variants:
        if not v.get("active"):
            continue
        p = perf_map.get(v["variant_id"])
        status = f"  [{v['type'].upper()}] {v['label']} ({v['variant_id']})"
        if p:
            status += (
                f"\n    Sent: {p['emails_sent']}  Replies: {p['replies']}  "
                f"Rate: {p['response_rate_pct']}%  "
                f"Positive: {p['positive_replies']}  Negative: {p['negative_replies']}"
            )
        else:
            status += "\n    No performance data"
        lines.append(status)

    lines.append("")
    lines.append("RECOMMENDATION:")
    lines.append("-" * 40)
    lines.append(f"Action: {recommendation['action']}")
    lines.append(f"Reason: {recommendation['reason']}")

    if recommendation.get("worst_human"):
        wh = recommendation["worst_human"]
        lines.append(f"Worst human: {wh.get('label', wh['variant_id'])} ({wh['variant_id']})")
    if recommendation.get("ai_variant"):
        av = recommendation["ai_variant"]
        lines.append(f"AI challenger: {av.get('label', av['variant_id'])} ({av['variant_id']})")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate AI challenger variants and analyze A/B performance"
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=["generate", "analyze", "recommend", "report", "activate"],
        help="Action to perform",
    )
    parser.add_argument("--variant-id", help="Variant ID (for activate action)")
    parser.add_argument("--step-id", help="Instantly step ID (for activate action)")
    parser.add_argument("--config", default=str(ROOT / "config" / "accessory_masters.json"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--mock", action="store_true", help="Use mock data")
    args = parser.parse_args()

    (ROOT / ".tmp").mkdir(exist_ok=True)

    config = load_config(args.config)
    copy_config = config.get("copy_optimization", {})
    instantly_config = config.get("instantly", {})
    tone_config = load_config(str(ROOT / config["personalization"]["tone_config"]))

    variants_file = copy_config.get("variants_file", "config/email_variants.json")
    variants_data = load_variants(variants_file)
    all_variants = variants_data.get("variants", []) + variants_data.get("ai_challengers", [])
    human_variants = [v for v in variants_data.get("variants", []) if v.get("type") == "human"]
    constraints = copy_config.get("variant_constraints", {})
    model = args.model or copy_config.get("model", DEFAULT_MODEL)

    if args.action == "generate":
        max_variants = copy_config.get("max_variants", 5)
        current_ai = len(variants_data.get("ai_challengers", []))
        if current_ai >= max_variants:
            logger.warning("Already at max AI variants (%d). Remove or deactivate one first.", max_variants)
            sys.exit(0)

        new_variant = generate_challenger_variant(
            human_variants, tone_config, constraints, model, args.mock
        )
        variants_data["ai_challengers"].append(new_variant)
        saved_path = save_variants(variants_data, variants_file)
        logger.info(
            "Generated AI challenger '%s' and saved to %s",
            new_variant["variant_id"],
            saved_path,
        )
        logger.info(
            "Next step: Add this variant to Instantly as a campaign step, "
            "then run: py execution/personalization/variant_generator.py "
            "--action activate --variant-id %s --step-id <INSTANTLY_STEP_ID>",
            new_variant["variant_id"],
        )
        logger.info("Subject: %s", new_variant["subject"])
        logger.info("Body: %s", new_variant["body"])

    elif args.action == "analyze":
        performance = fetch_variant_performance(
            instantly_config.get("api_url", ""),
            os.environ.get("INSTANTLY_API_KEY", ""),
            instantly_config.get("campaign_id", ""),
            all_variants,
            args.mock,
        )
        for p in performance:
            logger.info(
                "Variant %s: %d sent, %d replies, %.2f%% rate",
                p["variant_id"],
                p["emails_sent"],
                p["replies"],
                p["response_rate_pct"],
            )

    elif args.action == "recommend":
        performance = fetch_variant_performance(
            instantly_config.get("api_url", ""),
            os.environ.get("INSTANTLY_API_KEY", ""),
            instantly_config.get("campaign_id", ""),
            all_variants,
            args.mock,
        )
        recommendation = recommend_replacement(all_variants, performance, copy_config)
        logger.info("Recommendation: %s — %s", recommendation["action"], recommendation["reason"])

    elif args.action == "report":
        performance = fetch_variant_performance(
            instantly_config.get("api_url", ""),
            os.environ.get("INSTANTLY_API_KEY", ""),
            instantly_config.get("campaign_id", ""),
            all_variants,
            args.mock,
        )
        recommendation = recommend_replacement(all_variants, performance, copy_config)
        report_text = format_variant_report(all_variants, performance, recommendation)
        logger.info("\n%s", report_text)

        report_path = ROOT / ".tmp" / "variant_report.json"
        report_data = {
            "generated_at": now_iso(),
            "variants": all_variants,
            "performance": performance,
            "recommendation": recommendation,
            "report_text": report_text,
        }
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        logger.info("Report saved to %s", report_path)

    elif args.action == "activate":
        if not args.variant_id or not args.step_id:
            logger.error("--variant-id and --step-id are required for activate")
            sys.exit(1)

        found = False
        for section in ("variants", "ai_challengers"):
            for v in variants_data.get(section, []):
                if v["variant_id"] == args.variant_id:
                    v["instantly_step_id"] = args.step_id
                    v["active"] = True
                    v["activated_at"] = now_iso()
                    found = True
                    break
            if found:
                break

        if not found:
            logger.error("Variant '%s' not found in %s", args.variant_id, variants_file)
            sys.exit(1)

        save_variants(variants_data, variants_file)
        logger.info(
            "Activated variant '%s' with Instantly step_id '%s'",
            args.variant_id, args.step_id,
        )


if __name__ == "__main__":
    main()
