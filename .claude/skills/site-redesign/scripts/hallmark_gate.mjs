#!/usr/bin/env node
// Hallmark sloplint gate for a built concept site. Read-only: runs the vendored sloplint in static
// mode (writes nothing) on every page, then applies the record in the build HANDOFF.md.
//
//   node .claude/skills/site-redesign/scripts/hallmark_gate.mjs <site-dir> <HANDOFF.md> [--json]
//
// Exit 0 = PASS, 1 = blocked (open FAIL, or REFLEX neither fixed nor waived), 2 = usage/tool error.
// HANDOFF record lines (one per gate, reason required):
//   hallmark-waive: <reflex gate> — <reason>        waives a REFLEX gate on every page
//   hallmark-house: <54|67> — <reason>               house-standard exception for a Floor gate the
//                                                    site-redesign standard (d) itself trips (amber
//                                                    small caps). Only gates in HOUSE are accepted.
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, resolve, dirname, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const HOUSE = new Set(['54', '67']);
const HERE = dirname(fileURLToPath(import.meta.url));
const SLOPLINT = resolve(HERE, '..', '..', 'hallmark', 'scripts', 'sloplint.mjs');
const [siteArg, handoffArg] = process.argv.slice(2).filter((a) => !a.startsWith('--'));
const asJson = process.argv.includes('--json');
if (!siteArg || !handoffArg) { console.error('usage: hallmark_gate.mjs <site-dir> <HANDOFF.md> [--json]'); process.exit(2); }
const site = resolve(siteArg);
if (!existsSync(site) || !statSync(site).isDirectory()) { console.error(`no site dir: ${site}`); process.exit(2); }
if (!existsSync(SLOPLINT)) { console.error(`vendored sloplint missing: ${SLOPLINT}`); process.exit(2); }

const handoff = existsSync(handoffArg) ? readFileSync(handoffArg, 'utf8') : '';
const record = (tag) => {
  const m = new Map();
  for (const line of handoff.split('\n')) {
    const r = new RegExp(`hallmark-${tag}:\\s*([0-9]{1,2}[a-z]{0,3})\\s*[—:-]+\\s*(\\S.{3,})`, 'i').exec(line);
    if (r) m.set(r[1].toLowerCase(), r[2].trim());
  }
  return m;
};
const waived = record('waive');
const house = new Map([...record('house')].filter(([g]) => HOUSE.has(g)));

const pages = [];
const walk = (d) => {
  for (const n of readdirSync(d)) {
    if (n.startsWith('.') || n === 'node_modules') continue;
    const p = join(d, n);
    const s = statSync(p);
    if (s.isDirectory()) walk(p);
    else if (extname(n).toLowerCase() === '.html') pages.push(p);
  }
};
walk(site);
if (!pages.length) { console.error(`no .html pages under ${site}`); process.exit(2); }

const open = [];
const excused = { house: 0, waived: 0 };
for (const page of pages) {
  const run = spawnSync(process.execPath, [SLOPLINT, page, '--json'], { encoding: 'utf8', timeout: 120000, cwd: HERE, maxBuffer: 64 * 1024 * 1024 });
  let rep;
  try { rep = JSON.parse(run.stdout); } catch { console.error(`sloplint did not return JSON for ${page}: ${(run.stderr || '').slice(0, 300)}`); process.exit(2); }
  for (const f of rep.findings || []) {
    const g = String(f.gate).toLowerCase();
    if (f.grade === 'FAIL' && house.has(g)) { excused.house++; continue; }
    if (f.grade === 'REFLEX' && waived.has(g)) { excused.waived++; continue; }
    if (f.grade === 'FAIL' || f.grade === 'REFLEX') open.push({ page: page.slice(site.length + 1), grade: f.grade, gate: f.gate, line: f.line, evidence: f.evidence, fix: f.fix });
  }
}

const count = (gr) => open.filter((f) => f.grade === gr).length;
const verdict = open.length ? 'BLOCKED' : 'PASS';
if (asJson) console.log(JSON.stringify({ verdict, pages: pages.length, open_fail: count('FAIL'), open_reflex: count('REFLEX'), excused, open }, null, 1));
else {
  for (const f of open.slice(0, 40)) console.log(`${f.grade} ${f.gate} ${f.page}:${f.line} ${String(f.evidence).slice(0, 90)} | fix: ${f.fix}`);
  if (open.length > 40) console.log(`(+${open.length - 40} more; --json for all)`);
  console.log(`hallmark gate: ${verdict} · ${pages.length} page(s) · open ${count('FAIL')} FAIL, ${count('REFLEX')} REFLEX · excused ${excused.house} house, ${excused.waived} waived`);
}
process.exit(open.length ? 1 : 0);
