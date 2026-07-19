# Instantly Kill Switch Runbook

**Purpose**: instantly halt the self_outbound_v2 campaign in any of the following failures:
- Bounce cascade (bounce rate >3%)
- Spam surge (spam-complaint rate >0.5%)
- Wrong ICP live-firing
- Deliverability collapse on Pool A or Pool B
- CNIL complaint escalation
- Google Workspace account termination on any mailbox

**Response time target**: <5 minutes from decision to campaign paused.

---

## Method 1 — Instantly UI (fastest, 3 clicks)

1. Login: https://app.instantly.ai
2. Left nav → **Campaigns**
3. Locate `self_outbound_v2` → click the pause icon (⏸) on the right side of the row
4. Confirm the modal

**Result**: no more sends. Warmup continues (safe to keep on).

---

## Method 2 — Instantly API (scriptable)

```bash
# Requires INSTANTLY_API_KEY in .env
export INSTANTLY_API_KEY="[from .env]"
export CAMPAIGN_ID="[from Instantly UI URL after clicking the campaign]"

curl -X POST "https://api.instantly.ai/api/v1/campaign/pause" \
  -H "Content-Type: application/json" \
  -d "{\"api_key\":\"$INSTANTLY_API_KEY\",\"campaign_id\":\"$CAMPAIGN_ID\"}"
```

Expected: HTTP 200 with `{"status":"paused"}`. If different, escalate to Method 1.

---

## Method 3 — env killswitch (belt AND suspenders)

The workspace's `sourcer.py` / `personalizer.py` / `campaign_launcher.py` scripts (per plan) respect a `PAUSE_ALL=1` environment variable. Set it in `.env`:

```bash
# Append to .env
echo "PAUSE_ALL=1" >> .env
```

**Result**: even if the Instantly pause fails, no new leads are pushed to the campaign. Existing queued sends may still fire — combine with Method 1 or 2 for full stop.

---

## Method 4 — scorched earth (nuclear option)

If methods 1-3 fail (e.g., Instantly account compromised, mass fraud complaint from Google):

1. **Null-route all 10 outbound domains** via DNS. In Cloudflare / Namecheap / Porkbun DNS:
   - Delete all MX records
   - Point A record to `127.0.0.1`
2. Any queued send from any mailbox will fail with SMTP 5xx.
3. This is destructive to reputation but stops all sending immediately.
4. Recovery: restore MX records once safe; expect 24-48h propagation delay.

---

## After the kill switch fires — checklist

- [ ] Log the reason for kill in HANDOFF_PHASE_3.md (or successor)
- [ ] Screenshot Instantly dashboard showing paused state
- [ ] Notify operator via Telegram (this is auto if Worker is healthy)
- [ ] Assess: is this a fixable issue (bad copy, bad ICP) or systemic (vendor issue)?
- [ ] If systemic: activate the CNIL response playbook (`cnil_response_playbook.md`) + reach out to vendor support
- [ ] Do not restart sending until root cause is identified AND fixed AND vetted by mail-tester across all mailboxes

---

## Verification (do this weekly)

Every Monday, verify all 4 kill-switch paths work:
- [ ] Method 1: log into Instantly UI, verify pause button exists on the campaign
- [ ] Method 2: `curl -X POST` with a dummy campaign ID — expect either 200 or 404 (not 401/403 = key valid)
- [ ] Method 3: verify `PAUSE_ALL` is documented in the code paths that read it
- [ ] Method 4: verify you can log into all 3 registrar accounts + know how to edit DNS
