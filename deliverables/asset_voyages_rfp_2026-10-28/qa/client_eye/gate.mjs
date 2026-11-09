// Client-eye gate (28_PreMortem_Client_Eye_Gate.md): the last release check that nothing a non-technical reader sees
// looks wrong. Crawls the hub, Option B (+ « Le lien de groupe ») and Option A (local build + one hosted boot of each
// Playground link) in every role and state reachable through visible UI, then runs the page-independent checks.
//
//   node gate.mjs                      all sections, then the report
//   node gate.mjs --only=a,ahosted     re-run some sections; the report merges the latest saved part of every section
//   node gate.mjs --report             rebuild report.json / report.md from the saved parts only
//
// Sections: hub, b (public crawl, replay at 1440, phone journeys at 390, traveller), a (local Playground: public
// crawl, replay, phone/6 widths), ahosted (hosted boots). Env: HUB, B_BASE, A_BASE override the targets.
import { readFileSync, writeFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { chromium, RUN, OUT, HERE, log, writeJson, finding } from './lib/core.mjs';
import { crawlHub, parseHub, HUB } from './lib/hub.mjs';
import { crawlBPublic, replayB, phoneB, travellerPhone, B } from './lib/optb.mjs';
import { crawlAPublic, replayA, phoneA, hostedA, A } from './lib/opta.mjs';
import * as ST from './lib/static.mjs';
import { CHECKS, writeReport } from './lib/report.mjs';

const args = process.argv.slice(2);
const only = (args.find((a) => a.startsWith('--only=')) || '').slice(7).split(',').filter(Boolean);
const reportOnly = args.includes('--report');
const want = (s) => !reportOnly && (!only.length || only.includes(s));

function savePart(name, extra = {}) {
  const part = { name, at: new Date().toISOString(), findings: RUN.findings.splice(0), states: RUN.states.splice(0), coverage: RUN.coverage.splice(0), words: RUN.words.splice(0), labels: RUN.labels.splice(0), styles: RUN.styles.splice(0), urls: [...RUN.urls.values()], notes: RUN.notes.splice(0), checks: { ...RUN.checks }, logins: RUN.logins, writing: [...RUN.writingContexts], ...extra };
  RUN.urls.clear(); RUN.checks = {};
  writeJson(`part-${name}.json`, part);
  // small companion for reading by hand (the part itself can be several MB)
  writeJson(`summary-${name}.json`, { name, at: part.at, logins: part.logins, writing: part.writing, sbx: part.sbx, resets: part.resets, replay: part.replay, boots: part.boots, pagesEditor: part.pagesEditor, notes: part.notes, findings: part.findings.length });
  log(`saved part ${name}: ${part.findings.length} raw findings, ${part.states.length} states`);
}

const browser = await chromium.launch({ args: ['--lang=fr-FR'], env: { ...process.env, LANG: 'fr_FR.UTF-8' } });
let hub;
try {
  hub = await parseHub(browser);
  // which option each hub quote belongs to (B6)
  hub.quotesBy = {};
  for (const t of hub.tasks) for (const k of ['A', 'B']) for (const s of (t.opts[k] || { steps: [] }).steps) for (const m of s.text.matchAll(/«\s*([^»]+?)\s*»/g)) hub.quotesBy[m[1].replace(/[  ]/g, ' ').trim()] = hub.quotesBy[m[1]] && hub.quotesBy[m[1]] !== k ? 'A+B' : k;
  if (hub.group) for (const s of hub.group.steps) for (const m of s.text.matchAll(/«\s*([^»]+?)\s*»/g)) hub.quotesBy[m[1].replace(/[  ]/g, ' ').trim()] = 'B';
  writeJson('hub_parsed.json', { ...hub, full: undefined });

  if (want('hub')) { await crawlHub(browser); savePart('hub'); }
  if (want('b')) {
    const sb = { sbx: [] };
    try { await crawlBPublic(browser); } catch (e) { log('B public crawl failed', e.stack); finding({ check: 'GATE', option: 'B', text: e.message, note: 'B public crawl aborted' }); }
    let rb = { rows: [], evidence: {}, sbx: [] };
    try { rb = await replayB(browser, hub); } catch (e) { log('B replay failed', e.stack); finding({ check: 'GATE', option: 'B', text: e.message, note: 'B replay aborted' }); }
    let pb = { sbx: [] };
    try { pb = await phoneB(browser); } catch (e) { log('B phone failed', e.stack); finding({ check: 'GATE', option: 'B', text: e.message, note: 'B phone journeys aborted' }); }
    try { await travellerPhone(browser, rb.groupUrl); } catch (e) { log('traveller failed', e.message); }
    sb.sbx = [...(rb.sbx || []), ...(pb.sbx || [])];
    savePart('b', { replay: rb.rows, evidence: rb.evidence, sbx: sb.sbx, resets: { replay: rb.reset1, phone: pb.reset }, groupUrl: rb.groupUrl ? rb.groupUrl.replace(/\/g\/.*/, '/g/<token>') : '' });
  }
  if (want('a')) {
    try { await crawlAPublic(browser); } catch (e) { log('A public failed', e.stack); finding({ check: 'GATE', option: 'A', text: e.message, note: 'A public crawl aborted' }); }
    let ra = { rows: [], evidence: {} };
    try { ra = await replayA(browser, hub); } catch (e) { log('A replay failed', e.stack); finding({ check: 'GATE', option: 'A', text: e.message, note: 'A replay aborted' }); }
    try { await phoneA(browser); } catch (e) { log('A phone failed', e.stack); finding({ check: 'GATE', option: 'A', text: e.message, note: 'A phone crawl aborted' }); }
    savePart('a', { replay: ra.rows, evidence: ra.evidence, pagesEditor: ra.pagesEditor, target: A });
  }
  if (want('ahosted')) {
    let h = { boots: [] };
    try { h = await hostedA(browser, hub); } catch (e) { log('A hosted failed', e.stack); finding({ check: 'GATE', option: 'A-hosted', text: e.message, note: 'hosted boot aborted' }); }
    savePart('ahosted', { boots: h.boots, replay: h.c10 || [], adminWho: h.adminWho });
  }
} finally { await browser.close(); }

// ---------------------------------------------------------------- merge the parts, run the page-independent checks
const parts = {};
for (const f of readdirSync(OUT).filter((f) => /^part-(hub|b|a|ahosted)\.json$/.test(f))) { const p = JSON.parse(readFileSync(join(OUT, f), 'utf8')); parts[p.name] = p; }
for (const p of Object.values(parts)) {
  RUN.findings.push(...p.findings); RUN.states.push(...p.states); RUN.coverage.push(...p.coverage); RUN.words.push(...p.words); RUN.labels.push(...p.labels); RUN.styles.push(...p.styles); RUN.notes.push(...p.notes);
  for (const u of p.urls) RUN.urls.set(u.url, u);
  Object.assign(RUN.checks, p.checks || {});
}
const b2 = await chromium.launch();
const rq = await (await b2.newContext()).request;
const results = {};
results.email = await ST.checkEmail(rq).catch((e) => ({ err: e.message }));
const bctx = await b2.newContext({ locale: 'fr-FR' });
const browserCheck = async (u) => { const p = await bctx.newPage(); try { const r = await p.goto(u, { timeout: 30000 }); return r ? r.status() : 0; } catch { return 0; } finally { await p.close(); } };
results.links = (await ST.checkLinks(rq, browserCheck).catch((e) => { log('links failed', e.stack); return []; })).length;
results.videos = await ST.checkVideos(HUB).catch((e) => ({ err: e.message }));
results.favicons = await ST.checkFavicons(rq).catch((e) => ({ err: e.message }));
results.midnight = ST.checkMidnight();
try { results.spelling = ST.checkSpelling().allowlist_errors; } catch (e) { log('spelling failed', e.message); }
results.glossary = ST.checkGlossary(hub);
results.styles = ST.checkStyles();
ST.checkC7(hub);
results.numbers = ST.checkNumbers(hub).length;
results.claims = ST.checkClaims(hub, { rows: (parts.a || {}).replay || [], pagesEditor: (parts.a || {}).pagesEditor }, { rows: (parts.b || {}).replay || [] }, parts.ahosted);
results.versions = await ST.checkVersions(rq, HUB, B).catch((e) => ({ err: e.message }));
await b2.close();
// A7 is a decision for the operator, not a defect: listed, never counted as a finding.
RUN.checks.A7 = { status: 'OPERATOR DECISION', detail: `Option B's address is ${B} (contains « debanjan186 »). Accepted unless the operator asks for a custom domain.` };
// E2 is a process guard; E3 and E5 are checked from what this run captured.
RUN.checks.E2 = { status: 'HUMAN/PROCESS', detail: 'The suites (wp_demo/tests/run_all.sh, custom_demo playwright) must run twice green after the last change; this gate does not run them. It runs last, on the deployed versions named above.' };
const shotsOld = RUN.states.filter((s) => s.shot).filter((s) => { try { return statSync(join(HERE, s.shot)).mtimeMs < Date.parse(parts[Object.keys(parts)[0]] ? Object.values(parts).map((p) => p.at).sort()[0] : 0) - 6 * 3600e3; } catch { return true; } });
RUN.checks.E3 = { status: shotsOld.length ? 'FAIL' : 'PASS', detail: `${RUN.states.filter((s) => s.shot).length} screenshots, all written by this gate from fresh browser contexts on the deployed hub and Option B and the local Option A build${shotsOld.length ? `; ${shotsOld.length} missing or older than the run` : ''}.` };
const cov = {};
for (const c of RUN.coverage) { const k = c.option; cov[k] = cov[k] || new Set(); cov[k].add(c.width); }
const missing = Object.entries(cov).filter(([k]) => k !== 'A-hosted').map(([k, s]) => [k, [320, 390, 768, 1280, 1440, 1920].filter((w) => !s.has(w))]).filter(([, m]) => m.length);
RUN.checks.E5 = { status: missing.length ? 'FAIL' : 'PASS', detail: `${Object.entries(cov).map(([k, s]) => `${k}: ${[...s].sort((a, b) => a - b).join('/')}`).join('; ')}. The hosted Option A boot is one boot per link at 1440 by design (brief).${missing.length ? ' Missing: ' + JSON.stringify(missing) : ''}` };
writeReport({ parts, results, hub });
log('done');
