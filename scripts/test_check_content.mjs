#!/usr/bin/env node
// scripts/test_check_content.mjs — re-runnable test for check_content.mjs.
//
// Copies the repo's content, scripts, .pages.yml and public/ into a scratch
// directory (/tmp/cc_sim, or $CC_SIM_DIR) and simulates the mistakes a CMS
// save can make. Each "bad" case must fail (exit 1) with a clear message;
// each "ok" case must pass (exit 0).
//
//   node scripts/test_check_content.mjs

import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SIM = path.resolve(process.env.CC_SIM_DIR || '/tmp/cc_sim');
const CHECKER = path.join(REPO, 'scripts', 'check_content.mjs');

function fresh() {
  fs.rmSync(SIM, { recursive: true, force: true });
  fs.mkdirSync(SIM, { recursive: true });
  for (const p of ['src', 'scripts', 'public', '.pages.yml']) {
    fs.cpSync(path.join(REPO, p), path.join(SIM, p), { recursive: true });
  }
}

const readJson = (r) => JSON.parse(fs.readFileSync(path.join(SIM, r), 'utf8'));
const writeJson = (r, v) => fs.writeFileSync(path.join(SIM, r), JSON.stringify(v, null, 2));
function mutate(r, fn) { const d = readJson(r); fn(d); writeJson(r, d); }

const cases = [
  { name: 'unchanged tree passes', expect: 0, setup() {} },
  {
    name: 'broken JSON (missing comma)', expect: 1,
    must: [/PROBLÈME \/ PROBLEM/, /Home page \(French\)/, /src\/content\/hero\.fr\.json/, /line \/ ligne \d+, column \/ colonne \d+/],
    setup() {
      const f = path.join(SIM, 'src/content/hero.fr.json');
      fs.writeFileSync(f, fs.readFileSync(f, 'utf8').replace(/",\n/, '"\n'));
    },
  },
  {
    name: 'deleted top-level key', expect: 1,
    must: [/lost the field/, /About page \(English\)/, /'Title' \(title\)|'title'/],
    setup() { mutate('src/content/about.en.json', (d) => { delete d.title; }); },
  },
  {
    name: 'list turned into text', expect: 1,
    must: [/should be a list/, /now \/ mais est maintenant: text/, /offerings\.fr\.json/],
    setup() { mutate('src/content/offerings.fr.json', (d) => { d.tiles = 'oops'; }); },
  },
  {
    name: 'null object', expect: 1,
    must: [/primary_cta/, /empty \(null\)/, /contact\.fr\.json/],
    setup() { mutate('src/content/contact.fr.json', (d) => { d.primary_cta = null; }); },
  },
  {
    name: 'null item in a list of objects', expect: 1,
    must: [/élément n°1/, /schedule\.en\.json/],
    setup() { mutate('src/content/schedule.en.json', (d) => { d.gallery[0] = null; }); },
  },
  {
    name: '30 MB video in public/assets/videos', expect: 1,
    must: [/too big for Cloudflare \(max 25 MB\): public\/assets\/videos\/x\.mp4/, /delete it in Media/],
    setup() {
      const dir = path.join(SIM, 'public/assets/videos');
      fs.mkdirSync(dir, { recursive: true });
      const fd = fs.openSync(path.join(dir, 'x.mp4'), 'w');
      fs.ftruncateSync(fd, 30 * 1024 * 1024);
      fs.closeSync(fd);
    },
  },
  {
    name: 'empty lists and empty strings pass', expect: 0,
    setup() {
      mutate('src/content/offerings.en.json', (d) => { d.tiles = []; d.subtitle = ''; });
      mutate('src/content/about.fr.json', (d) => { d.paragraphs = []; d.markers = []; d.eyebrow = ''; });
      mutate('src/content/hero.en.json', (d) => { d.featured_in = []; d.headline = ''; });
    },
  },
  {
    name: 'missing image -> warning only', expect: 0,
    must: [/WARNING \/ ATTENTION/, /does-not-exist\.jpg/, /hero_image/],
    setup() { mutate('src/content/hero.fr.json', (d) => { d.hero_image = '/assets/does-not-exist.jpg'; }); },
  },
];

let failed = 0;
for (const c of cases) {
  fresh();
  c.setup();
  const r = spawnSync(process.execPath, [CHECKER, '--root', SIM], { encoding: 'utf8' });
  const out = `${r.stdout}\n${r.stderr}`;
  const missing = (c.must || []).filter((re) => !re.test(out));
  const ok = r.status === c.expect && missing.length === 0;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${c.name} (exit ${r.status}, expected ${c.expect})`);
  if (!ok) {
    failed++;
    if (missing.length) console.log(`      missing in output: ${missing.map(String).join(', ')}`);
    console.log(out.split('\n').map((l) => `      | ${l}`).join('\n'));
  }
}
fs.rmSync(SIM, { recursive: true, force: true });
console.log(failed ? `\n${failed} case(s) failed.` : `\nAll ${cases.length} cases passed.`);
process.exit(failed ? 1 : 0);
