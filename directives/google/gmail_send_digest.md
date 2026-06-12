# Gmail SMTP — Digest Sender SOP

## Goal

Send the rendered HTML job digest as an email via Gmail SMTP using an App Password (not OAuth2). Attaches an auto-generated plain-text fallback so that mail clients that reject HTML-only messages still render something. Used by the orchestrator at Stage H, and can also be called standalone to test credentials or resend a previously generated digest HTML file.

## When to use

- Called automatically by the orchestrator at Stage H when `--send` is passed and `--dry-run` is not set.
- Run standalone to test SMTP credentials or resend a digest from `.tmp/job_tracker/{run_id}/digest.html`.
- Called whenever any other personal workflow needs to send an HTML email via Gmail.

## Inputs

### CLI args (standalone use)

| Flag | Required | Default | Purpose |
|------|----------|---------|---------|
| `--html PATH` | Yes | — | Path to the HTML file to send as the email body |
| `--subject TEXT` | No | `"PM/PO France — Job Digest"` | Email subject line |
| `--recipient EMAIL` | No | `JOB_TRACKER_RECIPIENT` env | Override destination address |
| `--dry-run` | No | off | Validate config and print what would be sent without connecting to SMTP |

### Environment variables required

| Variable | Purpose |
|----------|---------|
| `GMAIL_SMTP_USER` | Gmail address used as the SMTP login and `From` address (e.g. `you@gmail.com`) |
| `GMAIL_SMTP_APP_PASSWORD` | 16-character App Password — **no spaces** in the value. Generate at https://myaccount.google.com/apppasswords. Requires 2FA to be enabled on the Gmail account. |
| `JOB_TRACKER_RECIPIENT` | Default `To` address. Can be overridden by the `recipient` argument to `send_digest()` or the `--recipient` CLI flag. |

**App Password setup checklist:**
1. Sign in to the Gmail account at https://myaccount.google.com.
2. Navigate to Security → 2-Step Verification → confirm it is enabled.
3. Navigate to Security → App passwords.
4. Create a new app password (name it "PM Tracker" for clarity).
5. Copy the 16-character code (Google shows it once, with spaces for readability — strip all spaces before storing).
6. Add to `.env`: `GMAIL_SMTP_APP_PASSWORD=abcdabcdabcdabcd` (no spaces).
7. **Rotate every 90 days** — set a calendar reminder.

### Config keys consumed from `config/job_tracker.json`

- `smtp.host` — SMTP server hostname (default: `smtp.gmail.com`)
- `smtp.port` — SMTP port (default: `587`)
- `smtp.use_tls` — whether to use STARTTLS (default: `true`)

## Outputs

- **Email sent** to the configured recipient via `smtp.gmail.com:587` with STARTTLS.
- **MIME structure:** `multipart/alternative` with a plain-text part followed by an HTML part. Clients render the last alternative they support (HTML for modern clients, plain text as fallback).
- **Return value from `send_digest()`:** `(True, None)` on success; `(False, error_string)` on failure.
- **Logs:**
  - `Digest sent to {addr} via {host}:{port}` — info level on success
  - `SMTP server disconnected on first attempt; retrying once.` — warning before retry
  - Error strings returned in the tuple are not printed to log — caller handles them.
- **DB row:** The orchestrator calls `log_notification()` after `send_digest()` regardless of outcome — both successes and failures are recorded in `notifications_log`.

## How to run

```bash
# Test SMTP credentials (dry-run — no email sent)
py execution\google\gmail_send_digest.py --html .tmp\job_tracker\{run_id}\digest.html --dry-run

# Send a specific digest file
py execution\google\gmail_send_digest.py --html .tmp\job_tracker\{run_id}\digest.html --subject "PM/PO France — 12 openings — Wed 14 May"

# Send to an alternate address
py execution\google\gmail_send_digest.py --html .tmp\job_tracker\{run_id}\digest.html --recipient other@example.com
```

## Public interface

```python
from execution.google.gmail_send_digest import send_digest, send_digest_and_log

# Simple send
success, error = send_digest(html_string, subject="PM/PO France — 8 openings — Wed 14 May")
if not success:
    print(f"Send failed: {error}")

# Send + log to DB in one call (convenience wrapper for orchestrator use)
ok = send_digest_and_log(
    db_path=Path(".tmp/job_tracker.db"),
    html=html_string,
    subject="PM/PO France — 8 openings — Wed 14 May",
    run_id="20260514-060000",
    recipient="you@gmail.com",   # optional override
)
```

## Tools / dependencies

- Python packages: `python-dotenv` — standard library only for SMTP (`smtplib`, `email.mime`)
- External services: Gmail SMTP (`smtp.gmail.com:587`) — free; 500 recipient/day limit for regular Gmail accounts (irrelevant for personal self-email use).
- No third-party SMTP libraries: uses Python's built-in `smtplib` and `email.mime` directly.

## Edge cases & gotchas

- **App Password ≠ account password:** App Passwords are 16-character tokens, separate from the Gmail login password. They are not affected by password changes but are tied to the Google account's 2FA status — if 2FA is disabled, all App Passwords are immediately revoked.
- **No spaces in the env value:** Google's UI displays the App Password with spaces for readability (e.g., `abcd efgh ijkl mnop`). Strip all spaces before storing in `.env`.
- **Plain-text fallback is required:** Gmail will silently reject sending if the only MIME part is `text/html` from some sending paths. The module always attaches a stripped plain-text version (HTML tags removed, whitespace collapsed) before attaching the HTML. Do not remove this.
- **One internal retry on `SMTPServerDisconnected`:** This is the most common transient error (the SMTP server reset the connection during idle). The retry is internal — the outer orchestrator does not retry the entire send. No other exceptions are retried because auth failures and quota failures do not benefit from retry.
- **Auth failures do not retry:** An `SMTPAuthenticationError` (wrong app password, 2FA disabled, app password revoked) returns `(False, error_string)` immediately. Check credentials.
- **`From` display name:** The module currently uses the bare Gmail address as `From`. If Gmail starts flagging the digest as spam (unlikely for self-email), add a display name: change `msg["From"] = smtp_user` to `msg["From"] = f'"PM Tracker" <{smtp_user}>'`.
- **Rotate App Password every 90 days:** This is a security best practice. Add a calendar reminder. After rotation, update `GMAIL_SMTP_APP_PASSWORD` in `.env` and re-run `--dry-run` to verify.

## Self-anneal hooks

On `SMTPAuthenticationError`:
1. Check that `GMAIL_SMTP_APP_PASSWORD` in `.env` is the 16-character App Password with no spaces.
2. Verify that 2FA is still enabled on the Gmail account at https://myaccount.google.com/security.
3. Generate a new App Password if the old one was revoked (e.g., after a password change or 2FA reconfiguration).
4. Update `.env` and re-run `--dry-run` to confirm.

On `ConnectionRefusedError` or `OSError` (port 587 blocked by network):
1. Check if you're on a network that blocks outbound port 587 (common on some corporate networks).
2. Try port 465 with SSL instead: update `smtp.port` to 465 and `smtp.use_tls` to false in `config/job_tracker.json`, and switch to `smtplib.SMTP_SSL`. This is a code change — update and test.

On digest appearing in spam:
1. Add a display name to the `From` header (see gotchas above).
2. Mark the digest as "Not Spam" in Gmail once — this trains the filter for future messages.

## Exit Criteria

- `py execution\google\gmail_send_digest.py --html <path> --dry-run` exits `0` and prints the subject, recipient, and SMTP config to stdout without connecting to `smtp.gmail.com`.
- All three env vars (`GMAIL_SMTP_USER`, `GMAIL_SMTP_APP_PASSWORD`, `JOB_TRACKER_RECIPIENT`) are present in `.env`; `--dry-run` does not print any `MISSING` warning.
- Real send (`--html <path>` without `--dry-run`) returns `(True, None)` from `send_digest()` — confirmed by a `Digest sent to` log line in stdout.
- The sent email is received at the `JOB_TRACKER_RECIPIENT` address and renders HTML in the client (not raw tags), with a plain-text fallback part also present.
- No `SMTPAuthenticationError` in stderr — confirming the App Password is a valid 16-character token with no embedded spaces.

## Changelog

- 2026-05-14: created.
