// ProdCraft weekly notes, wk 02 — "32 inboxes, 800 sends. Who replied?"  House style: ProdCraft Notes (swiss-motion re-skin).
// 1080×1350, 30 fps, Canvas 2D. Deterministic: the frame is a pure function of t.
// Every glyph goes through drawText(), which also logs it (window.__DRAWN) for tools/drawn_text.mjs.
import { clamp, lerp, seg } from '/core/lib.js';
import { K, b, DUR, CARDS, ORDERS, RESULT, RULE_TAG, TXT } from './timeline.js';

const W = 1080, H = 1350, cv = document.getElementById('c'), ctx = cv.getContext('2d');
const CODE = await (await fetch('out/code.json')).json();          // reply_classifier.py lines 99–107, dedented by 4 (tools/code.py)
const LOGO = new Image(); LOGO.src = 'logo-prodcraft.png'; await LOGO.decode();
window.DUR = DUR;
// the card prints the mark in ink: tint the PNG's alpha with the ink colour once
const LOGO_INK = (() => { const o = document.createElement('canvas'); o.width = o.height = 512; const g = o.getContext('2d');
  g.drawImage(LOGO, 0, 0); g.globalCompositeOperation = 'source-in'; g.fillStyle = '#16181c'; g.fillRect(0, 0, 512, 512); return o; })();

// ---------- ProdCraft Notes palette (sampled from ref/wk02_card.png and the site CSS) ----------
const C = {
  paper: '#EFEDE8', ink: '#16181c', ink2: '#464951', panel: '#E6E3DC', tabbar: '#E7E4DD', hl: '#DCD3C2',
  border: '#B8B6B1', rule: '#BEBDBA', card: '#F7F6F2', cardEdge: '#CDCAC3', blue: '#3A5A78',
  gold: '#A58239', goldL: '#C8A35C', goldT: '#7A5C22',           // bar / light mark / gold TEXT (≥ 4.5:1 on paper)
};
const F = {
  disp: (s, w = 500) => `${w} ${s}px NRD${w}`, text: (s, w = 400) => `${w} ${s}px NRT${w}`, ital: s => `italic 400 ${s}px NRI`,
  mono: (s, w = 400) => `${w} ${s}px JBM`, sans: (s, w = 500) => `${w} ${s}px GEI`,
};

// ---------- motion: the swiss-motion curve cubic-bezier(.7,0,.2,1), linear for lines being drawn ----------
const bez = (x1, y1, x2, y2) => x => {
  if (x <= 0) return 0; if (x >= 1) return 1;
  let t = x;
  for (let i = 0; i < 8; i++) {
    const cx = 3 * x1 * t * (1 - t) ** 2 + 3 * x2 * t * t * (1 - t) + t ** 3 - x;
    const d = 3 * x1 * (1 - t) ** 2 + 6 * (x2 - x1) * t * (1 - t) + 3 * (1 - x2) * t * t;
    if (Math.abs(d) < 1e-6) break; t = clamp(t - cx / d);
  }
  return 3 * y1 * t * (1 - t) ** 2 + 3 * y2 * t * t * (1 - t) + t ** 3;
};
const EZ = bez(.7, 0, .2, 1);
const ez = (t, beat, dur = 0.5) => EZ(seg(t, b(beat), b(beat + dur)));          // eased progress of a snap
const lin = (t, beat, dur) => seg(t, b(beat), b(beat + dur));

// ---------- the one text path: draw + log ----------
let DRAWN = [], TX = [];
function drawText(s, x, y, font, color, { align = 'left', ls = 0 } = {}) {
  if (!s) return 0;
  const a = ctx.globalAlpha; if (a < 0.02) return 0;
  ctx.font = font; ctx.letterSpacing = ls + 'px'; ctx.fillStyle = color; ctx.textAlign = align;
  ctx.fillText(s, x, y);
  const w = ctx.measureText(s).width;
  const m = ctx.getTransform(), k = Math.hypot(m.a, m.b), size = parseFloat(font.split(' ').find(p => p.endsWith('px')));
  DRAWN.push({ text: s, x: Math.round(m.a * x + m.c * y + m.e), y: Math.round(m.b * x + m.d * y + m.f), px: +(size * k).toFixed(1), a: +a.toFixed(2) });
  ctx.textAlign = 'left'; ctx.letterSpacing = '0px';
  return w;
}
const measure = (s, font, ls = 0) => { ctx.font = font; ctx.letterSpacing = ls + 'px'; const w = ctx.measureText(s).width; ctx.letterSpacing = '0px'; return w; };
// a text block the viewer must read: reported to readcheck only while fully on screen (not mid-reveal, not leaving)
const readable = (id, text, x0, y0, x1, y1) => TX.push({ id, text, x0: Math.round(x0), y0: Math.round(y0), x1: Math.round(x1), y1: Math.round(y1) });

// clip-reveal: a line rises out of its own slot from below the baseline (in), and leaves upward (out). Never a fade.
// returns true when the line is fully in place.
function line(t, inB, outB, s, x, y, font, color, { size, align = 'left', ls = 0, dur = 0.5, outDur = 0.5 } = {}) {
  if (t < b(inB)) return false;
  if (outB != null && t >= b(outB + outDur)) return false;
  const p = ez(t, inB, dur), q = outB != null ? ez(t, outB, outDur) : 0;
  const hgt = size * 1.32, top = y - size * 1.0;
  const dy = (1 - p) * hgt - q * hgt;
  const w = measure(s, font, ls), x0 = align === 'right' ? x - w : x;
  ctx.save(); ctx.beginPath(); ctx.rect(x0 - 12, top, w + 24, hgt); ctx.clip();
  drawText(s, x, y + dy, font, color, { align, ls });
  ctx.restore();
  return p >= 1 && q <= 0;
}

// ---------- chrome: the wk 02 card's header and footer, at the card's exact positions ----------
function chrome() {
  // logo: the PNG's ink spans x 42–469, y 2–509 of 512; on the card it sits at x 98–128, y 98–133
  const s = 35.4 / 507;  // px per source px
  ctx.drawImage(LOGO_INK, 98 - 42 * s, 98 - 2 * s, 512 * s, 512 * s);
  drawText(TXT.brand, 144, 124, F.text(26.4, 500), C.ink, { ls: -0.2 });
  drawText(TXT.wk, 982, 128, F.mono(14), C.ink2, { align: 'right', ls: 1.6 });
  ctx.fillStyle = C.rule; ctx.fillRect(96, 1210, 888, 1);
  drawText(TXT.foot, 96, 1247, F.mono(14), C.ink2, { ls: 1.6 });
  drawText(TXT.page, 982, 1247, F.mono(14), C.goldT, { align: 'right', ls: 1.6 });
  readable('hdr-brand', TXT.brand, 144, 100, 260, 128); readable('hdr-wk', TXT.wk, 930, 114, 984, 132);
  readable('ftr', TXT.foot, 96, 1232, 340, 1252); readable('ftr-page', TXT.page, 960, 1232, 984, 1252);
}

// ---------- the 32 inboxes (F01): an 8×4 grid on the poster, a ribbon once the replies arrive ----------
const GRID = i => ({ x: 96 + (i % 8) * (97 + 16), y: 500 + Math.floor(i / 8) * (80 + 16), w: 97, h: 80 });
const RIB = (i, ry) => ({ x: 96 + i * 27.75, y: ry, w: 23.75, h: 18 });
const LIGHT_ORDER = (() => { const o = [...Array(32).keys()].filter(i => !CARDS.some(c => c.tile === i)); let s = 7; for (let i = o.length - 1; i > 0; i--) { s = (s * 1103515245 + 12345) & 0x7fffffff; const j = s % (i + 1); [o[i], o[j]] = [o[j], o[i]]; } return o; })();
function tileLit(i, t) {
  const ci = CARDS.findIndex(c => c.tile === i);
  if (ci >= 0) return t >= b(K.card0 + ci * 0.5);
  const k = LIGHT_ORDER.indexOf(i);
  return t >= b(K.lights + k * 0.25 * 32 / LIGHT_ORDER.length);   // sixteenth-ish steps, all lit by beat 14.5
}
function envelope(r, lit, lw) {
  ctx.fillStyle = lit ? C.goldL : C.paper; ctx.fillRect(r.x, r.y, r.w, r.h);
  ctx.strokeStyle = C.ink; ctx.lineWidth = lw; ctx.lineJoin = 'miter';
  ctx.strokeRect(r.x + lw / 2, r.y + lw / 2, r.w - lw, r.h - lw);
  ctx.beginPath(); ctx.moveTo(r.x + lw / 2, r.y + lw / 2); ctx.lineTo(r.x + r.w / 2, r.y + r.h * 0.56); ctx.lineTo(r.x + r.w - lw / 2, r.y + lw / 2); ctx.stroke();
}

// ---------- layout states (y of the ribbon, label and ledger) ----------
// B1: under the headline · B2: after the headline leaves · C: under the code panel · D: after the panel leaves
const L = {
  B1: { ry: 392, lab: 442, ly: 458, pitch: 74, f05: 1030 },
  B2: { ry: 202, lab: 252, ly: 268, pitch: 74, f05: 840 },
  C: { ry: 202, lab: 652, ly: 666, pitch: 72, f05: 840 },
  D: { ry: 202, lab: 300, ly: 316, pitch: 86, f05: 840 },
};
function layout(t) {
  const mix = (A, B, p) => Object.fromEntries(Object.keys(A).map(k => [k, lerp(A[k], B[k], p)]));
  let s = mix(L.B1, L.B2, ez(t, K.reflowUp, 1));
  s = mix(s, L.C, ez(t, K.reflowC, 1));
  return mix(s, L.D, ez(t, K.reflowD, 1));
}
function slot(i, t) {   // the row a card sits in, eased between the sorts
  const steps = [[K.oooSort, 1], [K.stopSort, 2], [K.hotSort, 3]];
  let y = ORDERS[0].indexOf(i);
  for (const [beat, k] of steps) y = lerp(y, ORDERS[k].indexOf(i), ez(t, beat, 1));
  return y;
}

// ---------- the code panel (F21: verbatim, dedented by 4 only) ----------
const PX = 72, PW = 936, PY = 228, TABH = 46, LH = 33, PH = TABH + 16 + 9 * LH + 18;
const KW = new Set(['if', 'return']);
function tokens(s) {   // [text, colour, weight]: strings blue, keywords bold, the rest ink (as on the card)
  const out = []; const re = /("[^"]*")|(\b(?:if|return)\b)|([^"]+?(?=("|\bif\b|\breturn\b|$)))/g; let m;
  while ((m = re.exec(s)) && m[0]) out.push(m[1] ? [m[1], C.blue, 400] : m[2] ? [m[2], C.ink, 700] : [m[3], C.ink, 400]);
  return out;
}
CODE.lines.forEach(s => { if (tokens(s).map(x => x[0]).join('') !== s) throw new Error('tokenizer altered a code line: ' + s); });
const HL_LINE = t => (t >= b(K.oooRes) ? 3 : t >= b(K.ooo) ? 0 : -1);
function panel(t) {
  if (t < b(K.panel) || t >= b(K.panelOut + 0.5)) return;
  const xin = (1 - ez(t, K.panel, 1)) * (W - PX + 8), up = ez(t, K.panelOut, 0.5);
  const x = PX + xin, y = PY;
  ctx.save(); ctx.beginPath(); ctx.rect(0, PY - 2, W, PH + 4); ctx.clip();           // leaves by a wipe upward into its own frame
  ctx.translate(0, -up * (PH + 4));
  ctx.fillStyle = C.panel; ctx.fillRect(x, y, PW, PH);
  ctx.fillStyle = C.tabbar; ctx.fillRect(x, y, PW, TABH);
  const tabW = 36 + measure(TXT.file[0] + TXT.file[1], F.mono(18), 0.2) + 30;
  ctx.fillStyle = C.paper; ctx.fillRect(x + 25, y, tabW, TABH);
  ctx.fillStyle = C.border; ctx.fillRect(x + 25, y, 1, TABH); ctx.fillRect(x + 25 + tabW, y, 1, TABH); ctx.fillRect(x, y + TABH, PW, 1);
  ctx.fillStyle = C.gold; ctx.beginPath(); ctx.arc(x + 50, y + 25, 4.5, 0, Math.PI * 2); ctx.fill();
  const w0 = drawText(TXT.file[0], x + 68, y + 30, F.mono(18), C.ink2, { ls: 0.2 });
  drawText(TXT.file[1], x + 68 + w0, y + 30, F.mono(18), C.ink, { ls: 0.2 });
  drawText(TXT.verbatim, x + PW - 22, y + 29, F.mono(14), C.ink2, { align: 'right', ls: 1.6 });
  const hl = HL_LINE(t);
  CODE.lines.forEach((s, k) => {
    const by = y + TABH + 16 + 25 + k * LH;
    if (k === hl) { ctx.fillStyle = C.hl; ctx.fillRect(x, by - 25, PW, LH); ctx.fillStyle = C.gold; ctx.fillRect(x, by - 25, 7, LH); }
    let cx = x + 34;
    for (const [tx, col, wt] of tokens(s)) cx += drawText(tx, cx, by, F.mono(24, wt), col);
  });
  ctx.fillStyle = C.border; ctx.fillRect(x, y, PW, 1); ctx.fillRect(x, y + PH - 1, PW, 1); ctx.fillRect(x, y, 1, PH); ctx.fillRect(x + PW - 1, y, 1, PH);
  ctx.restore();
  if (t >= b(K.panel + 1) && t < b(K.panelOut))
    CODE.lines.forEach((s, k) => readable('code' + k, s.trim(), PX + 34, PY + TABH + 16 + k * LH, PX + 34 + measure(s, F.mono(24)), PY + TABH + 16 + (k + 1) * LH));
}

// ---------- the ledger: seven reply cards ----------
const fire = { ooo: K.ooo, stop: K.stop, hot: K.hot };
const resB = { ooo: K.oooRes, stop: K.stop + 0.5, hot: K.hot + 0.5 };
const ROWH = 64;
function check(x, y, s, col) { ctx.strokeStyle = col; ctx.lineWidth = 2.4; ctx.lineCap = 'square'; ctx.beginPath(); ctx.moveTo(x, y - s * 0.45); ctx.lineTo(x + s * 0.35, y - s * 0.1); ctx.lineTo(x + s, y - s * 0.9); ctx.stroke(); ctx.lineCap = 'butt'; }
function ledger(t, lay) {
  const knife = lin(t, K.knife, 0.25), collapse = ez(t, K.knife + 0.25, 0.5);
  if (collapse >= 1) return;
  // the label, once
  const labIn = K.label;
  line(t, labIn, null, TXT.label, 96, lay.lab, F.mono(15), C.ink2, { size: 15, ls: 1.6 })
    && t < b(K.knife) && readable('label', TXT.label, 96, lay.lab - 14, 96 + measure(TXT.label, F.mono(15), 1.6), lay.lab + 4);
  const dimP = ez(t, K.reflowD, 1);
  const order = [...CARDS.keys()].sort((p, q) => (CARDS[p].kind === 'rest') - (CARDS[q].kind === 'rest') || 0).reverse();
  order.forEach(i => { const c = CARDS[i];
    const arrive = K.card0 + i * 0.5; if (t < b(arrive)) return;
    const y = lay.ly + slot(i, t) * lay.pitch, x = 96, w = 888;
    const grow = ez(t, arrive, 0.5);                                     // wipes down out of the ribbon
    const hgt = ROWH * grow * (1 - collapse), top = y + (ROWH - hgt) * (collapse > 0 ? 0.5 : 0);
    ctx.save(); ctx.beginPath(); ctx.rect(x - 2, top, w + 4, hgt + 1); ctx.clip();
    const fb = fire[c.kind], lit = fb != null && t >= b(fb) && t < b(resB[c.kind] + 0.5);
    ctx.fillStyle = lit ? C.hl : C.card; ctx.fillRect(x, y, w, ROWH);
    ctx.strokeStyle = C.cardEdge; ctx.lineWidth = 1; ctx.strokeRect(x + 0.5, y + 0.5, w - 1, ROWH - 1);
    const sorted = fb != null && t >= b(fb);
    const rest = c.kind === 'rest' && t >= b(K.crm + 0.25 * CARDS.filter((d, j) => d.kind === 'rest' && j < i).length);
    if (sorted) { ctx.fillStyle = C.gold; ctx.fillRect(x, y, 7, ROWH); }
    if (rest) { ctx.fillStyle = C.ink; ctx.fillRect(x, y, 7, ROWH); }
    const dim = sorted ? dimP : 0, txtCol = dim > 0.5 ? C.ink2 : C.ink;
    drawText(c.text, x + 24, y + 28, F.sans(25, 500), txtCol);
    let res = null;
    if (sorted) {
      const r0 = resB[c.kind];
      res = RESULT[c.kind];
      if (t >= b(r0)) {
        const p = ez(t, r0, 0.5), rw = measure(res, F.mono(19));
        ctx.save(); ctx.beginPath(); ctx.rect(x + 22, y + 36, (rw + 6) * p, 24); ctx.clip();      // stamped left to right
        drawText(res, x + 24, y + 53, F.mono(19), dim > 0.5 ? C.ink2 : C.ink);
        if (RULE_TAG[c.kind]) drawText(RULE_TAG[c.kind], x + w - 20, y + 53, F.mono(17), C.ink2, { align: 'right' });
        ctx.restore();
        if (p >= 1 && t < b(K.knife)) readable('res' + i, res, x + 24, y + 38, x + 24 + rw, y + 58);
      }
    }
    if (rest) {
      const k = CARDS.filter((d, j) => d.kind === 'rest' && j < i).length, r0 = K.crm + 0.25 * k, p = ez(t, r0, 0.25);
      ctx.save(); ctx.beginPath(); ctx.rect(x + 20, y + 58 - 22 * p, 300, 24); ctx.clip();
      check(x + 25, y + 53, 15, C.ink);
      drawText(TXT.crm, x + 50, y + 53, F.mono(19), C.ink);
      ctx.restore();
      if (p >= 1 && t < b(K.knife)) readable('crm' + i, TXT.crm, x + 50, y + 38, x + 50 + measure(TXT.crm, F.mono(19)), y + 58);
    }
    ctx.restore();
    if (grow >= 1 && t < b(K.knife)) readable('card' + i, c.text, x + 24, y + 6, x + 24 + measure(c.text, F.sans(25, 500)), y + 34);
    // knife cut: a line runs through the card's midline, then the card collapses onto it
    if (knife > 0 && collapse < 1) {
      const kd = clamp(knife * 1.6 - slot(i, t) * 0.1);
      ctx.fillStyle = C.ink; ctx.fillRect(x, y + ROWH / 2 - 1, w * kd, 2);
    }
  });
}

// ---------- scenes ----------
const HEAD = (() => { const q = new URLSearchParams(location.search); return { size: +(q.get('hs') || 93), w: +(q.get('hw') || 500), ls: +(q.get('hl') || -2.86), x: 96 }; })();
function headline(t, alpha = 1) {
  if (t >= b(K.headOut + 0.5)) return;
  ctx.globalAlpha = alpha;
  const a = line(t, -1, K.headOut, TXT.head[0], HEAD.x, 231, F.disp(HEAD.size, HEAD.w), C.ink, { size: HEAD.size, ls: HEAD.ls });
  line(t, -1, K.headOut, TXT.head[1], HEAD.x, 327, F.disp(HEAD.size, HEAD.w), C.ink, { size: HEAD.size, ls: HEAD.ls });
  ctx.globalAlpha = 1;
  if (a && t < b(K.headOut)) readable('head', TXT.head.join(' '), 96, 150, 984, 350);
}
function inboxes(t, lay, alpha = 1) {
  ctx.globalAlpha = alpha;
  const knifeP = lin(t, K.knifeRibbon, 0.25), gone = ez(t, K.knifeRibbon + 0.25, 0.25);
  if (gone >= 1) { ctx.globalAlpha = 1; return; }
  for (let i = 0; i < 32; i++) {
    const g = GRID(i), r = RIB(i, lay.ry), col = i % 8, row = Math.floor(i / 8);
    const p = ez(t, K.ribbon + (col + row) * 0.0625, 0.5);              // ripple from the top-left tile
    const box = { x: lerp(g.x, r.x, p), y: lerp(g.y, r.y, p), w: lerp(g.w, r.w, p), h: lerp(g.h, r.h, p) };
    if (gone > 0) { const hh = box.h * (1 - gone); box.y += (box.h - hh) / 2; box.h = hh; }
    envelope(box, tileLit(i, t), lerp(2, 1.5, p));
  }
  if (knifeP > 0) { ctx.fillStyle = C.ink; ctx.fillRect(96, lay.ry + 8, 888 * knifeP, 2); }
  ctx.globalAlpha = 1;
}
function inboxesEnd(t) {
  if (t < b(K.out + 0.5)) return;
  for (let i = 0; i < 32; i++) {
    const g = GRID(i), col = i % 8, row = Math.floor(i / 8), p = ez(t, K.out + 0.5 + (col + row) * 0.0625, 0.5);
    if (p <= 0) continue;
    ctx.save(); ctx.beginPath(); ctx.rect(g.x - 2, g.y - 2, g.w + 4, (g.h + 4) * p); ctx.clip();
    envelope(g, false, 2); ctx.restore();
  }
}
function f05(t, lay) {
  if (t < b(K.f05) || t >= b(K.f05Out + 0.5)) return;
  const y = lay.f05, grow = ez(t, K.f05, 0.5), up = ez(t, K.f05Out, 0.5);
  ctx.save(); ctx.beginPath(); ctx.rect(90, y - 4, 900, 8); ctx.clip();
  const read = lin(t, K.f05 + 1, K.f05Out - K.f05 - 1.5);
  ctx.fillStyle = C.gold; ctx.fillRect(96, y - up * 8, 64 * grow + (888 - 64) * read, 3); ctx.restore();
  const a = line(t, K.f05 + 0.25, K.f05Out, TXT.f05[0], 92, y + 58, F.ital(46), C.ink, { size: 46 });
  const c = line(t, K.f05 + 0.5, K.f05Out, TXT.f05[1], 96, y + 112, F.ital(46), C.ink, { size: 46 });
  if (a && c && t < b(K.f05Out)) readable('f05', TXT.f05.join(' '), 92, y + 14, 92 + measure(TXT.f05[1], F.ital(46)), y + 126);
}
function headings(t) {
  if (line(t, K.rules, K.rulesOut, TXT.rules, 96, 205, F.disp(64, 600), C.ink, { size: 64, ls: -1.2 }) && t < b(K.rulesOut))
    readable('rules', TXT.rules, 96, 150, 96 + measure(TXT.rules, F.disp(64, 600), -1.2), 215);
  if (line(t, K.f15, K.f15Out, TXT.f15, 96, 205, F.disp(46, 500), C.ink, { size: 46, ls: -0.6 }) && t < b(K.f15Out))
    readable('f15', TXT.f15, 96, 160, 96 + measure(TXT.f15, F.disp(46, 500), -0.6), 215);
}
function reframe(t) {
  if (t < b(K.f19) || t >= b(K.out + 0.5)) return;
  const f = F.disp(84, 600);
  const ok = TXT.f19.map((s, k) => line(t, K.f19 + k * 0.5, K.out, s, 96, 268 + k * 92, f, C.ink, { size: 84, ls: -1.8 }));
  if (ok.every(Boolean) && t < b(K.out)) readable('f19', TXT.f19.join(' '), 96, 190, 984, 470);
  // F18: scale contrast, a giant range next to small text
  const a = line(t, K.f18, K.out, TXT.f18a, 96, 600, F.text(40, 400), C.ink, { size: 40 });
  const n = line(t, K.f18, K.out, TXT.f18n, 90, 840, F.disp(250, 600), C.ink, { size: 250, ls: -6 });
  const c = line(t, K.f18 + 0.25, K.out, TXT.f18b, 96, 920, F.text(44, 400), C.ink, { size: 44 });
  const d = line(t, K.f18 + 0.5, K.out, TXT.f18c, 96, 976, F.text(44, 400), C.ink, { size: 44 });
  if (a && n && c && d && t < b(K.out)) readable('f18', [TXT.f18a, TXT.f18n, TXT.f18b, TXT.f18c].join(' '), 90, 560, 984, 990);
  if (t >= b(K.f18Rule)) {   // the one linear element: a gold rule draws itself while the viewer reads
    const p = lin(t, K.f18Rule, K.out - 0.5 - K.f18Rule), up = ez(t, K.out, 0.5);
    ctx.save(); ctx.beginPath(); ctx.rect(90, 1012, 900, 8); ctx.clip();
    ctx.fillStyle = C.gold; ctx.fillRect(96, 1014 - up * 8, 888 * p, 3); ctx.restore();
  }
}
function credits(t, alpha = 1) {
  if (t < b(K.credits)) return;
  ctx.globalAlpha = alpha;
  const a = line(t, K.credits, null, TXT.credits[0], 96, 1132, F.mono(15), C.ink2, { size: 15, ls: 1.2 });
  const c = line(t, K.credits + 0.5, null, TXT.credits[1], 96, 1162, F.mono(15), C.ink2, { size: 15, ls: 1.2 });
  ctx.globalAlpha = 1;
  if (alpha >= 1) {
    if (a) readable('cred0', TXT.credits[0], 96, 1116, 96 + measure(TXT.credits[0], F.mono(15), 1.2), 1138);
    if (c) readable('cred1', TXT.credits[1], 96, 1146, 96 + measure(TXT.credits[1], F.mono(15), 1.2), 1168);
  }
}

// ---------- render(t) ----------
window.render = t => {
  DRAWN = []; TX = [];
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1;
  ctx.fillStyle = C.paper; ctx.fillRect(0, 0, W, H);
  chrome();
  const lay = layout(t);
  const loopP = clamp((t - b(K.loop)) / (DUR - b(K.loop)));    // last half beat: dissolve into frame 0 (seamless loop)
  if (loopP > 0) {
    credits(t, 1 - loopP); inboxesEnd(t);
    headline(0, loopP);
  } else {
    headline(t); inboxes(t, lay); f05(t, lay); headings(t); panel(t); ledger(t, lay); reframe(t); credits(t); inboxesEnd(t);
  }
  window.__DRAWN = DRAWN; window.__TEXTS = TX;
};
window.TEXTS = t => { window.render(t); return window.__TEXTS; };

// ---------- sound events for mix.py (same numbers as the picture) ----------
const EV = [];
const ev = (beat, type, o = {}) => EV.push({ t: b(beat), beat, type, ...o });
ev(K.ribbon, 'slide', { v: 0.5 });
CARDS.forEach((c, i) => ev(K.card0 + i * 0.5, 'card', { i }));
LIGHT_ORDER.forEach((tile, k) => ev(K.lights + k * 0.25 * 32 / LIGHT_ORDER.length, 'light', { k }));
ev(K.f05, 'rule'); ev(K.headOut, 'slide', { v: 0.35 }); ev(K.reflowUp, 'slide', { v: 0.3 });
ev(K.knifeRibbon, 'knife'); ev(K.panel, 'panel'); ev(K.panel + 1, 'land');
ev(K.ooo, 'fire', { kind: 'ooo' }); ev(K.oooRes, 'stamp', { n: 2 }); ev(K.oooSort, 'slide', { v: 0.3 });
ev(K.stop, 'fire', { kind: 'stop' }); ev(K.stop + 0.5, 'stamp', { n: 1 }); ev(K.stopSort, 'slide', { v: 0.3 });
ev(K.hot, 'fire', { kind: 'hot' }); ev(K.hot + 0.5, 'stamp', { n: 1 }); ev(K.hotSort, 'slide', { v: 0.3 });
ev(K.panelOut, 'slide', { v: 0.45 });
[0, 1, 2].forEach(k => ev(K.crm + 0.25 * k, 'crm', { k }));
ev(K.knife, 'knife'); ev(K.f19, 'land'); ev(K.f18, 'thunk'); ev(K.out, 'slide', { v: 0.35 }); ev(K.out + 0.5, 'slide', { v: 0.25 });
window.EV = EV;

await document.fonts.ready;
for (const f of ['500 20px NRD500', '600 20px NRD600', '400 20px NRT400', '500 20px NRT500', 'italic 400 20px NRI', '400 20px JBM', '700 20px JBM', '500 20px GEI'])
  await document.fonts.load(f, 'ProdCraft·–€“”0123');
window.render(0);
window.READY = true;
