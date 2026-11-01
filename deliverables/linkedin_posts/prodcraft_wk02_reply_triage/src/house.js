// ProdCraft Notes house tokens (same every week). Mirrors the tokens tables in
// execution/video/lemo_house_styles/prodcraft-notes/STYLE.md; change them there and here together.
export const FPS = 30, BPM = 112.5, BEAT = 60 / BPM;             // one beat = 16 frames
export const b = beats => +(beats * BEAT).toFixed(6);            // beats -> seconds (whole frames)
export const W = 1080, H = 1350;
export const GRID = { margin: 96, col_x0: 96, col_x1: 984, col_w: 888, bleed_x0: 44, bleed_x1: 1036 };
export const SAFE = { header_y0: 90, header_y1: 145, content_y0: 145, content_y1: 1185, footer_y0: 1200, footer_y1: 1260 };
export const C = {
  paper: '#EFEDE8', ink: '#16181c', ink2: '#464951', panel: '#E6E3DC', tabbar: '#E7E4DD', hl: '#DCD3C2',
  border: '#B8B6B1', rule: '#BEBDBA', card: '#F7F6F2', cardEdge: '#CDCAC3', blue: '#3A5A78',
  gold: '#A58239', goldL: '#C8A35C', goldT: '#7A5C22',
};
// type scale: [family face, px, letter-spacing px]. Faces are the @font-face names in index.html.
export const TYPE = {
  poster: ['NRD500', 93, -2.86],       // the card headline
  statement: ['NRD600', 84, -1.8],      // the reframe
  numeral: ['NRD600', 250, -6],         // payoff range / number
  heading: ['NRD600', 64, -1.2],        // section heading
  heading_s: ['NRD500', 34, -0.4],      // one-line statement heading
  quote: ['NRI', 46, 0],                // italic quoted line under a gold rule
  body: ['NRT400', 44, 0], lead: ['NRT400', 40, 0],
  card: ['NRT400', 32, 0],              // reply / item cards
  group: ['NRI', 32, 0],                // group label
  chip: ['JBM400', 31, 0],              // results and rule tags
  code: ['JBM400', 31, -0.6], code_kw: ['JBM700', 31, -0.6],   // 53 chars x 18.0 = 954 px, same line width as 30 px
  tab: ['JBM400', 31, -1.6],              // code panel tab (provenance)
  label: ['JBM400', 31, 0.6],           // "illustrative …" label
  wordmark: ['NRT500', 26.4, -0.2], chrome: ['JBM400', 14, 1.6], credits: ['JBM400', 18, 0.8],
};
// card chrome at the wk 02 card's measured positions
export const CHROME = {
  logo: { ink_x0: 98, ink_y0: 98, size: 37, src_ink_x0: 42, src_ink_y0: 2, levels: [0.3, 0.6], sat_k: 2 },
  wordmark: { x: 144, y: 124 }, wk: { x: 982, y: 128 }, rule: { x: 96, y: 1210, w: 888 },
  foot: { x: 96, y: 1247 }, page: { x: 982, y: 1247 },
};
// components
export const CARD = { h: 56, chip_h: 38, pad_b: 6, gap: 8, text_dy: 38, chip_dy: 84, bar: 7, inset: 24 };
export const PANEL = { x: 44, w: 992, tab_h: 50, pad_t: 14, lh: 38, pad_b: 12, code_x: 20, bar: 7 };
export const TILE = { grid: { x0: 96, y0: 500, w: 97, h: 80, gx: 16, gy: 16 }, ribbon: { w: 23.75, h: 18, pitch: 27.75 } };
