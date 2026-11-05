// Monkey A. Usage: WP_BASE=... node monkey_A.mjs [seed] [actionsPerRole=300] [roles=anon,contributeur,equipe,direction]
import fs from 'fs';
import path from 'path';
import { launch, asRole, BASE, LOGS, USERS, sleep } from './common.mjs';

const SEED = parseInt(process.argv[2] || '20261105', 10);
const N = parseInt(process.argv[3] || '300', 10);
const ROLES = (process.argv[4] || 'anon,contributeur,equipe,direction').split(',');

function rng(seed) { // mulberry32
  let a = seed >>> 0;
  return () => { a = (a + 0x6d2b79f5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
const INPUTS = ['Élodie Ñandú 日本語 😀', 'x'.repeat(5000), '<script>window.__pwn=1</script>', '=HYPERLINK("http://evil.example","x")', '"; DROP TABLE wp_posts;--', '../../etc/passwd', '0', '-1', '99999999999', '2027-13-45', ''];
// Hrefs the monkey must never follow.
const DENY = /logout|action=logout|delete|trash|untrash|plugins\.php|plugin-install|plugin-editor|themes\.php|theme-install|theme-editor|users\.php|user-new|user-edit|profile\.php|wp-login\.php\?action|action=delete|export\.php|import\.php|tools\.php\?page=asset-demo-tools|options|site-health|update-core|upgrade/i;
const DENY_TEXT = /déconnex|log ?out|supprimer|corbeille|delete|trash|mettre à la corbeille|désactiver|activer|install|révoquer/i;
const FATAL = /(Fatal error|Warning|Notice|Deprecated)\s*:|<b>(Fatal error|Warning|Notice|Deprecated)<\/b>/;
const AUTH_REVEAL_ROLES = ['direction', 'equipe'];

const browser = await launch();
let totalFail = 0;
const summary = [];

for (const role of ROLES) {
  const rand = rng(SEED + ROLES.indexOf(role) * 7919);
  const pick = (a) => a[Math.floor(rand() * a.length)];
  const logf = path.join(LOGS, `monkey_${role}.log`);
  const log = [];
  const L = (s) => { log.push(s); };
  const { ctx, page } = await asRole(browser, role === 'anon' ? null : role);
  const hist = [];
  const errs = [];
  let status5xx = [];
  let revealAllowedUntil = -1; // action index until which DEMO-GME- may appear (authorised reveal result)
  page.on('pageerror', (e) => errs.push(String(e.message).slice(0, 300)));
  page.on('response', (r) => { if (r.status() >= 500) status5xx.push(`${r.status()} ${r.url()}`); });
  page.on('dialog', (d) => d.dismiss().catch(() => {}));
  await page.goto(BASE + (role === 'anon' ? '/' : '/wp-admin/'), { waitUntil: 'load', timeout: 90000 }).catch(() => {});
  let fails = 0, firstFail = null;

  const act = async (i) => {
    const r = rand();
    const origin = new URL(BASE).origin;
    if (r < 0.40) { // same-origin click
      const links = await page.$$eval('a[href], button, input[type=submit]', (els) => els.map((e, k) => ({ k, tag: e.tagName, href: e.getAttribute('href') || '', text: (e.innerText || e.value || '').slice(0, 60), type: e.getAttribute('type') || '', vis: !!(e.offsetWidth || e.offsetHeight) })).filter((x) => x.vis));
      const ok = links.filter((x) => !DENY.test(x.href) && !DENY_TEXT.test(x.text) && (x.tag !== 'A' || !x.href || x.href.startsWith('#') || x.href.startsWith('/') || x.href.startsWith(origin)));
      if (!ok.length) return 'click:none';
      const t = pick(ok);
      const el = (await page.$$('a[href], button, input[type=submit]'))[t.k];
      const isReveal = /révéler/i.test(t.text);
      hist.push(`click ${t.tag} "${t.text}" ${t.href}`);
      await el.click({ timeout: 5000, noWaitAfter: true }).catch(() => {});
      await page.waitForLoadState('domcontentloaded', { timeout: 15000 }).catch(() => {});
      if (isReveal && AUTH_REVEAL_ROLES.includes(role)) revealAllowedUntil = i + 1;
      return 'click';
    }
    if (r < 0.65) { // typed input
      const inputs = await page.$$('input:not([type=hidden]):not([type=submit]):not([type=checkbox]):not([type=radio]):not([type=file]):not([type=password]):not([name=log]), textarea');
      const vis = [];
      for (const e of inputs) if (await e.isVisible().catch(() => false)) vis.push(e);
      if (!vis.length) return 'type:none';
      const e = pick(vis); const v = pick(INPUTS);
      hist.push(`type len=${v.length} ${v.slice(0, 40)}`);
      await e.fill(v, { timeout: 3000 }).catch(() => {});
      return 'type';
    }
    if (r < 0.80) { // submit form (non-destructive: skip forms with deny words)
      const forms = await page.$$('form');
      const cand = [];
      for (const f of forms) {
        const info = await f.evaluate((el) => ({ txt: (el.innerText || '').slice(0, 300), act: el.getAttribute('action') || '', vis: !!(el.offsetWidth || el.offsetHeight) }));
        if (info.vis && !DENY.test(info.act) && !DENY_TEXT.test(info.txt) && !/wp-login|logout/i.test(info.act)) cand.push(f);
      }
      if (!cand.length) return 'submit:none';
      const f = pick(cand);
      const isReveal = await f.evaluate((el) => /révéler/i.test(el.innerText));
      hist.push('submit form' + (isReveal ? ' (reveal)' : ''));
      await f.evaluate((el) => { const b = el.querySelector('button[type=submit],input[type=submit],button:not([type])'); if (b) b.click(); else el.requestSubmit(); }).catch(() => {});
      await page.waitForLoadState('domcontentloaded', { timeout: 15000 }).catch(() => {});
      if (isReveal && AUTH_REVEAL_ROLES.includes(role)) revealAllowedUntil = i + 1;
      return 'submit';
    }
    if (r < 0.90) { hist.push('back/forward'); if (rand() < 0.5) await page.goBack({ timeout: 10000, waitUntil: 'domcontentloaded' }).catch(() => {}); else await page.goForward({ timeout: 10000, waitUntil: 'domcontentloaded' }).catch(() => {}); return 'nav'; }
    const w = 390 + Math.floor(rand() * 1051); const h = 600 + Math.floor(rand() * 400);
    hist.push(`resize ${w}x${h}`); await page.setViewportSize({ width: w, height: h }); return 'resize';
  };

  const check = async (i) => {
    const problems = [];
    const html = await page.content().catch(() => '');
    const url = page.url();
    if (!url.startsWith(BASE)) { problems.push('left origin ' + url); await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' }).catch(() => {}); }
    const body = await page.evaluate(() => document.body ? document.body.innerText : '').catch(() => '');
    if (FATAL.test(html) || FATAL.test(body)) { const m = html.match(FATAL); const at = m ? html.indexOf(m[0]) : -1; problems.push('PHP error text: ' + (at >= 0 ? html.slice(Math.max(0, at - 40), at + 400).replace(/\s+/g, ' ') : (body.match(FATAL) || [''])[0])); }
    if (status5xx.length) { problems.push('5xx ' + status5xx.join(' | ')); status5xx = []; }
    if (errs.length) { problems.push('pageerror ' + errs.join(' | ')); errs.length = 0; }
    const dom = await page.evaluate(() => {
      let s = document.documentElement.outerHTML;
      for (const e of document.querySelectorAll('input,textarea')) s += '\n' + e.value;
      return s;
    }).catch(() => '');
    if (/DEMO-GME-/.test(dom) && i > revealAllowedUntil) problems.push('DEMO-GME- in DOM outside authorised reveal');
    return problems;
  };

  for (let i = 0; i < N; i++) {
    let kind = 'err';
    try { kind = await act(i); } catch (e) { kind = 'act-exception ' + String(e.message).split('\n')[0]; }
    const probs = await check(i);
    L(`#${i} ${kind} url=${page.url().slice(0, 110)} ${probs.length ? 'FAIL ' + probs.join(' ;; ') : 'ok'}`);
    if (probs.length) {
      fails++;
      if (!firstFail) firstFail = { seed: SEED, role, action: i, problems: probs, last20: hist.slice(-20), url: page.url() };
      if (fails <= 3) fs.writeFileSync(path.join(LOGS, `monkey_${role}_failure_${fails}.json`), JSON.stringify({ seed: SEED, role, action: i, problems: probs, last20: hist.slice(-20), url: page.url() }, null, 2));
      if (/DEMO-GME-/.test(probs.join())) revealAllowedUntil = i; // avoid cascading on the same page
      await page.goto(BASE + (role === 'anon' ? '/' : '/wp-admin/'), { waitUntil: 'domcontentloaded' }).catch(() => {});
    }
    if (i % 25 === 24) { // keep session alive/recover if logged out by a stray action
      if (role !== 'anon' && /wp-login\.php/.test(page.url())) { L('session lost, re-login'); await page.fill('#user_login', USERS[role][0]).catch(() => {}); await page.fill('#user_pass', USERS[role][1]).catch(() => {}); await page.click('#wp-submit').catch(() => {}); await page.waitForLoadState('domcontentloaded').catch(() => {}); }
    }
  }
  const line = `ROLE ${role} seed=${SEED} actions=${N} failures=${fails}`;
  L(line); summary.push(line);
  fs.writeFileSync(logf, log.join('\n') + '\n');
  console.log(line);
  totalFail += fails;
  await ctx.close();
}
await browser.close();
fs.writeFileSync(path.join(LOGS, 'monkey_summary.log'), summary.join('\n') + `\nTOTAL failures=${totalFail}\n`);
process.exit(totalFail ? 1 : 0);
