// Eye review 2026-11-20 M2: staging must let staff test the job-alert sign-up end to end WITHOUT real mail.
// The change itself (ALERTS_ENABLED="1" in [env.staging.vars]) is written up in
// execution/gtm_client_workflows/greenjobs_redesign/deploy/STAGING_FLAGS_NOTE.md for the owner of wrangler.toml.
// This test runs the real Worker with the staging vars as committed PLUS that one change and proves:
// /api/config says alerts on, a sign-up from the staging Pages origin is stored pending (202), and nothing is sent
// (DRY_RUN stays "1", MAIL_PROVIDER "none"), including on the scheduled digest run.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';
import { REPO, makeWorld } from './helpers.mjs';

const TOML = readFileSync(resolve(REPO, 'execution/gtm_client_workflows/greenjobs_redesign/platform_worker/wrangler.toml'), 'utf8');
const MIGRATION = readFileSync(resolve(REPO, 'deliverables/greenjobs_migration_2026-11-06/build/d1/migrations/0004_job_alerts_newsletter.sql'), 'utf8');
const NOTE = readFileSync(resolve(REPO, 'execution/gtm_client_workflows/greenjobs_redesign/deploy/STAGING_FLAGS_NOTE.md'), 'utf8');

export function stagingVars(toml) {
  const sec = toml.split(/^\[env\.staging\.vars\]\s*$/m)[1].split(/^\[/m)[0];
  const out = {};
  for (const m of sec.matchAll(/^([A-Z0-9_]+)\s*=\s*(?:"([^"]*)"|'([^']*)')/gm)) out[m[1]] = m[2] ?? m[3];
  return out;
}

test('M2: staging vars + ALERTS_ENABLED="1" -> sign-up works end to end, DRY_RUN keeps every mail unsent', async () => {
  const vars = stagingVars(TOML);
  assert.equal(vars.DRY_RUN, '1', 'staging is pinned dry');
  assert.equal(vars.MAIL_PROVIDER, 'none');
  assert.match(NOTE, /ALERTS_ENABLED = "1"/);
  const host = 'greenjobs-platform-staging.debanjan186.workers.dev';
  const origin = 'https://greenjobs-stg-ie.pages.dev';
  const w = await makeWorld({ ...vars, ALERTS_ENABLED: '1', LIST_MAIL_SIGNING_KEY: 'test-signing-key-0123456789abcdef-not-real' });
  w.db.sqlite.exec(MIGRATION);
  const cfg = await (await w.fetch(new Request(`https://${host}/api/config?site=ie`, { headers: { Origin: origin } }))).json();
  assert.deepEqual(cfg, { site: 'ie', alerts: true, newsletter: false });
  const r = await w.fetch(new Request(`https://${host}/api/alerts?site=ie`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', Origin: origin, 'CF-Connecting-IP': '198.51.100.8' },
    body: JSON.stringify({ email: 'staff-test@example.com', consent: true, sectors: ['Wind energy'] }),
  }));
  assert.equal(r.status, 202);
  assert.equal(r.headers.get('Access-Control-Allow-Origin'), origin);
  const rows = w.db.q(`SELECT site, status FROM alert_subscriptions WHERE email_norm = 'staff-test@example.com'`);
  assert.deepEqual(rows.map((x) => [x.site, x.status]), [['ie', 'pending']]);
  // the scheduled run (confirmations, digests) also sends nothing on staging
  if (typeof w.handler.scheduled === 'function') await w.handler.scheduled({ cron: '*/10 * * * *', scheduledTime: Date.now() }, w.env, { waitUntil() {} });
  assert.equal(w.mail.calls.length, 0, 'no mail leaves a DRY_RUN staging Worker');
});
