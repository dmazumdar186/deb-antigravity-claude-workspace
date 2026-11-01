// ProdCraft Notes film page (house style prodcraft-notes, based on swiss-motion). 1080×1350, 30 fps, Canvas 2D.
// Everything that changes per week comes from content.json; everything that stays comes from house.js.
// Deterministic: the frame is a pure function of t. Every glyph goes through drawText(), which logs it
// (window.__DRAWN) only when some of it is inside the current clip and alpha > 0, so the manifest matches the pixels.
import { clamp, lerp, seg } from '/core/lib.js';
import { b, W, H, GRID, SAFE, C, TYPE, CHROME, CARD, PANEL, TILE } from './house.js';

const cv = document.getElementById('c'), ctx = cv.getContext('2d');
const S = await (await fetch('content.json')).json();
const CODE = await (await fetch('out/code.json')).json();            // verbatim lines (tools/code.py)
const K = S.beats, DUR = b(S.meta.dur_beats);
const LOGO = new Image(); LOGO.src = 'assets/logo-prodcraft.png'; await LOGO.decode();
window.DUR = DUR;

// ---------- type ----------
const FAM = { NRD500: '500 {}px NRD500', NRD600: '600 {}px NRD600', NRT400: '400 {}px NRT400', NRT500: '500 {}px NRT500',
  NRI: 'italic 400 {}px NRI', JBM400: '400 {}px JBM', JBM700: '700 {}px JBM' };
const font = (key, px) => { const [f, size] = TYPE[key]; return FAM[f].replace('{}', px ?? size); };
const size = key => TYPE[key][1], ls = key => TYPE[key][2];

// ---------- motion: cubic-bezier(.7,0,.2,1) for snaps, linear for lines that draw themselves ----------
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
const ez = (t, beat, dur = 0.5) => EZ(seg(t, b(beat), b(beat + dur)));
const lin = (t, beat, dur) => seg(t, b(beat), b(beat + dur));

// ---------- clip stack in screen space (translate/scale only) ----------
let CLIP = [0, 0, W, H];
const CLIPS = [];
function pushClip(x, y, w, h) {
  const m = ctx.getTransform();
  const r = [m.a * x + m.e, m.d * y + m.f, m.a * (x + w) + m.e, m.d * (y + h) + m.f];
  CLIPS.push(CLIP); CLIP = [Math.max(CLIP[0], r[0]), Math.max(CLIP[1], r[1]), Math.min(CLIP[2], r[2]), Math.min(CLIP[3], r[3])];
  ctx.save(); ctx.beginPath(); ctx.rect(x, y, w, h); ctx.clip();
}
function popClip() { ctx.restore(); CLIP = CLIPS.pop(); }

// ---------- the one text path: draw + log what is actually visible ----------
let DRAWN = [], TX = [];
function drawText(s, x, y, fnt, color, { align = 'left', ls: sp = 0 } = {}) {
  if (!s) return 0;
  ctx.font = fnt; ctx.letterSpacing = sp + 'px';
  const w = ctx.measureText(s).width;
  const a = ctx.globalAlpha;
  if (a >= 0.02) {
    ctx.fillStyle = color; ctx.textAlign = align;
    ctx.fillText(s, x, y);
    const m = ctx.getTransform(), k = Math.hypot(m.a, m.b), px = parseFloat(fnt.split(' ').find(p => p.endsWith('px')));
    const x0 = align === 'right' ? x - w : x;
    const bx0 = m.a * x0 + m.e, bx1 = m.a * (x0 + w) + m.e, by0 = m.d * (y - px * 0.8) + m.f, by1 = m.d * (y + px * 0.22) + m.f;
    const ix = Math.min(bx1, CLIP[2]) - Math.max(bx0, CLIP[0]), iy = Math.min(by1, CLIP[3]) - Math.max(by0, CLIP[1]);
    const vis = ix > 0 && iy > 0 && bx1 > 0 && bx0 < W && by1 > 0 && by0 < H;
    if (vis) DRAWN.push({ text: s, x: Math.round(m.a * x + m.e), y: Math.round(m.d * y + m.f), px: +(px * k).toFixed(1), a: +a.toFixed(2),
      vis: +clamp((ix * iy) / ((bx1 - bx0) * (by1 - by0))).toFixed(2) });
  }
  ctx.textAlign = 'left'; ctx.letterSpacing = '0px';
  return w;
}
const measure = (s, fnt, sp = 0) => { ctx.font = fnt; ctx.letterSpacing = sp + 'px'; const w = ctx.measureText(s).width; ctx.letterSpacing = '0px'; return w; };
const readable = (id, text, x0, y0, x1, y1) => TX.push({ id, text, x0: Math.round(x0), y0: Math.round(y0), x1: Math.round(x1), y1: Math.round(y1) });

// clip-reveal: a line rises out of its own slot (in) and leaves upward (out); the slot never reaches above the
// header's safe line, so exits cannot run through the header (QA D6/D8). Returns true when fully in place.
function line(t, inB, outB, s, x, y, key, color, { align = 'left', dur = 0.5, outDur = 0.5, px } = {}) {
  if (t < b(inB)) return false;
  if (outB != null && t >= b(outB + outDur)) return false;
  const sz = px ?? size(key), f = font(key, sz), sp = ls(key);
  const p = ez(t, inB, dur), q = outB != null ? ez(t, outB, outDur) : 0;
  const hgt = sz * 1.32, top = Math.max(y - sz * 1.0, SAFE.content_y0);
  const dy = (1 - p) * hgt - q * hgt;
  const w = measure(s, f, sp), x0 = align === 'right' ? x - w : x;
  pushClip(x0 - 12, top, w + 24, y + sz * 0.32 - top);
  drawText(s, x, y + dy, f, color, { align, ls: sp });
  popClip();
  return p >= 1 && q <= 0;
}

// ---------- chrome: the card's header and footer ----------
const LOGO_INK = (() => {   // the card prints the mark in ink with its light details kept: tone-map by darkness, keep alpha
  const o = document.createElement('canvas'); o.width = o.height = 512; const g = o.getContext('2d'); g.drawImage(LOGO, 0, 0);
  const d = g.getImageData(0, 0, 512, 512), p = d.data, [lo, hi] = CHROME.logo.levels, k = CHROME.logo.sat_k;
  const ink = [0x16, 0x18, 0x1c], paper = [0xEF, 0xED, 0xE8];
  for (let i = 0; i < p.length; i += 4) {
    const mx = Math.max(p[i], p[i + 1], p[i + 2]) / 255, mn = Math.min(p[i], p[i + 1], p[i + 2]) / 255;
    const sat = mx > 0 ? (mx - mn) / mx : 0, v = clamp((mn * (1 - k * sat) - lo) / (hi - lo));
    for (let c = 0; c < 3; c++) p[i + c] = Math.round(ink[c] + v * (paper[c] - ink[c]));
  }
  g.putImageData(d, 0, 0); return o;
})();
function chrome() {
  const L = CHROME.logo, s = L.size / 512;
  ctx.drawImage(LOGO_INK, L.ink_x0 - L.src_ink_x0 * s, L.ink_y0 - L.src_ink_y0 * s, 512 * s, 512 * s);
  drawText('ProdCraft', CHROME.wordmark.x, CHROME.wordmark.y, font('wordmark'), C.ink, { ls: ls('wordmark') });
  drawText(S.chrome.wk, CHROME.wk.x, CHROME.wk.y, font('chrome'), C.ink2, { align: 'right', ls: ls('chrome') });
  ctx.fillStyle = C.rule; ctx.fillRect(CHROME.rule.x, CHROME.rule.y, CHROME.rule.w, 1);
  drawText('ProdCraft · weekly notes', CHROME.foot.x, CHROME.foot.y, font('chrome'), C.ink2, { ls: ls('chrome') });
  drawText(S.chrome.page, CHROME.page.x, CHROME.page.y, font('chrome'), C.goldT, { align: 'right', ls: ls('chrome') });
  readable('hdr-brand', 'ProdCraft', 144, 100, 260, 128); readable('hdr-wk', S.chrome.wk, 930, 114, 984, 132);
  readable('ftr', 'ProdCraft · weekly notes', 96, 1232, 340, 1252); readable('ftr-page', S.chrome.page, 960, 1232, 984, 1252);
}

// ---------- the inbox tiles: a grid on the poster, a ribbon once the replies arrive ----------
const NT = S.poster.tiles, COLS = S.poster.tile_cols, G = TILE.grid, R = TILE.ribbon;
const GRIDR = i => ({ x: G.x0 + (i % COLS) * (G.w + G.gx), y: G.y0 + Math.floor(i / COLS) * (G.h + G.gy), w: G.w, h: G.h });
const RIBR = (i, ry) => ({ x: GRID.col_x0 + i * R.pitch, y: ry, w: R.w, h: R.h });
const CARD_TILES = S.cards.map(c => c.tile);
const FREE = (() => { const o = [...Array(NT).keys()].filter(i => !CARD_TILES.includes(i)); let s = 7;
  for (let i = o.length - 1; i > 0; i--) { s = (s * 1103515245 + 12345) & 0x7fffffff; const j = s % (i + 1); [o[i], o[j]] = [o[j], o[i]]; } return o; })();
const POSTER_LIT = FREE.slice(0, K.lightCount), LATER_LIT = FREE.slice(K.lightCount);
function tileFill(i, t) {   // 0..1: how far the gold fill has wiped down
  const ci = CARD_TILES.indexOf(i);
  if (ci >= 0) return ez(t, K.card0 + ci * K.cardStep, 0.25);
  const k = POSTER_LIT.indexOf(i);
  if (k >= 0) return ez(t, K.light0 + k * K.lightStep, 0.25);
  return ez(t, K.lights + LATER_LIT.indexOf(i) * 0.25, 0.25);
}
function envelope(r, fill, lw) {
  ctx.fillStyle = C.paper; ctx.fillRect(r.x, r.y, r.w, r.h);
  if (fill > 0) { ctx.fillStyle = C.goldL; ctx.fillRect(r.x, r.y, r.w, r.h * fill); }
  ctx.strokeStyle = C.ink; ctx.lineWidth = lw; ctx.lineJoin = 'miter';
  ctx.strokeRect(r.x + lw / 2, r.y + lw / 2, r.w - lw, r.h - lw);
  ctx.beginPath(); ctx.moveTo(r.x + lw / 2, r.y + lw / 2); ctx.lineTo(r.x + r.w / 2, r.y + r.h * 0.56); ctx.lineTo(r.x + r.w - lw / 2, r.y + lw / 2); ctx.stroke();
}

// ---------- layout states: ribbon y, label baseline, ledger top, quote y ----------
const L = {
  B1: { ry: 392, lab: 448, ly: 462, q: 930 },
  B2: { ry: 202, lab: 258, ly: 272, q: 740 },
  C: { ry: 202, lab: 682, ly: 696, q: 740 },
  D: { ry: 202, lab: 330, ly: 344, q: 740 },
};
function layout(t) {
  const mix = (A, B, p) => Object.fromEntries(Object.keys(A).map(k => [k, lerp(A[k], B[k], p)]));
  let s = mix(L.B1, L.B2, ez(t, K.reflowUp, 1));
  s = mix(s, L.C, ez(t, K.reflowC, K.reflowCDur ?? 1));   // done before the panel starts to slide in (no overlap)
  return mix(s, L.D, ez(t, K.reflowD, 1));
}

// ---------- the sort: one rule at a time. A caught card collapses where it is (knife), the column closes,
// it re-opens at the top of the column, then its rule tag and result stamp in. Cards never overlap. ----------
const RULE = Object.fromEntries(S.rules.map((r, k) => [r.kind, { ...r, k, at: K.sort[k] }]));
const ph = r => ({ fire: r.at, out: r.at + 0.75, swap: r.at + 1.0, in: r.at + 1.0, stamp: r.at + 1.5 });
function order(t) {   // current top-to-bottom order of the cards
  let o = S.cards.map((_, i) => i), placed = 0;
  for (const r of S.rules) {
    if (t < b(ph(RULE[r.kind]).swap)) break;
    const i = S.cards.findIndex(c => c.kind === r.kind);
    o = o.filter(j => j !== i); o.splice(placed, 0, i); placed++;
  }
  return o;
}
function presence(i, t) {
  const c = S.cards[i], arrive = K.card0 + i * K.cardStep;
  let p = ez(t, arrive, 0.5);
  const r = RULE[c.kind];
  if (r) { const P = ph(r); if (t >= b(P.out) && t < b(P.in)) p = 1 - ez(t, P.out, 0.25); else if (t >= b(P.in)) p = ez(t, P.in, 0.5); }
  return p;
}
const chipLines = c => (RULE[c.kind] ? RULE[c.kind].result.length : 0);
const fullH = c => CARD.h + (chipLines(c) ? chipLines(c) * CARD.chip_h + CARD.pad_b : 0);
function cardH(i, t) {   // the result rows open as the stamp lands
  const c = S.cards[i], r = RULE[c.kind];
  if (!r) return CARD.h;
  return CARD.h + (fullH(c) - CARD.h) * ez(t, ph(r).stamp, 0.5);
}
const GROUP_H = 52;
function ledger(t, lay) {
  const knife = lin(t, K.knife, 0.25), collapse = ez(t, K.knife + 0.25, 0.5);
  if (collapse >= 1) return;
  // label, once
  if (line(t, K.label, null, S.label.text, GRID.col_x0, lay.lab, 'label', C.ink2) && t < b(K.knife))
    readable('label', S.label.text, GRID.col_x0, lay.lab - 26, GRID.col_x0 + measure(S.label.text, font('label'), ls('label')), lay.lab + 6);
  const ord = order(t), dim = ez(t, K.reflowD, 1), groupP = ez(t, K.group, 0.5);
  const lastRule = S.rules.length;   // the group row sits after the caught cards
  let y = lay.ly, rows = [];
  ord.forEach((i, pos) => {
    if (pos === lastRule && groupP > 0) { rows.push({ group: true, y, p: groupP }); y += (GROUP_H + CARD.gap) * groupP; }
    const p = presence(i, t); if (p <= 0) return;
    const h = cardH(i, t);
    rows.push({ i, y, p, h }); y += (h + CARD.gap) * p;
  });
  const x = GRID.col_x0, w = GRID.col_w;
  for (const r of rows) {
    if (r.group) { group(t, x, r.y, w, r.p, knife, collapse); continue; }
    const c = S.cards[r.i], rule = RULE[c.kind], P = rule && ph(rule);
    const vis = r.h * r.p * (1 - collapse);
    const top = collapse > 0 ? r.y + (r.h - vis) / 2 : (rule && t >= b(P.out) && t < b(P.in)) ? r.y + (r.h - vis) / 2 : r.y;
    if (vis < 0.5) continue;
    pushClip(x - 2, top, w + 4, vis + 1);
    const lit = rule && t >= b(P.fire) && t < b(P.stamp + 0.5);
    ctx.fillStyle = lit ? C.hl : C.card; ctx.fillRect(x, r.y, w, r.h);
    ctx.strokeStyle = C.cardEdge; ctx.lineWidth = 1; ctx.strokeRect(x + 0.5, r.y + 0.5, w - 1, r.h - 1);
    const caught = rule && t >= b(P.fire), routed = !rule && t >= b(K.group);
    if (caught) { ctx.fillStyle = C.gold; ctx.fillRect(x, r.y, CARD.bar, r.h); }
    if (routed) { ctx.fillStyle = C.ink; ctx.fillRect(x, r.y, CARD.bar, r.h); }
    const txtCol = caught && dim > 0.5 ? C.ink2 : C.ink;
    drawText(c.text, x + CARD.inset, r.y + CARD.text_dy, font('card'), txtCol);
    if (caught && t >= b(P.stamp)) {
      const p = ez(t, P.stamp, 0.5), fT = font('chip'), tw = measure(rule.tag, fT);
      // rule tag (which pattern list fired), right-aligned on the card's first line, its own wipe
      pushClip(x + w - 20 - tw * p, r.y + 6, tw * p + 2, 44);
      drawText(rule.tag, x + w - 20, r.y + CARD.text_dy, fT, C.goldT, { align: 'right' });
      popClip();
      rule.result.forEach((s, k) => {
        const rw = measure(s, fT), q = ez(t, P.stamp + 0.125 * k, 0.5);
        if (q <= 0) return;
        pushClip(x + CARD.inset - 2, r.y + CARD.h + k * CARD.chip_h - 4, rw * q + 2, CARD.chip_h);
        drawText(s, x + CARD.inset, r.y + CARD.chip_dy + k * CARD.chip_h, fT, dim > 0.5 ? C.ink2 : C.ink);
        popClip();
      });
      const done = ez(t, P.stamp + 0.125 * (rule.result.length - 1), 0.5) >= 1 && r.p >= 1;
      if (done && t < b(K.knife)) {
        readable('tag-' + c.kind, rule.tag, x + w - 20 - tw, r.y + 12, x + w - 20, r.y + 46);
        readable('res-' + c.kind, rule.result.join(' '), x + CARD.inset, r.y + CARD.h, x + CARD.inset + Math.max(...rule.result.map(s => measure(s, fT))), r.y + r.h - 2);
      }
    }
    popClip();
    if (r.p >= 1 && t < b(K.knife) && collapse <= 0)
      readable('card' + r.i, c.text, x + CARD.inset, r.y + 10, x + CARD.inset + measure(c.text, font('card')), r.y + 48);
    if (knife > 0) { ctx.fillStyle = C.ink; ctx.fillRect(x, r.y - CARD.gap / 2 - 1, w * knife, 2); }   // in the gap above the card, not through its text
  }
}
function logShape(text, x0, y0, x1, y1, px) {   // a path that reads as a character (e.g. ✓): logged like drawText when visible
  const m = ctx.getTransform(), a = ctx.globalAlpha;
  const bx0 = m.a * x0 + m.e, bx1 = m.a * x1 + m.e, by0 = m.d * y0 + m.f, by1 = m.d * y1 + m.f;
  const ix = Math.min(bx1, CLIP[2]) - Math.max(bx0, CLIP[0]), iy = Math.min(by1, CLIP[3]) - Math.max(by0, CLIP[1]);
  if (a >= 0.02 && ix > 0 && iy > 0) DRAWN.push({ text, x: Math.round(bx0), y: Math.round(by1), px, a: +a.toFixed(2), vis: +clamp((ix * iy) / ((bx1 - bx0) * (by1 - by0))).toFixed(2), shape: true });
}
function check(x, y, s, col) {
  logShape('✓', x - 2, y - s - 2, x + s + 2, y + 2, size('chip')); ctx.strokeStyle = col; ctx.lineWidth = 3; ctx.lineCap = 'square'; ctx.beginPath(); ctx.moveTo(x, y - s * 0.45); ctx.lineTo(x + s * 0.35, y - s * 0.1); ctx.lineTo(x + s, y - s * 0.9); ctx.stroke(); ctx.lineCap = 'butt'; }
function group(t, x, y, w, p, knife, collapse) {   // the routed group: one label and one shared CRM tick
  const h = GROUP_H * p * (1 - collapse); if (h < 0.5) return;
  pushClip(x - 2, collapse > 0 ? y + (GROUP_H - h) / 2 : y, w + 4, h);
  drawText(S.routing.label, x + 2, y + 36, font('group'), C.ink);
  const cp = ez(t, K.crm, 0.25), fT = font('chip'), cw = measure(S.routing.crm, fT);
  if (cp > 0) {
    pushClip(x + w - cw - 60, y + 36 - 40 + 40 * (1 - cp), cw + 64, 52);
    check(x + w - cw - 50, y + 34, 22, C.ink); drawText(S.routing.crm, x + w - 4, y + 36, fT, C.ink, { align: 'right' });
    popClip();
  }
  popClip();
  if (knife > 0) { ctx.fillStyle = C.ink; ctx.fillRect(x, y - CARD.gap / 2 - 1, w * knife, 2); }
  if (p >= 1 && t < b(K.knife) && collapse <= 0) {
    readable('group', S.routing.label, x + 2, y + 8, x + 2 + measure(S.routing.label, font('group')), y + 44);
    if (cp >= 1) readable('crm', S.routing.crm, x + w - 4 - cw, y + 8, x + w - 4, y + 44);
  }
}

// ---------- the code panel: verbatim (F21), 1-space re-indent per level to fit 30 px; the gold bar marks the line that fired ----------
const PH = PANEL.tab_h + PANEL.pad_t + CODE.lines.length * PANEL.lh + PANEL.pad_b, PY = 222;
function tokens(s) {
  const out = []; const re = /("[^"]*")|(\b(?:if|return)\b)|([^"]+?(?=("|\bif\b|\breturn\b|$)))/g; let m;
  while ((m = re.exec(s)) && m[0]) out.push(m[1] ? [m[1], C.blue, 'code'] : m[2] ? [m[2], C.ink, 'code_kw'] : [m[3], C.ink, 'code']);
  return out;
}
CODE.shown.forEach(s => { if (tokens(s).map(x => x[0]).join('') !== s) throw new Error('tokenizer altered a code line: ' + s); });
function hlLine(t) {   // OOO lines only while the OOO rule is the one firing; no bar for the other rules
  const r = RULE.ooo; if (!r) return -1;
  const next = S.rules[r.k + 1] ? K.sort[r.k + 1] : 1e9;
  if (t >= b(next)) return -1;
  if (t >= b(r.at + 0.5)) return r.code_lines[1];
  if (t >= b(r.at)) return r.code_lines[0];
  return -1;
}
function panel(t) {
  if (t < b(K.panel) || t >= b(K.panelOut + 0.5)) return;
  const xin = (1 - ez(t, K.panel, K.panelIn)) * (W - PANEL.x + 8), up = ez(t, K.panelOut, 0.5);
  const x = PANEL.x + xin, y = PY;
  pushClip(0, PY - 2, W, PH + 4);
  ctx.translate(0, -up * (PH + 4));
  ctx.fillStyle = C.panel; ctx.fillRect(x, y, PANEL.w, PH);
  ctx.fillStyle = C.paper; ctx.fillRect(x, y, PANEL.w, PANEL.tab_h);
  ctx.fillStyle = C.border; ctx.fillRect(x, y + PANEL.tab_h, PANEL.w, 1);
  ctx.fillStyle = C.gold; ctx.beginPath(); ctx.arc(x + 16, y + PANEL.tab_h / 2, 5, 0, Math.PI * 2); ctx.fill();
  drawText(S.code.tab, x + 30, y + 35, font('tab'), C.ink2, { ls: ls('tab') });
  const hl = hlLine(t);
  CODE.shown.forEach((s, k) => {
    const by = y + PANEL.tab_h + PANEL.pad_t + 28 + k * PANEL.lh;
    if (k === hl) { ctx.fillStyle = C.hl; ctx.fillRect(x, by - 29, PANEL.w, PANEL.lh); ctx.fillStyle = C.gold; ctx.fillRect(x, by - 29, PANEL.bar, PANEL.lh); }
    let cx = x + PANEL.code_x;
    for (const [tx, col, key] of tokens(s)) cx += drawText(tx, cx, by, font(key), col, { ls: ls(key) });
  });
  ctx.fillStyle = C.border; ctx.fillRect(x, y, PANEL.w, 1); ctx.fillRect(x, y + PH - 1, PANEL.w, 1); ctx.fillRect(x, y, 1, PH); ctx.fillRect(x + PANEL.w - 1, y, 1, PH);
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  popClip();
  if (t >= b(K.panel + K.panelIn) && t < b(K.panelOut)) {
    readable('tab', S.code.tab, PANEL.x + 30, PY + 8, PANEL.x + 30 + measure(S.code.tab, font('tab'), ls('tab')), PY + 44);
    CODE.shown.forEach((s, k) => readable('code' + k, s.trim(), PANEL.x + PANEL.code_x, PY + PANEL.tab_h + PANEL.pad_t + k * PANEL.lh,
      PANEL.x + PANEL.code_x + measure(s, font('code'), ls('code')), PY + PANEL.tab_h + PANEL.pad_t + (k + 1) * PANEL.lh));
  }
}

// ---------- scenes ----------
function headline(t, alpha = 1) {
  if (t >= b(K.headOut + 0.5)) return;
  ctx.globalAlpha = alpha;
  const a = line(t, -1, K.headOut, S.poster.head[0], 96, 231, 'poster', C.ink);
  line(t, -1, K.headOut, S.poster.head[1], 96, 327, 'poster', C.ink);
  ctx.globalAlpha = 1;
  if (a && t < b(K.headOut) && alpha >= 1) readable('head', S.poster.head.join(' '), 96, 150, 984, 350);
}
function inboxes(t, lay, alpha = 1) {
  ctx.globalAlpha = alpha;
  const knifeP = lin(t, K.knifeRibbon, 0.25), gone = ez(t, K.knifeRibbon + 0.25, 0.25);
  if (gone < 1) {
    for (let i = 0; i < NT; i++) {
      const g = GRIDR(i), r = RIBR(i, lay.ry), col = i % COLS, row = Math.floor(i / COLS);
      const p = ez(t, K.ribbon + (col + row) * 0.0625, 0.5);
      const box = { x: lerp(g.x, r.x, p), y: lerp(g.y, r.y, p), w: lerp(g.w, r.w, p), h: lerp(g.h, r.h, p) };
      if (gone > 0) { const hh = box.h * (1 - gone); box.y += (box.h - hh) / 2; box.h = hh; }
      envelope(box, tileFill(i, t), lerp(2, 1.5, p));
    }
    if (knifeP > 0) { ctx.fillStyle = C.ink; ctx.fillRect(96, lay.ry + 8, 888 * knifeP, 2); }
  }
  ctx.globalAlpha = 1;
}
function inboxesEnd(t) {
  if (t < b(K.out + 0.5)) return;
  for (let i = 0; i < NT; i++) {
    const g = GRIDR(i), col = i % COLS, row = Math.floor(i / COLS), p = ez(t, K.out + 0.5 + (col + row) * 0.0625, 0.5);
    if (p <= 0) continue;
    ctx.save(); ctx.beginPath(); ctx.rect(g.x - 2, g.y - 2, g.w + 4, (g.h + 4) * p); ctx.clip(); envelope(g, 0, 2); ctx.restore();
  }
}
function quote(t, lay) {
  if (t < b(K.f05) || t >= b(K.f05Out + 0.5)) return;
  const y = lay.q, grow = ez(t, K.f05, 0.5), up = ez(t, K.f05Out, 0.5);
  const read = lin(t, K.f05 + 1, K.f05Out - K.f05 - 1.5);
  ctx.save(); ctx.beginPath(); ctx.rect(90, y - 4, 900, 8); ctx.clip();
  ctx.fillStyle = C.gold; ctx.fillRect(96, y - up * 8, 64 * grow + (888 - 64) * read, 3); ctx.restore();
  const a = line(t, K.f05, K.f05Out, S.quote.lines[0], 92, y + 58, 'quote', C.ink);
  const c = line(t, K.f05 + 0.25, K.f05Out, S.quote.lines[1], 96, y + 112, 'quote', C.ink);
  if (a && c && t < b(K.f05Out)) readable('f05', S.quote.lines.join(' '), 92, y + 14, 92 + measure(S.quote.lines[1], font('quote')), y + 126);
}
function headings(t) {
  const H1 = S.headings.rules, H2 = S.headings.limits;
  // one flip, in sequence: the old heading leaves (quarter beat), then the new one rises in; never both in the slot
  if (line(t, K.rules, K.limits, H1.text, 96, 200, 'heading', C.ink, { outDur: 0.25 }) && t < b(K.limits))
    readable('rules', H1.text, 96, 150, 96 + measure(H1.text, font('heading'), ls('heading')), 212);
  if (line(t, K.limits + 0.25, K.limitsOut, H2.text, 96, 200, 'heading_s', C.ink) && t < b(K.limitsOut))
    readable('limits', H2.text, 96, 170, 96 + measure(H2.text, font('heading_s'), ls('heading_s')), 210);
  if (t >= b(K.reflowD + 1) && t < b(K.limitsOut + 0.5)) {   // while the routed group holds, a gold rule draws itself (no static hold > 3 s)
    const p = lin(t, K.reflowD + 1, K.knife - K.reflowD - 1), up = ez(t, K.limitsOut, 0.5);
    ctx.save(); ctx.beginPath(); ctx.rect(90, 214, 900, 8); ctx.clip();
    ctx.fillStyle = C.gold; ctx.fillRect(96, 216 - up * 8, 888 * p, 3); ctx.restore();
  }
}
function reframe(t) {
  if (t < b(K.f19) || t >= b(K.out + 0.5)) return;
  const ok = S.reframe.lines.map((s, k) => line(t, K.f19 + k * 0.5, K.out, s, 96, 268 + k * 92, 'statement', C.ink));
  if (ok.every(Boolean) && t < b(K.out)) readable('f19', S.reframe.lines.join(' '), 96, 190, 984, 470);
  const P = S.payoff;
  const a = line(t, K.f18, K.out, P.lead, 96, 600, 'lead', C.ink);
  const n = line(t, K.f18, K.out, P.numeral, 90, 840, 'numeral', C.ink);
  const c = line(t, K.f18 + 0.25, K.out, P.lines[0], 96, 920, 'body', C.ink);
  const d = line(t, K.f18 + 0.5, K.out, P.lines[1], 96, 976, 'body', C.ink);
  if (a && n && c && d && t < b(K.out)) readable('f18', [P.lead, P.numeral, ...P.lines].join(' '), 90, 560, 984, 990);
  if (t >= b(K.f18Rule)) {
    const p = lin(t, K.f18Rule, K.out - 0.5 - K.f18Rule), up = ez(t, K.out, 0.5);
    ctx.save(); ctx.beginPath(); ctx.rect(90, 1012, 900, 8); ctx.clip();
    ctx.fillStyle = C.gold; ctx.fillRect(96, 1014 - up * 8, 888 * p, 3); ctx.restore();
  }
}
function credits(t, alpha = 1) {
  if (t < b(K.credits)) return;
  ctx.globalAlpha = alpha;
  const ys = [1130, 1162];
  const ok = S.credits.map((s, k) => line(t, K.credits + 0.5 * k, null, s, 96, ys[k], 'credits', C.ink2));
  ctx.globalAlpha = 1;
  if (alpha >= 1) S.credits.forEach((s, k) => ok[k] && readable('cred' + k, s, 96, ys[k] - 16, 96 + measure(s, font('credits'), ls('credits')), ys[k] + 5));
}

// ---------- render(t) ----------
window.render = t => {
  DRAWN = []; TX = []; CLIP = [0, 0, W, H]; CLIPS.length = 0;
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1;
  ctx.fillStyle = C.paper; ctx.fillRect(0, 0, W, H);
  chrome();
  const lay = layout(t);
  const loopP = clamp((t - b(K.loop)) / (DUR - b(K.loop)));   // last half beat: dissolve into frame 0
  if (loopP > 0) { credits(t, 1 - loopP); inboxesEnd(t); headline(0, loopP); }
  else { headline(t); inboxes(t, lay); quote(t, lay); headings(t); ledger(t, lay); panel(t); reframe(t); credits(t); inboxesEnd(t); }
  window.__DRAWN = DRAWN; window.__TEXTS = TX;
};
window.TEXTS = t => { window.render(t); return window.__TEXTS; };

// ---------- sound events for mix.py ----------
const EV = [], ev = (beat, type, o = {}) => EV.push({ t: b(beat), beat, type, ...o });
POSTER_LIT.forEach((_, k) => ev(K.light0 + k * K.lightStep, 'light', { k, v: 1.6 }));
ev(K.f05, 'rule'); ev(K.ribbon, 'slide', { v: 0.5 });
S.cards.forEach((c, i) => ev(K.card0 + i * K.cardStep, 'card', { i }));
LATER_LIT.forEach((_, k) => ev(K.lights + k * 0.25, 'light', { k }));
ev(K.headOut, 'slide', { v: 0.35 }); ev(K.reflowUp, 'slide', { v: 0.3 });
ev(K.knifeRibbon, 'knife'); ev(K.panel, 'panel'); ev(K.panel + K.panelIn, 'land');
for (const r of S.rules) { const P = ph(RULE[r.kind]); ev(P.fire, 'fire', { kind: r.kind }); ev(P.out, 'slide', { v: 0.25 }); ev(P.stamp, 'stamp', { n: r.result.length }); }
ev(K.limits, 'slide', { v: 0.3 }); ev(K.panelOut, 'slide', { v: 0.45 }); ev(K.group, 'slide', { v: 0.3 }); ev(K.crm, 'crm', { k: 0 });
ev(K.knife, 'knife'); ev(K.f19, 'land'); ev(K.f18, 'thunk'); ev(K.out, 'slide', { v: 0.35 }); ev(K.out + 0.5, 'slide', { v: 0.25 });
window.EV = EV;

await document.fonts.ready;
for (const f of ['500 20px NRD500', '600 20px NRD600', '400 20px NRT400', '500 20px NRT500', 'italic 400 20px NRI', '400 20px JBM', '700 20px JBM'])
  await document.fonts.load(f, 'ProdCraft·–€“”0123');
window.render(0);
window.READY = true;
