// Page-independent checks: A1 e-mail, A4 links, A5 videos, A6 favicons, B2 midnight, B5 spelling, B6 glossary,
// C5 styles, C7 hub statement + purge rule, D1 claims, D3 numbers, E1 versions, E4 browsers.
import { readFileSync, writeFileSync, existsSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { finding, log, RUN, OUT, HERE, chromium, markCheck } from './core.mjs';
import { CLIENT_CONTACTS as RCLIENT } from './rules.mjs';

export const DELIV = join(HERE, '..', '..');
const rd = (p) => readFileSync(join(DELIV, p), 'utf8');
const lineOf = (file, needle) => { const L = rd(file).split('\n'); const i = L.findIndex((l) => l.includes(needle)); return i < 0 ? null : `${file}:${i + 1}`; };

// ---------------------------------------------------------------- A1: the e-mail draft
export async function checkEmail(request) {
  const file = '27_Email_Reply_Draft.md';
  const body = rd(file);
  const urls = [...new Set(body.match(/https?:\/\/[^\s)*\]>]+/g) || [])];
  if (urls.length !== 1) finding({ check: 'A1', option: 'EMAIL', page: file, text: urls.join(' '), note: `${urls.length} links in the e-mail; the rule is one short link` });
  for (const u of urls) {
    if (!u.startsWith('https://')) finding({ check: 'A1', option: 'EMAIL', page: file, text: u, note: 'not https' });
    if (/playground\.wordpress\.net/.test(u)) finding({ check: 'A1', option: 'EMAIL', page: file, text: u, note: 'Playground URL in the e-mail' });
    if (u.length > 60) finding({ check: 'A1', option: 'EMAIL', page: file, text: u, note: `${u.length} characters: may wrap in Outlook` });
    const r = await request.get(u, { maxRedirects: 5 }).catch((e) => ({ status: () => 0, e }));
    if (r.status() !== 200) finding({ check: 'A1', option: 'EMAIL', page: file, text: u, note: `HTTP ${r.status()}` });
  }
  return { urls };
}

// ---------------------------------------------------------------- A4: every link and source
const EXPECT_TYPE = [[/\.mp4(\?|$)/, /video\/mp4/], [/\.(jpe?g)(\?|$)/, /image\/jpeg/], [/\.png(\?|$)/, /image\/png/], [/\.svg(\?|$)/, /image\/svg/], [/\.woff2(\?|$)/, /font\/woff2|application\/(font|octet)/], [/\.css(\?|$)/, /text\/css/], [/\.js(\?|$)/, /javascript/], [/\.ico(\?|$)/, /image\/(x-icon|vnd\.microsoft\.icon|png)/], [/\.json(\?|$)/, /json/], [/\.zip(\?|$)/, /zip|octet/], [/\.csv(\?|$)/, /csv|text\/plain/]];
export async function checkLinks(request, browserCheck) {
  const all = [...RUN.urls.values()];
  // the Playground links carry the blueprint as a parameter: check the blueprint and the plugin zip too
  for (const e of all.slice()) {
    const m = /blueprint-url=([^&]+)/.exec(e.url);
    if (m) { const bp = decodeURIComponent(m[1]); if (!RUN.urls.has(bp)) { RUN.urls.set(bp, { url: bp, refs: [{ from: e.url, kind: 'blueprint' }] }); all.push(RUN.urls.get(bp)); } }
  }
  const results = [];
  // Tightened: an anchor that is never visible in any captured state (e.g. the fallback link inside a recording
  // figure that stays hidden until media/manifest.json announces the file) is not reachable by a reader. It is
  // listed as « latent » in links.json, not reported. Every src/poster/stylesheet is checked whether visible or not.
  const reachable = (e) => !e.refs.length || e.refs.some((r) => r.kind !== 'a' || r.visible !== false);
  const latent = all.filter((e) => !reachable(e)).map((e) => e.url);
  const queue = all.filter((e) => /^https?:/.test(e.url) && reachable(e) && !/\/console\/deconnexion|action=logout|_wpnonce|wp-login\.php\?action=|reinitialiser|export\.csv|groupe\.csv|\.csv\?|asset_export|download/.test(e.url));
  for (const e of all.filter((x) => /^mailto:/.test(x.url))) {
    const ok = /^mailto:[^@\s"<>]+@[\w-]+(\.[\w-]+)+(\?[^\s"<>]*)?$/.test(e.url.replace(/&amp;/g, '&'));
    if (!ok) finding({ check: 'A4', option: e.refs[0].option, page: e.refs[0].from, text: e.url.slice(0, 120), element: 'a[href^=mailto]', note: 'malformed mailto' });
  }
  let i = 0;
  const worker = async () => {
    while (i < queue.length) {
      const e = queue[i++];
      let st = 0, ct = '', final = e.url, err = '';
      try {
        const r = await request.get(e.url, { maxRedirects: 10, timeout: 30000, headers: /\.mp4/.test(e.url) ? { range: 'bytes=0-65535' } : {} });
        st = r.status(); ct = r.headers()['content-type'] || ''; final = r.url();
        // A site that refuses scripted clients (403/429) is re-checked as a reader would open it, in a real browser tab.
        if ((st === 403 || st === 429) && browserCheck) { const bs = await browserCheck(e.url); if (bs) { results.push({ url: e.url, status: st, browserStatus: bs, note: 'scripted client refused; browser status used' }); st = bs; } }
        if (/blueprint[^/]*\.json$/.test(new URL(e.url).pathname)) { try { const bp = JSON.parse(await r.text()); const zips = JSON.stringify(bp).match(/https?:\/\/[^"]+\.zip/g) || []; for (const z of zips) if (!RUN.urls.has(z)) { RUN.urls.set(z, { url: z, refs: [{ from: e.url, kind: 'plugin zip' }] }); queue.push(RUN.urls.get(z)); } } catch { err = 'blueprint is not valid JSON'; } }
      } catch (x) { err = x.message.split('\n')[0]; }
      results.push({ url: e.url, status: st, type: ct, final, err, refs: e.refs.length });
      const ref = e.refs[0] || {};
      const okStatus = st === 200 || st === 206 || (st >= 300 && st < 400);
      // console pages answer 302 to the login page for an anonymous checker: that is the 30x-to-200 case
      if (!okStatus || err) finding({ check: 'A4', option: ref.option || '?', page: ref.from || '', text: e.url.slice(0, 160), element: `${ref.kind || ''} « ${(ref.text || '').slice(0, 40)} »`, note: err || `HTTP ${st}` });
      // content type is checked for resources (src, poster, stylesheet, icon) and for same-site anchors; an anchor to
      // another site's « File:x.jpg » description page is a page by design.
      else if (e.refs.some((r) => r.kind !== 'a') || (ref.from && new URL(e.url).host === new URL(ref.from).host)) { for (const [re, want] of EXPECT_TYPE) if (re.test(new URL(e.url).pathname) && !want.test(ct)) finding({ check: 'A4', option: ref.option || '?', page: ref.from || '', text: e.url.slice(0, 160), element: ref.kind || '', note: `answers 200 but as « ${ct} » (missing file served as a page)` }); }
      if (/^http:\/\//.test(e.url) && !/127\.0\.0\.1|localhost/.test(e.url) && (e.refs || []).some((r) => /^https:/.test(r.from || ''))) finding({ check: 'A4', option: ref.option || '?', page: ref.from || '', text: e.url, note: 'http link on an https page (mixed content)' });
    }
  };
  await Promise.all(Array.from({ length: 6 }, worker));
  writeFileSync(join(OUT, 'links.json'), JSON.stringify({ results, latent }, null, 1));
  log('A4 links checked', results.length);
  return results;
}

// ---------------------------------------------------------------- A5: videos on the hub
export async function checkVideos(hubBase) {
  const out = [];
  // Chromium builds without proprietary codecs cannot decode H.264: Google Chrome (installed) is used for playback.
  let b; try { b = await chromium.launch({ executablePath: '/usr/bin/google-chrome' }); } catch { b = await chromium.launch(); out.push({ note: 'Chrome not available; Chromium used' }); }
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, locale: 'fr-FR' });
  const page = await ctx.newPage();
  await page.goto(hubBase + '/demo/'); await page.waitForTimeout(2500);
  const figs = await page.$$eval('[data-rec]', (fs) => fs.map((f) => ({ name: f.dataset.rec, hidden: f.hidden || !f.offsetParent, video: !!f.querySelector('video') })));
  const manifest = await (await ctx.request.get(hubBase + '/demo/media/manifest.json')).json().catch(() => ({}));
  for (const f of figs) {
    const row = { name: f.name, hidden: f.hidden, announced: manifest[f.name] === true };
    const mp4 = `${hubBase}/demo/media/${f.name}.mp4`;
    const head = await ctx.request.get(mp4, { headers: { range: 'bytes=0-262143' } });
    row.type = head.headers()['content-type']; row.status = head.status();
    const range = head.headers()['content-range'] || '';
    row.size = +(range.split('/')[1] || head.headers()['content-length'] || 0);
    const buf = await head.body();
    // faststart: the moov atom comes before mdat in the first bytes
    let off = 0; const atoms = [];
    while (off + 8 <= buf.length && atoms.length < 12) { const sz = buf.readUInt32BE(off); const ty = buf.toString('latin1', off + 4, off + 8); atoms.push(ty); if (sz < 8) break; off += sz; }
    row.atoms = atoms;
    if (!f.hidden) {
      const v = await page.$eval(`[data-rec="${f.name}"] video`, (v) => ({ poster: v.getAttribute('poster'), controls: v.controls, playsinline: v.playsInline, preload: v.getAttribute('preload'), w: v.getBoundingClientRect().width, vw: innerWidth })).catch(() => null);
      row.attrs = v;
      if (!v) finding({ check: 'A5', option: 'HUB', page: hubBase + '/demo/', width: 390, text: f.name, note: 'recording shown without a <video>' });
      else {
        for (const k of ['poster', 'controls', 'playsinline']) if (!v[k]) finding({ check: 'A5', option: 'HUB', page: hubBase + '/demo/', width: 390, text: f.name, note: `video lacks ${k}` });
        if (v.preload !== 'metadata') finding({ check: 'A5', option: 'HUB', page: hubBase + '/demo/', width: 390, text: f.name, note: `preload="${v.preload}"` });
        if (v.w > v.vw) finding({ check: 'A5', option: 'HUB', page: hubBase + '/demo/', width: 390, text: f.name, note: 'video wider than the phone screen' });
        const frames = await page.$eval(`[data-rec="${f.name}"] video`, async (v) => { v.muted = true; try { await v.play(); } catch (e) { return -1; } await new Promise((r) => setTimeout(r, 2500)); v.pause(); return v.getVideoPlaybackQuality ? v.getVideoPlaybackQuality().totalVideoFrames : (v.webkitDecodedFrameCount || 0); }).catch(() => -2);
        row.frames = frames;
        if (!(frames > 0)) finding({ check: 'A5', option: 'HUB', page: hubBase + '/demo/', width: 390, text: f.name, note: `decoded frames ${frames}` });
        const poster = await ctx.request.get(new URL(v.poster, hubBase + '/demo/').href);
        if (poster.status() !== 200 || !/image/.test(poster.headers()['content-type'] || '')) finding({ check: 'A5', option: 'HUB', page: hubBase + '/demo/', text: v.poster, note: `poster HTTP ${poster.status()} ${poster.headers()['content-type']}` });
      }
      if (!/video\/mp4/.test(row.type || '')) finding({ check: 'A5', option: 'HUB', page: mp4, text: f.name, note: `served as ${row.type}` });
      if (row.size > 25 * 1024 * 1024) finding({ check: 'A5', option: 'HUB', page: mp4, text: `${(row.size / 1048576).toFixed(1)} MB`, note: 'over 25 MB' });
      const mo = atoms.indexOf('moov'), md = atoms.indexOf('mdat');
      if (mo < 0 || (md >= 0 && md < mo)) finding({ check: 'A5', option: 'HUB', page: mp4, text: atoms.join(','), note: 'not faststart (moov not before mdat)' });
    } else if (row.announced) finding({ check: 'A5', option: 'HUB', page: hubBase + '/demo/', text: f.name, note: 'announced in manifest.json but hidden' });
    out.push(row);
  }
  await b.close();
  return out;
}

// ---------------------------------------------------------------- A6: favicons per site
export async function checkFavicons(request) {
  const seen = new Map();
  for (const st of RUN.states) {
    const origin = (() => { try { return new URL(st.page).origin; } catch { return ''; } })();
    const icons = (st.favicons && st.favicons.length) ? st.favicons : [origin + '/favicon.ico'];
    for (const u of icons) if (!seen.has(u)) seen.set(u, st);
  }
  for (const [u, st] of seen) {
    const r = await request.get(u).catch(() => null);
    const ct = r ? r.headers()['content-type'] || '' : '';
    if (!r || r.status() !== 200 || !/image|icon/.test(ct)) finding({ check: 'A6', option: st.option, page: st.page, text: u, note: `favicon ${r ? r.status() : 'error'} ${ct}` });
  }
  return [...seen.keys()];
}

// ---------------------------------------------------------------- B2: a clock at 00:05 Paris (B source helpers)
export function checkMidnight() {
  const out = {};
  const probe = join(HERE, 'lib', 'midnight_probe.mjs');
  try { out.b = JSON.parse(execFileSync('node', [probe, join(DELIV, 'custom_demo', 'src', 'lib.js')], { encoding: 'utf8' })); } catch (e) { out.err = e.message; }
  if (out.b && out.b.today !== out.b.parisToday) {
    // every user-facing use of the UTC « today() » is one day off between 00:00 and 01:00 (02:00 in summer) Paris
    const src = ['public.js', 'console.js', 'group.js'];
    for (const f of src) {
      const L = readFileSync(join(DELIV, 'custom_demo', 'src', f), 'utf8').split('\n');
      L.forEach((l, i) => { if (/\btoday\(\)/.test(l) && !/parisToday/.test(l) && !/^\s*\/\//.test(l)) finding({ check: 'B2', option: 'B', page: `custom_demo/src/${f}:${i + 1}`, text: l.trim().slice(0, 160), element: 'source', note: `at 00:05 Paris (${out.b.at}) today() = ${out.b.today} but the Paris date is ${out.b.parisToday}` }); });
    }
  }
  // Option A: dates should come from WordPress' Paris clock (wp_date/current_time), not PHP's UTC date()
  const dir = join(DELIV, 'wp_demo', 'plugin', 'asset-congres-demo', 'includes');
  for (const f of readdirSync(dir)) {
    const L = readFileSync(join(dir, f), 'utf8').split('\n');
    L.forEach((l, i) => { if (/(?<![\w>])(gmdate|date)\(\s*'[^']*[Ymd]/.test(l) && !/^\s*(\/\/|\*)/.test(l)) finding({ check: 'B2', option: 'A', page: `wp_demo/plugin/asset-congres-demo/includes/${f}:${i + 1}`, text: l.trim().slice(0, 160), element: 'source', note: 'PHP date()/gmdate() uses UTC, not Europe/Paris: one day off near midnight if shown or compared to a Paris date' }); });
  }
  return out;
}

// ---------------------------------------------------------------- B5: spelling (pyspellchecker, fr + en)
export function checkSpelling() {
  const inFile = join(OUT, 'words.json');
  writeFileSync(inFile, JSON.stringify(RUN.words));
  const res = JSON.parse(execFileSync('python3', ['-I', join(HERE, 'spell.py'), inFile, join(HERE, 'allowlist_spell.tsv')], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 }));
  for (const u of res.unknown) finding({ check: 'B5', option: u.option, page: u.page, role: u.role, width: u.width, text: u.word, element: u.lang, note: `unknown ${u.lang} word in « ${u.context} » (${u.count}×)` });
  return res;
}

// ---------------------------------------------------------------- B6: glossary
export function checkGlossary(hub) {
  const G = JSON.parse(readFileSync(join(HERE, 'glossary.json'), 'utf8'));
  const inv = { A: new Set(), B: new Set() };
  for (const l of RUN.labels) { const k = l.option.startsWith('A') ? 'A' : l.option === 'B' ? 'B' : null; if (!k) continue; for (const t of l.labels) inv[k].add(t.replace(/[  ]/g, ' ').trim()); for (const c of l.clickables) inv[k].add(c.label.replace(/[  ]/g, ' ').trim()); }
  const hubQuotes = [...(hub.full || '').matchAll(/«\s*([^»]+?)\s*»/g)].map((m) => m[1].replace(/[  ]/g, ' ').trim());
  const rows = [];
  for (const g of G.terms) {
    const found = {};
    for (const k of ['A', 'B']) found[k] = g.forms.filter((f) => [...inv[k]].some((t) => t === f || t.startsWith(f + ' (') || t.replace(/\s*\d+$/, '') === f));
    const quoted = g.forms.filter((f) => hubQuotes.includes(f));
    const row = { term: g.term, A: found.A, B: found.B, hub: quoted, scope: g.scope || 'AB' };
    rows.push(row);
    if (row.scope.includes('A') && row.scope.includes('B') && found.A.length && found.B.length && !found.A.some((x) => found.B.includes(x))) finding({ check: 'B6', option: 'A+B', page: 'glossary', text: `${g.term}: A « ${found.A.join(' / ')} » vs B « ${found.B.join(' / ')} »`, note: 'the same thing has different names in the two demos' });
    for (const q of quoted) for (const k of ['A', 'B']) if (row.scope.includes(k) && found[k].length && !found[k].includes(q) && (hub.quotesBy || {})[q] === k) finding({ check: 'B6', option: k, page: 'hub vs UI', text: `${g.term}: hub « ${q} », UI « ${found[k].join(' / ')} »`, note: 'the hub quotes a label the UI does not use' });
    for (const k of ['A', 'B']) if (row.scope.includes(k) && !found[k].length) finding({ check: 'B6', option: k, page: 'glossary', text: g.term, note: `none of « ${g.forms.join(' / ')} » seen in the ${k} UI` });
  }
  // every label the hub quotes for an option must exist in that option's UI
  for (const [q, k] of Object.entries(hub.quotesBy || {})) if (!['A+B'].includes(k) && inv[k] && ![...inv[k]].some((t) => t === q || t.startsWith(q + ' (') || t.replace(/\s*\(\d+\/\d+\)$/, '') === q)) finding({ check: 'B6', option: k, page: 'hub', text: `« ${q} »`, note: `quoted on the hub for Option ${k} but not seen as a label in that UI` });
  return rows;
}

// ---------------------------------------------------------------- C5: one look per surface
const rgb = (s) => (s.match(/[\d.]+/g) || []).map(Number);
const hueSat = ([r, g, b]) => { r /= 255; g /= 255; b /= 255; const mx = Math.max(r, g, b), mn = Math.min(r, g, b); const l = (mx + mn) / 2; const d = mx - mn; if (!d) return { h: 0, s: 0, l }; const s = d / (1 - Math.abs(2 * l - 1)); let h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4; h *= 60; if (h < 0) h += 360; return { h, s, l }; };
export function checkStyles() {
  const by = {};
  for (const s of RUN.styles) {
    if (!s.surface || !s.styles) continue;
    const k = s.surface;
    by[k] = by[k] || { body: new Map(), display: new Map(), btn: new Map(), accent: new Map() };
    const add = (m, v, st) => { if (!v) return; if (!m.has(v)) m.set(v, st); };
    add(by[k].body, s.styles.body, s.state);
    (s.styles.display || []).forEach((d) => add(by[k].display, d, s.state));
    for (const b of s.styles.buttons || []) {
      if (/wpadminbar|adminmenu|collapse|screen-meta|handle|toggle|switch|mini/.test(b.path) || b.bg === 'rgba(0, 0, 0, 0)' && /^0px/.test(b.border.split(' ').pop())) continue; // link-like or chrome controls
      add(by[k].btn, `${b.font} | radius ${b.radius}`, `${s.state} « ${b.label} »`);
      const c = hueSat(rgb(b.bg)); if (c.s > 0.35 && c.l > 0.15 && c.l < 0.85) add(by[k].accent, `hue ${Math.round(c.h / 30) * 30}`, `${s.state} button « ${b.label} » ${b.bg}`);
    }
    for (const l of s.styles.links || []) { const c = hueSat(rgb(l)); if (c.s > 0.35 && c.l > 0.15 && c.l < 0.85) add(by[k].accent, `hue ${Math.round(c.h / 30) * 30}`, `${s.state} link ${l}`); }
  }
  const summary = {};
  for (const [k, v] of Object.entries(by)) {
    summary[k] = { body: [...v.body.keys()], display: [...v.display.keys()], buttons: [...v.btn.keys()], accents: [...v.accent.keys()] };
    if (v.body.size > 1) finding({ check: 'C5', option: k, page: k, text: [...v.body.entries()].map(([f, s]) => `${f} (${s})`).join('; '), note: `${v.body.size} body font families` });
    if (v.display.size > 1) finding({ check: 'C5', option: k, page: k, text: [...v.display.entries()].map(([f, s]) => `${f} (${s})`).join('; '), note: `${v.display.size} display font families` });
    if (v.btn.size > 1) finding({ check: 'C5', option: k, page: k, text: [...v.btn.entries()].map(([f, s]) => `${f} (${s})`).join('; ').slice(0, 400), note: `${v.btn.size} button style families` });
    if (v.accent.size > 1) finding({ check: 'C5', option: k, page: k, text: [...v.accent.entries()].map(([f, s]) => `${f} (${s})`).join('; ').slice(0, 400), note: `${v.accent.size} accent colours` });
  }
  return summary;
}

// ---------------------------------------------------------------- C7: hub statement and the nightly purge rule
export function checkC7(hub) {
  const t = hub.full || '';
  // Tightened: « private » must describe the trial (a « private copy of the site » in the testing milestone does not)
  for (const c of RCLIENT) { if (!lineOf(c.source, c.needle)) finding({ check: 'D2', option: 'HUB', page: c.source, text: c.value, note: 'client contact allowlisted but not found at its cited source' }); }
  if (!/(sandbox|trial|demo|essai)[^.]{0,80}\bprivate\b|\bprivate\b[^.]{0,60}(sandbox|trial|browser|to you)|only (in|to) your browser|only you (can )?see/i.test(t)) finding({ check: 'C7', option: 'HUB', page: 'demo/', text: (t.match(/[^.]*sandbox[^.]*\./i) || [''])[0].slice(0, 200), note: 'the hub does not say that each trial is private' });
  if (!/24\s?h(ours)?[^.]{0,80}(reset|delet|clear)|(reset|delet|clear)[^.]{0,80}24\s?h/i.test(t)) finding({ check: 'C7', option: 'HUB', page: 'demo/', text: (t.match(/[^.]*resets?[^.]*\./i) || [''])[0].slice(0, 200), note: 'the hub does not say the trial is reset after 24 h' });
  const data = readFileSync(join(DELIV, 'custom_demo', 'src', 'data.js'), 'utf8');
  const m = /const expired = `([^`]+)`/.exec(data);
  if (m && /created_at\s*</.test(m[1]) && !/last_|seen|updated|activity/.test(m[1])) finding({ check: 'C7', option: 'B', page: `custom_demo/src/data.js:${data.slice(0, m.index).split('\n').length}`, text: m[1].slice(0, 160), element: 'source', note: 'the 03:00 UTC purge selects sandboxes CREATED more than 24 h ago, not sandboxes IDLE for more than 24 h: a trial in use at 03:00 is wiped if it started the day before' });
}

// ---------------------------------------------------------------- D3: numbers on the hub
export function checkNumbers(hub) {
  const trace = JSON.parse(readFileSync(join(HERE, 'd3_trace.json'), 'utf8'));
  const text = (hub.full || '').replace(/[  ]/g, ' ');
  const words = 'one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twice|half|dozen';
  const re = new RegExp(`(?:\\b\\d[\\d,.:]*(?:\\s?(?:–|-|to)\\s?\\d[\\d,.:]*)?\\b|\\b(?:${words})\\b)`, 'gi');
  const seen = new Map();
  let m;
  while ((m = re.exec(text))) {
    // the number is wrapped in ⟨ ⟩ so each trace pattern says where the number sits in its phrase
    const ctx = (text.slice(Math.max(0, m.index - 40), m.index) + '⟨' + m[0] + '⟩' + text.slice(m.index + m[0].length, m.index + m[0].length + 40)).replace(/\n/g, ' ⏎ ');
    const key = ctx;
    if (seen.has(key)) continue;
    seen.set(key, { n: m[0], ctx });
  }
  const rows = [];
  for (const { n, ctx } of seen.values()) {
    let cls = null, src = null;
    for (const t of trace) {
      if (!new RegExp(t.pattern, 'i').test(ctx)) continue;
      cls = t.class;
      if (t.source) { const loc = lineOf(t.source, t.needle); src = loc || `MISSING « ${t.needle} » in ${t.source}`; if (!loc) cls = null; }
      break;
    }
    rows.push({ n, ctx, cls, src });
    if (!cls) finding({ check: 'D3', option: 'HUB', page: 'demo/', text: n, element: ctx, note: src && src.startsWith('MISSING') ? src : 'number not classified (week, date, our demo data) and not traced to a source line' });
  }
  writeFileSync(join(OUT, 'd3_numbers.json'), JSON.stringify(rows, null, 1));
  return rows;
}

// ---------------------------------------------------------------- D1: « Works in the demo » cells
export function checkClaims(hub, A, B, Ahosted) {
  const rd2 = (p) => { try { return rd(p); } catch { return ''; } };
  const aReadme = rd2('wp_demo/README.md'); const bReadme = rd2('custom_demo/README.md');
  const ids = (txt, story) => [...txt.matchAll(new RegExp(`\\| (${story}-[A-Z]\\d+) \\| PASS`, 'g'))].map((x) => x[1]);
  const bIds = (story) => { const l = bReadme.split('\n').find((x) => x.includes(`s${story.slice(1)}_`) && /pass/.test(x)); return l ? [l.split('|')[1].trim() + ' ' + l.split('|')[3].trim()] : []; };
  const map = [];
  const funcOk = (rows, task) => rows.filter((r) => r.task === task).every((r) => r.ok || /^hub (label|says)|equipe sees no access record|step text/.test(r.why) && !/not visible|no reference|not shown|did not/.test(r.why.replace(/^hub [^:]*:/, '')));
  const KEYS = [['1', 'S1', 'T1'], ['2', 'S2', 'T2'], ['3', 'S3', 'T3'], ['4', 'S4', 'T4'], ['5', 'S5', 'T5']];
  for (const row of hub.rows) {
    for (const opt of ['A', 'B']) {
      const cell = row[opt];
      const works = /^Works in the demo/.test(cell);
      const k = KEYS.find(([n]) => row.fn.startsWith(n + '.'));
      let ev = []; let ok = false;
      if (works && k) {
        const reg = opt === 'A' ? ids(aReadme, k[1]) : bIds(k[1]);
        const live = funcOk((opt === 'A' ? A : B).rows, k[2]);
        ev = [`this run: C10 ${k[2]} ${live ? 'functional PASS' : 'FAIL'}`, `${opt === 'A' ? 'wp_demo/README.md' : 'custom_demo/README.md'}: ${reg.join(', ') || 'no PASS id'}`];
        ok = live && reg.length > 0;
      } else if (works && /Editing all the site/.test(row.fn) && opt === 'A') {
        ok = !!(A.pagesEditor && A.pagesEditor.ok); ev = [`this run (gate test CE-D1-PAGES): direction opens « Pages » (edit.php?post_type=page) HTTP ${A.pagesEditor && A.pagesEditor.status}`, 'no earlier test ID in wp_demo/README.md'];
      } else if (works) { ev = ['no mapping']; ok = false; }
      else {
        // « Built during the project »: no working UI may pretend otherwise
        const labels = RUN.labels.filter((l) => l.option.startsWith(opt)).flatMap((l) => l.labels.concat(l.clickables.map((c) => c.label)));
        const pret = { 'Email notifications': /^(Envoyer l’e-mail|Envoyer un e-mail|E-mail envoyé)$/i, 'Importing about 300': /^Import(er)? (des )?congrès|^Importer$/i, 'English version': /^(English|EN|Version anglaise)$/, 'Two-step login': /code de vérification|double authentification|2FA/i, 'Backups and restore': /^(Sauvegarde|Restaurer)/i, 'Editing all the site': /^Pages$/ };
        const key = Object.keys(pret).find((p) => row.fn.startsWith(p));
        const hits = key ? [...new Set(labels.filter((l) => pret[key].test(l.trim())))] : [];
        ok = !hits.length; ev = [hits.length ? `UI shows: ${hits.join(', ')}` : 'no UI label pretends it works'];
      }
      map.push({ fn: row.fn, option: opt, cell: cell.slice(0, 120), works, ok, evidence: ev.join(' · ') });
      if (!ok) finding({ check: 'D1', option: opt, page: 'demo/#compare', text: `${row.fn}: ${cell.slice(0, 80)}`, element: 'table.cmp', note: ev.join(' · ') });
    }
  }
  if (hub.group) {
    const live = B.rows.filter((r) => r.task === 'G').every((r) => r.ok);
    const ok = live && /G-F1/.test(bReadme);
    const notDeployed = /extra_group\.spec\.mjs[^\n]*not deployed/.test(bReadme);
    map.push({ fn: 'Group link (#group)', option: 'B', cell: 'Works in the Option B demo', works: true, ok: ok && !notDeployed, evidence: `this run: G steps ${live ? 'PASS' : 'FAIL'} · custom_demo/README.md extra_group.spec.mjs G-F1..G-X3${notDeployed ? ' (README says « not deployed »)' : ''}` });
    if (!ok || notDeployed) finding({ check: 'D1', option: 'B', page: 'demo/#group', text: 'Works in the Option B demo', note: map[map.length - 1].evidence });
  }
  writeFileSync(join(OUT, 'd1_claims.json'), JSON.stringify(map, null, 1));
  return map;
}

// ---------------------------------------------------------------- E1 / E4
export async function checkVersions(request, hubBase, bBase) {
  const v = {};
  v.commit = execFileSync('git', ['-C', DELIV, 'rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
  v.dirty = execFileSync('git', ['-C', DELIV, 'status', '--porcelain', '--', 'site', 'custom_demo/src', 'wp_demo/plugin'], { encoding: 'utf8' }).trim().split('\n').filter(Boolean);
  // hub: deployed bytes vs source
  for (const p of ['demo/index.html', 'index.html', 'js/demo.js', 'css/demo.css']) {
    const live = await (await request.get(`${hubBase}/${p.replace('index.html', '')}`)).body();
    const src = readFileSync(join(DELIV, 'site', p));
    const same = createHash('sha256').update(live).digest('hex') === createHash('sha256').update(src).digest('hex');
    v['hub ' + p] = same ? 'deployed = source' : 'DIFFERS from source';
    if (!same) finding({ check: 'E1', option: 'HUB', page: `${hubBase}/${p}`, text: p, note: 'deployed file differs from site/ in the repository' });
  }
  // Option A hosted zip vs the zip built from the current plugin code
  const hostedZip = await (await request.get('https://asset-voyages-redesign.pages.dev/demo-wordpress/asset-congres-demo.zip')).body();
  const localZip = readFileSync(join(DELIV, 'wp_demo', 'asset-congres-demo.zip'));
  v.zipHosted = createHash('sha256').update(hostedZip).digest('hex'); v.zipLocal = createHash('sha256').update(localZip).digest('hex');
  if (v.zipHosted !== v.zipLocal) finding({ check: 'E1', option: 'A-hosted', page: 'demo-wordpress/asset-congres-demo.zip', text: `hosted ${v.zipHosted.slice(0, 12)} ≠ local build ${v.zipLocal.slice(0, 12)}`, note: 'the hub\'s Playground links install an older plugin than the current wp_demo/ code' });
  // Option B: the deployed Worker version (wrangler, read-only)
  try { v.worker = execFileSync('npx', ['wrangler', 'deployments', 'list', '--json'], { cwd: join(DELIV, 'custom_demo'), encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], timeout: 60000 }); const j = JSON.parse(v.worker); const last = j[j.length - 1] || j[0]; v.worker = { id: last.id, created_on: last.created_on, message: last.annotations && last.annotations['workers/message'] }; } catch (e) { v.worker = 'wrangler deployments list failed: ' + e.message.split('\n')[0]; }
  try { v.bSrcLastCommit = execFileSync('git', ['-C', DELIV, 'log', '-1', '--format=%h %cI', '--', 'custom_demo/src'], { encoding: 'utf8' }).trim(); } catch {}
  if (v.worker && v.worker.created_on && v.bSrcLastCommit && new Date(v.worker.created_on) < new Date(v.bSrcLastCommit.split(' ')[1])) finding({ check: 'E1', option: 'B', page: bBase, text: `Worker deployed ${v.worker.created_on}, src last commit ${v.bSrcLastCommit}`, note: 'deployed Worker is older than the last source commit' });
  const pw = readdirSync('/opt/pw-browsers');
  v.browsers = pw;
  markCheck('E4', 'N/A', `Only Chromium is installed (${pw.join(', ')}); Firefox and WebKit are not, and the brief forbids installing them. Recorded N/A, never PASS.`);
  return v;
}
