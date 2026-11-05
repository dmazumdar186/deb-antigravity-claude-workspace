import { clamp, seg, eo, eio, ei, back, lerp, mulberry } from '/core/lib.js';
const W = innerWidth, H = innerHeight, cv = document.getElementById('c'); cv.width = W; cv.height = H;
const g = cv.getContext('2d');
const P = { paper: '#EFEDE6', ink: '#16140F', gold: '#B8913A', goldTx: '#8A6A1F', panel: '#E3DDCB', bar: '#CBC4B4', grey: '#6F695E', red: '#A86458', chip: '#EADBB4' };
await Promise.all(['700 40px Newsreader', '400 40px Newsreader', 'italic 400 40px Newsreader', '600 20px "Plex Mono"', '400 20px "Plex Mono"'].map(f => document.fonts.load(f)));

window.DUR = 31.6;
const M = 80, CW = W - 2 * M;
const SERIF = (w, s, it = '') => `${it} ${w} ${s}px Newsreader`.trim();
const MONO = (w, s) => `${w} ${s}px "Plex Mono"`;

// ---------- timeline (seconds) ----------
const T = {
  h1: 0.15, shrink: 3.0, kick: 3.5, rows: [3.65, 3.95, 4.25, 4.55, 4.85], waves: [4.6, 4.75, 4.9, 5.15], goldFill: 5.3, quote: 5.5,
  b2out: 8.5, quoteOut: 10.6,
  h3: 8.9, rule: 8.95, notes: [9.4, 9.8, 10.2], cards: 10.65, red: 11.25, slide: 11.45, shift: 11.95, tick: 12.35, b3out: 13.85,
  h4: 14.0, stack: 14.2, chips: [15.1, 15.6, 16.1], priv: 16.4, h4out: 17.5,
  h5: 17.6, l1: 17.85, l2: 18.2, sweep: 19.1, stamp: 20.6, b5out: 23.3,
  pay: 23.6, ten: 23.85, of158: 24.3, cta: 24.6, credit: 24.1, b6out: 30.7, gridBack: 30.85
};
window.EV = [
  ...T.rows.map((t, i) => ({ t, type: 'tick', i })),
  ...T.waves.map((t, i) => ({ t, type: 'paper', v: .35 })),
  { t: T.goldFill, type: 'chime', note: 'A5' },
  { t: T.quote, type: 'paper', v: .5 },
  { t: T.b2out, type: 'whoosh' },
  { t: T.rule, type: 'paper', v: .6 },
  ...T.notes.map(t => ({ t, type: 'click', v: .45 })),
  { t: T.cards, type: 'paper', v: .5 },
  { t: T.red, type: 'click', v: .5 },
  { t: T.slide, type: 'whoosh' },
  { t: T.tick, type: 'chime', note: 'D6' },
  { t: T.b3out, type: 'whoosh' },
  { t: T.stack, type: 'paper', v: .7 },
  ...T.chips.map((t, i) => ({ t, type: 'tick', i: i + 1 })),
  { t: T.priv, type: 'click', v: .4 },
  { t: T.sweep, type: 'paper', v: .4 },
  { t: T.stamp, type: 'stamp' },
  { t: T.b5out, type: 'whoosh' },
  { t: T.ten + .7, type: 'chime', note: 'F#5' },
  { t: T.cta, type: 'paper', v: .45 },
  { t: T.b6out, type: 'whoosh' },
  { t: T.gridBack, type: 'paper', v: .3 }
];

// ---------- helpers ----------
let TX = [], lastT = null;
const rep = (id, text, x0, y0, x1, y1) => TX.push({ id, text, x0, y0, x1, y1 });
function wrap(text, font, maxW) {
  g.font = font; const out = []; let cur = '';
  for (const w of text.split(' ')) { const s = cur ? cur + ' ' + w : w; if (g.measureText(s).width > maxW && cur) { out.push(cur); cur = w; } else cur = s; }
  if (cur) out.push(cur); return out;
}
// a block of text: lines rise out of a clip (swiss clip-reveal) and leave upward
function block({ id, text, lines, font, size, lh, x, y, color = P.ink, t0, t1, t, st = .09, tin = .5, tout = .3, align = 'left', maxW = CW, report = true }) {
  lines = lines || wrap(text, font, maxW);
  if (t < t0 || t >= t1 + tout + st * lines.length) return lines;
  g.font = font; g.fillStyle = color; g.textAlign = align;
  let wmax = 0;
  lines.forEach((s, i) => {
    const w = g.measureText(s).width; wmax = Math.max(wmax, w);
    const pin = eo(seg(t, t0 + i * st, t0 + i * st + tin)), pout = ei(seg(t, t1 + i * st * .5, t1 + i * st * .5 + tout));
    const by = y + i * lh, hh = size * 1.32, lx = align === 'left' ? x : align === 'right' ? x - w : x - w / 2;
    g.save(); g.beginPath(); g.rect(lx - 6, by - size * 1.02, w + 12, hh); g.clip();
    g.fillText(s, x, by + (1 - pin) * hh - pout * hh); g.restore();
  });
  g.textAlign = 'left';
  if (report && t < t1) { const lx = align === 'left' ? x : align === 'right' ? x - wmax : x - wmax / 2; rep(id, text, lx, y - size * .85, lx + wmax, y + (lines.length - 1) * lh + size * .28); }
  return lines;
}
const line = (x0, y0, x1, y1, p, col = P.gold, lw = 6) => { if (p <= 0) return; g.strokeStyle = col; g.lineWidth = lw; g.lineCap = 'round'; g.beginPath(); g.moveTo(x0, y0); g.lineTo(lerp(x0, x1, p), lerp(y0, y1, p)); g.stroke(); };
const rr = (x, y, w, h, r, fill, stroke, lw = 2) => { g.beginPath(); g.roundRect(x, y, w, h, r); if (fill) { g.fillStyle = fill; g.fill(); } if (stroke) { g.strokeStyle = stroke; g.lineWidth = lw; g.stroke(); } };
function check(cx, cy, s, p, col = P.gold, lw = 5) { // line-drawn tick mark
  if (p <= 0) return; const pts = [[-.5, 0], [-.15, .35], [.55, -.4]].map(([a, b]) => [cx + a * s, cy + b * s]);
  g.strokeStyle = col; g.lineWidth = lw; g.lineCap = 'round'; g.lineJoin = 'round'; g.beginPath(); g.moveTo(...pts[0]);
  const l1 = Math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]), l2 = Math.hypot(pts[2][0] - pts[1][0], pts[2][1] - pts[1][1]), d = p * (l1 + l2);
  if (d <= l1) g.lineTo(lerp(pts[0][0], pts[1][0], d / l1), lerp(pts[0][1], pts[1][1], d / l1));
  else { g.lineTo(...pts[1]); const q = (d - l1) / l2; g.lineTo(lerp(pts[1][0], pts[2][0], q), lerp(pts[1][1], pts[2][1], q)); }
  g.stroke();
}
const fadeIO = (t, a, b, fi = .4, fo = .3) => Math.min(eo(seg(t, a, a + fi)), 1 - ei(seg(t, b, b + fo)));

// ---------- the 158-dot pool ----------
const N = 158, COLS = 16, rnd = mulberry(303);
const order = Array.from({ length: N }, (_, i) => i).sort(() => 0).map(i => ({ i, r: rnd() }));
const ranked = [...order].sort((a, b) => a.r - b.r).map(o => o.i);   // ranked[k] = dot index; last 10 survive
const fate = new Array(N);                                           // which wave removes the dot (0..3), 4 = survivor
ranked.forEach((d, k) => { fate[d] = k < 48 ? 0 : k < 94 ? 1 : k < 140 ? 2 : k < 148 ? 3 : 4; });
function person(cx, cy, s, fill, alpha) {
  if (alpha <= 0) return; g.globalAlpha = alpha; g.lineWidth = Math.max(1.6, s * .07);
  g.strokeStyle = fill ? P.gold : P.ink; g.fillStyle = P.gold;
  g.beginPath(); g.arc(cx, cy - s * .16, s * .15, 0, Math.PI * 2); fill ? g.fill() : g.stroke();
  g.beginPath(); g.arc(cx, cy + s * .34, s * .27, Math.PI, 0); g.closePath(); fill ? g.fill() : g.stroke();
  g.globalAlpha = 1;
}
function grid(t) {
  const big = { sp: 52, x: (W - 15 * 52) / 2, y: 600 }, small = { sp: 30, x: (W - 15 * 30) / 2, y: 735 };
  const k = eio(seg(t, T.shrink, T.shrink + .55));
  const sp = lerp(big.sp, small.sp, k), x0 = lerp(big.x, small.x, k), y0 = lerp(big.y, small.y, k);
  const back = t >= T.gridBack - .2;
  for (let i = 0; i < N; i++) {
    const cx = x0 + (i % COLS) * sp, cy = y0 + Math.floor(i / COLS) * sp;
    let a = 1, fill = false;
    if (back) { const d = T.gridBack + (i % COLS) * .008 + Math.floor(i / COLS) * .018; a = eo(seg(t, d, d + .35)); person(big.x + (i % COLS) * big.sp, big.y + Math.floor(i / COLS) * big.sp, big.sp, false, a); continue; }
    const f = fate[i];
    if (f < 4) a = 1 - eo(seg(t, T.waves[f] + (i % 7) * .015, T.waves[f] + .3 + (i % 7) * .015));
    else fill = t >= T.goldFill + (i % 5) * .04;
    a *= 1 - ei(seg(t, T.b2out, T.b2out + .35));
    person(cx, cy, sp, fill, a);
  }
}

// ---------- chrome (every frame) ----------
function chrome(t) {
  g.fillStyle = P.ink; g.font = MONO(600, 24); g.textBaseline = 'alphabetic';
  g.fillText('ProdCraft', M, 76); rep('hdrL', 'ProdCraft', M, 56, M + g.measureText('ProdCraft').width, 82);
  g.font = MONO(400, 24); g.textAlign = 'right'; g.fillText('wk 03', W - M, 76); g.textAlign = 'left';
  rep('hdrR', 'wk 03', W - M - g.measureText('wk 03').width, 56, W - M, 82);
  g.globalAlpha = .25; g.strokeStyle = P.ink; g.lineWidth = 2;
  g.beginPath(); g.moveTo(M, 102); g.lineTo(W - M, 102); g.stroke();
  g.beginPath(); g.moveTo(M, H - 110); g.lineTo(W - M, H - 110); g.stroke(); g.globalAlpha = 1;
  g.font = MONO(400, 24); g.fillStyle = P.ink; g.fillText('ProdCraft · weekly notes', M, H - 60);
  rep('ftrL', 'ProdCraft · weekly notes', M, H - 80, M + g.measureText('ProdCraft · weekly notes').width, H - 54);
  g.textAlign = 'right'; g.fillText('03', W - M, H - 60); g.textAlign = 'left';
  rep('ftrR', '03', W - M - g.measureText('03').width, H - 80, W - M, H - 54);
  // credit, in the footer band
  const cr = 'Made in code with lemo-opuscar (MIT) · music: original, CC0 samples (Versilian Studios)';
  const a = fadeIO(t, T.credit, T.b6out + .05);
  if (a > 0) { g.globalAlpha = a; g.font = MONO(400, 17); g.fillStyle = P.grey; g.fillText(cr, M, H - 126); g.globalAlpha = 1;
    if (t < T.b6out + .05) rep('credit', cr, M, H - 141, M + g.measureText(cr).width, H - 121); }
}

// ---------- scenes ----------
const H1 = 'One senior role. 158 profiles. Who do you call first?';
const H1L = ['One senior role.', '158 profiles.', 'Who do you call first?'];
g.font = SERIF(700, 100); const H1S = Math.min(100, 100 * CW / g.measureText(H1L[2]).width);
function beat1_2(t) {
  if (t >= T.b2out + .6) return;
  // headline: big, then shrinks to a running title
  const k = eio(seg(t, T.shrink, T.shrink + .55)), s = lerp(1, .5, k), oy = lerp(250, 175, k), lh = H1S * 1.04;
  g.save(); g.translate(M, oy); g.scale(s, s);
  const sub = TX.length; block({ id: 'h1', text: H1, lines: H1L, font: SERIF(700, H1S), size: H1S, lh, x: 0, y: 0, t0: T.h1, t1: T.b2out, t, st: .12, tin: .6 });
  g.restore();
  for (let j = sub; j < TX.length; j++) { const b = TX[j]; b.x0 = M + b.x0 * s; b.x1 = M + b.x1 * s; b.y0 = oy + b.y0 * s; b.y1 = oy + b.y1 * s; }
  // underline under the question, line-drawn, shrinks with the headline
  g.font = SERIF(700, H1S); const qw = g.measureText(H1L[2]).width;
  const u = eio(seg(t, 1.05, 1.75)) * (1 - ei(seg(t, T.b2out, T.b2out + .3)));
  line(M, oy + (2 * lh + H1S * .2) * s, M + qw * s, oy + (2 * lh + H1S * .2) * s, u, P.gold, lerp(7, 4, k));
  // kicker + funnel rows
  block({ id: 'kick', text: 'the pool, counted', font: MONO(600, 24), size: 24, lh: 30, x: M, y: 352, color: P.goldTx, t0: T.kick, t1: T.b2out, t });
  const rows = [[158, 'profiles assessed'], [594, 'claims pulled from public sources'], [446, 'survived the quote check'], [18, 'passed every hard rule'], [10, 'on the shortlist, as the brief asked']];
  rows.forEach(([v, lab], i) => {
    const t0 = T.rows[i], y = 410 + i * 60;
    if (t < t0) return;
    const p = eo(seg(t, t0, t0 + .45)), q = ei(seg(t, T.b2out + i * .03, T.b2out + .3 + i * .03)), off = (1 - p) * 40 - q * 40;
    const n = Math.round(v * eo(seg(t, t0, t0 + .6)));
    g.save(); g.beginPath(); g.rect(M - 6, y - 50, CW + 12, 66); g.clip(); g.translate(0, off);
    g.font = SERIF(700, 46); g.fillStyle = i === 4 ? P.goldTx : P.ink; g.textAlign = 'right'; g.fillText(String(n), M + 120, y); g.textAlign = 'left';
    g.font = SERIF(400, 34); g.fillStyle = P.ink; g.fillText(lab, M + 145, y);
    g.restore();
    line(M, y + 18, W - M, y + 18, eio(seg(t, t0 + .1, t0 + .6)) * (1 - q), P.ink, 1);
    if (t < T.b2out) { g.font = SERIF(400, 34); rep('row' + i, v + ' ' + lab, M, y - 40, M + 145 + g.measureText(lab).width, y + 10); }
  });
}
function quote(t) {
  // pull quote, gold rule beside it
  const qa = seg(t, T.quote, T.quote + .5);
  if (t < T.quoteOut + .4) {
    g.strokeStyle = P.gold; g.lineWidth = 5; g.lineCap = 'butt';
    const r = eio(qa) * (1 - ei(seg(t, T.quoteOut, T.quoteOut + .3)));
    if (r > 0) { g.beginPath(); g.moveTo(M, 1032); g.lineTo(M, 1032 + 126 * r); g.stroke(); }
  }
  block({ id: 'quote', text: '"A shortlist without a denominator is a claim, not a finding."', lines: ['"A shortlist without a denominator', 'is a claim, not a finding."'], font: SERIF(400, 42, 'italic'), size: 42, lh: 54, x: M + 30, y: 1072, t0: T.quote, t1: T.quoteOut, t, maxW: CW - 40 });
}
function beat3(t) {
  if (t < T.h3 || t >= T.b3out + .6) return;
  const hl = block({ id: 'h3', text: 'Every factual claim carries a quote. No match, no claim.', lines: ['Every factual claim carries', 'a quote. No match, no claim.'], font: SERIF(700, 62), size: 62, lh: 68, x: M, y: 190, t0: T.h3, t1: T.b3out, t });
  // the rule card (beige panel)
  const cp = back(seg(t, T.rule, T.rule + .55), 1.3), ca = clamp(cp) * (1 - ei(seg(t, T.b3out, T.b3out + .3)));
  if (ca > 0) {
    g.save(); g.globalAlpha = ca; g.translate(0, (1 - cp) * 50);
    rr(M, 350, CW, 220, 14, P.panel);
    g.restore();
  }
  block({ id: 'rulek', text: 'the rule', font: MONO(600, 24), size: 24, lh: 30, x: M + 36, y: 404, color: P.goldTx, t0: T.rule + .15, t1: T.b3out, t });
  block({ id: 'rule', text: 'keep a claim only if its quote is found in the cached source', font: SERIF(400, 42), size: 42, lh: 54, x: M + 36, y: 470, t0: T.rule + .08, t1: T.b3out, t, maxW: CW - 72 });
  const notes = ["148 of 594 couldn't be matched · none reached the page", 'anything inferred is labelled as inferred', 'the hard rules are code, not a model'];
  notes.forEach((s, i) => {
    const y = 658 + i * 58, t0 = T.notes[i];
    const a = eo(seg(t, t0, t0 + .3)) * (1 - ei(seg(t, T.b3out, T.b3out + .3)));
    if (a > 0) { g.globalAlpha = a; g.fillStyle = P.gold; g.fillRect(M, y - 16, 14, 14); g.globalAlpha = 1; }
    block({ id: 'note' + i, text: s, font: MONO(400, 26), size: 26, lh: 32, x: M + 32, y, t0, t1: T.b3out, t });
  });
  // claim cards: one fails the quote check and slides off, the next is kept
  const cw = 268, chh = 160, cy = 856, gap = 58;
  for (let k = 0; k < 4; k++) {
    const d = k === 3 ? T.shift : T.cards + k * .12; if (t < d) continue;
    let x = M + k * (cw + gap) + (k === 3 ? 0 : (1 - eo(seg(t, d, d + .45))) * 40);
    let a = eo(seg(t, d, d + .4)) * (1 - ei(seg(t, T.b3out, T.b3out + .3)));
    if (k === 0) x -= ei(seg(t, T.slide, T.slide + .55)) * (cw + M + 200), a *= 1 - seg(t, T.slide + .3, T.slide + .55);
    else x -= eio(seg(t, T.shift, T.shift + .4)) * (cw + gap);
    if (a <= 0 || x > W) continue;
    g.globalAlpha = a;
    const red = k === 0 ? eo(seg(t, T.red, T.red + .2)) : 0;
    rr(x, cy, cw, chh, 12, red > 0 ? (red > .5 ? '#E7CFC8' : P.panel) : P.panel, red > 0 ? P.red : null, 3);
    g.fillStyle = red > .5 ? P.red : P.gold; g.fillRect(x, cy + 14, 5, chh - 28);
    [[.78, 0], [.6, 1], [.7, 2]].forEach(([w, j]) => rr(x + 26, cy + 30 + j * 32, (cw - 52) * w * (k === 3 ? .9 : 1), 14, 7, red > .5 ? '#CFA79E' : P.bar));
    if (k === 1) check(x + cw - 34, cy + chh - 34, 30, eo(seg(t, T.tick, T.tick + .35)), P.goldTx, 5);
    g.globalAlpha = 1;
  }
}
function beat4_5(t) {
  if (t < T.h4 || t >= T.b5out + .6) return;
  const out = T.b5out, fo = 1 - ei(seg(t, out, out + .3));
  block({ id: 'h4', text: 'One row per candidate.', font: SERIF(700, 62), size: 62, lh: 68, x: M, y: 200, t0: T.h4, t1: T.h4out, t });
  block({ id: 'h5', text: 'Drafts wait for your approval. Nothing sends on its own.', font: SERIF(700, 56), size: 56, lh: 62, x: M, y: 182, t0: T.h5, t1: out, t });
  // stacked cards, C at the back
  const stack = [['Candidate C', 40, 300], ['Candidate B', 20, 336], [null, 0, 372]];
  stack.forEach(([lab, inset, top], j) => {
    const d = T.stack + j * .12, p = back(seg(t, d, d + .55), 1.2), a = clamp(p) * fo;
    if (a <= 0) return;
    g.save(); g.globalAlpha = a; g.translate(0, (1 - p) * 60);
    rr(M + inset, top, CW - 2 * inset, j < 2 ? 420 : 400, 14, j === 2 ? '#F6F4EE' : P.panel, P.ink + '40', 1.5);
    g.restore();
    if (lab) block({ id: 'stack' + j, text: lab, font: MONO(400, 20), size: 20, lh: 24, x: M + inset + 24, y: top + 25, color: P.grey, t0: d + .2, t1: out, t });
  });
  const cx = M + 36, ty = 438;
  // row header: name + tier badge
  const nameP = seg(t, T.stack + .45, T.stack + .9);
  if (t >= T.stack + .45) {
    g.font = SERIF(700, 40); const nw = g.measureText('Candidate A').width, dw = g.measureText(' · ').width;
    g.font = MONO(600, 24); const tw = g.measureText('Tier A').width;
    g.save(); g.beginPath(); g.rect(cx - 6, ty - 46, CW, 64); g.clip(); g.translate(0, (1 - eo(nameP)) * 60 - ei(seg(t, out, out + .3)) * 60);
    g.font = SERIF(700, 40); g.fillStyle = P.ink; g.fillText('Candidate A', cx, ty); g.fillText(' · ', cx + nw, ty);
    rr(cx + nw + dw, ty - 31, tw + 28, 40, 20, P.chip, P.gold, 2);
    g.font = MONO(600, 24); g.fillStyle = P.goldTx; g.fillText('Tier A', cx + nw + dw + 14, ty - 3);
    g.restore();
    if (t < out) rep('candA', 'Candidate A · Tier A', cx, ty - 34, cx + nw + dw + tw + 28, ty + 10);
  }
  // why them + placeholder bars
  block({ id: 'why', text: 'Why them', font: MONO(600, 20), size: 20, lh: 24, x: cx, y: 500, color: P.grey, t0: T.stack + .6, t1: out, t });
  [[.82, 0], [.58, 1]].forEach(([w, j]) => { const p = eio(seg(t, T.stack + .75 + j * .12, T.stack + 1.25 + j * .12)) * fo; if (p > 0) rr(cx, 520 + j * 30, (CW - 72) * w * p, 16, 8, P.bar); });
  block({ id: 'msg', text: 'Message to send', font: MONO(600, 20), size: 20, lh: 24, x: cx, y: 618, color: P.grey, t0: T.stack + .8, t1: out, t });
  const chips = ['LinkedIn note', 'Email', 'Follow-up, about a week later'];
  g.font = MONO(400, 23); let x = cx;
  chips.forEach((s, i) => {
    const w = g.measureText(s).width + 36, d = T.stack + .95 + i * .1, a = eo(seg(t, d, d + .35)) * fo, on = eo(seg(t, T.chips[i], T.chips[i] + .25));
    if (a > 0) {
      g.globalAlpha = a; rr(x, 640, w, 48, 24, on > 0 ? (on > .5 ? P.chip : '#F6F4EE') : '#F6F4EE', on > .5 ? P.gold : P.ink + '55', on > .5 ? 2.5 : 1.5);
      g.fillStyle = on > .5 ? P.ink : P.grey; g.font = MONO(on > .5 ? 600 : 400, 23); g.fillText(s, x + 18, 672); g.globalAlpha = 1;
      if (t < out) rep('chip' + i, s, x, 640, x + w, 688);
    }
    g.font = MONO(400, 23); x += w + 14;
  });
  block({ id: 'priv', text: 'privacy notice + STOP line in every email, fixed text', font: MONO(400, 24), size: 24, lh: 30, x: M, y: 822, color: P.ink, t0: T.priv, t1: out, t });
  const l1 = block({ id: 'l1', text: 'ready-to-contact rows first: verified address, resolved profile', font: SERIF(400, 36), size: 36, lh: 46, x: M, y: 912, t0: T.l1, t1: out, t });
  g.font = SERIF(400, 36); const l1w = g.measureText(l1[0]).width;
  line(M, 912 + (l1.length - 1) * 46 + 16, M + Math.max(l1w, l1.length > 1 ? g.measureText(l1[1]).width : 0), 912 + (l1.length - 1) * 46 + 16, eio(seg(t, T.sweep, T.sweep + .7)) * fo, P.gold, 5);
  block({ id: 'l2', text: 'professional network first, then email, then the switchboard', font: SERIF(400, 36), size: 36, lh: 46, x: M, y: 912 + l1.length * 46 + 44, t0: T.l2, t1: out, t });
  // approval stamp lands on the row
  if (t >= T.stamp) {
    const p = seg(t, T.stamp, T.stamp + .32), s = lerp(1.7, 1, eo(p)), a = clamp(p * 3) * fo;
    g.font = MONO(600, 28); const sw = g.measureText('approved').width + 86, sx = W - M - 36 - sw / 2, sy = 450;
    g.save(); g.globalAlpha = a; g.translate(sx, sy); g.rotate(-.07); g.scale(s, s);
    rr(-sw / 2, -30, sw, 60, 8, 'rgba(234,219,180,.9)', P.goldTx, 3);
    check(-sw / 2 + 32, -2, 26, 1, P.goldTx, 4.5);
    g.fillStyle = P.goldTx; g.fillText('approved', -sw / 2 + 60, 10);
    g.restore();
    if (t < out) rep('stamp', '✓ approved', sx - sw / 2 - 4, sy - 36, sx + sw / 2 + 4, sy + 36);
  }
}
function beat6(t) {
  if (t < T.pay || t >= T.b6out + .6) return;
  const out = T.b6out;
  block({ id: 'pay', text: 'Your team reads 10 rows, with the full funnel from 158 next to them.', font: SERIF(700, 58), size: 58, lh: 64, x: M, y: 196, t0: T.pay, t1: out, t });
  // huge 10, ticking down from 158
  if (t >= T.ten) {
    const n = Math.round(lerp(158, 10, eio(seg(t, T.ten, T.ten + .7))));
    g.save(); g.beginPath(); g.rect(M - 10, 360, CW, 330); g.clip();
    g.translate(0, (1 - eo(seg(t, T.ten, T.ten + .45))) * 320 - ei(seg(t, out, out + .3)) * 320);
    g.font = SERIF(700, 340); g.fillStyle = P.gold; g.fillText(String(n), M - 12, 660); g.restore();
    g.font = SERIF(700, 340); const tw = g.measureText('10').width;
    if (t < out) rep('ten', '10', M, 420, M + tw, 670);
    line(M, 698, M + tw, 698, eio(seg(t, T.ten + .7, T.ten + 1.2)) * (1 - ei(seg(t, out, out + .3))), P.gold, 6);
    // the ten, as gold person-dots
    for (let k = 0; k < 10; k++) { const d = T.ten + .75 + k * .05; person(M + tw + 130 + (k % 5) * 76, 500 + Math.floor(k / 5) * 96, 80, true, eo(seg(t, d, d + .3)) * (1 - ei(seg(t, out, out + .3)))); }
  }
  block({ id: 'of158', text: 'of 158', font: MONO(600, 34), size: 34, lh: 40, x: M, y: 752, color: P.goldTx, t0: T.of158, t1: out, t });
  block({ id: 'cta', text: 'I build systems like this for recruiting desks, around your roles and your rules.', font: SERIF(400, 40), size: 40, lh: 54, x: M, y: 880, t0: T.cta, t1: out, t });
}

window.render = t => {
  TX = []; lastT = t;
  g.textBaseline = 'alphabetic'; g.globalAlpha = 1;
  g.fillStyle = P.paper; g.fillRect(0, 0, W, H);
  grid(t);
  beat1_2(t); quote(t); beat3(t); beat4_5(t); beat6(t);
  chrome(t);
};
window.TEXTS = t => { if (lastT !== t) window.render(t); return TX; };
window.READY = true;
