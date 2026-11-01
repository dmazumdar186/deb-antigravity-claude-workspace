// Trusted Segments v2 — Archive Light Table. One world, one camera, one loupe; Canvas 2D.
// Reads timeline.js (structure) and out/timeline.json (voice-locked times, written by tools/export.mjs).
// Every glyph goes through drawText(), which also logs it (window.__DRAWN) for tools/drawn_text.mjs.
import { clamp, lerp, seg, ss, eio, eo, mulberry, track } from '/core/lib.js';
import * as TLm from './timeline.js';

const W = 1920, H = 1080, cv = document.getElementById('c'), ctx = cv.getContext('2d');
const Q = new URLSearchParams(location.search);
const NOSUBS = Q.get('nosubs') === '1';
const TL = await (await fetch('out/timeline.json')).json();
const HT = TL.hit, WD = TL.words, CUES = TL.cues;
window.DUR = TL.dur;

// ---------- palette & type ----------
const SIG = '#FF5A1F', SIG2 = '#FF7A45', INK = '#15171A', PAPERW = '#F1F2F3', SUB = '#c4c8ce';
const PLATE_A = 0.94, PLATE = `rgba(14,15,17,${PLATE_A})`;
const F = { mono: (s, w = 400) => `${w} ${s}px PM`, sans: (s, w = 400) => `${w} ${s}px PS`, serif: s => `500 ${s}px PF`, serifI: s => `italic 400 ${s}px PF` };
const rgba = (r, g, b, a) => `rgba(${r | 0},${g | 0},${b | 0},${a})`;

// ---------- the one text path: draw + log ----------
let DRAWN = [];
function drawText(s, x, y, font, color, align = 'left') {
  if (!s) return;
  const a = ctx.globalAlpha; if (a < 0.02) return;
  ctx.font = font; ctx.fillStyle = color; ctx.textAlign = align;
  ctx.fillText(s, x, y);
  const m = ctx.getTransform(), k = Math.hypot(m.a, m.b), size = parseFloat(font.split(' ').find(p => p.endsWith('px')));
  DRAWN.push({ text: s, x: Math.round(m.a * x + m.c * y + m.e), y: Math.round(m.b * x + m.d * y + m.f), px: +(size * k).toFixed(1), a: +a.toFixed(2) });
  ctx.textAlign = 'left';
}

// ---------- the facts on screen (FACTS.md ids in comments) ----------
const F01 = TLm.F01;                                                                                  // F01
const SPELLINGS = ['Greater London', 'LONDON', 'London', 'London - Canary Wharf', 'London, UK', 'Londres', 'Londres (Royaume-Uni)', 'london']; // F04 (VERIFICATION §2)
const F24 = ['The administrator’s problem is not building the list.', 'It is believing it.'];         // F24
const REAL = { id: 'M0271', city: 'Londres (Royaume-Uni)' };                                          // F26 (annexB_result.csv)

// ---------- the table: 525 schematic record cards (F02); no card carries an ID except F26 ----------
const COLS = 25, ROWS = 21, PX = 200, PY = 128, CW = 180, CH = 110;
const TW = COLS * PX, TH = ROWS * PY;
const rnd = mulberry(20261012);
const shuffle = a => { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
const OTHER = ['Paris', 'Lyon', 'Lille', 'Bordeaux', 'Nantes', 'Toulouse', 'Geneva', 'Brussels', 'Montreal', 'New York', 'Singapore', 'Luxembourg', 'Milan', 'Madrid', '—', '—', '—', '—'];
const OV = [0, 0, 0.37, 0];
// screen rectangles that cover the table at the overview camera: reading plates (top corners) and captions (bottom)
const BLOCK = [[60, 30, 820, 360], [1100, 30, 1880, 360], [0, 860, 1920, 1080]];
const ovs = c => [W / 2 + c.x * OV[2], H / 2 + c.y * OV[2]];
const free = c => { const [x, y] = ovs(c); return !BLOCK.some(([a, b, cc, d]) => x > a - 50 && x < cc + 50 && y > b - 35 && y < d + 35); };
const cards = [];
let T1, T2;
{
  for (let i = 0; i < 525; i++) cards.push({ k: i, dup: i >= 500, city: '—' });
  const slots = shuffle([...Array(525).keys()]);
  cards.forEach((c, i) => {
    const s = slots[i], col = s % COLS, row = Math.floor(s / COLS);
    c.x = -TW / 2 + PX / 2 + col * PX + (rnd() - .5) * 16; c.y = -TH / 2 + PY / 2 + row * PY + (rnd() - .5) * 12;
    c.rot = (rnd() - .5) * 0.04; c.bars = [0.35 + rnd() * 0.25, 0.55 + rnd() * 0.3, 0.4 + rnd() * 0.35, 0.5 + rnd() * 0.4];
  });
  const swap = (a, b) => { for (const p of ['x', 'y', 'rot']) [a[p], b[p]] = [b[p], a[p]]; };
  const nearest = (list, x, y) => list.reduce((a, c) => (Math.hypot(c.x - x, c.y - y) < Math.hypot(a.x - x, a.y - y) ? c : a));
  // F26: the real record, placed where the loupe can land without covering a plate
  T1 = cards[270]; T1.id = REAL.id; T1.city = REAL.city; T1.real = true;
  swap(T1, nearest(cards.filter(c => c !== T1), 650, -250));
  // the duplicates lie where nothing covers them
  for (const c of cards.filter(c => c.dup && !free(c))) swap(c, cards.find(o => !o.dup && o !== T1 && free(o) && !o.taken) || c), c.taken = true;
  // the 49 (F09): T1 plus 48 free, non-duplicate cards; 2 ⊂ 26 ⊂ 49 (F07, F08) never include T1
  const pool = shuffle(cards.filter(c => !c.dup && c !== T1 && free(c)));
  const s48 = pool.slice(0, 48);
  s48.forEach((c, i) => { c.in49 = true; c.o49 = i; if (i < 26) c.in26 = true; if (i < 2) c.in2 = true; });
  T1.in49 = true; T1.o49 = 48;
  // schematic cities: the 49 carry London spellings (all eight appear; the naive 2 carry the exact "London")
  s48.forEach((c, i) => { c.city = c.in2 ? 'London' : SPELLINGS[i % 8]; });
  const others = shuffle(cards.filter(c => !c.dup && !c.in49));
  others.forEach((c, i) => { c.city = i < 24 ? SPELLINGS[i % 8] : OTHER[Math.floor(rnd() * OTHER.length)]; });
  cards.filter(c => c.dup).forEach(c => { c.city = others[Math.floor(rnd() * others.length)].city; });
  // F11: 1 current, 5 to confirm, 43 to reactivate (M0271 is "to reactivate" in the result file)
  T1.status = 'reactivate';
  shuffle([...s48]).forEach((c, i) => { c.status = i === 0 ? 'current' : i < 6 ? 'confirm' : 'reactivate'; });
  // F13: 68 % of the 500 untouched for 2+ years = 340 cards; the 43 to reactivate are among them
  cards.filter(c => c.status === 'reactivate').forEach(c => c.stale = true);
  shuffle(cards.filter(c => !c.dup && !c.in49)).slice(0, 340 - 43).forEach(c => c.stale = true);
  cards.filter(c => c.dup).forEach(c => c.stale = rnd() < 0.68);
  // the example card for the dates (not a member record: no ID, schematic fields)
  T2 = nearest(cards.filter(c => c.status === 'reactivate' && c !== T1), -450, 300); T2.example = true;
}
const S49 = cards.filter(c => c.in49);
const NOTE = { x: -700, y: 260, rot: -0.022, w: 1180, h: 440 };
const STRIP = { x: 0, y: -TH / 2 - 80 - 60 - 280, w: 2000 };

// ---------- camera ----------
const camFor = (c, sx, sy, z) => [c.x + (W / 2 - sx) / z, c.y + (H / 2 - sy) / z, z, 0];
const L1 = [1300, 590], L2 = [840, 580];                         // loupe screen positions
const C1a = camFor(T1, ...L1, 0.95), C1b = camFor(T1, ...L1, 0.99);
const C2a = camFor(T2, ...L2, 0.95), C2b = camFor(T2, ...L2, 0.98);
const ENDC = [0, STRIP.y + (540 - 300) / 0.85, 0.85, 0];
const CAM = track([
  [0, [0, STRIP.y, 0.9, 0.012]], [HT.pullStart, [0, STRIP.y, 0.935, 0.008]],
  [HT.pullEnd, OV], [HT.drop1, C1a], [HT.lift1, C1b],
  [HT.lift1 + 1.3, OV], [HT.drop2 - 1.1, [0, 0, 0.395, 0]], [HT.drop2, C2a], [HT.lift2, C2b],
  [HT.lift2 + 1.9, [0, 0, 0.372, 0]], [HT.quote, [0, 0, 0.388, 0.006]],
  [HT.quote + 1.5, [NOTE.x - 60, NOTE.y + 10, 1.0, 0]], [HT.index - 0.3, [NOTE.x + 60, NOTE.y + 10, 1.05, 0]],
  [HT.index + 1.1, OV], [HT.glideUp, [0, 0, 0.385, 0]], [HT.glideUp + 2.0, ENDC], [HT.endCard + 0.5, [0, ENDC[1], 0.89, 0]], [TL.dur, [0, ENDC[1], 0.9, 0]],
]);
let cam;
const w2s = (x, y, c = cam) => { const dx = x - c[0], dy = y - c[1], co = Math.cos(c[3]), si = Math.sin(c[3]); return [W / 2 + (dx * co - dy * si) * c[2], H / 2 + (dx * si + dy * co) * c[2]]; };
const applyCam = (c, sx = W / 2, sy = H / 2, cx = c[0], cy = c[1], z = c[2]) => { ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.translate(sx, sy); ctx.rotate(c[3]); ctx.scale(z, z); ctx.translate(-cx, -cy); };

// ---------- light ----------
function lightLevel(t) {
  if (t < HT.lightOn) return 0.035;
  const on = t - HT.lightOn;
  let L = on < 0.12 ? 0.7 : on < 0.2 ? 0.08 : on < 0.4 ? 0.85 : on < 0.48 ? 0.25 : Math.min(1, 0.9 + (on - 0.48) * 0.5);
  if (t > HT.off) { const o = t - HT.off; L = o < 0.06 ? 0.5 : o < 0.12 ? 0.75 : Math.max(0.035, 0.3 * (1 - o / 0.25)); }
  return L;
}
const FRONT_DUR = 3.4;
const frontR = t => t < HT.front ? -1 : eio(seg(t, HT.front, HT.front + FRONT_DUR)) * 6200;
const darkOf = (c, t) => { if (!c.stale) return 0; const r = frontR(t); if (r < 0) return 0; return ss((r - Math.hypot(c.x - T2.x, c.y - T2.y)) / 160); };

// ---------- level of detail: glyphs only when ≥ ~24 px on screen, bars otherwise ----------
const MW = new Map();
function mw(s, font) { const k = font + '|' + s; let v = MW.get(k); if (v === undefined) { ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.font = font; v = ctx.measureText(s).width; ctx.restore(); MW.set(k, v); } return v; }
function lodText(s, x, y, size, font, col, a, scale, maxW) {
  const px = size * scale, g = ss((px - 22) / 7);
  let fs = size; const w0 = mw(s, font(size)); if (maxW && w0 > maxW) fs = size * maxW / w0;
  const w = Math.min(w0, maxW || 1e9);
  const ga = ctx.globalAlpha;
  if (g < 1) { ctx.globalAlpha = ga * a * (1 - g) * 0.32; ctx.fillStyle = col; ctx.fillRect(x, y - fs * 0.62, w, fs * 0.55); }
  if (g > 0) { ctx.globalAlpha = ga * a * g; drawText(s, x, y, font(fs), col); }
  ctx.globalAlpha = ga;
}

// ---------- one record card (local coords, centre origin) ----------
function drawCard(c, t, scale, opt = {}) {
  const L = opt.light ?? lightLevel(t), d = opt.dark ?? darkOf(c, t), glow = opt.glow || 0;
  const lit = Math.max(L, glow);
  const dk = lerp(0.3, 1, clamp(L * 1.2));
  const pr = lerp(lerp(40, 244, lit), 86 * dk, d), pg = lerp(lerp(40, 239, lit), 84 * dk, d), pb = lerp(lerp(42, 227, lit), 80 * dk, d);
  ctx.fillStyle = rgba(pr, pg, pb, 1); ctx.fillRect(-CW / 2, -CH / 2, CW, CH);
  ctx.lineWidth = 1.2 / scale; ctx.strokeStyle = rgba(255, 248, 232, 0.55 * lit * (1 - d)); ctx.strokeRect(-CW / 2 + 1 / scale, -CH / 2 + 1 / scale, CW - 2 / scale, CH - 2 / scale);
  ctx.strokeStyle = rgba(0, 0, 0, 0.16); ctx.strokeRect(-CW / 2, -CH / 2, CW, CH);
  const ink = d > 0.5 ? '#c9c4ba' : INK, ia = lerp(0.88, 0.5, d) * clamp(lit * 1.4, 0.15, 1);
  const barA = clamp(lit * 1.5, .2, 1);
  // ID slot: only the real record (F26) shows its ID; the dates card says it is an example; all others are blank bars
  if (c.real) lodText(c.id, -80, -32, 19, s => F.mono(s, 500), ink, ia * (opt.idA ?? 1), scale);
  else if (c.example) lodText('example', -80, -32, 17, s => F.mono(s, 500), ink, ia * (opt.idA ?? 1), scale);
  else { ctx.fillStyle = rgba(30, 32, 36, 0.3 * barA); ctx.fillRect(-80, -45, 62, 14); }
  ctx.fillStyle = rgba(36, 38, 42, 0.9 * barA); ctx.fillRect(4, -45, 76 * c.bars[0] + 20, 15);
  lodText(c.city, -80, -6, 17, s => F.sans(s, 500), ink, ia * (opt.cityA ?? 1), scale, 160);
  if (c.example) {
    lodText('in post: 3 yrs', -80, 20, 15, s => F.mono(s, 400), ink, ia * (opt.dateA ?? 1), scale);
    lodText('updated: 3 yrs ago', -80, 42, 15, s => F.mono(s, 400), ink, ia * (opt.dateA ?? 1), scale);
  } else {
    ctx.fillStyle = rgba(36, 38, 42, 0.85 * barA);
    ctx.fillRect(-80, 8, 150 * c.bars[1], 11); ctx.fillRect(-80, 27, 150 * c.bars[2], 11);
    ctx.fillStyle = rgba(30, 32, 36, 0.28 * barA); ctx.fillRect(-80, 44, 46, 7); ctx.fillRect(-20, 44, 46, 7);
  }
  if (opt.underline) { ctx.strokeStyle = SIG; ctx.lineWidth = 2.6 / scale; ctx.beginPath(); const [y, a, w] = opt.underline; ctx.moveTo(-80, y); ctx.lineTo(-80 + w * a, y); ctx.stroke(); }
}

// ---------- the world ----------
function drawWorld(t, scale, lens = null) {
  const L = lightLevel(t);
  ctx.fillStyle = '#0e0f11'; ctx.fillRect(-TW * 2, -TH * 3, TW * 4, TH * 6);
  const fr = 64;
  const g = ctx.createLinearGradient(0, -TH / 2 - fr, 0, TH / 2 + fr);
  g.addColorStop(0, '#9da3a9'); g.addColorStop(0.5, '#7f858b'); g.addColorStop(1, '#a8aeb4');
  ctx.fillStyle = g; ctx.globalAlpha = lerp(0.03, 1, clamp(L * 1.1)); ctx.fillRect(-TW / 2 - fr, -TH / 2 - fr, TW + 2 * fr, TH + 2 * fr);
  ctx.globalAlpha = 1; ctx.fillStyle = '#5b6066'; ctx.fillRect(-TW / 2 - 6, -TH / 2 - 6, TW + 12, TH + 12);
  const s = ctx.createRadialGradient(0, 0, 200, 0, 0, TW * 0.62);
  const top = lerp(26, 247, L), edge = lerp(22, 226, L);
  s.addColorStop(0, rgba(top, top + 2 * L, top + 4 * L, 1)); s.addColorStop(1, rgba(edge, edge + 2 * L, edge + 5 * L, 1));
  ctx.fillStyle = s; ctx.fillRect(-TW / 2, -TH / 2, TW, TH);
  const flying = t >= HT.index - 0.01;
  for (const c of cards) {
    if (flying && c.in49 && flightK(c, t) > 0) continue;
    if (lens) { if (Math.hypot(c.x - lens[0], c.y - lens[1]) > lens[2] + 120) continue; }
    else { const [sx, sy] = w2s(c.x, c.y); if (sx < -150 || sx > W + 150 || sy < -150 || sy > H + 150) continue; }
    ctx.save(); ctx.translate(c.x, c.y); ctx.rotate(c.rot);
    const o = {};
    if (c === T1 && t > HT.cityLit - 0.05 && t < HT.lift1 + 1) { const a = eo(seg(t, HT.cityLit, HT.cityLit + 0.45)); o.idA = lerp(1, 0.6, a); o.cityA = 1; o.underline = [2, a, Math.min(160, mw(c.city, F.sans(17, 500)))]; }
    if (c === T2 && t > HT.dateLit - 0.05 && t < HT.lift2 + 2) { const a = eo(seg(t, HT.dateLit, HT.dateLit + 0.45)); o.idA = lerp(1, 0.45, a); o.cityA = lerp(1, 0.45, a); o.dateA = 1; o.underline = [48, a, mw('updated: 3 yrs ago', F.mono(15, 400))]; }
    drawCard(c, t, scale, o);
    ctx.restore();
  }
  marks(t, scale);
  drawStrip(t, scale);
  if (t > HT.quote + 0.2 && t < HT.index) drawNote(t, scale);
}

function ring(x, y, r, a, scale, w = 3) { ctx.globalAlpha = a; ctx.strokeStyle = SIG; ctx.lineWidth = w / scale; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.stroke(); ctx.globalAlpha = 1; }
function outline(c, a, scale, w = 3) {
  ctx.save(); ctx.translate(c.x, c.y); ctx.rotate(c.rot); ctx.globalAlpha = a; ctx.strokeStyle = SIG; ctx.lineWidth = w / scale;
  const p = 6 / scale + 4; ctx.fillStyle = 'rgba(255,90,31,0.14)'; ctx.fillRect(-CW / 2, -CH / 2, CW, CH); ctx.strokeRect(-CW / 2 - p, -CH / 2 - p, CW + 2 * p, CH + 2 * p); ctx.restore(); ctx.globalAlpha = 1;
}
// one threshold for the label AND the value of each step (finding 1): the step changes on the narrator's number
const STEPS = () => [
  { t: -1, label: 'Naive filter · file as delivered', value: '—', source: 'rows matching the sentence', lit: 0 },
  { t: WD.n2 - 0.05, label: 'Naive filter · file as delivered', value: '2', source: 'rows matching the sentence', lit: 2 },
  { t: WD.n26 - 0.05, label: 'Normalised · spellings and labels', value: '26', source: 'rows matching the sentence', lit: 26 },
  { t: WD.n49 - 0.05, label: 'Full logic · dedup + employer + job title', value: '49', source: 'members matching the sentence', lit: 49 },
];
const stepAt = t => STEPS().filter(s => t >= s.t).at(-1);
function marks(t, scale) {
  if (t > WD.dup25 - 0.1 && t < HT.hush1 + 0.6) {
    const fade = 1 - seg(t, HT.hush1, HT.hush1 + 0.6);
    cards.filter(c => c.dup).forEach((c, i) => { const t0 = WD.dup25 + i * TLm.DUP_DT, a = eo(seg(t, t0, t0 + 0.25)); if (a > 0) ring(c.x, c.y, lerp(150, 112, a), a * fade, scale, 3); });
  }
  if (t > WD.n2 - 0.6 && t < HT.index + 0.2) {
    const st = stepAt(t), prev = STEPS()[STEPS().indexOf(st) - 1];
    const grow = prev ? Math.round(lerp(prev.lit, st.lit, eo(seg(t, st.t, st.t + 0.5)))) : st.lit;
    const fadeTo = t > HT.front ? lerp(1, 0.55, seg(t, HT.front, HT.front + 1)) : 1;
    for (const c of S49) if (c.o49 < grow) outline(c, fadeTo, scale, 3);
  }
  const r = frontR(t);
  if (r > 0 && r < 6100) { ctx.globalAlpha = 0.5 * (1 - seg(r, 4800, 6100)); ctx.strokeStyle = '#FF8A4C'; ctx.lineWidth = 3 / scale; ctx.beginPath(); ctx.arc(T2.x, T2.y, r, 0, Math.PI * 2); ctx.stroke(); ctx.globalAlpha = 1; }
}

// ---------- query strip ----------
const SLOT_X = [-495, -165, 165, 495], SLOT_LAB = ['as delivered', 'normalised', 'full logic', 'worth contacting'], SLOT_VAL = ['2', '26', '49', '6'];
const slotFill = i => HT.glideUp + 1.6 + i * 0.3;
function drawStrip(t, scale) {
  const S = STRIP; ctx.save(); ctx.translate(S.x, S.y);
  ctx.fillStyle = 'rgba(22,24,27,0.96)'; rr(-S.w / 2, -290, S.w, 490, 18); ctx.fill();
  ctx.lineWidth = 1.5 / scale; ctx.strokeStyle = 'rgba(255,255,255,0.16)'; ctx.stroke();
  ctx.strokeStyle = 'rgba(255,255,255,0.28)'; ctx.lineWidth = 2 / scale; rr(-930, -250, 1860, 150, 12); ctx.stroke();
  // the query fades out completely before the title wipes in (no ghost)
  const qA = 1 - seg(t, HT.title - 0.45, HT.title - 0.1);
  if (qA > 0) {
    ctx.globalAlpha = qA; ctx.strokeStyle = '#d9dbde'; ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(-880, -182, 15, 0, Math.PI * 2); ctx.moveTo(-869, -171); ctx.lineTo(-855, -157); ctx.stroke();
    const n = Math.max(0, Math.min(F01.length, Math.floor((t - HT.typeOn) / TLm.TYPE_DT)));
    drawText(F01.slice(0, n), -830, -162, F.mono(42, 400), PAPERW);
    const typing = n < F01.length, cx = -830 + mw(F01.slice(0, n), F.mono(42, 400)) + 4;
    if (typing || Math.floor(t / 0.5) % 2 === 0) { ctx.fillStyle = SIG; ctx.fillRect(cx, -200, 3, 48); }
    ctx.globalAlpha = 1;
  }
  if (t > HT.title) { const a = eo(seg(t, HT.title, HT.title + 0.6)); ctx.save(); ctx.beginPath(); ctx.rect(-930, -260, 1860 * a, 170); ctx.clip(); drawText('Trusted Segments', 0, -148, F.serif(84), PAPERW, 'center'); ctx.restore(); } // F23
  SLOT_X.forEach((x, i) => {
    const a = eo(seg(t, HT.slots + i * 0.12, HT.slots + i * 0.12 + 0.35));
    if (a <= 0) return;
    ctx.globalAlpha = a; ctx.strokeStyle = 'rgba(255,255,255,0.3)'; ctx.lineWidth = 2 / scale; rr(x - 150, -40, 300, 124, 10); ctx.stroke();
    const f = eo(seg(t, slotFill(i), slotFill(i) + 0.3));
    if (f < 1) { ctx.globalAlpha = a * (1 - f) * 0.55; drawText('?', x, 47, F.mono(72, 400), '#c8cbd0', 'center'); }
    if (f > 0) { ctx.globalAlpha = f; drawText(SLOT_VAL[i], x, 49, F.mono(76, 500), i === 3 ? SIG2 : PAPERW, 'center'); drawText(SLOT_LAB[i], x, 146, F.sans(37, 400), '#c4c8ce', 'center'); }
    ctx.globalAlpha = 1;
  });
  ctx.restore();
}
function rr(x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }

// ---------- quoted note (F17): ink fades first, then the paper, both before the table dims (finding 8) ----------
const NOTE_L = ['“340 London expats.', 'Twenty had moved back years ago.', 'Two unsubscribed.”'];
function drawNote(t, scale) {
  const pa = eo(seg(t, HT.quote + 0.45, HT.quote + 0.8)) * (1 - seg(t, HT.index - 0.2, HT.index - 0.05));
  const ia = eo(seg(t, HT.quote + 0.62, HT.quote + 0.87)) * (1 - seg(t, HT.index - 0.35, HT.index - 0.2)), aa = ia * eo(seg(t, HT.quote + 1.3, HT.quote + 1.5));
  if (pa <= 0) return;
  ctx.save(); ctx.translate(NOTE.x, NOTE.y + (1 - Math.min(1, pa * 1.2)) * 40); ctx.rotate(NOTE.rot); ctx.globalAlpha = pa;
  ctx.shadowColor = 'rgba(0,0,0,0.25)'; ctx.shadowBlur = 30 * scale; ctx.shadowOffsetY = 8 * scale;
  ctx.fillStyle = '#f6f1e6'; ctx.fillRect(-NOTE.w / 2, -NOTE.h / 2, NOTE.w, NOTE.h);
  ctx.shadowColor = 'transparent';
  ctx.fillStyle = SIG; ctx.fillRect(-NOTE.w / 2, -NOTE.h / 2, 6, NOTE.h);
  ctx.globalAlpha = pa * ia;
  NOTE_L.forEach((s, i) => drawText(s, -NOTE.w / 2 + 70, -NOTE.h / 2 + 110 + i * 82, F.serifI(56), INK));
  ctx.globalAlpha = pa * aa; drawText('user verbatim', -NOTE.w / 2 + 70, NOTE.h / 2 - 50, F.mono(32, 400), '#5d6168');
  ctx.restore(); ctx.globalAlpha = 1;
}

// ---------- the loupe ----------
const LR = 240, MAG = 2.5;
function loupeState(t) {
  for (const [d, l, c, p] of [[HT.drop1, HT.lift1, T1, L1], [HT.drop2, HT.lift2, T2, L2]]) {
    if (t >= d - 0.4 && t < l + 0.4) return { c, k: t < d ? eo(seg(t, d - 0.4, d)) : 1 - eo(seg(t, l, l + 0.4)) };
  }
  return null;
}
function drawLoupe(t) {
  const st = loupeState(t); if (!st) return;
  const { c, k } = st; const [sx, sy] = w2s(c.x, c.y);
  const s = lerp(1.35, 1, k), R = LR * s, a = k;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.save(); ctx.globalAlpha = 0.45 * a; ctx.shadowColor = 'rgba(0,0,0,0.6)'; ctx.shadowBlur = lerp(60, 26, k); ctx.shadowOffsetX = lerp(30, 10, k); ctx.shadowOffsetY = lerp(40, 14, k);
  ctx.fillStyle = '#000'; ctx.beginPath(); ctx.arc(sx, sy, R + 46, 0, Math.PI * 2); ctx.fill(); ctx.restore();
  ctx.save(); ctx.globalAlpha = a; ctx.beginPath(); ctx.arc(sx, sy, R, 0, Math.PI * 2); ctx.clip();
  const z = cam[2] * MAG; applyCam(cam, sx, sy, c.x, c.y, z); drawWorld(t, z, [c.x, c.y, R / z]);
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const v = ctx.createRadialGradient(sx, sy, R * 0.7, sx, sy, R); v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,0.22)');
  ctx.fillStyle = v; ctx.fillRect(sx - R, sy - R, 2 * R, 2 * R);
  const hl = ctx.createLinearGradient(sx - R, sy - R, sx + R * 0.2, sy + R * 0.2); hl.addColorStop(0, 'rgba(255,255,255,0.16)'); hl.addColorStop(0.5, 'rgba(255,255,255,0)');
  ctx.fillStyle = hl; ctx.fillRect(sx - R, sy - R, 2 * R, 2 * R);
  ctx.restore();
  ctx.save(); ctx.globalAlpha = a;
  ctx.beginPath(); ctx.arc(sx, sy, R + 48, 0, Math.PI * 2); ctx.arc(sx, sy, R + 22, 0, Math.PI * 2, true);
  const sk = ctx.createRadialGradient(sx, sy, R + 22, sx, sy, R + 48); sk.addColorStop(0, 'rgba(235,240,245,0.25)'); sk.addColorStop(0.85, 'rgba(255,255,255,0.55)'); sk.addColorStop(1, 'rgba(255,255,255,0.2)');
  ctx.fillStyle = sk; ctx.fill();
  ctx.beginPath(); ctx.arc(sx, sy, R + 22, 0, Math.PI * 2); ctx.arc(sx, sy, R, 0, Math.PI * 2, true); ctx.fillStyle = '#0b0b0c'; ctx.fill();
  const bv = ctx.createLinearGradient(sx - R, sy - R, sx + R, sy + R); bv.addColorStop(0, 'rgba(255,255,255,0.55)'); bv.addColorStop(0.45, 'rgba(255,255,255,0.0)'); bv.addColorStop(1, 'rgba(255,255,255,0.18)');
  ctx.strokeStyle = bv; ctx.lineWidth = 2.5; ctx.beginPath(); ctx.arc(sx, sy, R + 18, 0, Math.PI * 2); ctx.stroke();
  ctx.restore();
}

// ---------- screen-space plates ----------
function plate(x, y, w, h, a) { ctx.globalAlpha = a; ctx.fillStyle = PLATE; rr(x, y, w, h, 8); ctx.fill(); ctx.globalAlpha = 1; }
function reading(x, y, w, a, label, value, source, opt = {}) {
  if (a <= 0) return;
  const h = opt.h || 250; plate(x, y, w, h, a);
  ctx.globalAlpha = a; drawText(label, x + 32, y + 52, F.sans(30, 500), 'rgba(241,242,243,0.95)');
  drawText(value, x + 28, y + 52 + 106, opt.vfont || F.mono(104, 500), SIG2);
  if (source) drawText(source, x + 32, y + h - 30, F.mono(28, 400), SUB);
  ctx.globalAlpha = 1;
}
const fadeWin = (t, a, b, fi = 0.35, fo = 0.35) => Math.min(eo(seg(t, a, a + fi)), 1 - seg(t, b - fo, b));

// ---------- index (F11, F21 status words, F25 actions) ----------
const COLX = [[150, 420, 'Current', '→ send'], [620, 500, 'To confirm', '→ confirm'], [1170, 600, 'To reactivate', '→ reactivate']];
const colOf = c => c.status === 'current' ? 0 : c.status === 'confirm' ? 1 : 2;
const inCol = {}; ['current', 'confirm', 'reactivate'].forEach(s => S49.filter(c => c.status === s).forEach((c, i) => inCol[cards.indexOf(c)] = i));
const ci = c => inCol[cards.indexOf(c)];
function colTarget(c) {
  const k = colOf(c), i = ci(c);
  if (k === 0) return [360, 560, 1.15];
  if (k === 1) return [800 + (i % 2) * 150, 440 + Math.floor(i / 2) * 115, 0.72];
  return [1206 + (i % 7) * 76 + 34, 400 + Math.floor(i / 7) * 58 + 21, 0.37];
}
const live = c => c.status !== 'reactivate';
const heroIdx = c => live(c) ? (c.status === 'current' ? 0 : 1 + ci(c)) : -1;
function heroTarget(c) { const i = heroIdx(c); return [960 + (i - 2.5) * 150, 820, 0.6]; }
const flightStart = c => HT.index + 0.35 + (colOf(c) === 0 ? 0 : colOf(c) === 1 ? 0.25 + ci(c) * 0.1 : 0.6 + ci(c) * 0.022);
const flightK = (c, t) => eio(seg(t, flightStart(c), flightStart(c) + 0.95));
const zoomIdx = t => 1 + 0.03 * seg(t, HT.index + 1, HT.six + 2.9);       // a slow push on the index (no freeze)
function drawIndex(t) {
  if (t < HT.index || t > HT.glideUp + 1.2) return;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const veil = eo(seg(t, HT.index, HT.index + 1.0)) * 0.6 + eo(seg(t, HT.six - 0.1, HT.six + 0.4)) * 0.3;
  ctx.fillStyle = `rgba(14,15,17,${Math.min(0.9, veil)})`; ctx.fillRect(0, 0, W, H);
  const zi = zoomIdx(t), Z = (x, y) => [W / 2 + (x - W / 2) * zi, H / 2 + (y - H / 2) * zi];
  const pa = fadeWin(t, HT.index + 0.45, HT.six + 0.25, 0.5, 0.4);
  const words = [WD.c1, WD.c5, WD.c43], nums = [1, 5, 43];
  COLX.forEach(([x, w], k) => { const [px, py] = Z(x, 120); plate(px, py, w * zi, 680 * zi, pa * 0.94); });
  // flying cards (below the headers)
  const heroT = HT.six - 0.15;
  for (const c of S49) {
    const k = flightK(c, t); if (k <= 0) continue;
    const [wx, wy] = w2s(c.x, c.y), [tx0, ty0, ts] = colTarget(c), [tx, ty] = Z(tx0, ty0);
    const lift = Math.sin(Math.PI * k) * 60;
    let x = lerp(wx, tx, k), y = lerp(wy, ty, k) - lift, s = lerp(cam[2], ts * zi, k), r = lerp(c.rot + cam[3], 0, k);
    let a = 1;
    if (live(c)) {           // the six fly again, into the hero row
      const h = eio(seg(t, heroT, heroT + 0.6)); const [hx, hy, hs] = heroTarget(c);
      x = lerp(x, hx, h); y = lerp(y, hy, h); s = lerp(s, hs, h);
      a = 1 - seg(t, HT.glideUp, HT.glideUp + 0.7);
    } else a = 1 - seg(t, HT.six - 0.1, HT.six + 0.4) * 0.85 - seg(t, HT.off, HT.off + 0.4) * 0.15;
    if (a <= 0) continue;
    ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = a; ctx.translate(x, y); ctx.rotate(r); ctx.scale(s, s);
    if (live(c) && t > HT.off) { ctx.shadowColor = 'rgba(255,236,200,0.9)'; ctx.shadowBlur = 40; }
    drawCard(c, t, s, { light: live(c) ? 1 : Math.max(lightLevel(t), 0.3), dark: live(c) ? 0 : 1, glow: live(c) ? 1 : 0 });
    ctx.shadowColor = 'transparent'; ctx.shadowBlur = 0; ctx.globalAlpha = 1;
  }
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  // headers, actions and counts above the cards (finding 10)
  COLX.forEach(([x, w, lab, act], k) => {
    const [px, py] = Z(x, 120);
    ctx.globalAlpha = pa; drawText(lab, px + 30, py + 58, F.sans(36, 500), PAPERW);
    drawText(act, px + 30 + mw(lab, F.sans(36, 500)) + 18, py + 58, F.sans(30, 400), SUB);
    const na = eo(seg(t, words[k] - 0.1, words[k] + 0.25));
    if (na > 0) { ctx.globalAlpha = pa * na; drawText(String(nums[k]), px + 26, py + 170 - (1 - na) * 14, F.mono(96, 500), SIG2); }
    ctx.globalAlpha = 1;
  });
  // the payoff (F12): the largest element, centred, held ≥ 2.5 s
  const ha = Math.min(eo(seg(t, HT.six + 0.3, HT.six + 0.7)), 1 - seg(t, HT.glideUp, HT.glideUp + 0.5));
  if (ha > 0) {
    const sc = 1 + 0.04 * seg(t, HT.six, HT.off);
    ctx.save(); ctx.translate(W / 2, 470); ctx.scale(sc, sc); ctx.globalAlpha = ha;
    drawText('6', 0, 0, F.mono(330, 500), SIG2, 'center');
    drawText('worth contacting today:', 0, 120, F.sans(56, 500), PAPERW, 'center');
    drawText('1 to send, 5 to confirm.', 0, 192, F.sans(48, 400), '#d9dce0', 'center');
    ctx.restore(); ctx.globalAlpha = 1;
  }
}

// ---------- the two records, one plate (F22) ----------
function drawPair(t) {
  const a = fadeWin(t, HT.pair, HT.quote + 0.25, 0.4, 0.35); if (a <= 0) return;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const b2 = fadeWin(t, HT.pair + 0.5, HT.quote + 0.25, 0.4, 0.35);
  plate(130, 320, 1660, 250, a);
  ctx.globalAlpha = a; drawText('read as tenure', 170, 378, F.sans(30, 500), SUB); drawText('“Three years in post”', 170, 466, F.sans(46, 500), PAPERW);
  ctx.globalAlpha = b2; drawText('read as freshness', 1030, 378, F.sans(30, 500), SUB); drawText('“Three years without an update”', 1030, 466, F.sans(46, 500), PAPERW);
  const e = eo(seg(t, WD.sameSig - 0.15, WD.sameSig + 0.35));
  if (e > 0) {
    ctx.strokeStyle = SIG2; ctx.lineWidth = 9; ctx.lineCap = 'round'; ctx.globalAlpha = a; ctx.beginPath();
    ctx.moveTo(934, 428); ctx.lineTo(934 + 52 * clamp(e * 2), 426); if (e > 0.5) { ctx.moveTo(934, 462); ctx.lineTo(934 + 52 * clamp(e * 2 - 1), 460); } ctx.stroke(); ctx.lineCap = 'butt';
  }
  ctx.globalAlpha = 1;
}

// ---------- captions: two-line strip, bottom centre, 3 px signal edge ----------
function drawSubs(t) {
  if (NOSUBS) return;
  const c = CUES.find(c => t >= c.t0 && t < c.t1 && c.burn); if (!c) return;
  const a = Math.min(seg(t, c.t0, c.t0 + 0.1), 1 - seg(t, c.t1 - 0.1, c.t1));
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const font = F.sans(40, 500); ctx.font = font;
  const w = Math.max(...c.lines.map(l => ctx.measureText(l).width)) + 64, h = 30 + c.lines.length * 52, x = (W - w) / 2, y = H - 56 - h;
  ctx.globalAlpha = a; ctx.fillStyle = 'rgba(14,15,17,0.86)'; ctx.fillRect(x, y, w, h); ctx.fillStyle = SIG; ctx.fillRect(x, y, w, 3);
  c.lines.forEach((l, i) => drawText(l, W / 2, y + 56 + i * 52, font, PAPERW, 'center')); ctx.globalAlpha = 1;
}

// ---------- what is on screen when (also feeds readcheck) ----------
const TAG = 'Schematic · no member data';
function screenTexts(t) {
  const T = [];
  const put = (id, text, x0, y0, x1, y1, a) => { if (a > 0.02) T.push({ id, text, x0, y0, x1, y1, a }); };
  put('rec', 'for 500 members', 100, 70, 650, 320, fadeWin(t, L03T, HT.drop1 - 0.2, 0.35, 0.3));
  // the tag is up whenever cards are on the lit table (finding 4)
  put('tag', TAG, 1440, 968, 1824, 1024, fadeWin(t, HT.lightOn + 0.4, HT.off + 0.3, 0.35, 0.35));
  put('spell', 'London, as typed in the file', 100, 150, 790, 770, fadeWin(t, HT.spell, HT.spellEnd, 0.4, 0.3));
  const st = stepAt(t);
  const ca = fadeWin(t, HT.climb, WD.n49 + 4.1, 0.4, 0.35);
  put('climbL', st.label, 1130, 70, 1840, 320, ca);
  if (st.value !== '—') put('climbV', st.value, 1130, 70, 1840, 320, ca);
  put('stale', 'Profiles untouched for 2+ years', 100, 70, 780, 320, fadeWin(t, Math.max(WD.n68 - 0.3, HT.lift2 + 0.4), HT.pair + 0.6));
  return T;
}
const productT = () => HT.thesis;
const L03T = TL.voice.find(v => v.id === 'L03').t;
window.TEXTS = t => {
  const out = screenTexts(t).map(({ id, text, x0, y0, x1, y1 }) => ({ id, text, x0, y0, x1, y1 }));
  if (t >= HT.typeOn && t < HT.title - 0.1) out.push({ id: 'query', text: F01, ...box(-930, -260, 930, -100, t) });
  if (t >= HT.title && t < HT.endCard) out.push({ id: 'title', text: 'Trusted Segments', ...box(-930, -260, 930, -100, t) });
  for (let i = 0; i < 4; i++) if (t > slotFill(i) && t < HT.endCard) out.push({ id: 'slot' + i, text: SLOT_VAL[i] + ' ' + SLOT_LAB[i], ...box(SLOT_X[i] - 150, -40, SLOT_X[i] + 150, 150, t) });
  if (t > HT.pair && t < HT.quote + 0.25) out.push({ id: 'pairA', text: 'Three years in post', x0: 130, y0: 320, x1: 920, y1: 570 });
  if (t > HT.pair + 0.5 && t < HT.quote + 0.25) out.push({ id: 'pairB', text: 'Three years without an update', x0: 1000, y0: 320, x1: 1790, y1: 570 });
  if (t > HT.quote + 0.63 && t < HT.index - 0.35) out.push({ id: 'note', text: NOTE_L.join(' '), ...noteBox(t) });
  if (t > HT.index + 0.5 && t < HT.six + 0.25) COLX.forEach(([x, w, lab, act], k) => out.push({ id: 'col' + k, text: lab + ' ' + act, x0: x, y0: 120, x1: x + w, y1: 800 }));
  if (t > HT.six + 0.3 && t < HT.glideUp + 0.5) { out.push({ id: 'six', text: '6', x0: 860, y0: 220, x1: 1060, y1: 480 }); out.push({ id: 'sixA', text: 'worth contacting today:', x0: 600, y0: 540, x1: 1320, y1: 600 }); out.push({ id: 'sixB', text: '1 to send, 5 to confirm.', x0: 640, y0: 615, x1: 1280, y1: 670 }); }
  F24.forEach((s, i) => { if (t > productT() && t < HT.endCard) out.push({ id: 'f24_' + i, text: s, x0: 260, y0: 690 + i * 74, x1: 1660, y1: 750 + i * 74 }); });
  if (t >= HT.endCard) END.forEach(([s], i) => out.push({ id: 'end' + i, text: s, x0: 200, y0: endY(i) - 44, x1: 1720, y1: endY(i) + 12 }));
  return out.filter(clampBox);
};
function box(x0, y0, x1, y1, t) { const c = CAM(t), a = w2s(STRIP.x + x0, STRIP.y + y0, c), b = w2s(STRIP.x + x1, STRIP.y + y1, c); return { x0: a[0], y0: a[1], x1: b[0], y1: b[1] }; }
function noteBox(t) { const c = CAM(t), a = w2s(NOTE.x - NOTE.w / 2, NOTE.y - NOTE.h / 2, c), b = w2s(NOTE.x + NOTE.w / 2, NOTE.y + NOTE.h / 2, c); return { x0: a[0], y0: a[1], x1: b[0], y1: b[1] }; }
const clampBox = o => o.x0 >= -2 && o.y0 >= -2 && o.x1 <= W + 2 && o.y1 <= H + 2;

function drawPlates(t) {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const A = Object.fromEntries(screenTexts(t).map(o => [o.id, o.a]));
  if (A.rec) reading(100, 70, 550, A.rec, 'Rows in the file', '525', 'for 500 members');
  if (A.tag) { const a = A.tag; plate(1440, 968, 384, 56, a); ctx.globalAlpha = a; drawText(TAG, 1632, 1006, F.sans(28, 500), '#e2e4e7', 'center'); ctx.globalAlpha = 1; }
  if (A.spell) {
    const a = A.spell, x = 100, y = 150; plate(x, y, 690, 620, a);
    ctx.globalAlpha = a; drawText('London, as typed in the file', x + 32, y + 52, F.sans(30, 500), 'rgba(241,242,243,0.95)');
    SPELLINGS.forEach((s, i) => { const k = eo(seg(t, HT.spell + 0.1 + i * 0.08, HT.spell + 0.4 + i * 0.08)); ctx.globalAlpha = a * k; drawText(s, x + 32 + (1 - k) * -20, y + 112 + i * 52, F.mono(34, 500), PAPERW); });
    ctx.globalAlpha = a; drawText('8 spellings', x + 32, y + 590, F.mono(32, 500), SIG2); ctx.globalAlpha = 1;
    if (loupeState(t)) { const [sx, sy] = w2s(T1.x, T1.y); ctx.globalAlpha = a; ctx.strokeStyle = SIG; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(sx - LR - 50, sy); ctx.lineTo(x + 690, sy); ctx.stroke(); ctx.fillStyle = SIG; ctx.beginPath(); ctx.arc(sx - LR - 50, sy, 5, 0, 7); ctx.fill(); ctx.globalAlpha = 1; }
  }
  if (A.climbL) { const st = stepAt(t); reading(1130, 70, 710, A.climbL, st.label, st.value === '—' ? '' : st.value, st.source); }
  if (A.stale) reading(100, 70, 680, A.stale, 'Profiles untouched for 2+ years', '68 %', 'of 500 members · ref. 2026-10-12', { vfont: F.sans(104, 600) });
}

function drawThesis(t) {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const a = eo(seg(t, productT(), productT() + 0.5)) * (1 - seg(t, HT.endCard, HT.endCard + 0.3)); if (a <= 0) return;
  ctx.globalAlpha = a;
  drawText(F24[0], W / 2, 740 + (1 - a) * 10, F.sans(48, 400), '#e4e6e9', 'center');
  drawText(F24[1], W / 2, 814 + (1 - a) * 10, F.sans(48, 600), PAPERW, 'center');
  ctx.globalAlpha = 1;
}

// ---------- end card: disclosure and credits (FACTS hard rules) ----------
const END = [
  ['Made in code by an AI agent with lemo-opuscar (MIT)', 400], ['Synthetic voice: Kokoro (Apache 2.0)', 400],
  ['Piano: Salamander Grand Piano V3 by Alexander Holm', 400], ['Licence CC BY 3.0', 400], ['https://creativecommons.org/licenses/by/3.0/', 400],
  ['Strings and mallets: CC0, Versilian Studios', 400], ['Fonts: IBM Plex (OFL)', 400], ['Record cards are schematic · no member data', 500],
];
const endY = i => 380 + i * 64;
function drawEnd(t) {
  if (t < HT.endCard) return;
  const a = eo(seg(t, HT.endCard, HT.endCard + 0.35));
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = a; ctx.fillStyle = '#0e0f11'; ctx.fillRect(0, 0, W, H);
  drawText('Trusted Segments', W / 2, 290, F.serif(64), PAPERW, 'center');
  ctx.fillStyle = SIG; ctx.fillRect(W / 2 - 60, 322, 120, 3);
  END.forEach(([s, w], i) => drawText(s, W / 2, endY(i), F.sans(36, w), '#d9dce0', 'center'));
  ctx.globalAlpha = 1;
}

// ---------- frame ----------
window.render = t => {
  DRAWN = []; cam = CAM(t);
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1; ctx.fillStyle = '#0e0f11'; ctx.fillRect(0, 0, W, H);
  applyCam(cam); drawWorld(t, cam[2]);
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  drawLoupe(t); drawIndex(t); drawPair(t); drawPlates(t); drawThesis(t);
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const v = ctx.createRadialGradient(W / 2, H / 2, H * 0.45, W / 2, H / 2, H * 1.05); v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,0.28)');
  ctx.fillStyle = v; ctx.fillRect(0, 0, W, H);
  drawEnd(t);
  drawSubs(t);
  window.__DRAWN = DRAWN;
};

await Promise.all([F.mono(40, 400), F.mono(40, 500), F.sans(40, 400), F.sans(40, 500), F.sans(40, 600), F.serif(40), F.serifI(40)].map(f => document.fonts.load(f, 'Ag0')));
window.render(0);
window.READY = true;
