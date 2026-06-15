"""
gmail_send_digest.py
description: Send an HTML email digest via Gmail SMTP using an App Password. Self-contained; does not import from execution/modules.
inputs: --html (path to HTML file), --subject (email subject), --recipient (email address), --dry-run (flag); env vars GMAIL_SMTP_USER, GMAIL_SMTP_APP_PASSWORD, JOB_TRACKER_RECIPIENT.
outputs: Email sent via SMTP; stdout confirmation or error message; notifications_log row written (via send_digest_and_log helper).
"""

import argparse
import html as _html
import os
import re
import smtplib
import sys
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv; load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution.personal_workflows._jt_utils import setup_logging, load_jt_config  # noqa: E402
from execution.personal_workflows.job_tracker_db import init_db, log_notification  # noqa: E402

logger = setup_logging("gmail_send_digest")

# ---------------------------------------------------------------------------
# SMTP defaults
# ---------------------------------------------------------------------------

_SMTP_HOST_DEFAULT = "smtp.gmail.com"
_SMTP_PORT_DEFAULT = 587
_USE_TLS_DEFAULT = True


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _build_smtp_config(override: "dict | None" = None) -> dict:
    """Merge config file smtp block with env credentials.

    Precedence: override arg > env vars > config file > hard-coded defaults.
    Returns a dict with keys: host, port, use_tls, user, password.
    """
    base: dict = {
        "host": _SMTP_HOST_DEFAULT,
        "port": _SMTP_PORT_DEFAULT,
        "use_tls": _USE_TLS_DEFAULT,
        "user": "",
        "password": "",
    }

    # Layer 1: config file
    try:
        cfg = load_jt_config()
        smtp_cfg = cfg.get("smtp", {})
        if smtp_cfg.get("host"):
            base["host"] = smtp_cfg["host"]
        if smtp_cfg.get("port"):
            base["port"] = int(smtp_cfg["port"])
        if "use_tls" in smtp_cfg:
            base["use_tls"] = bool(smtp_cfg["use_tls"])
    except Exception:
        pass  # Config file missing or malformed — rely on env / defaults

    # Layer 2: environment variables
    env_user = os.environ.get("GMAIL_SMTP_USER", "").strip()
    env_pass = os.environ.get("GMAIL_SMTP_APP_PASSWORD", "").strip()
    if env_user:
        base["user"] = env_user
    if env_pass:
        base["password"] = env_pass

    # Layer 3: caller override (highest priority)
    if override:
        for k in ("host", "port", "use_tls", "user", "password"):
            if k in override and override[k] is not None:
                base[k] = override[k]

    return base


_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_STYLE_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL)
_CDATA_RE = re.compile(r"<!\[CDATA\[.*?\]\]>", re.DOTALL)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_BR_RE = re.compile(r"<br\s*/?\s*>", re.IGNORECASE)
_BLOCK_RE = re.compile(r"</(?:p|div|li|h[1-6]|tr|td|th)\s*>", re.IGNORECASE)


def _plain_text_fallback(html: str) -> str:
    """HTML -> plain text suitable for an SMTP alternative part.

    Order matters:
      1. Drop <script>, <style>, CDATA, HTML comments (their content is not text).
      2. Map <br> and end-of-block tags to newlines so paragraph structure survives.
      3. Strip remaining tags.
      4. Decode HTML entities (&nbsp;, &amp;, &#160;, ...) via stdlib html.unescape.
      5. Collapse whitespace.
    """
    if not html:
        return ""
    s = _SCRIPT_RE.sub(" ", html)
    s = _STYLE_RE.sub(" ", s)
    s = _CDATA_RE.sub(" ", s)
    s = _COMMENT_RE.sub(" ", s)
    s = _BR_RE.sub("\n", s)
    s = _BLOCK_RE.sub("\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = _html.unescape(s)
    # Collapse whitespace while preserving paragraph breaks.
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


# Transient SMTP exceptions worth retrying. Auth and quota failures are NOT
# included — those should fail fast so the operator sees the real problem.
_TRANSIENT_SMTP_EXCEPTIONS = (
    smtplib.SMTPServerDisconnected,
    smtplib.SMTPConnectError,
    smtplib.SMTPHeloError,
)
# OSError covers DNS / TCP failures. Auth failures are SMTPAuthenticationError
# which is a subclass of SMTPResponseException, not in the transient set.

SMTP_MAX_ATTEMPTS = 3
SMTP_BASE_BACKOFF_S = 1.0  # 1s, 2s, 4s; tests can shrink to 0.


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_digest(
    html: str,
    *,
    subject: str,
    recipient: "str | None" = None,
    smtp_config: "dict | None" = None,
) -> "tuple[bool, str | None]":
    """Send *html* as an HTML email via Gmail SMTP.

    Args:
        html: Full HTML body string.
        subject: Email subject line.
        recipient: Destination address. Defaults to env JOB_TRACKER_RECIPIENT.
        smtp_config: SMTP overrides. Keys: host, port, use_tls, user, password.

    Returns:
        (True, None) on success; (False, error_message) on failure.
    """
    # Resolve recipient
    to_addr = (recipient or os.environ.get("JOB_TRACKER_RECIPIENT", "")).strip()
    if not to_addr:
        return (False, "no recipient configured — set JOB_TRACKER_RECIPIENT env var or pass recipient arg")

    # Resolve SMTP config
    cfg = _build_smtp_config(smtp_config)
    smtp_user = cfg.get("user", "").strip()
    smtp_password = cfg.get("password", "").strip()
    if not smtp_user or not smtp_password:
        return (False, "smtp credentials missing — set GMAIL_SMTP_USER and GMAIL_SMTP_APP_PASSWORD env vars")

    smtp_host: str = cfg["host"]
    smtp_port: int = int(cfg["port"])
    use_tls: bool = bool(cfg["use_tls"])

    # Build MIME message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_addr

    plain = _plain_text_fallback(html)
    # Attach plain first, HTML second — clients render the last alternative they support
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    def _attempt_send() -> None:
        """Single SMTP send attempt (extracted for retry logic)."""
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

    last_exc: Exception | None = None
    for attempt in range(1, SMTP_MAX_ATTEMPTS + 1):
        try:
            _attempt_send()
            note = "" if attempt == 1 else f" (after {attempt - 1} retr{'y' if attempt == 2 else 'ies'})"
            logger.info("Digest sent to %s via %s:%s%s", to_addr, smtp_host, smtp_port, note)
            return (True, None)
        except _TRANSIENT_SMTP_EXCEPTIONS as exc:
            last_exc = exc
            if attempt == SMTP_MAX_ATTEMPTS:
                return (False, f"{type(exc).__name__} after {attempt} attempts: {exc}")
            backoff = SMTP_BASE_BACKOFF_S * (2 ** (attempt - 1))
            logger.warning(
                "SMTP transient %s (attempt %d/%d); retrying in %.1fs",
                type(exc).__name__, attempt, SMTP_MAX_ATTEMPTS, backoff,
            )
            time.sleep(backoff)
        except smtplib.SMTPAuthenticationError as exc:
            # Auth failures are NOT transient — fail fast so the operator rotates the App Password.
            return (False, f"SMTPAuthenticationError: {exc}")
        except smtplib.SMTPException as exc:
            # Other SMTP errors (data error, recipient refused, quota) are not retried.
            return (False, f"SMTPException: {type(exc).__name__}: {exc}")
        except OSError as exc:
            # Treat as transient: DNS hiccup, TCP reset. Retry like SMTP transient.
            last_exc = exc
            if attempt == SMTP_MAX_ATTEMPTS:
                return (False, f"OSError after {attempt} attempts to {smtp_host}:{smtp_port}: {exc}")
            backoff = SMTP_BASE_BACKOFF_S * (2 ** (attempt - 1))
            logger.warning(
                "SMTP OSError %s (attempt %d/%d); retrying in %.1fs",
                type(exc).__name__, attempt, SMTP_MAX_ATTEMPTS, backoff,
            )
            time.sleep(backoff)
        except Exception as exc:  # noqa: BLE001
            # Defensive: any unanticipated exception is non-retryable.
            return (False, f"Unexpected error: {type(exc).__name__}: {exc}")

    return (False, f"send_digest exhausted attempts: {last_exc}")


# ---------------------------------------------------------------------------
# Orchestrator convenience wrapper
# ---------------------------------------------------------------------------

def send_digest_and_log(
    db_path: "Path | str",
    html: str,
    *,
    subject: str,
    run_id: str,
    recipient: "str | None" = None,
) -> bool:
    """Send the digest and record the outcome in notifications_log.

    Args:
        db_path: Path to the SQLite job tracker database.
        html: Full HTML body string.
        subject: Email subject line.
        run_id: Run identifier used to correlate the log row.
        recipient: Destination address. Defaults to env JOB_TRACKER_RECIPIENT.

    Returns:
        True if the email was sent successfully, False otherwise.
    """
    success, error = send_digest(html, subject=subject, recipient=recipient)

    to_addr = (recipient or os.environ.get("JOB_TRACKER_RECIPIENT", "")).strip()
    status = "sent" if success else "failed"

    try:
        conn = init_db(db_path)
        log_notification(
            conn,
            run_id=run_id,
            recipient=to_addr or "unknown",
            job_ids=[],  # Caller may pass job_ids separately if needed; default empty
            status=status,
            error=error,
        )
        conn.close()
    except Exception as log_exc:
        logger.warning("Could not write notifications_log row: %s", log_exc)

    if not success:
        logger.error("Digest send failed [run=%s]: %s", run_id, error)
    return success


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Send an HTML email digest via Gmail SMTP.",
    )
    parser.add_argument(
        "--html",
        metavar="PATH",
        required=True,
        help="Path to the HTML file to send as the email body.",
    )
    parser.add_argument(
        "--subject",
        metavar="TEXT",
        default="PM/PO France — Job Digest",
        help='Email subject line (default: "PM/PO France — Job Digest").',
    )
    parser.add_argument(
        "--recipient",
        metavar="EMAIL",
        help="Destination email address. Defaults to JOB_TRACKER_RECIPIENT env var.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config and print what would be sent without connecting to SMTP.",
    )
    args = parser.parse_args()

    html_path = Path(args.html)
    if not html_path.exists():
        logger.error("HTML file not found: %s", html_path)
        sys.exit(1)

    try:
        html_body = html_path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.error("Failed to read HTML file: %s", exc)
        sys.exit(1)

    to_addr = (args.recipient or os.environ.get("JOB_TRACKER_RECIPIENT", "")).strip()
    cfg = _build_smtp_config()

    if args.dry_run:
        smtp_user = cfg.get("user", "").strip()
        smtp_host = cfg.get("host", _SMTP_HOST_DEFAULT)
        smtp_port = cfg.get("port", _SMTP_PORT_DEFAULT)

        if not to_addr:
            logger.error("dry-run: no recipient configured — set JOB_TRACKER_RECIPIENT or use --recipient.")
            sys.exit(1)
        if not smtp_user or not cfg.get("password", ""):
            logger.error("dry-run: SMTP credentials missing (GMAIL_SMTP_USER / GMAIL_SMTP_APP_PASSWORD).")
            sys.exit(1)

        print(f"[dry-run] would send to {to_addr} via {smtp_host}:{smtp_port} (subject: {args.subject!r})")
        sys.exit(0)

    success, error = send_digest(
        html_body,
        subject=args.subject,
        recipient=args.recipient or None,
    )

    if not success:
        logger.error("Send failed: %s", error)
        sys.exit(1)

    print(f"Digest sent successfully to {to_addr}.")
