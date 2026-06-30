"""
description: Operator-facing listen-test for the Retell POC. Creates a web call via Retell's
REST API, writes a tiny HTML harness with the Retell client SDK + the access token, opens it
in the default browser. After the operator hangs up, polls Retell for the finished call,
pulls the transcript + tool history, runs the audit grader, and prints a verdict.

This is the side-by-side counterpart to tests/listen_test_voice_agent.py (the Vapi version).

inputs (env from .env):
    RETELL_API_KEY        required
    RETELL_AGENT_ID       required

CLI:
    --no-browser          skip opening the harness automatically
    --wait-seconds N      max seconds to wait for the call to end (default 300)
    --poll-interval N     seconds between polls (default 5)

outputs:
    stdout: harness file path, transcript, audit verdict
    exit code: 0 if call passes, 1 if it fails, 2 if no call captured
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    # Best-effort stream reconfigure on platforms that don't support it.
    pass

try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_retell_calls import grade_call  # type: ignore[import-not-found]


RETELL_BASE = "https://api.retellai.com"
HARNESS_DIR = Path(__file__).resolve().parents[1] / ".tmp" / "retell_listen_test"
HARNESS_HTML_TMPL = """<!doctype html>
<html><head>
<meta charset="utf-8">
<title>Retell dental POC -- listen test</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 720px; margin: 40px auto; padding: 0 20px; }}
  button {{ font-size: 18px; padding: 14px 28px; border-radius: 8px; cursor: pointer; }}
  #start {{ background: #14a37f; color: white; border: none; }}
  #stop  {{ background: #c0392b; color: white; border: none; margin-left: 12px; }}
  #log   {{ white-space: pre-wrap; background: #f4f4f4; padding: 16px; border-radius: 8px;
            margin-top: 24px; font-family: monospace; font-size: 13px; max-height: 360px; overflow: auto; }}
</style>
</head><body>
<h2>Retell dental POC -- listen test</h2>
<p>call_id: <code>{call_id}</code></p>
<p>Click <b>Start call</b>, allow mic, say <b>"Consultation."</b> right after the greeting.
The bug we are watching for: agent fires <code>list_slots</code> before asking name/phone.</p>
<button id="start">Start call</button>
<button id="stop">End call</button>
<div id="log">(SDK loading...)</div>
<script type="module">
  import {{ RetellWebClient }} from 'https://cdn.jsdelivr.net/npm/retell-client-js-sdk@2.0.7/+esm';
  const log = (m) => {{ const e = document.getElementById('log'); e.textContent += '\\n' + m; e.scrollTop = e.scrollHeight; }};
  log('SDK loaded');
  const client = new RetellWebClient();
  client.on('call_started', () => log('-> call_started'));
  client.on('call_ended',   () => log('-> call_ended  (you may close this tab)'));
  client.on('error',        (e) => log('-> error: ' + (e?.message || e)));
  client.on('agent_start_talking', () => log('   [agent speaking]'));
  client.on('agent_stop_talking',  () => log('   [agent silent]'));
  client.on('update', (u) => {{
    if (u.transcript) {{
      const last = u.transcript[u.transcript.length - 1];
      if (last) log(`   ${{last.role}}: ${{last.content}}`);
    }}
  }});
  document.getElementById('start').onclick = async () => {{
    try {{ await client.startCall({{ accessToken: '{access_token}' }}); }}
    catch (e) {{ log('startCall failed: ' + e.message); }}
  }};
  document.getElementById('stop').onclick = () => client.stopCall();
</script>
</body></html>
"""


def retell_request(method: str, path: str, api_key: str, body: dict | None = None) -> dict:
    url = f"{RETELL_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--wait-seconds", type=int, default=300)
    ap.add_argument("--poll-interval", type=int, default=5)
    args = ap.parse_args()

    api_key = os.environ.get("RETELL_API_KEY")
    agent_id = os.environ.get("RETELL_AGENT_ID")
    if not api_key or not agent_id:
        print("RETELL_API_KEY and RETELL_AGENT_ID required", file=sys.stderr)
        return 2

    try:
        web_call = retell_request("POST", "/v2/create-web-call", api_key, {"agent_id": agent_id})
    except urllib.error.HTTPError as exc:
        print(f"create-web-call failed: HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:200]}",
              file=sys.stderr)
        return 2

    call_id = web_call["call_id"]
    access_token = web_call["access_token"]
    print(f"created web call {call_id}")

    HARNESS_DIR.mkdir(parents=True, exist_ok=True)
    harness = HARNESS_DIR / f"{call_id}.html"
    harness.write_text(
        HARNESS_HTML_TMPL.format(call_id=call_id, access_token=access_token),
        encoding="utf-8",
    )
    file_url = f"file:///{harness.as_posix().lstrip('/')}"
    print(f"harness: {file_url}")

    if not args.no_browser:
        webbrowser.open(file_url)
    print()
    print(">> click 'Start call', allow mic, say 'Consultation.' then watch the harness log.")
    print(f">> polling Retell for completion every {args.poll_interval}s for up to {args.wait_seconds}s...")
    print()

    deadline = time.time() + args.wait_seconds
    finished = None
    while time.time() < deadline:
        try:
            c = retell_request("GET", f"/v2/get-call/{call_id}", api_key)
        except urllib.error.HTTPError as exc:
            print(f"  (poll error: HTTP {exc.code})")
            time.sleep(args.poll_interval)
            continue
        status = c.get("call_status")
        if status in ("ended", "error"):
            finished = c
            break
        remaining = int(deadline - time.time())
        print(f"  ...status={status} ({remaining}s left)")
        time.sleep(args.poll_interval)

    if not finished:
        print("\nno call ended within window. exit 2.")
        return 2

    print()
    print(f"call_id={call_id}")
    print(f"  call_status={finished.get('call_status')}")
    print(f"  disconnection_reason={finished.get('disconnection_reason')}")
    print(f"  duration_ms={finished.get('duration_ms')}")
    print()
    print("transcript:")
    for turn in finished.get("transcript_object") or []:
        role = turn.get("role", "?")
        content = turn.get("content", "")
        print(f"  {role}: {content}")
    if not finished.get("transcript_object") and finished.get("transcript"):
        print(finished["transcript"])
    print()

    verdict = grade_call(finished)
    print(f"audit verdict: {verdict['severity']}")
    for f in verdict["findings"]:
        print(f"  - {f}")
    print()
    if verdict["severity"] == "FAIL":
        print("FAIL -- this call would not pass production gate.")
        return 1
    if verdict["severity"] == "WARN":
        print("WARN -- caller experience degraded; investigate.")
        return 0
    print("PASS -- call meets production gate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
