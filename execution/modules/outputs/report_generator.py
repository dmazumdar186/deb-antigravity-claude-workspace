"""
report_generator.py
description: Reusable weekly report generator — aggregates Instantly + GHL metrics into HTML/Slack reports.
inputs: API keys (env), campaign/pipeline IDs, date range, config dict.
outputs: Formatted HTML email and/or Slack message with campaign metrics.
"""

import logging
import os
import random
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from modules.outputs.telegram import send_message as telegram_send_message
from modules.pipeline_utils import retry_with_backoff

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _default_date_range() -> dict:
    """Return a date range dict for the last 7 days (ISO 8601 strings)."""
    now = datetime.now(timezone.utc)
    return {
        "start": (now - timedelta(days=7)).strftime("%Y-%m-%d"),
        "end": now.strftime("%Y-%m-%d"),
    }


# ---------------------------------------------------------------------------
# Instantly metrics
# ---------------------------------------------------------------------------

@retry_with_backoff(max_retries=3, base_delay=2.0)
def _instantly_get(url: str, api_key: str, params: dict | None = None) -> dict:
    """Low-level GET against Instantly API with auth + retry."""
    resp = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        params=params or {},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_instantly_metrics(
    api_url: str,
    api_key: str,
    campaign_id: str | None = None,
    date_range: dict | None = None,
    mock: bool = False,
) -> dict:
    """Pull campaign analytics from Instantly.

    Args:
        api_url: Base Instantly API URL (e.g. https://api.instantly.ai/api/v2).
        api_key: Instantly API key.
        campaign_id: Optional campaign ID to filter by.
        date_range: Dict with 'start' and 'end' ISO date strings.
        mock: If True, return realistic sample data without calling the API.

    Returns:
        Dict with keys: emails_sent, emails_delivered, emails_opened,
        replies, bounces, unsubscribes, deliverability_pct, open_rate_pct,
        reply_rate_pct, bounce_rate_pct.
    """
    if mock:
        return generate_mock_metrics()["instantly"]

    dr = date_range or _default_date_range()
    params: dict = {
        "start_date": dr["start"],
        "end_date": dr["end"],
    }
    if campaign_id:
        params["campaign_id"] = campaign_id

    try:
        overview = _instantly_get(
            f"{api_url}/campaigns/analytics/overview",
            api_key,
            params,
        )
    except Exception:
        logger.exception("Failed to fetch Instantly analytics overview")
        overview = {}

    sent = overview.get("total_emails_sent", 0)
    delivered = overview.get("total_emails_delivered", sent)
    opened = overview.get("total_emails_opened", 0)
    replies = overview.get("total_replies", 0)
    bounces = overview.get("total_bounces", 0)
    unsubscribes = overview.get("total_unsubscribes", 0)

    return {
        "emails_sent": sent,
        "emails_delivered": delivered,
        "emails_opened": opened,
        "replies": replies,
        "bounces": bounces,
        "unsubscribes": unsubscribes,
        "deliverability_pct": round((delivered / sent * 100) if sent else 0, 1),
        "open_rate_pct": round((opened / delivered * 100) if delivered else 0, 1),
        "reply_rate_pct": round((replies / delivered * 100) if delivered else 0, 1),
        "bounce_rate_pct": round((bounces / sent * 100) if sent else 0, 1),
    }


# ---------------------------------------------------------------------------
# GHL metrics
# ---------------------------------------------------------------------------

@retry_with_backoff(max_retries=3, base_delay=2.0)
def _ghl_get(url: str, api_key: str, params: dict | None = None,
             api_version: str = "2021-07-28") -> dict:
    """Low-level GET against GHL API with auth + retry."""
    resp = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Version": api_version,
        },
        params=params or {},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_ghl_metrics(
    api_url: str,
    api_key: str,
    location_id: str | None = None,
    pipeline_id: str | None = None,
    date_range: dict | None = None,
    api_version: str = "2021-07-28",
    mock: bool = False,
) -> dict:
    """Pull CRM metrics from GoHighLevel.

    Args:
        api_url: Base GHL API URL (e.g. https://services.leadconnectorhq.com).
        api_key: GHL API key.
        location_id: GHL location ID.
        pipeline_id: GHL pipeline ID for opportunity queries.
        date_range: Dict with 'start' and 'end' ISO date strings.
        api_version: GHL API version header.
        mock: If True, return realistic sample data.

    Returns:
        Dict with keys: contacts_created, opportunities_total,
        opportunities_open, opportunities_won, appointments_booked,
        pipeline_value.
    """
    if mock:
        return generate_mock_metrics()["ghl"]

    dr = date_range or _default_date_range()
    metrics = {
        "contacts_created": 0,
        "opportunities_total": 0,
        "opportunities_open": 0,
        "opportunities_won": 0,
        "appointments_booked": 0,
        "pipeline_value": 0.0,
    }

    # --- Contacts created in date range ---
    if location_id:
        try:
            contacts_resp = _ghl_get(
                f"{api_url}/contacts/",
                api_key,
                params={
                    "locationId": location_id,
                    "startAfter": dr["start"],
                    "startBefore": dr["end"],
                    "limit": 1,
                },
                api_version=api_version,
            )
            metrics["contacts_created"] = contacts_resp.get("meta", {}).get("total", 0)
        except Exception:
            logger.exception("Failed to fetch GHL contacts count")

    # --- Opportunities in pipeline ---
    if pipeline_id and location_id:
        try:
            opps_resp = _ghl_get(
                f"{api_url}/opportunities/search",
                api_key,
                params={
                    "location_id": location_id,
                    "pipeline_id": pipeline_id,
                },
                api_version=api_version,
            )
            opps = opps_resp.get("opportunities", [])
            metrics["opportunities_total"] = len(opps)
            metrics["opportunities_open"] = sum(
                1 for o in opps if o.get("status") == "open"
            )
            metrics["opportunities_won"] = sum(
                1 for o in opps if o.get("status") == "won"
            )
            metrics["pipeline_value"] = sum(
                float(o.get("monetaryValue", 0) or 0) for o in opps
            )
        except Exception:
            logger.exception("Failed to fetch GHL opportunities")

    # --- Appointments booked ---
    if location_id:
        try:
            appts_resp = _ghl_get(
                f"{api_url}/calendars/events/appointments",
                api_key,
                params={
                    "locationId": location_id,
                    "startTime": dr["start"],
                    "endTime": dr["end"],
                },
                api_version=api_version,
            )
            events = appts_resp.get("events", [])
            metrics["appointments_booked"] = len(events)
        except Exception:
            logger.exception("Failed to fetch GHL appointments")

    return metrics


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(
    instantly_metrics: dict,
    ghl_metrics: dict,
    config: dict | None = None,
) -> dict:
    """Combine Instantly + GHL metrics into a single report dict.

    Args:
        instantly_metrics: Output of fetch_instantly_metrics().
        ghl_metrics: Output of fetch_ghl_metrics().
        config: Optional client config with 'client' key etc.

    Returns:
        Dict with 'client', 'generated_at', 'date_range', 'email',
        'crm', and 'summary' sections.
    """
    cfg = config or {}
    now = datetime.now(timezone.utc)

    report = {
        "client": cfg.get("client", "Unknown Client"),
        "generated_at": now.isoformat(),
        "date_range": {
            "start": (now - timedelta(days=7)).strftime("%Y-%m-%d"),
            "end": now.strftime("%Y-%m-%d"),
        },
        "email": instantly_metrics,
        "crm": ghl_metrics,
        "summary": _build_summary(instantly_metrics, ghl_metrics),
    }
    return report


def _build_summary(instantly: dict, ghl: dict) -> dict:
    """Derive headline summary stats from raw metrics."""
    return {
        "total_emails_sent": instantly.get("emails_sent", 0),
        "total_replies": instantly.get("replies", 0),
        "reply_rate_pct": instantly.get("reply_rate_pct", 0),
        "deliverability_pct": instantly.get("deliverability_pct", 0),
        "contacts_created": ghl.get("contacts_created", 0),
        "appointments_booked": ghl.get("appointments_booked", 0),
        "pipeline_value": ghl.get("pipeline_value", 0),
        "opportunities_open": ghl.get("opportunities_open", 0),
    }


# ---------------------------------------------------------------------------
# HTML formatting
# ---------------------------------------------------------------------------

DEFAULT_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #333; max-width: 640px; margin: auto; padding: 20px; }}
  h1 {{ color: #1a1a2e; border-bottom: 2px solid #e94560; padding-bottom: 8px; font-size: 22px; }}
  h2 {{ color: #16213e; font-size: 16px; margin-top: 24px; }}
  .metric-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 12px 0; }}
  .metric-card {{ background: #f5f5f5; border-radius: 8px; padding: 14px; text-align: center; }}
  .metric-value {{ font-size: 28px; font-weight: 700; color: #1a1a2e; }}
  .metric-label {{ font-size: 12px; color: #666; margin-top: 4px; }}
  .highlight {{ background: #e8f5e9; }}
  .warn {{ background: #fff3e0; }}
  .footer {{ margin-top: 32px; font-size: 11px; color: #999; border-top: 1px solid #eee; padding-top: 12px; }}
</style>
</head>
<body>
<h1>{client} — Weekly Report</h1>
<p style="color:#666;font-size:13px;">{date_range_start} to {date_range_end} &middot; Generated {generated_at}</p>

<h2>Email Performance</h2>
<div class="metric-grid">
  <div class="metric-card">
    <div class="metric-value">{emails_sent}</div>
    <div class="metric-label">Emails Sent</div>
  </div>
  <div class="metric-card {deliverability_class}">
    <div class="metric-value">{deliverability_pct}%</div>
    <div class="metric-label">Deliverability</div>
  </div>
  <div class="metric-card">
    <div class="metric-value">{open_rate_pct}%</div>
    <div class="metric-label">Open Rate</div>
  </div>
  <div class="metric-card {reply_class}">
    <div class="metric-value">{reply_rate_pct}%</div>
    <div class="metric-label">Reply Rate</div>
  </div>
  <div class="metric-card">
    <div class="metric-value">{replies}</div>
    <div class="metric-label">Total Replies</div>
  </div>
  <div class="metric-card {bounce_class}">
    <div class="metric-value">{bounce_rate_pct}%</div>
    <div class="metric-label">Bounce Rate</div>
  </div>
</div>

<h2>CRM Pipeline</h2>
<div class="metric-grid">
  <div class="metric-card">
    <div class="metric-value">{contacts_created}</div>
    <div class="metric-label">Contacts Created</div>
  </div>
  <div class="metric-card">
    <div class="metric-value">{opportunities_total}</div>
    <div class="metric-label">Opportunities</div>
  </div>
  <div class="metric-card highlight">
    <div class="metric-value">{appointments_booked}</div>
    <div class="metric-label">Appointments Booked</div>
  </div>
  <div class="metric-card highlight">
    <div class="metric-value">${pipeline_value:,.0f}</div>
    <div class="metric-label">Pipeline Value</div>
  </div>
</div>

<div class="footer">
  Auto-generated by the GTM Pipeline Report Generator. Do not reply to this email.
</div>
</body>
</html>
"""


def format_html_report(report: dict, template: str | None = None) -> str:
    """Render a report dict as an HTML email string.

    Args:
        report: Output of generate_report().
        template: Optional custom HTML template with {placeholder} tokens.

    Returns:
        Formatted HTML string.
    """
    tmpl = template or DEFAULT_HTML_TEMPLATE
    email = report.get("email", {})
    crm = report.get("crm", {})

    # Conditional CSS classes for health indicators
    deliverability = email.get("deliverability_pct", 0)
    reply_rate = email.get("reply_rate_pct", 0)
    bounce_rate = email.get("bounce_rate_pct", 0)

    return tmpl.format(
        client=report.get("client", "Client"),
        date_range_start=report.get("date_range", {}).get("start", ""),
        date_range_end=report.get("date_range", {}).get("end", ""),
        generated_at=report.get("generated_at", "")[:10],
        emails_sent=email.get("emails_sent", 0),
        deliverability_pct=deliverability,
        deliverability_class="highlight" if deliverability >= 95 else "warn" if deliverability < 90 else "",
        open_rate_pct=email.get("open_rate_pct", 0),
        reply_rate_pct=reply_rate,
        reply_class="highlight" if reply_rate >= 3 else "",
        replies=email.get("replies", 0),
        bounce_rate_pct=bounce_rate,
        bounce_class="warn" if bounce_rate > 3 else "",
        contacts_created=crm.get("contacts_created", 0),
        opportunities_total=crm.get("opportunities_total", 0),
        appointments_booked=crm.get("appointments_booked", 0),
        pipeline_value=crm.get("pipeline_value", 0),
    )


# ---------------------------------------------------------------------------
# Slack formatting
# ---------------------------------------------------------------------------

DEFAULT_SLACK_TEMPLATE = (
    ":bar_chart: *{client} — Weekly Report*\n"
    "_{date_range_start} to {date_range_end}_\n\n"
    "*Email Performance*\n"
    ":envelope: Sent: *{emails_sent}*  |  "
    ":dart: Deliverability: *{deliverability_pct}%*  |  "
    ":eyes: Open Rate: *{open_rate_pct}%*\n"
    ":speech_balloon: Replies: *{replies}* ({reply_rate_pct}%)  |  "
    ":warning: Bounces: {bounce_rate_pct}%\n\n"
    "*CRM Pipeline*\n"
    ":busts_in_silhouette: Contacts: *{contacts_created}*  |  "
    ":handshake: Opportunities: *{opportunities_total}*\n"
    ":calendar: Appointments: *{appointments_booked}*  |  "
    ":moneybag: Pipeline: *${pipeline_value:,.0f}*\n"
)


def format_slack_report(report: dict, template: str | None = None) -> str:
    """Render a report dict as a Slack mrkdwn message.

    Args:
        report: Output of generate_report().
        template: Optional custom Slack template with {placeholder} tokens.

    Returns:
        Formatted Slack message string.
    """
    tmpl = template or DEFAULT_SLACK_TEMPLATE
    email = report.get("email", {})
    crm = report.get("crm", {})

    return tmpl.format(
        client=report.get("client", "Client"),
        date_range_start=report.get("date_range", {}).get("start", ""),
        date_range_end=report.get("date_range", {}).get("end", ""),
        emails_sent=email.get("emails_sent", 0),
        deliverability_pct=email.get("deliverability_pct", 0),
        open_rate_pct=email.get("open_rate_pct", 0),
        replies=email.get("replies", 0),
        reply_rate_pct=email.get("reply_rate_pct", 0),
        bounce_rate_pct=email.get("bounce_rate_pct", 0),
        contacts_created=crm.get("contacts_created", 0),
        opportunities_total=crm.get("opportunities_total", 0),
        appointments_booked=crm.get("appointments_booked", 0),
        pipeline_value=crm.get("pipeline_value", 0),
    )


# ---------------------------------------------------------------------------
# Telegram formatting
# ---------------------------------------------------------------------------

DEFAULT_TELEGRAM_TEMPLATE = (
    "*{client} — Weekly Report*\n"
    "_{date_range_start} to {date_range_end}_\n\n"
    "*Email Performance*\n"
    "Sent: *{emails_sent}*  |  Deliverability: *{deliverability_pct}%*\n"
    "Replies: *{replies}* ({reply_rate_pct}%)  |  Bounces: {bounce_rate_pct}%\n\n"
    "*CRM Pipeline*\n"
    "Contacts: *{contacts_created}*  |  Appointments: *{appointments_booked}*\n"
    "Pipeline: *${pipeline_value}*"
)


def format_telegram_report(report: dict, template: str | None = None) -> str:
    """Render a report dict as a Telegram Markdown message.

    Args:
        report: Output of generate_report().
        template: Optional custom Telegram template with {placeholder} tokens.

    Returns:
        Formatted Telegram message string.
    """
    tmpl = template or DEFAULT_TELEGRAM_TEMPLATE
    email = report.get("email", {})
    crm = report.get("crm", {})

    return tmpl.format(
        client=report.get("client", "Client"),
        date_range_start=report.get("date_range", {}).get("start", ""),
        date_range_end=report.get("date_range", {}).get("end", ""),
        emails_sent=email.get("emails_sent", 0),
        deliverability_pct=email.get("deliverability_pct", 0),
        replies=email.get("replies", 0),
        reply_rate_pct=email.get("reply_rate_pct", 0),
        bounce_rate_pct=email.get("bounce_rate_pct", 0),
        contacts_created=crm.get("contacts_created", 0),
        appointments_booked=crm.get("appointments_booked", 0),
        pipeline_value=f"{crm.get('pipeline_value', 0):,.0f}",
    )


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------

def send_report_email(
    report_html: str,
    recipients: list[str],
    subject: str,
    smtp_config: dict,
) -> bool:
    """Send an HTML report via SMTP.

    Args:
        report_html: Rendered HTML string.
        recipients: List of email addresses.
        subject: Email subject line.
        smtp_config: Dict with 'host', 'port', 'username', 'password',
                     'from_email', and optional 'use_tls' (default True).

    Returns:
        True on success, False on failure.
    """
    if not recipients:
        logger.warning("No report recipients configured — skipping email send.")
        return False
    if not smtp_config:
        logger.warning("SMTP config not provided — skipping email send.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_config.get("from_email", smtp_config.get("username", ""))
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(report_html, "html"))

        host = smtp_config["host"]
        port = int(smtp_config.get("port", 587))
        use_tls = smtp_config.get("use_tls", True)

        with smtplib.SMTP(host, port) as server:
            if use_tls:
                server.starttls()
            server.login(smtp_config["username"], smtp_config["password"])
            server.sendmail(msg["From"], recipients, msg.as_string())

        logger.info("Report email sent to %s", recipients)
        return True
    except Exception:
        logger.exception("Failed to send report email")
        return False


@retry_with_backoff(max_retries=3, base_delay=2.0)
def send_report_slack(report_slack: str, webhook_url: str) -> bool:
    """Send a formatted Slack report via incoming webhook.

    Args:
        report_slack: Formatted Slack message string.
        webhook_url: Slack incoming webhook URL.

    Returns:
        True on success.
    """
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL not set — skipping report Slack send.")
        return False

    resp = requests.post(
        webhook_url,
        json={"text": report_slack},
        timeout=10,
    )
    resp.raise_for_status()
    logger.info("Report sent to Slack.")
    return True


def send_report_telegram(
    report_text: str, bot_token: str, chat_id: str,
) -> bool:
    """Send a formatted Telegram report via the telegram module.

    Args:
        report_text: Formatted Telegram message string.
        bot_token: Telegram Bot API token.
        chat_id: Telegram chat ID to send to.

    Returns:
        True on success, False on failure.
    """
    if not bot_token or not chat_id:
        logger.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — skipping report Telegram send.")
        return False

    try:
        return telegram_send_message(bot_token, chat_id, report_text, parse_mode="Markdown")
    except Exception:
        logger.exception("Failed to send report via Telegram")
        return False


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

def generate_mock_metrics() -> dict:
    """Return realistic sample metrics for testing without API calls.

    Returns:
        Dict with 'instantly' and 'ghl' keys, each containing metric dicts.
    """
    sent = random.randint(600, 1200)
    bounces = random.randint(5, int(sent * 0.03))
    delivered = sent - bounces
    opened = random.randint(int(delivered * 0.35), int(delivered * 0.55))
    replies = random.randint(int(delivered * 0.02), int(delivered * 0.06))
    unsubscribes = random.randint(0, 5)

    contacts = random.randint(3, 15)
    opps_total = random.randint(2, contacts)
    opps_open = random.randint(1, opps_total)
    opps_won = opps_total - opps_open
    appointments = random.randint(0, min(5, opps_total))
    pipeline_val = round(random.uniform(50_000, 500_000), 2)

    return {
        "instantly": {
            "emails_sent": sent,
            "emails_delivered": delivered,
            "emails_opened": opened,
            "replies": replies,
            "bounces": bounces,
            "unsubscribes": unsubscribes,
            "deliverability_pct": round(delivered / sent * 100, 1),
            "open_rate_pct": round(opened / delivered * 100, 1),
            "reply_rate_pct": round(replies / delivered * 100, 1),
            "bounce_rate_pct": round(bounces / sent * 100, 1),
        },
        "ghl": {
            "contacts_created": contacts,
            "opportunities_total": opps_total,
            "opportunities_open": opps_open,
            "opportunities_won": opps_won,
            "appointments_booked": appointments,
            "pipeline_value": pipeline_val,
        },
    }


# ---------------------------------------------------------------------------
# Convenience: full report workflow
# ---------------------------------------------------------------------------

def run_weekly_report(
    config: dict,
    mock: bool = False,
    date_range: dict | None = None,
) -> dict:
    """End-to-end: fetch metrics, generate report, send via configured channels.

    Args:
        config: Full client config dict (must have 'instantly', 'ghl',
                and 'reporting' sections).
        mock: If True, use mock data instead of live API calls.
        date_range: Optional date range override.

    Returns:
        Dict with 'report', 'html_sent', 'slack_sent' keys.
    """
    dr = date_range or _default_date_range()
    reporting_cfg = config.get("reporting", {})

    # --- Fetch metrics ---
    instantly_cfg = config.get("instantly", {})
    ghl_cfg = config.get("ghl", {})

    instantly_metrics = fetch_instantly_metrics(
        api_url=instantly_cfg.get("api_url", ""),
        api_key=os.environ.get("INSTANTLY_API_KEY", ""),
        campaign_id=instantly_cfg.get("campaign_id"),
        date_range=dr,
        mock=mock,
    )

    ghl_metrics = fetch_ghl_metrics(
        api_url=ghl_cfg.get("api_url", ""),
        api_key=os.environ.get("GHL_API_KEY", ""),
        location_id=ghl_cfg.get("location_id"),
        pipeline_id=ghl_cfg.get("pipeline_id"),
        date_range=dr,
        api_version=ghl_cfg.get("api_version", "2021-07-28"),
        mock=mock,
    )

    # --- Generate report ---
    report = generate_report(instantly_metrics, ghl_metrics, config)

    result = {"report": report, "html_sent": False, "slack_sent": False, "telegram_sent": False}

    # --- Send via configured channels ---
    client_name = config.get("client", "Client")
    subject = f"{client_name} — Weekly Pipeline Report ({dr['start']} to {dr['end']})"

    if reporting_cfg.get("email_enabled"):
        html = format_html_report(report, reporting_cfg.get("html_template"))
        result["html_sent"] = send_report_email(
            html,
            reporting_cfg.get("recipients", []),
            subject,
            reporting_cfg.get("smtp_config") or {},
        )

    if reporting_cfg.get("slack_enabled"):
        webhook = os.environ.get("SLACK_WEBHOOK_URL", "")
        slack_msg = format_slack_report(report, reporting_cfg.get("slack_template"))
        try:
            result["slack_sent"] = send_report_slack(slack_msg, webhook)
        except Exception:
            logger.exception("Slack report delivery failed")
            result["slack_sent"] = False

    if reporting_cfg.get("telegram_enabled"):
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        tg_msg = format_telegram_report(report, reporting_cfg.get("telegram_template"))
        try:
            result["telegram_sent"] = send_report_telegram(tg_msg, bot_token, chat_id)
        except Exception:
            logger.exception("Telegram report delivery failed")
            result["telegram_sent"] = False

    return result


if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path

    from dotenv import load_dotenv

    _ROOT = Path(__file__).resolve().parent.parent.parent.parent
    sys.path.insert(0, str(_ROOT / "execution"))
    load_dotenv(_ROOT / ".env")

    from modules.pipeline_utils import load_config

    parser = argparse.ArgumentParser(description="Generate and send weekly report")
    parser.add_argument("--config", default=str(_ROOT / "config" / "accessory_masters.json"))
    parser.add_argument("--mock", action="store_true", help="Use mock data")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    config = load_config(args.config)
    result = run_weekly_report(config, mock=args.mock)
    print(f"Email: {result['html_sent']} | Slack: {result['slack_sent']} | Telegram: {result['telegram_sent']}")
