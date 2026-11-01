// Trusted Segments — Archive Light Table. One world, one camera, one loupe; Canvas 2D.
// Reads timeline.js (structure) and out/timeline.json (voice-locked times, written by tools/export.mjs).
import { clamp, lerp, seg, ss, eio, eo, mulberry, track } from '/core/lib.js';
import * as TLm from './timeline.js';

const W = 1920, H = 1080, cv = document.getElementById('c'), ctx = cv.getContext('2d');
const Q = new URLSearchParams(location.search);
const NOSUBS = Q.get('nosubs') === '1';
const TL = await (await fetch('out/timeline.json')).json();
const HT = TL.hit, WD = TL.words, CUES = TL.cues;
window.DUR = TL.dur;

// ---------- palette & type ----------
const SIG = '#FF5A1F', INK = '#15171A', PAPERW = '#F1F2F3', PLATE = 'rgba(14,15,17,0.80)';
const F = { mono: (s, w = 400) => `${w} ${s}px PM`, sans: (s, w = 400) => `${w} ${s}px PS`, serif: s => `500 ${s}px PF`, serifI: s => `italic 400 ${s}px PF` };
const rgba = (r, g, b, a) => `rgba(${r | 0},${g | 0},${b | 0},${a})`;

// ---------- the facts on screen (FACTS.md ids in comments) ----------
const F01 = 'Graduates working in finance in London for more than three years';                       // F01
const SPELLINGS = ['Greater London', 'LONDON', 'London', 'London - Canary Wharf', 'London, UK', 'Londres', 'Londres (Royaume-Uni)', 'london']; // F04 (VERIFICATION §2)
const F19 = ['Describe your audience in one sentence.', 'Get a segment you can trust.', 'No member record ever leaves the platform.']; // F19

// ---------- the table: 525 schematic record cards (F02), 25 duplicates M0501–M0525 (F03) ----------
const COLS = 25, ROWS = 21, PX = 200, PY = 128, CW = 180, CH = 110;
const TW = COLS * PX, TH = ROWS * PY;                          // 5000 × 2688 world units
const rnd = mulberry(20261012);
const shuffle = a => { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
const OTHER = ['Paris', 'Lyon', 'Lille', 'Bordeaux', 'Nantes', 'Toulouse', 'Geneva', 'Brussels', 'Montreal', 'New York', 'Singapore', 'Luxembourg', 'Milan', 'Madrid', '—', '—', '—', '—'];
const LCOUNT = [5, 8, 28, 4, 9, 6, 5, 7];                     // schematic spread of the 8 spellings over 72 cards
const cards = [];
{
  const london = []; LCOUNT.forEach((n, i) => { for (let k = 0; k < n; k++) london.push(SPELLINGS[i]); });
  const cityOf = shuffle([...london, ...Array.from({ length: 500 - london.length }, () => OTHER[Math.floor(rnd() * OTHER.length)])]);
  for (let i = 0; i < 500; i++) cards.push({ id: 'M' + String(i + 1).padStart(4, '0'), city: cityOf[i], dup: false });
  const orig = shuffle([...Array(500).keys()]).slice(0, 25);
  for (let i = 0; i < 25; i++) cards.push({ id: 'M' + String(501 + i).padStart(4, '0'), city: cards[orig[i]].city, dup: true });
  const slots = shuffle([...Array(525).keys()]);
  cards.forEach((c, i) => {
    const s = slots[i], col = s % COLS, row = Math.floor(s / COLS);
    c.x = -TW / 2 + PX / 2 + col * PX + (rnd() - .5) * 16; c.y = -TH / 2 + PY / 2 + row * PY + (rnd() - .5) * 12;
    c.rot = (rnd() - .5) * 0.04; c.k = i; c.lon = SPELLINGS.includes(c.city);
    c.bars = [0.35 + rnd() * 0.25, 0.55 + rnd() * 0.3, 0.4 + rnd() * 0.35];
  });
  // the sets: 2 ⊂ 26 ⊂ 49 (F07–F09), all London-spelled, non-duplicate; split 1 / 5 / 43 (F11)
  const lonU = shuffle(cards.filter(c => c.lon && !c.dup));
  const exact = lonU.filter(c => c.city === 'London');
  const s49 = [...exact.slice(0, 2), ...lonU.filter(c => !exact.slice(0, 2).includes(c))].slice(0, 49);
  s49.forEach((c, i) => { c.in49 = true; c.o49 = i; if (i < 26) c.in26 = true; if (i < 2) c.in2 = true; });
  const order = shuffle([...s49]);
  order.forEach((c, i) => { c.status = i === 0 ? 'current' : i < 6 ? 'confirm' : 'reactivate'; });
  // 68 % untouched for 2+ years (F13): 340 of the 500 members; the 43 to reactivate are among them
  const rest = shuffle(cards.filter(c => !c.dup && c.status !== 'current' && c.status !== 'confirm' && c.status !== 'reactivate'));
  cards.filter(c => c.status === 'reactivate').forEach(c => c.stale = true);
  rest.slice(0, 340 - 43).forEach(c => c.stale = true);
  cards.filter(c => c.dup).forEach(c => c.stale = rnd() < 0.68);
}
const near = (list, x, y) => list.reduce((a, c) => (Math.hypot(c.x - x, c.y - y) < Math.hypot(a.x - x, a.y - y) ? c : a));
const T1 = near(cards.filter(c => c.in49 && c.city === 'Londres (Royaume-Uni)'), -900, -250);   // the London card
const T2 = near(cards.filter(c => c.status === 'reactivate' && c.city === 'London'), 900, 250);  // the date card
T2.dates = true;
const S49 = cards.filter(c => c.in49);
const NOTE = { x: -700, y: 260, rot: -0.022, w: 1180, h: 440 };
const STRIP = { x: 0, y: -TH / 2 - 80 - 60 - 280, w: 2000, h: 560 };

// ---------- camera: centre, zoom, roll on monotone keys ----------
const OV = [0, 0, 0.37, 0];
const camFor = (c, sx, sy, z) => [c.x + (W / 2 - sx) / z, c.y + (H / 2 - sy) / z, z, 0];
const C1a = camFor(T1, 620, 470, 0.95), C1b = camFor(T1, 620, 470, 1.0);
const C2a = camFor(T2, 960, 470, 0.95), C2b = camFor(T2, 960, 470, 0.98);
const ENDC = [0, STRIP.y + (540 - 330) / 0.85, 0.85, 0];
const pullEnd = TLm.b(13.5);
const CAM = track([
  [0, [0, STRIP.y, 0.9, 0.012]], [HT.lightOn, [0, STRIP.y, 0.935, 0.008]],
  [pullEnd, OV], [pullEnd + 0.12, OV], [HT.drop1, C1a], [HT.lift1, C1b],
  [HT.lift1 + 1.6, OV], [30.2, [0, 0, 0.40, 0]], [HT.drop2, C2a], [HT.lift2, C2b],
  [HT.lift2 + 2.3, OV], [HT.quote - 0.1, [0, 0, 0.375, 0.006]],
  [HT.quote + 0.95, [NOTE.x - 60, NOTE.y + 10, 1.0, 0]], [HT.index, [NOTE.x + 60, NOTE.y + 10, 1.04, 0]],
  [HT.index + 1.1, OV], [HT.glideUp, OV], [HT.glideUp + 2.3, ENDC], [TL.dur, [0, ENDC[1], 0.88, 0]],
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
// develop front from the date card: stale cards go dark as it passes (the turn)
const FRONT_DUR = 3.6;
const frontR = t => t < HT.front ? -1 : eio(seg(t, HT.front, HT.front + FRONT_DUR)) * 6200;
const darkOf = (c, t) => { if (!c.stale) return 0; const r = frontR(t); if (r < 0) return 0; return ss((r - Math.hypot(c.x - T2.x, c.y - T2.y)) / 160); };

// ---------- text with level of detail: glyphs only when they are ≥ ~24 px on screen, bars otherwise ----------
const MW = new Map();
function mw(s, font) { const k = font + '|' + s; let v = MW.get(k); if (v === undefined) { ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.font = font; v = ctx.measureText(s).width; ctx.restore(); MW.set(k, v); } return v; }
function lodText(s, x, y, size, font, col, a, scale, maxW) {
  const px = size * scale, g = ss((px - 22) / 7);
  let fs = size; const w0 = mw(s, font(size)); if (maxW && w0 > maxW) fs = size * maxW / w0;
  const w = Math.min(w0, maxW || 1e9);
  if (g < 1) { ctx.globalAlpha = a * (1 - g) * 0.32; ctx.fillStyle = col; ctx.fillRect(x, y - fs * 0.62, w, fs * 0.55); }
  if (g > 0) { ctx.globalAlpha = a * g; ctx.fillStyle = col; ctx.font = font(fs); ctx.fillText(s, x, y); }
  ctx.globalAlpha = 1;
}

// ---------- one record card (local coords, centre origin) ----------
function drawCard(c, t, scale, opt = {}) {
  const L = opt.light ?? lightLevel(t), d = opt.dark ?? darkOf(c, t), glow = opt.glow || 0;
  const lit = Math.max(L, glow);
  // backlit paper: tone × light; an opaque (stale) card blocks the light
  const dk = lerp(0.3, 1, clamp(L * 1.2)), pr = lerp(lerp(40, 244, lit), 86 * dk, d), pg = lerp(lerp(40, 239, lit), 84 * dk, d), pb = lerp(lerp(42, 227, lit), 80 * dk, d);
  ctx.fillStyle = rgba(pr, pg, pb, 1); ctx.fillRect(-CW / 2, -CH / 2, CW, CH);
  ctx.lineWidth = 1.2 / scale; ctx.strokeStyle = rgba(255, 248, 232, 0.55 * lit * (1 - d)); ctx.strokeRect(-CW / 2 + 1 / scale, -CH / 2 + 1 / scale, CW - 2 / scale, CH - 2 / scale);
  ctx.strokeStyle = rgba(0, 0, 0, 0.16); ctx.strokeRect(-CW / 2, -CH / 2, CW, CH);
  const ink = d > 0.5 ? '#c9c4ba' : INK, ia = lerp(0.88, 0.5, d) * clamp(lit * 1.4, 0.15, 1);
  const dim = opt.dim ?? 1;
  // ID stub and redacted name
  lodText(c.id, -80, -32, 19, s => F.mono(s, 500), ink, ia * (opt.idA ?? dim), scale);
  ctx.fillStyle = rgba(36, 38, 42, 0.9 * clamp(lit * 1.5, .2, 1)); ctx.fillRect(4, -45, 76 * c.bars[0] + 20, 15);
  // city field
  lodText(c.city, -80, -6, 17, s => F.sans(s, 500), ink, ia * (opt.cityA ?? dim), scale, 160);
  if (c.dates) {
    lodText('in post: 3 yrs', -80, 20, 15, s => F.mono(s, 400), ink, ia * (opt.dateA ?? dim), scale);
    lodText('updated: 3 yrs ago', -80, 42, 15, s => F.mono(s, 400), ink, ia * (opt.dateA ?? dim), scale);
  } else {
    ctx.fillStyle = rgba(36, 38, 42, 0.85 * clamp(lit * 1.5, .2, 1));
    ctx.fillRect(-80, 8, 150 * c.bars[1], 11); ctx.fillRect(-80, 27, 150 * c.bars[2], 11);
    ctx.fillStyle = rgba(30, 32, 36, 0.28 * clamp(lit * 1.5, .2, 1)); ctx.fillRect(-80, 44, 46, 7); ctx.fillRect(-20, 44, 46, 7);
  }
  if (opt.underline) { ctx.strokeStyle = SIG; ctx.lineWidth = 2.6 / scale; ctx.beginPath(); const [y, a, w] = opt.underline; ctx.moveTo(-80, y); ctx.lineTo(-80 + w * a, y); ctx.stroke(); }
}

// ---------- the world: desk, table, cards, strip, note, marks ----------
function drawWorld(t, scale, lens = null) {
  const L = lightLevel(t);
  // desk
  ctx.fillStyle = '#0e0f11'; ctx.fillRect(-TW * 2, -TH * 3, TW * 4, TH * 6);
  // aluminium frame
  const fr = 64;
  const g = ctx.createLinearGradient(0, -TH / 2 - fr, 0, TH / 2 + fr);
  g.addColorStop(0, '#9da3a9'); g.addColorStop(0.5, '#7f858b'); g.addColorStop(1, '#a8aeb4');
  ctx.fillStyle = g; ctx.globalAlpha = lerp(0.08, 1, clamp(L * 1.1)); ctx.fillRect(-TW / 2 - fr, -TH / 2 - fr, TW + 2 * fr, TH + 2 * fr);
  ctx.globalAlpha = 1; ctx.fillStyle = '#5b6066'; ctx.fillRect(-TW / 2 - 6, -TH / 2 - 6, TW + 12, TH + 12);
  // emissive surface with a soft falloff toward the frame
  const s = ctx.createRadialGradient(0, 0, 200, 0, 0, TW * 0.62);
  const top = lerp(26, 247, L), edge = lerp(22, 226, L);
  s.addColorStop(0, rgba(top, top + 2 * L, top + 4 * L, 1)); s.addColorStop(1, rgba(edge, edge + 2 * L, edge + 5 * L, 1));
  ctx.fillStyle = s; ctx.fillRect(-TW / 2, -TH / 2, TW, TH);
  // cards
  const flying = t >= HT.index - 0.01 && t < HT.glideUp + 1.5;
  for (const c of cards) {
    if (flying && c.in49 && flightK(c, t) > 0) continue;
    if (lens) { if (Math.hypot(c.x - lens[0], c.y - lens[1]) > lens[2] + 120) continue; }
    else { const [sx, sy] = w2s(c.x, c.y); if (sx < -150 || sx > W + 150 || sy < -150 || sy > H + 150) continue; }
    ctx.save(); ctx.translate(c.x, c.y); ctx.rotate(c.rot);
    const o = {};
    if (c === T1 && t > HT.cityLit - 0.05 && t < HT.lift1 + 1) { const a = eo(seg(t, HT.cityLit, HT.cityLit + 0.45)); o.idA = lerp(1, 0.45, a); o.cityA = 1; o.underline = [2, a, mw(c.city, F.sans(17, 500)) * Math.min(1, 160 / mw(c.city, F.sans(17, 500)))]; }
    if (c === T2 && t > HT.dateLit - 0.05 && t < HT.lift2 + 2) { const a = eo(seg(t, HT.dateLit, HT.dateLit + 0.45)); o.idA = lerp(1, 0.45, a); o.cityA = lerp(1, 0.45, a); o.dateA = 1; o.underline = [48, a, mw('updated: 3 yrs ago', F.mono(15, 400))]; }
    drawCard(c, t, scale, o);
    ctx.restore();
  }
  // marks on the table
  marks(t, scale);
  // the query strip (dark glass on the desk beyond the table)
  drawStrip(t, scale);
  // the quoted note (F17)
  if (t > HT.quote - 0.2 && t < HT.index + 0.4) drawNote(t, scale);
}

function ring(x, y, r, a, scale, w = 3) { ctx.globalAlpha = a; ctx.strokeStyle = SIG; ctx.lineWidth = w / scale; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.stroke(); ctx.globalAlpha = 1; }
function outline(c, a, scale, w = 3) {
  ctx.save(); ctx.translate(c.x, c.y); ctx.rotate(c.rot); ctx.globalAlpha = a; ctx.strokeStyle = SIG; ctx.lineWidth = w / scale;
  const p = 6 / scale + 4; ctx.fillStyle = 'rgba(255,90,31,0.14)'; ctx.fillRect(-CW / 2, -CH / 2, CW, CH); ctx.strokeRect(-CW / 2 - p, -CH / 2 - p, CW + 2 * p, CH + 2 * p); ctx.restore(); ctx.globalAlpha = 1;
}
const countAt = (t, w, n0, n1, d = 0.55) => Math.round(lerp(n0, n1, eo(seg(t, w - d, w))));
// displayed value lands on the narrator's word: only the facts' own numbers are ever on screen (no count-up)
function climbV(t) { return t < WD.n2 - 0.05 ? '—' : t < WD.n26 - 0.05 ? '2' : t < WD.n49 - 0.05 ? '26' : '49'; }
function climbN(t) { if (t < WD.n2 - 0.55) return 0; if (t < WD.n26 - 0.55) return countAt(t, WD.n2, 0, 2); if (t < WD.n49 - 0.55) return countAt(t, WD.n26, 2, 26); return countAt(t, WD.n49, 26, 49); }
function marks(t, scale) {
  // 25 duplicates ring up one by one (F03)
  if (t > WD.dup25 - 0.1 && t < HT.climb + 0.6) {
    const fade = 1 - seg(t, HT.climb, HT.climb + 0.6);
    cards.filter(c => c.dup).forEach((c, i) => { const t0 = WD.dup25 + i * TLm.DUP_DT, a = eo(seg(t, t0, t0 + 0.25)); if (a > 0) ring(c.x, c.y, lerp(150, 112, a), a * fade, scale, 3); });
  }
  // the count climbs: matching cards light in signal colour (F07–F09), held faint until the index
  if (t > WD.n2 - 0.6 && t < HT.index + 0.2) {
    const n = climbN(t), fadeTo = t > HT.front ? lerp(1, 0.55, seg(t, HT.front, HT.front + 1)) : 1;
    for (const c of S49) if (c.o49 < n) outline(c, fadeTo, scale, 3);
  }
  // the develop front's thin warm edge
  const r = frontR(t);
  if (r > 0 && r < 6100) { ctx.globalAlpha = 0.5 * (1 - seg(r, 4800, 6100)); ctx.strokeStyle = '#FF8A4C'; ctx.lineWidth = 3 / scale; ctx.beginPath(); ctx.arc(T2.x, T2.y, r, 0, Math.PI * 2); ctx.stroke(); ctx.globalAlpha = 1; }
}

// ---------- query strip ----------
const SLOT_X = [-495, -165, 165, 495], SLOT_LAB = ['as delivered', 'normalised', 'full logic', 'e-mail today'], SLOT_VAL = ['2', '26', '49', '6'];
const slotFill = i => HT.glideUp + 2.0 + i * 0.35;
function drawStrip(t, scale) {
  const S = STRIP; ctx.save(); ctx.translate(S.x, S.y);
  ctx.fillStyle = 'rgba(22,24,27,0.96)'; rr(-S.w / 2, -290, S.w, 490, 18); ctx.fill();
  ctx.lineWidth = 1.5 / scale; ctx.strokeStyle = 'rgba(255,255,255,0.16)'; ctx.stroke();
  // search box
  ctx.strokeStyle = 'rgba(255,255,255,0.28)'; ctx.lineWidth = 2 / scale; rr(-930, -250, 1860, 150, 12); ctx.stroke();
  const tA = 1 - seg(t, HT.title - 0.1, HT.title + 0.35);
  ctx.globalAlpha = tA; ctx.strokeStyle = '#d9dbde'; ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(-880, -182, 15, 0, Math.PI * 2); ctx.moveTo(-869, -171); ctx.lineTo(-855, -157); ctx.stroke();
  const n = Math.max(0, Math.min(F01.length, Math.floor((t - HT.typeOn) / TLm.TYPE_DT)));
  ctx.font = F.mono(42, 400); ctx.fillStyle = PAPERW; ctx.fillText(F01.slice(0, n), -830, -162);
  const typing = n < F01.length, cx = -830 + mw(F01.slice(0, n), F.mono(42, 400)) + 4;
  if ((typing || Math.floor(t / 0.5) % 2 === 0) && t < HT.title) { ctx.fillStyle = SIG; ctx.fillRect(cx, -200, 3, 48); }
  ctx.globalAlpha = 1;
  if (t > HT.title - 0.1) { const a = eo(seg(t, HT.title, HT.title + 0.6)); ctx.save(); ctx.beginPath(); ctx.rect(-930, -260, 1860 * a, 170); ctx.clip(); ctx.font = F.serif(84); ctx.fillStyle = PAPERW; ctx.textAlign = 'center'; ctx.fillText('Trusted Segments', 0, -148); ctx.restore(); ctx.textAlign = 'left'; } // F23
  // four answer slots
  const sA = eo(seg(t, HT.slots, HT.slots + 0.5));
  SLOT_X.forEach((x, i) => {
    const a = eo(seg(t, HT.slots + i * 0.12, HT.slots + i * 0.12 + 0.35));
    if (a <= 0) return;
    ctx.globalAlpha = a; ctx.strokeStyle = 'rgba(255,255,255,0.3)'; ctx.lineWidth = 2 / scale; rr(x - 150, -40, 300, 124, 10); ctx.stroke();
    const f = eo(seg(t, slotFill(i), slotFill(i) + 0.3));
    ctx.textAlign = 'center';
    if (f < 1) { ctx.globalAlpha = a * (1 - f) * 0.55; ctx.font = F.mono(72, 400); ctx.fillStyle = '#c8cbd0'; ctx.fillText('?', x, 47); }
    if (f > 0) { ctx.globalAlpha = f; ctx.font = F.mono(76, 500); ctx.fillStyle = i === 3 ? SIG : PAPERW; ctx.fillText(SLOT_VAL[i], x, 49); ctx.font = F.sans(34, 400); ctx.fillStyle = '#b9bdc3'; ctx.fillText(SLOT_LAB[i], x, 142); }
    ctx.textAlign = 'left'; ctx.globalAlpha = 1;
  });
  ctx.restore(); void sA;
}
function rr(x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }

// ---------- quoted note (F17), lying on the table ----------
const NOTE_L = ['“340 London expats.', 'Twenty had moved back years ago.', 'Two unsubscribed.”'];
function drawNote(t, scale) {
  const a = eo(seg(t, HT.quote - 0.2, HT.quote + 0.5)) * (1 - seg(t, HT.index - 0.2, HT.index + 0.35));
  if (a <= 0) return;
  ctx.save(); ctx.translate(NOTE.x, NOTE.y + (1 - a) * 40); ctx.rotate(NOTE.rot); ctx.globalAlpha = a;
  ctx.shadowColor = 'rgba(0,0,0,0.25)'; ctx.shadowBlur = 30 * scale; ctx.shadowOffsetY = 8 * scale;
  ctx.fillStyle = '#f6f1e6'; ctx.fillRect(-NOTE.w / 2, -NOTE.h / 2, NOTE.w, NOTE.h);
  ctx.shadowColor = 'transparent';
  ctx.fillStyle = SIG; ctx.fillRect(-NOTE.w / 2, -NOTE.h / 2, 6, NOTE.h);
  ctx.fillStyle = INK; ctx.font = F.serifI(56);
  NOTE_L.forEach((s, i) => ctx.fillText(s, -NOTE.w / 2 + 70, -NOTE.h / 2 + 110 + i * 82));
  ctx.font = F.mono(30, 400); ctx.fillStyle = '#5d6168'; ctx.fillText('user verbatim', -NOTE.w / 2 + 70, NOTE.h / 2 - 50);
  ctx.restore(); ctx.globalAlpha = 1;
}

// ---------- the loupe ----------
const LR = 240, MAG = 2.5;
function loupeState(t) {
  const L = [[HT.drop1, HT.lift1, T1], [HT.drop2, HT.lift2, T2]];
  for (const [d, l, c] of L) {
    if (t >= d - 0.4 && t < l + 0.4) {
      const k = t < d ? eo(seg(t, d - 0.4, d)) : 1 - eo(seg(t, l, l + 0.4));   // land / lift, fast ease-out
      return { c, k };
    }
  }
  return null;
}
function drawLoupe(t) {
  const st = loupeState(t); if (!st) return;
  const { c, k } = st; const [sx, sy] = w2s(c.x, c.y);
  const s = lerp(1.35, 1, k), R = LR * s, a = k;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  // soft shadow (tightens as it lands)
  ctx.save(); ctx.globalAlpha = 0.45 * a; ctx.shadowColor = 'rgba(0,0,0,0.6)'; ctx.shadowBlur = lerp(60, 26, k); ctx.shadowOffsetX = lerp(30, 10, k); ctx.shadowOffsetY = lerp(40, 14, k);
  ctx.fillStyle = '#000'; ctx.beginPath(); ctx.arc(sx, sy, R + 46, 0, Math.PI * 2); ctx.fill(); ctx.restore();
  // inside the lens: the same world, magnified about the lens point
  ctx.save(); ctx.globalAlpha = a; ctx.beginPath(); ctx.arc(sx, sy, R, 0, Math.PI * 2); ctx.clip();
  const z = cam[2] * MAG; applyCam(cam, sx, sy, c.x, c.y, z); drawWorld(t, z, [c.x, c.y, R / z]);
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const v = ctx.createRadialGradient(sx, sy, R * 0.7, sx, sy, R); v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,0.22)');
  ctx.fillStyle = v; ctx.fillRect(sx - R, sy - R, 2 * R, 2 * R);
  const hl = ctx.createLinearGradient(sx - R, sy - R, sx + R * 0.2, sy + R * 0.2); hl.addColorStop(0, 'rgba(255,255,255,0.16)'); hl.addColorStop(0.5, 'rgba(255,255,255,0)');
  ctx.fillStyle = hl; ctx.fillRect(sx - R, sy - R, 2 * R, 2 * R);
  ctx.restore();
  // acrylic skirt, glowing at its foot
  ctx.save(); ctx.globalAlpha = a;
  ctx.beginPath(); ctx.arc(sx, sy, R + 48, 0, Math.PI * 2); ctx.arc(sx, sy, R + 22, 0, Math.PI * 2, true);
  const sk = ctx.createRadialGradient(sx, sy, R + 22, sx, sy, R + 48); sk.addColorStop(0, 'rgba(235,240,245,0.25)'); sk.addColorStop(0.85, 'rgba(255,255,255,0.55)'); sk.addColorStop(1, 'rgba(255,255,255,0.2)');
  ctx.fillStyle = sk; ctx.fill();
  // black ring with a bevel highlight
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
  ctx.globalAlpha = a; ctx.font = F.sans(30, 500); ctx.fillStyle = 'rgba(241,242,243,0.92)'; ctx.fillText(label, x + 32, y + 52);
  ctx.font = F.mono(opt.vs || 104, 500); ctx.fillStyle = SIG; ctx.fillText(value, x + 28, y + 52 + (opt.vs || 104) * 1.02);
  if (source) { ctx.font = F.mono(28, 400); ctx.fillStyle = '#aeb3ba'; ctx.fillText(source, x + 32, y + h - 30); }
  ctx.globalAlpha = 1;
}
const fadeWin = (t, a, b, fi = 0.35, fo = 0.35) => Math.min(eo(seg(t, a, a + fi)), 1 - seg(t, b - fo, b));

// index: where each of the 49 goes (F11, F21)
const COLX = [[130, 420, 'Current'], [600, 500, 'To confirm'], [1150, 640, 'To reactivate']];
const colOf = c => c.status === 'current' ? 0 : c.status === 'confirm' ? 1 : 2;
const inCol = {}; ['current', 'confirm', 'reactivate'].forEach(s => S49.filter(c => c.status === s).forEach((c, i) => inCol[c.id] = i));
function target(c) {
  const k = colOf(c), i = inCol[c.id];
  if (k === 0) return [340, 545, 1.15];
  if (k === 1) return [780 + (i % 2) * 150, 420 + Math.floor(i / 2) * 115 + (i === 4 ? 0 : 0), 0.72];
  return [1186 + (i % 8) * 76 + 34, 372 + Math.floor(i / 8) * 58 + 21, 0.37];
}
const flightStart = c => HT.index + 0.35 + (colOf(c) === 0 ? 0 : colOf(c) === 1 ? 0.25 + inCol[c.id] * 0.1 : 0.6 + inCol[c.id] * 0.022);
const flightK = (c, t) => eio(seg(t, flightStart(c), flightStart(c) + 0.95));
function drawIndex(t) {
  if (t < HT.index || t > HT.glideUp + 1.6) return;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const veil = eo(seg(t, HT.index, HT.index + 1.0)) * 0.6;
  ctx.fillStyle = `rgba(14,15,17,${veil})`; ctx.fillRect(0, 0, W, H);
  const pa = fadeWin(t, HT.index + 0.45, HT.off + 0.6, 0.5, 0.5);
  const words = [WD.c1, WD.c5, WD.c43], nums = [1, 5, 43];
  COLX.forEach(([x, w, lab], k) => {
    plate(x, 120, w, 680, pa * 0.92);
    ctx.globalAlpha = pa; ctx.font = F.sans(36, 500); ctx.fillStyle = PAPERW; ctx.fillText(lab, x + 30, 178);
    const na = eo(seg(t, words[k] - 0.1, words[k] + 0.25));
    if (na > 0) { ctx.globalAlpha = pa * na; ctx.font = F.mono(96, 500); ctx.fillStyle = SIG; ctx.fillText(String(nums[k]), x + 26, 290 - (1 - na) * 14); }
    ctx.globalAlpha = 1;
  });
  // the flying cards
  const glowOff = t > HT.off;
  for (const c of S49) {
    const k = flightK(c, t); if (k <= 0) continue;
    const [wx, wy] = w2s(c.x, c.y), [tx, ty, ts] = target(c);
    const lift = Math.sin(Math.PI * k) * 60;
    const x = lerp(wx, tx, k), y = lerp(wy, ty, k) - lift, s = lerp(cam[2], ts, k), r = lerp(c.rot + cam[3], 0, k);
    let a = 1; if (glowOff) a = c.status === 'reactivate' ? 1 - seg(t, HT.off, HT.off + 0.5) : 1 - seg(t, HT.glideUp, HT.glideUp + 0.7);
    if (a <= 0) continue;
    ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = a; ctx.translate(x, y); ctx.rotate(r); ctx.scale(s, s);
    const live = c.status !== 'reactivate';
    if (live && glowOff) { ctx.shadowColor = 'rgba(255,236,200,0.9)'; ctx.shadowBlur = 40; }
    drawCard(c, t, s, { light: live ? 1 : Math.max(lightLevel(t), 0.3), dark: live ? 0 : 1, glow: live ? 1 : 0 });
    ctx.shadowColor = 'transparent'; ctx.shadowBlur = 0;
    ctx.globalAlpha = 1;
  }
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  // bracket: 1 + 5 = 6 worth e-mailing today (F12)
  if (t > WD.n6 - 0.1) {
    const a = eo(seg(t, WD.n6 - 0.1, WD.n6 + 0.5)), fa = 1 - seg(t, HT.off, HT.off + 0.5);
    ctx.save(); ctx.globalAlpha = fa; ctx.strokeStyle = SIG; ctx.lineWidth = 3.5; ctx.setLineDash([2600 * a, 4000]); rr(112, 102, 1006, 716, 12); ctx.stroke(); ctx.restore();
    const la = eo(seg(t, WD.n6, WD.n6 + 0.4)) * fa;
    plate(325, 836, 580, 92, la);
    ctx.globalAlpha = la; ctx.font = F.mono(72, 500); ctx.fillStyle = SIG; ctx.fillText('6', 350, 906);
    ctx.font = F.sans(40, 500); ctx.fillStyle = PAPERW; ctx.fillText('can be e-mailed today', 410, 897); ctx.globalAlpha = 1;
  }
}

// ---------- the side-by-side records (F22) ----------
function drawPair(t) {
  const a = fadeWin(t, HT.pair, HT.quote + 0.3, 0.4, 0.5); if (a <= 0) return;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const b2 = fadeWin(t, HT.pair + 0.5, HT.quote + 0.3, 0.4, 0.5);
  const card = (x, aa, lab, q) => { if (aa <= 0) return; plate(x, 330, 760, 230, aa); plate(x, 330, 760, 230, aa * 0.6); ctx.globalAlpha = aa; ctx.font = F.sans(30, 500); ctx.fillStyle = '#aeb3ba'; ctx.fillText(lab, x + 36, 388); ctx.font = F.sans(46, 500); ctx.fillStyle = PAPERW; ctx.fillText(q, x + 36, 470); ctx.globalAlpha = 1; };
  card(150, a, 'read as tenure', '“Three years in post”');
  card(1010, b2, 'read as freshness', '“Three years without an update”');
  const e = eo(seg(t, WD.sameSig - 0.15, WD.sameSig + 0.35));
  if (e > 0) {
    ctx.fillStyle = 'rgba(14,15,17,0.9)'; ctx.globalAlpha = a; ctx.fillRect(918, 400, 84, 90);
    ctx.strokeStyle = SIG; ctx.lineWidth = 9; ctx.lineCap = 'round'; ctx.beginPath();
    ctx.moveTo(934, 428); ctx.lineTo(934 + 52 * clamp(e * 2), 426); if (e > 0.5) { ctx.moveTo(934, 462); ctx.lineTo(934 + 52 * clamp(e * 2 - 1), 460); } ctx.stroke(); ctx.lineCap = 'butt';
    const la = eo(seg(t, WD.sameSig, WD.sameSig + 0.4)) * a; plate(735, 600, 450, 84, la);
    ctx.globalAlpha = la; ctx.font = F.sans(40, 500); ctx.fillStyle = PAPERW; ctx.textAlign = 'center'; ctx.fillText('the same signal', 960, 656); ctx.textAlign = 'left'; ctx.globalAlpha = 1;
  }
}

// ---------- subtitles: caption strip, bottom centre, 3 px signal edge ----------
const BURN = c => !/^S1[456]/.test(c.id);    // the closing lines are already on screen as type
function wrap(s, font, maxW) { ctx.font = font; if (ctx.measureText(s).width <= maxW) return [s]; const w = s.split(' '); let best = null; for (let i = 1; i < w.length; i++) { const a = w.slice(0, i).join(' '), b = w.slice(i).join(' '); const m = Math.max(ctx.measureText(a).width, ctx.measureText(b).width); if (!best || m < best[0]) best = [m, [a, b]]; } return best[1]; }
function drawSubs(t) {
  if (NOSUBS) return;
  const c = CUES.find((c, i) => { const nx = CUES[i + 1], end = nx && nx.t0 - c.t1 < 0.1 ? nx.t0 : c.t1; return t >= c.t0 && t < end && BURN(c); }); if (!c) return;
  const i = CUES.indexOf(c), pv = CUES[i - 1], nx = CUES[i + 1];
  const fin = pv && BURN(pv) && c.t0 - pv.t1 < 0.1 ? 1 : seg(t, c.t0, c.t0 + 0.12), fout = nx && BURN(nx) && nx.t0 - c.t1 < 0.1 ? 1 : 1 - seg(t, c.t1 - 0.12, c.t1);
  const a = Math.min(fin, fout);
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const font = F.sans(40, 500), lines = wrap(c.text, font, 1560); ctx.font = font;
  const w = Math.max(...lines.map(l => ctx.measureText(l).width)) + 64, h = 30 + lines.length * 52, x = (W - w) / 2, y = H - 52 - h;
  ctx.globalAlpha = a; ctx.fillStyle = 'rgba(14,15,17,0.80)'; ctx.fillRect(x, y, w, h); ctx.fillStyle = SIG; ctx.fillRect(x, y, w, 3);
  ctx.fillStyle = PAPERW; ctx.textAlign = 'center'; lines.forEach((l, i) => ctx.fillText(l, W / 2, y + 56 + i * 52)); ctx.textAlign = 'left'; ctx.globalAlpha = 1;
}

// ---------- the screen texts, by time (also feeds readcheck) ----------
function screenTexts(t) {
  const T = [];
  const put = (id, text, x0, y0, x1, y1, a) => { if (a > 0.02) T.push({ id, text, x0, y0, x1, y1, a }); };
  // F02: rows vs members
  put('rec', '525', 90, 70, 640, 320, fadeWin(t, WD.rec525 - 0.3, HT.drop1 - 0.35, 0.35, 0.3));
  put('schem', 'Schematic · IDs and city only · no member data', 60, 846, 1180, 896, fadeWin(t, HT.lightOn + 0.6, HT.drop1 - 0.45, 0.35, 0.3));
  // F04: eight spellings
  put('spell', 'London, as typed in the file', 1010, 150, 1700, 770, fadeWin(t, HT.spell, HT.climb - 0.1, 0.4, 0.4));
  // F03
  put('dup', '25', 90, 70, 640, 320, fadeWin(t, WD.dup25 + 0.2, HT.climb - 0.1));
  // F07–F09
  const cl = fadeWin(t, HT.climb, HT.drop2 + 0.4, 0.4, 0.4);
  const lab = t < WD.n26 - 0.55 ? 'Naive filter · file as delivered' : t < WD.n49 - 0.55 ? 'Normalised · 8 spellings, 3 sector labels' : 'Full logic · dedup + employer + job title';
  put('climbL', lab, 1150, 70, 1840, 320, cl);
  // F13
  put('stale', '68 %', 90, 70, 760, 320, fadeWin(t, WD.n68 - 0.5, HT.pair + 0.2));
  return T;
}
window.TEXTS = t => {
  const out = screenTexts(t).map(({ id, text, x0, y0, x1, y1 }) => ({ id, text, x0, y0, x1, y1 }));
  if (t >= HT.typeOn && t < HT.title) out.push({ id: 'query', text: F01, ...box(-930, -260, 930, -100) });
  if (t >= HT.title) out.push({ id: 'title', text: 'Trusted Segments', ...box(-930, -260, 930, -100) });
  for (let i = 0; i < 4; i++) { if (t > slotFill(i)) out.push({ id: 'slot' + i, text: SLOT_VAL[i] + ' ' + SLOT_LAB[i], ...box(SLOT_X[i] - 150, -40, SLOT_X[i] + 150, 150) }); }
  if (t > HT.pair && t < HT.quote + 0.3) out.push({ id: 'pairA', text: 'Three years in post', x0: 150, y0: 330, x1: 910, y1: 560 });
  if (t > HT.pair + 0.5 && t < HT.quote + 0.3) out.push({ id: 'pairB', text: 'Three years without an update', x0: 1010, y0: 330, x1: 1770, y1: 560 });
  if (t > WD.sameSig && t < HT.quote + 0.3) out.push({ id: 'same', text: 'the same signal', x0: 735, y0: 600, x1: 1185, y1: 684 });
  if (t > HT.quote + 0.3 && t < HT.index - 0.2) out.push({ id: 'note', text: NOTE_L.join(' '), ...noteBox() });
  if (t > HT.index + 0.7 && t < HT.off) COLX.forEach(([x, w, lab], k) => out.push({ id: 'col' + k, text: lab, x0: x, y0: 120, x1: x + w, y1: 800 }));
  if (t > WD.n6 + 0.1 && t < HT.off) out.push({ id: 'six', text: '6 can be e-mailed today', x0: 325, y0: 836, x1: 905, y1: 928 });
  F19.forEach((s, i) => { if (t > productT(i)) out.push({ id: 'f19_' + i, text: s, x0: 300, y0: 700 + i * 72, x1: 1620, y1: 760 + i * 72 }); });
  return out.filter(clampBox);
};
function box(x0, y0, x1, y1) { const a = w2s(STRIP.x + x0, STRIP.y + y0, CAM(window.__t ?? 0)), b = w2s(STRIP.x + x1, STRIP.y + y1, CAM(window.__t ?? 0)); return { x0: a[0], y0: a[1], x1: b[0], y1: b[1] }; }
function noteBox() { const c = CAM(window.__t ?? 0), a = w2s(NOTE.x - NOTE.w / 2, NOTE.y - NOTE.h / 2, c), b = w2s(NOTE.x + NOTE.w / 2, NOTE.y + NOTE.h / 2, c); return { x0: a[0], y0: a[1], x1: b[0], y1: b[1] }; }
const clampBox = o => o.x0 >= -2 && o.y0 >= -2 && o.x1 <= W + 2 && o.y1 <= H + 2;
const productT = i => [CUES.find(c => c.id === 'S15a').t0, CUES.find(c => c.id === 'S15b').t0, CUES.find(c => c.id === 'S15c').t0][i];

function drawPlates(t) {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const A = Object.fromEntries(screenTexts(t).map(o => [o.id, o.a]));
  if (A.rec) reading(90, 70, 550, A.rec, 'Rows in the file', '525', 'for 500 members announced');
  if (A.schem) { const a = A.schem; plate(60, 846, 860, 52, a * 0.9); ctx.globalAlpha = a; ctx.font = F.mono(28, 400); ctx.fillStyle = '#d5d8dc'; ctx.fillText('Schematic · IDs and city only · no member data', 80, 882); ctx.globalAlpha = 1; }
  if (A.spell) {
    const a = A.spell, x = 1010, y = 150; plate(x, y, 690, 620, a);
    ctx.globalAlpha = a; ctx.font = F.sans(30, 500); ctx.fillStyle = 'rgba(241,242,243,0.92)'; ctx.fillText('London, as typed in the file', x + 32, y + 52);
    SPELLINGS.forEach((s, i) => { const k = eo(seg(t, HT.spell + 0.1 + i * 0.08, HT.spell + 0.4 + i * 0.08)); ctx.globalAlpha = a * k; ctx.font = F.mono(34, 500); ctx.fillStyle = PAPERW; ctx.fillText(s, x + 32 + (1 - k) * -20, y + 112 + i * 52); });
    ctx.globalAlpha = a; ctx.font = F.mono(30, 500); ctx.fillStyle = SIG; ctx.fillText('8 spellings', x + 32, y + 590); ctx.globalAlpha = 1;
    // leader from the lens rim to the plate
    if (loupeState(t)) { const [sx, sy] = w2s(T1.x, T1.y); ctx.globalAlpha = a; ctx.strokeStyle = SIG; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(sx + LR + 50, sy); ctx.lineTo(x, sy); ctx.stroke(); ctx.fillStyle = SIG; ctx.beginPath(); ctx.arc(sx + LR + 50, sy, 5, 0, 7); ctx.fill(); ctx.globalAlpha = 1; }
  }
  if (A.dup) reading(90, 70, 550, A.dup, 'Duplicate persons', '25', 'IDs M0501 – M0525');
  if (A.climbL) { const lab = screenTexts(t).find(o => o.id === 'climbL').text; reading(1150, 70, 690, A.climbL, lab, climbV(t), 'members matching the sentence'); }
  if (A.stale) reading(90, 70, 670, A.stale, 'Profiles untouched for 2+ years', '68 %', 'of 500 members · ref. 2026-10-12');
}

function drawProduct(t) {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  F19.forEach((s, i) => {
    const t0 = productT(i), a = eo(seg(t, t0, t0 + 0.45)); if (a <= 0) return;
    ctx.save(); ctx.globalAlpha = a; ctx.font = F.sans(44, 400); ctx.fillStyle = i === 1 ? PAPERW : '#d9dce0'; ctx.textAlign = 'center';
    ctx.fillText(s, W / 2, 745 + i * 72 + (1 - a) * 10); ctx.restore();
  });
}

// ---------- frame ----------
window.render = t => {
  window.__t = t; cam = CAM(t);
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1; ctx.fillStyle = '#0e0f11'; ctx.fillRect(0, 0, W, H);
  applyCam(cam); drawWorld(t, cam[2]);
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  drawLoupe(t);
  drawIndex(t);
  drawPair(t);
  drawPlates(t);
  if (t > productT(0) - 0.1) drawProduct(t);
  // light vignette
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const v = ctx.createRadialGradient(W / 2, H / 2, H * 0.45, W / 2, H / 2, H * 1.05); v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,0.28)');
  ctx.fillStyle = v; ctx.fillRect(0, 0, W, H);
  drawSubs(t);
};

await Promise.all([F.mono(40, 400), F.mono(40, 500), F.sans(40, 400), F.sans(40, 500), F.serif(40), F.serifI(40)].map(f => document.fonts.load(f, 'Ag0')));
window.render(0);
window.READY = true;
