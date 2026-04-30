"""
telegram.py
description: Reusable Telegram Bot API notification sender.
inputs: Bot token, chat ID, message text or reply data with optional template.
outputs: HTTP response status.
"""

import argparse
import logging

import requests

from modules.pipeline_utils import retry_with_backoff

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE = (
    "✅ *Positive Reply Detected*\n"
    "*Lead:* {from_name} ({from_email})\n"
    "*Company:* {company}\n"
    "*Industry:* {industry}\n"
    "*Email Sent:* {email_subject}\n"
    "*Response:* {body_preview}\n"
    "*Time:* {received_at}\n"
    "[View in GHL]({ghl_link})"
)


@retry_with_backoff(max_retries=3, base_delay=2.0)
def send_message(
    bot_token: str, chat_id: str, text: str, parse_mode: str = "Markdown",
) -> bool:
    """Send a text message via Telegram Bot API. Returns True on success."""
    resp = requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
        timeout=10,
    )
    resp.raise_for_status()
    logger.info("Telegram notification sent.")
    return True


def format_positive_reply(reply: dict, template: str | None = None) -> str:
    """Format a positive reply dict into a Telegram message string."""
    tmpl = template or DEFAULT_TEMPLATE
    return tmpl.format(
        from_name=reply.get("from_name", "Unknown"),
        from_email=reply.get("from_email", ""),
        company=reply.get("company", "Unknown"),
        industry=reply.get("industry", "Unknown"),
        email_subject=reply.get("email_subject", ""),
        body_preview=(reply.get("body", "") or "")[:200],
        received_at=reply.get("received_at", ""),
        ghl_link=reply.get("ghl_link", "#"),
    )


def notify_positive_reply(
    bot_token: str, chat_id: str, reply: dict, template: str | None = None,
) -> bool:
    """Format and send a positive reply notification. Returns True on success."""
    if not bot_token or not chat_id:
        logger.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — skipping.")
        return False

    try:
        message = format_positive_reply(reply, template)
        return send_message(bot_token, chat_id, message)
    except Exception:
        logger.exception("Telegram notification failed for %s", reply.get("from_email"))
        return False


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser(description="Telegram notification module")
    parser.add_argument("--bot-token", default=None, help="Telegram bot token")
    parser.add_argument("--chat-id", default=None, help="Telegram chat ID")
    parser.add_argument("--mock", action="store_true", help="Print message instead of sending")
    args = parser.parse_args()

    sample_reply = {
        "from_name": "Jane Doe",
        "from_email": "jane@example.com",
        "company": "Acme Corp",
        "industry": "SaaS",
        "email_subject": "Quick question about your growth strategy",
        "body": "Hi, thanks for reaching out! I'd love to schedule a call to discuss.",
        "received_at": "2026-04-30T10:00:00Z",
        "ghl_link": "https://app.gohighlevel.com/contacts/example",
    }

    formatted = format_positive_reply(sample_reply)

    if args.mock:
        print(formatted)
    else:
        notify_positive_reply(args.bot_token, args.chat_id, sample_reply)
