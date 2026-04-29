"""
slack.py
description: Reusable Slack webhook notification sender.
inputs: Webhook URL, message text or reply data with optional template.
outputs: HTTP response status.
"""

import logging

import requests

from modules.pipeline_utils import retry_with_backoff

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE = (
    ":white_check_mark: *Positive Reply Detected*\n"
    "*From:* {from_name} ({from_email})\n"
    "*Company:* {company}\n"
    "*Reply:* {body_preview}\n"
    "*Time:* {received_at}"
)


@retry_with_backoff(max_retries=3, base_delay=2.0)
def send_notification(webhook_url: str, message_text: str) -> bool:
    """Send a text message to a Slack incoming webhook. Returns True on success."""
    resp = requests.post(
        webhook_url,
        json={"text": message_text},
        timeout=10,
    )
    resp.raise_for_status()
    logger.info("Slack notification sent.")
    return True


def format_positive_reply(reply: dict, template: str | None = None) -> str:
    """Format a positive reply dict into a Slack message string."""
    tmpl = template or DEFAULT_TEMPLATE
    return tmpl.format(
        from_name=reply.get("from_name", "Unknown"),
        from_email=reply.get("from_email", ""),
        company=reply.get("company", "Unknown"),
        body_preview=(reply.get("body", "") or "")[:200],
        received_at=reply.get("received_at", ""),
    )


def notify_positive_reply(
    webhook_url: str, reply: dict, template: str | None = None,
) -> bool:
    """Format and send a positive reply notification. Returns True on success."""
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL not set — skipping notification.")
        return False

    try:
        message = format_positive_reply(reply, template)
        return send_notification(webhook_url, message)
    except Exception:
        logger.exception("Slack notification failed for %s", reply.get("from_email"))
        return False
