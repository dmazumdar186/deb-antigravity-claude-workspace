import { clamp, seg, eo, eio, ei, back, lerp } from '/core/lib.js';
const W = innerWidth, H = innerHeight, cv = document.getElementById('c'); cv.width = W; cv.height = H;
const g = cv.getContext('2d');
const P = { paper: '#EFEDE6', ink: '#16140F', gold: '#B8913A', goldTx: '#8A6A1F', panel: '#E3DDCB', bar: '#CBC4B4', grey: '#6F695E', dim: '#A49D90' };
await Promise.all(['700 40px Newsreader', '400 40px Newsreader', 'italic 400 40px Newsreader', '600 20px "Plex Mono"', '400 20px "Plex Mono"'].map(f => document.fonts.load(f)));

window.DUR = 31.75;
const M = 80, CW = W - 2 * M;
const SERIF = (w, s, it = '') => `${it} ${w} ${s}px Newsreader`.trim();
const MONO = (w, s) => `${w} ${s}px "Plex Mono"`;

// ---------- timeline (seconds) ----------
const T = {
  ctr: 1.65, ctrEnd: 2.1, b1out: 3.85,
  b2: 3.95, steps: [4.0, 6.7], b2out: 8.65,
  b3: 8.75, lights: [9.15, 10.3, 11.45, 12.6, 13.75, 14.9, 16.05], b3out: 17.9,
  pay: 18.0, b4out: 21.5,
  l1: 21.6, l2: 22.1, b5out: 25.6,
  offer: 25.75, url: 26.2, credit: 25.75, b6out: 31.0, loop: 31.38
};
window.EV = [
  { t: T.ctr, type: 'paper', v: .35 },
  { t: T.ctrEnd, type: 'chime', note: 'A5' },
  { t: T.b1out, type: 'whoosh' },
  ...T.steps.map((t, i) => ({ t, type: 'tick', i })),
  ...T.steps.map(t => ({ t: t + .25, type: 'paper', v: .35 })),
  { t: T.b2out, type: 'whoosh' },
  ...T.lights.map((t, i) => ({ t, type: 'tick', i })),
  { t: T.lights[6] + .9, type: 'chime', note: 'D6' },
  { t: T.b3out, type: 'whoosh' },
  { t: T.pay + .1, type: 'chime', note: 'F#5' },
  { t: T.b4out, type: 'whoosh' },
  { t: T.l1, type: 'paper', v: .5 },
  { t: T.l2, type: 'paper', v: .5 },
  { t: T.b5out, type: 'whoosh' },
  { t: T.offer, type: 'paper', v: .45 },
  { t: T.url, type: 'click', v: .45 },
  { t: T.b6out, type: 'whoosh' }
];

// ---------- helpers ----------
let TX = [], lastT = null;
const rep = (id, text, x0, y0, x1, y1, pass) => TX.push(pass ? { id, text, x0, y0, x1, y1, pass: true } : { id, text, x0, y0, x1, y1 });
function wrap(text, font, maxW) {
  g.font = font; const out = []; let cur = '';
  for (const w of text.split(' ')) { const s = cur ? cur + ' ' + w : w; if (g.measureText(s).width > maxW && cur) { out.push(cur); cur = w; } else cur = s; }
  if (cur) out.push(cur); return out;
}
// lines rise out of a clip (swiss clip-reveal) and leave upward
function block({ id, text, lines, font, size, lh, x, y, color = P.ink, t0, t1, t, st = .09, tin = .5, tout = .3, maxW = CW, report = true }) {
  lines = lines || wrap(text, font, maxW);
  if (t < t0 || t >= t1 + tout + st * lines.length) return lines;
  g.font = font; g.fillStyle = color;
  let wmax = 0;
  lines.forEach((s, i) => {
    const w = g.measureText(s).width; wmax = Math.max(wmax, w);
    const pin = eo(seg(t, t0 + i * st, t0 + i * st + tin)), pout = ei(seg(t, t1 + i * st * .5, t1 + i * st * .5 + tout));
    const by = y + i * lh, hh = size * 1.32;
    g.save(); g.beginPath(); g.rect(x - 6, by - size * 1.02, w + 12, hh); g.clip();
    g.fillText(s, x, by + (1 - pin) * hh - pout * hh); g.restore();
  });
  if (report && t < t1) rep(id, text, x, y - size * .85, x + wmax, y + (lines.length - 1) * lh + size * .28);
  return lines;
}
const line = (x0, y0, x1, y1, p, col = P.gold, lw = 6) => { if (p <= 0) return; g.strokeStyle = col; g.lineWidth = lw; g.lineCap = 'round'; g.beginPath(); g.moveTo(x0, y0); g.lineTo(lerp(x0, x1, p), lerp(y0, y1, p)); g.stroke(); };
const rr = (x, y, w, h, r, fill, stroke, lw = 2) => { g.beginPath(); g.roundRect(x, y, w, h, r); if (fill) { g.fillStyle = fill; g.fill(); } if (stroke) { g.strokeStyle = stroke; g.lineWidth = lw; g.stroke(); } };
const fadeIO = (t, a, b, fi = .4, fo = .3) => Math.min(eo(seg(t, a, a + fi)), 1 - ei(seg(t, b, b + fo)));
// the Newsreader latin subset has no U+2192: the arrow is drawn as a vector in a 3-space cell
function arrow(x0, x1, y, col, lw = 2.4) {
  g.strokeStyle = col; g.lineWidth = lw; g.lineCap = 'round'; g.lineJoin = 'round'; g.beginPath();
  g.moveTo(x0 + 3, y); g.lineTo(x1 - 3, y); g.moveTo(x1 - 11, y - 7); g.lineTo(x1 - 3, y); g.lineTo(x1 - 11, y + 7); g.stroke();
}

// ---------- chrome (every frame) ----------
const CREDIT = 'Made in code with lemo-opuscar (MIT) · music: original, CC0 samples (Versilian Studios)';
function chrome(t) {
  g.fillStyle = P.ink; g.font = MONO(600, 24);
  g.fillText('ProdCraft', M, 76);
  g.font = MONO(400, 24); const wk = 'wk 04';
  g.textAlign = 'right'; g.fillText(wk, W - M, 76); g.textAlign = 'left';
  rep('hdr', 'ProdCraft · wk 04', M, 56, W - M, 82);
  g.globalAlpha = .25; g.strokeStyle = P.ink; g.lineWidth = 2;
  g.beginPath(); g.moveTo(M, 102); g.lineTo(W - M, 102); g.stroke();
  g.beginPath(); g.moveTo(M, H - 110); g.lineTo(W - M, H - 110); g.stroke(); g.globalAlpha = 1;
  g.font = MONO(400, 24); g.fillStyle = P.ink; g.fillText('ProdCraft · weekly notes', M, H - 60);
  g.textAlign = 'right'; g.fillText('04', W - M, H - 60); g.textAlign = 'left';
  rep('ftr', 'ProdCraft · weekly notes · 04', M, H - 80, W - M, H - 54);
  const a = fadeIO(t, T.credit, T.b6out - .3);
  if (a > 0) { g.globalAlpha = a; g.font = MONO(400, 17); g.fillStyle = P.grey; g.fillText(CREDIT, M, H - 126); g.globalAlpha = 1;
    if (t < T.b6out - .3) rep('credit', CREDIT, M, H - 141, M + g.measureText(CREDIT).width, H - 121, true); }
}

// ---------- beat 1: hook (frame 0 = thumbnail) ----------
const H1 = '12 emails a day, by hand. Then 800 a day.';
const H1L = ['12 emails a day,', 'by hand.', 'Then 800 a day.'];
g.font = SERIF(700, 100); const H1S = Math.min(128, 100 * CW / Math.max(...H1L.map(s => g.measureText(s).width)));
const H1Y = 250, H1LH = H1S * 1.02;
function hookStatic(a, n, report) { // the frame-0 composition, also used for the loop back
  g.globalAlpha = a; g.font = SERIF(700, H1S); g.fillStyle = P.ink;
  H1L.forEach((s, i) => g.fillText(s, M, H1Y + i * H1LH));
  const uw = g.measureText(H1L[2]).width;
  g.strokeStyle = P.gold; g.lineWidth = 7; g.lineCap = 'round'; g.beginPath(); g.moveTo(M, H1Y + 2 * H1LH + H1S * .2); g.lineTo(M + uw, H1Y + 2 * H1LH + H1S * .2); g.stroke();
  g.font = SERIF(700, 230); g.fillStyle = P.gold; g.fillText(String(n), M - 8, 930);
  g.globalAlpha = 1;
  if (report) { g.font = SERIF(700, H1S); rep('h1', H1, M, H1Y - H1S * .85, M + Math.max(...H1L.map(s => g.measureText(s).width)), H1Y + 2 * H1LH + H1S * .28);}
}
function beat1(t) {
  if (t >= T.b1out + .6) return;
  const out = T.b1out;
  block({ id: 'h1', text: H1, lines: H1L, font: SERIF(700, H1S), size: H1S, lh: H1LH, x: M, y: H1Y, t0: -1, t1: out, t, st: 0, tout: .25 });
  g.font = SERIF(700, H1S); const uw = g.measureText(H1L[2]).width;
  line(M, H1Y + 2 * H1LH + H1S * .2, M + uw, H1Y + 2 * H1LH + H1S * .2, 1 - ei(seg(t, out, out + .25)), P.gold, 7);
  // tally counter 12 -> 800, gold
  const n = Math.round(lerp(12, 800, eio(seg(t, T.ctr, T.ctrEnd))));
  const q = ei(seg(t, out, out + .25));
  g.save(); g.beginPath(); g.rect(M - 20, 700, CW + 40, 280); g.clip(); g.translate(0, -q * 280);
  g.font = SERIF(700, 230); g.fillStyle = P.gold; g.fillText(String(n), M - 8, 930); g.restore();
  g.font = SERIF(700, 230);
  if (t < out && t < T.ctr) rep('ctr12', '12', M, 930 - 196, M + g.measureText('12').width, 930 + 20);
  if (t < out && t >= T.ctrEnd) rep('ctr800', '800', M, 930 - 196, M + g.measureText('800').width, 930 + 20);
}

// ---------- beat 2: sending inboxes 32 -> 64 ----------
const COLS = 8, CELL = 84, BOX = 66, GX = (W - COLS * CELL) / 2 + (CELL - BOX) / 2, GY = 470;
const STEPS = [[32, '', ' inboxes at launch'], [64, 'then ', '']];
function inbox(x, y, p, a, gold) {
  if (a <= 0 || p <= 0) return;
  const s = lerp(.5, 1, back(p, 1.6)), cx = x + BOX / 2, cy = y + BOX / 2;
  g.save(); g.globalAlpha = a * clamp(p * 2); g.translate(cx, cy); g.scale(s, s);
  rr(-BOX / 2, -BOX * .36, BOX, BOX * .72, 6, gold ? '#EADBB4' : P.panel, gold ? P.gold : P.ink + '88', 2);
  g.strokeStyle = gold ? P.goldTx : P.ink + 'AA'; g.lineWidth = 2; g.lineJoin = 'round'; g.beginPath();
  g.moveTo(-BOX / 2 + 3, -BOX * .33); g.lineTo(0, BOX * .04); g.lineTo(BOX / 2 - 3, -BOX * .33); g.stroke();
  g.restore();
}
function beat2(t) {
  if (t < T.b2 || t >= T.b2out + .7) return;
  const out = T.b2out, fo = 1 - ei(seg(t, out, out + .3));
  // the count: big number + small words, rolls on each step
  STEPS.forEach(([n, pre, post], i) => {
    const t0 = T.steps[i], t1 = i < STEPS.length - 1 ? T.steps[i + 1] : out;
    if (t < t0 || t >= t1 + .35) return;
    const pin = eo(seg(t, t0, t0 + .4)), pout = ei(seg(t, t1, t1 + .3)), y = 380;
    g.font = SERIF(400, 52, 'italic'); const pw = g.measureText(pre).width;
    g.font = SERIF(700, 170); const nw = g.measureText(String(n)).width;
    g.font = SERIF(400, 52, 'italic'); const qw = g.measureText(post).width;
    g.save(); g.beginPath(); g.rect(M - 10, y - 160, CW + 20, 200); g.clip(); g.translate(0, (1 - pin) * 200 - pout * 200);
    g.fillStyle = P.ink; g.font = SERIF(400, 52, 'italic'); g.fillText(pre, M, y);
    g.font = SERIF(700, 170); g.fillStyle = i === 1 ? P.goldTx : P.ink; g.fillText(String(n), M + pw, y);
    g.font = SERIF(400, 52, 'italic'); g.fillStyle = P.ink; g.fillText(post, M + pw + nw + 6, y);
    g.restore();
    if (t < t1) rep('n' + n, (pre + n + post).trim(), M, y - 140, M + pw + nw + 6 + qw, y + 20);
  });
  // the grid: 64 slots, faint outlines, inboxes pop in by batch
  const ga = eo(seg(t, T.b2, T.b2 + .4)) * fo;
  for (let k = 0; k < 64; k++) {
    const x = GX + (k % COLS) * CELL, y = GY + Math.floor(k / COLS) * CELL;
    if (ga > 0) { g.globalAlpha = ga * .35; g.setLineDash([4, 5]); rr(x, y + BOX * .14, BOX, BOX * .72, 6, null, P.ink + '66', 1.3); g.setLineDash([]); g.globalAlpha = 1; }
    const b = Math.floor(k / 32), j = k % 32, d = T.steps[b] + .15 + j * .018;
    const latest = b === (t >= T.steps[1] ? 1 : 0);
    inbox(x, y, seg(t, d, d + .35), fo, latest);
  }
}

// ---------- beat 3: the pipeline ----------
const ROWS = [
  'Find the right people',
  'Check each address before sending',
  'Send from many inboxes, every day',
  'AI sorts the replies: hot · interested · neutral · not interested',
  'Hot lead → the client\'s phone pings, and a person takes over',
  'Interested → an automatic reply, asking for a call',
  'Interested leads go into the CRM; booked calls land on the calendar'
];
const RF = SERIF(400, 40), RS = 40, RLH = 50, RGAP = 40, RX = M + 64, NX = M + 18, RY0 = 300;
const ARW = '     '; // five spaces hold the vector arrow (space, arrow cell, space)
const RL = [['Find the right people'], ['Check each address before sending'], ['Send from many inboxes, every day'],
  ['AI sorts the replies:', 'hot · interested · neutral · not interested'],
  ['Hot lead' + ARW + 'the client\'s phone pings,', 'and a person takes over'],
  ['Interested' + ARW + 'an automatic reply,', 'asking for a call'],
  ['Interested leads go into the CRM;', 'booked calls land on the calendar']];
const RYS = []; { let y = RY0; RL.forEach(ls => { RYS.push(y); y += ls.length * RLH + RGAP; }); }
function beat3(t) {
  if (t < T.b3 || t >= T.b3out + .7) return;
  const out = T.b3out, fo = 1 - ei(seg(t, out, out + .3));
  block({ id: 'kick3', text: 'the pipeline', font: MONO(600, 28), size: 28, lh: 34, x: M, y: 200, color: P.goldTx, t0: T.b3, t1: out, t });
  // grey trunk, then the gold line draws down to each lit node
  const top = RYS[0] - RS * .35, bot = RYS[6] - RS * .35;
  const ta = eo(seg(t, T.b3 + .2, T.b3 + .7)) * fo;
  if (ta > 0) { g.globalAlpha = ta * .3; line(NX, top, NX, bot, 1, P.ink, 2); g.globalAlpha = 1; }
  let goldTo = top;
  T.lights.forEach((tl, i) => { const y = RYS[i] - RS * .35; if (i > 0) goldTo = lerp(goldTo, y, eio(seg(t, tl - .45, tl))); });
  if (t >= T.lights[0] - .1 && fo > 0) { g.globalAlpha = fo; line(NX, top, NX, goldTo, 1, P.gold, 6); g.globalAlpha = 1; }
  RL.forEach((ls, i) => {
    const y = RYS[i], tl = T.lights[i], d = T.b3 + .25 + i * .1;
    const lit = eo(seg(t, tl, tl + .3));
    // node
    const na = eo(seg(t, d, d + .3)) * fo;
    if (na > 0) { g.globalAlpha = na; g.beginPath(); g.arc(NX, y - RS * .35, 11, 0, Math.PI * 2); g.fillStyle = lit > .5 ? P.gold : P.paper; g.fill(); g.strokeStyle = lit > .5 ? P.gold : P.dim; g.lineWidth = 2.5; g.stroke(); g.globalAlpha = 1; }
    const col = lit > .5 ? P.ink : P.dim;
    block({ id: 'row' + i, text: ROWS[i], lines: ls, font: RF, size: RS, lh: RLH, x: RX, y, color: col, t0: d, t1: out, t, st: .06 });
    const ai = ROWS[i].indexOf('→');
    if (ai >= 0) {
      g.font = RF; const pre = ROWS[i].slice(0, ai).trimEnd(), x0 = RX + g.measureText(pre + ' ').width + 1, x1 = RX + g.measureText(pre + '    ').width - 1;
      const aa = eo(seg(t, d + .3, d + .5)) * fo; if (aa > 0) { g.globalAlpha = aa; arrow(x0, x1, y - RS * .3, col); g.globalAlpha = 1; }
    }
  });
}

// ---------- beat 4: payoff ----------
const PAY = 'revenue up almost $128K in 4 months';
function beat4(t) {
  if (t < T.pay || t >= T.b4out + .6) return;
  const out = T.b4out;
  g.font = SERIF(700, 100); const BS = Math.min(280, 100 * CW * .9 / g.measureText('$128K').width);
  block({ id: 'pay0', text: 'revenue up almost', lines: ['revenue up almost'], font: SERIF(400, 70, 'italic'), size: 70, lh: 70, x: M, y: 430, color: P.goldTx, t0: T.pay, t1: out, t, report: false });
  block({ id: 'pay1', text: '$128K', lines: ['$128K'], font: SERIF(700, BS), size: BS, lh: BS, x: M - 6, y: 430 + BS * .9, color: P.gold, t0: T.pay + .1, t1: out, t, report: false });
  const y2 = 430 + BS * .9 + 130;
  block({ id: 'pay2', text: 'in 4 months', lines: ['in 4 months'], font: SERIF(700, 78), size: 78, lh: 80, x: M, y: y2, color: P.goldTx, t0: T.pay + .25, t1: out, t, report: false });
  g.font = SERIF(700, BS); const bw = g.measureText('$128K').width; g.font = SERIF(700, 78); const sw = g.measureText('in 4 months').width;
  line(M, y2 + 50, M + sw, y2 + 50, eio(seg(t, T.pay + .6, T.pay + 1.2)) * (1 - ei(seg(t, out, out + .25))), P.gold, 6);
  if (t < out) rep('pay', PAY, M - 6, 430 - 60, M + Math.max(bw, sw), y2 + 22);
}

// ---------- beat 5: the point ----------
function beat5(t) {
  if (t < T.l1 || t >= T.b5out + .7) return;
  const out = T.b5out;
  block({ id: 'p1', text: 'The machine does the volume.', lines: ['The machine', 'does the volume.'], font: SERIF(700, 104), size: 104, lh: 108, x: M, y: 330, t0: T.l1, t1: out, t });
  const l = block({ id: 'p2', text: 'Your people do the conversations.', lines: ['Your people do', 'the conversations.'], font: SERIF(700, 104), size: 104, lh: 108, x: M, y: 700, t0: T.l2, t1: out, t });
  g.font = SERIF(700, 104); const w = g.measureText(l[1]).width;
  line(M, 700 + 108 + 26, M + w, 700 + 108 + 26, eio(seg(t, T.l2 + .7, T.l2 + 1.4)) * (1 - ei(seg(t, out, out + .25))), P.gold, 7);
}

// ---------- beat 6: offer ----------
function beat6(t) {
  if (t < T.offer || t >= T.b6out + .6) return;
  const out = T.b6out;
  const ls = block({ id: 'offer', text: 'I build GTM pipelines like this, around your market and your offer.', lines: ['I build GTM pipelines like this,', 'around your market', 'and your offer.'], font: SERIF(400, 66), size: 66, lh: 80, x: M, y: 360, t0: T.offer, t1: out, t, tout: .22 });
  const uy = 360 + ls.length * 80 + 110;
  block({ id: 'url', text: 'prodcraft.fyi · my DMs are open', font: MONO(600, 40), size: 40, lh: 48, x: M, y: uy, color: P.goldTx, t0: T.url, t1: out, t, tout: .22 });
  g.font = MONO(600, 40); const w = g.measureText('prodcraft.fyi · my DMs are open').width;
  line(M, uy + 24, M + w, uy + 24, eio(seg(t, T.url + .4, T.url + 1.0)) * (1 - ei(seg(t, out, out + .22))), P.gold, 5);
}

function loopEnd(t) {
  if (t < T.loop) return;
  hookStatic(eo(seg(t, T.loop, T.loop + .3)), 12, false);
}
window.render = t => {
  TX = []; lastT = t;
  g.textBaseline = 'alphabetic'; g.textAlign = 'left'; g.globalAlpha = 1;
  g.fillStyle = P.paper; g.fillRect(0, 0, W, H);
  beat1(t); beat2(t); beat3(t); beat4(t); beat5(t); beat6(t); loopEnd(t);
  chrome(t);
};
window.TEXTS = t => { if (lastT !== t) window.render(t); return TX; };
window.READY = true;
