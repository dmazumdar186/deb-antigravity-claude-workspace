# Phase 4b — Modal Scheduled Function (backend processing)

## Goal

Add a Modal cron that runs every 6 hours (configurable), performs the app's backend work (LLM calls, data refresh, third-party syncs), and writes status into the Phase 4a Worker's KV via its webhook. The mobile app reads results via the Worker; the cron is the only thing allowed to write expensive state.

## Inputs

- Phase 4a complete (Worker deployed with `/api/webhook/*` accepting `X-Worker-Secret`)
- App slug + Worker URL from registry (`registry.json` → `<slug>.worker_url`)
- `WORKER_SECRET` exported in Modal secrets (`modal secret create <slug>-worker-secret WORKER_SECRET=<value>`)
- Modal token present (`modal token current` returns ok — verified by preflight)

## Tools/Scripts

- `modal` CLI — deploy + invoke
- `execution/modal_webhook.py` — reference pattern for `modal.App` + `modal.Cron` + secrets
- New file in app repo: `C:\Users\deban\dev\mobile-apps\<slug>\backend\cron.py`
- `httpx` or `requests` (inside the Modal image) — POSTs to the Worker

## Steps

1. **Define the Modal app.** `backend/cron.py`:
   ```python
   import modal
   app = modal.App("<slug>-cron")
   image = modal.Image.debian_slim().pip_install("httpx")
   secrets = [modal.Secret.from_name("<slug>-worker-secret")]
   ```
2. **Decorate the cron handler.**
   ```python
   @app.function(image=image, secrets=secrets, schedule=modal.Cron("0 */6 * * *"), timeout=600)
   def refresh_job():
       ...
   ```
   - `timeout=600` (10 min) is conservative. Bump if the job is heavy; Modal's max is 86400 (24h) but anything > 1h should split.
3. **Implement the job.**
   - Do the work (LLM call, fetch external API, transform data).
   - On success: POST to the Worker:
     ```python
     resp = httpx.post(
         f"{WORKER_URL}/api/webhook/cron-status",
         headers={"X-Worker-Secret": os.environ["WORKER_SECRET"], "X-Idempotency-Key": f"cron:{run_id}"},
         json={"job": "refresh", "status": "ok", "result_summary": {...}, "ran_at": iso_now()},
         timeout=15,
     )
     resp.raise_for_status()
     ```
4. **Handle KV-write failure.** If `resp.raise_for_status()` throws, retry up to 3 times with exponential backoff (1s, 4s, 16s). After 3 failures: log loudly via `print()` (Modal captures), do NOT raise — letting the function fail re-runs the entire job on Modal's retry, which may double-spend (LLM credits). Better: write a sentinel locally noting "ran but failed to report", and let the next cron run reconcile.
5. **Idempotency key shape.** `cron:<job-name>:<modal-call-id>` — call id from `modal.current_function_call_id()`. Prevents duplicate writes if the same cron run retries.
6. **Add `--dry-run` mode.**
   ```python
   @app.function(...)
   def refresh_job(dry_run: bool = False):
       if dry_run:
           return {"would_call_openrouter": True, "would_post_to_kv": True}
       ...
   ```
   The canary (`mobile_app_canary.py`) invokes this with `dry_run=True` to validate the function is reachable + secrets are wired, without burning LLM credits.
7. **Deploy.** `modal deploy backend/cron.py`. Capture the function URL if any (mostly Modal stores it internally).
8. **First-run test.** `modal run backend/cron.py::refresh_job --dry-run`. Confirm output. Then `modal run backend/cron.py::refresh_job` (real, costs credits) — confirm the Worker's `/api/health` reflects the new `last_success_per_job.refresh`.
9. **Update registry.** Add `modal_app: "<slug>-cron"` and `cron_schedule: "0 */6 * * *"` to the app's registry entry.
10. **Commit.** `git commit -m "phase 4b — modal cron writing to <slug>-api KV"`.

## Outputs

- Deployed Modal app `<slug>-cron` with one or more `@app.function(schedule=modal.Cron(...))` handlers
- `--dry-run` parameter on every cost-incurring function
- Worker KV reflects `last_success_per_job.<job>` after each successful run
- Registry updated with `modal_app` + `cron_schedule`

## Edge Cases

- **KV write failure.** Job did expensive work, status didn't post. Don't re-raise (Modal would retry and re-spend). Write a local sentinel, log, accept eventual reconciliation on next run.
- **Modal timeout (600s default).** Long jobs hit the wall. Split into a fan-out (`modal.map`) or raise the timeout (cap at 1h for monitoring sanity).
- **`WORKER_SECRET` rotated in Cloudflare but not in Modal.** Cron writes fail silently (401 from Worker) → KV never updates → canary fires red. Rotation requires updating both sides; document in Phase 4a notes.
- **Cron drift.** `modal.Cron` runs in UTC. A "0 */6 * * *" cron is 00:00, 06:00, 12:00, 18:00 UTC — verify this matches the user's expected cadence (e.g. for "every morning" the user may need a UTC offset).
- **Cold start.** First invocation after long idle can take 30-60s to pull the image. Bake the image at deploy time (`modal deploy`) and use `keep_warm=1` on the function if cold start is unacceptable.
- **Duplicate runs.** If Modal retries a transient failure, the same `current_function_call_id()` is reused — idempotency-key dedup at the Worker catches the replay.
- **`pip_install` mismatch.** If `cron.py` imports something not in the image, Modal fails at import time. Always list every dep in `pip_install(...)`.

## Notes

- This phase is optional if the app is offline-only or doesn't need a backend. Skip on apps where Phase 1-3 + Phase 4a's webhook receivers cover all server work.
- Modal's free tier covers most personal-scale crons. Heavy LLM use may push into paid; budget via `modal.functioncall.list` periodically.
- Anneal adversarial mode runs after this phase via the `/mobile-app` skill.
