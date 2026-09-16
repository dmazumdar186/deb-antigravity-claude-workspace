#!/usr/bin/env node
// scripts/gen-stock.mjs
// description: Generates the template's licensing-safe "stock" imagery as
//   procedural abstract art (saturated brand-colored gradient fields + visible
//   grain + one bold geometric arc/circle, in the reference palette) using
//   pure Node — no canvas, no sharp, no downloaded photos. Encodes PNGs via
//   scripts/png-encoder.mjs. Colored per-business from business.json's
//   `primary_color` when present (falls back to a neutral default otherwise),
//   and idempotent: re-running with the same color is a fast no-op so it's
//   safe to run on every `npm run build`.
// inputs: ../business.json (optional — read for `primary_color`)
// outputs: public/stock/hero-01..04.png (1600x1000 + 800x500 variants),
//   public/stock/texture-01.png, public/stock/favicon.ico,
//   public/stock/.gen-manifest.json (idempotency marker), public/stock/LICENSE.md

import { mkdirSync, writeFileSync, readFileSync, existsSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { encodePng } from './png-encoder.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const templateRoot = path.resolve(__dirname, '..');
const outDir = path.join(templateRoot, 'public', 'stock');
mkdirSync(outDir, { recursive: true });

const DEFAULT_BRAND = '#7c5cff';
const FILES = [
  'hero-01.png',
  'hero-01-sm.png',
  'hero-02.png',
  'hero-02-sm.png',
  'hero-03.png',
  'hero-03-sm.png',
  'hero-04.png',
  'hero-04-sm.png',
  'texture-01.png',
  'favicon.ico',
];
const MANIFEST_PATH = path.join(outDir, '.gen-manifest.json');

function readBrandColor() {
  const businessPath = path.join(templateRoot, 'business.json');
  if (existsSync(businessPath)) {
    try {
      const data = JSON.parse(readFileSync(businessPath, 'utf-8'));
      if (typeof data.primary_color === 'string' && /^#[0-9a-fA-F]{6}$/.test(data.primary_color)) {
        return data.primary_color.toLowerCase();
      }
    } catch {
      // fall through to default — a malformed business.json is validated
      // (and the build failed) elsewhere; this script just needs *a* color.
    }
  }
  return DEFAULT_BRAND;
}

function isUpToDate(brandColor) {
  if (!existsSync(MANIFEST_PATH)) return false;
  let manifest;
  try {
    manifest = JSON.parse(readFileSync(MANIFEST_PATH, 'utf-8'));
  } catch {
    return false;
  }
  if (manifest.primary_color !== brandColor) return false;
  return FILES.every((f) => existsSync(path.join(outDir, f)));
}

// ---------------------------------------------------------------------------
// Color helpers
// ---------------------------------------------------------------------------

function hexToRgb(hex) {
  const clean = hex.replace('#', '');
  return [
    parseInt(clean.substring(0, 2), 16),
    parseInt(clean.substring(2, 4), 16),
    parseInt(clean.substring(4, 6), 16),
  ];
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function lerpColor(c1, c2, t) {
  return [lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t)];
}

const INK = [9, 10, 12];
const PAPER = [252, 250, 245];

// Deterministic seeded PRNG (mulberry32) so output is stable across runs.
function mulberry32(seed) {
  let a = seed;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Renders one procedural composition: a saturated diagonal gradient from the
 * brand color to a darkened brand/ink tone, 2-3 large soft radial "blooms"
 * of a lighter brand tint, one bold arc/circle with a light stroke at
 * 40-60% of the frame, and visible (but block-quantized, for compression)
 * film grain. Reads as an editorial abstract composition, not a blank card.
 */
function renderComposition(width, height, seed, variant, brandRgb) {
  const rand = mulberry32(seed);
  const buf = new Uint8Array(width * height * 3);

  const darkBrand = lerpColor(brandRgb, INK, 0.6);
  const lightTint = lerpColor(brandRgb, PAPER, 0.45);

  const angle = (variant * 41 + 25) * (Math.PI / 180);
  const dx = Math.cos(angle);
  const dy = Math.sin(angle);
  const diagNorm = width * Math.abs(dx) + height * Math.abs(dy) + 1e-6;

  // 2-3 soft radial blooms of the lighter tint, positions seeded per variant.
  const bloomCount = 2 + (variant % 2);
  const blooms = Array.from({ length: bloomCount }, () => ({
    x: width * (0.15 + rand() * 0.7),
    y: height * (0.15 + rand() * 0.7),
    r: Math.max(width, height) * (0.35 + rand() * 0.3),
    strength: 0.3 + rand() * 0.25,
  }));

  // Bold geometric element: a large arc/circle at 40-60% of the frame.
  const minDim = Math.min(width, height);
  const arcCx = width * (0.35 + 0.3 * ((variant * 0.37) % 1));
  const arcCy = height * (0.4 + 0.2 * ((variant * 0.53) % 1));
  const arcR = minDim * (0.4 + 0.2 * ((variant * 0.29) % 1));
  const strokeWidth = Math.max(4, Math.round(minDim * 0.018));
  const glowWidth = strokeWidth * 3.5;
  const fullCircle = variant % 2 === 0;
  const sweepStart = -2.6 + variant * 0.3;
  const sweepEnd = 1.9 + variant * 0.2;

  // Grain: block-quantized (one random offset per block) so texture reads as
  // visible film grain while keeping DEFLATE runs long enough to compress.
  const GRAIN_BLOCK = 6;
  const blocksX = Math.ceil(width / GRAIN_BLOCK);
  const blocksY = Math.ceil(height / GRAIN_BLOCK);
  const grainMap = new Float32Array(blocksX * blocksY);
  for (let i = 0; i < grainMap.length; i++) {
    grainMap[i] = (rand() - 0.5) * 16;
  }

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const t = Math.max(0, Math.min(1, (x * dx + y * dy) / diagNorm));
      let color = lerpColor(brandRgb, darkBrand, t);

      // Radial blooms: additive lighten toward lightTint with soft falloff.
      for (const bloom of blooms) {
        const ddx = x - bloom.x;
        const ddy = y - bloom.y;
        const dist = Math.sqrt(ddx * ddx + ddy * ddy);
        const glow = Math.max(0, 1 - dist / bloom.r);
        if (glow > 0) {
          const glowT = Math.pow(glow, 2) * bloom.strength;
          color = lerpColor(color, lightTint, glowT);
        }
      }

      // Bold arc/circle: soft outer glow band + crisp inner stroke line.
      const adx = x - arcCx;
      const ady = y - arcCy;
      const rdist = Math.sqrt(adx * adx + ady * ady);
      const ringDelta = Math.abs(rdist - arcR);
      const theta = Math.atan2(ady, adx);
      const inSweep = fullCircle || (theta > sweepStart && theta < sweepEnd);
      if (inSweep) {
        if (ringDelta < glowWidth) {
          const glowStrength = 1 - ringDelta / glowWidth;
          color = lerpColor(color, PAPER, 0.12 * glowStrength);
        }
        if (ringDelta < strokeWidth) {
          const strength = 1 - ringDelta / strokeWidth;
          color = lerpColor(color, PAPER, 0.85 * strength);
        }
      }

      // Visible grain (block-quantized, see grainMap above).
      const bx = Math.floor(x / GRAIN_BLOCK);
      const by = Math.floor(y / GRAIN_BLOCK);
      const grain = grainMap[by * blocksX + bx];
      color = [color[0] + grain, color[1] + grain, color[2] + grain];

      // Light posterization trims entropy for DEFLATE without visibly
      // banding the gradient.
      const STEP = 2;
      const idx = (y * width + x) * 3;
      buf[idx] = Math.max(0, Math.min(255, Math.round(Math.round(color[0] / STEP) * STEP)));
      buf[idx + 1] = Math.max(0, Math.min(255, Math.round(Math.round(color[1] / STEP) * STEP)));
      buf[idx + 2] = Math.max(0, Math.min(255, Math.round(Math.round(color[2] / STEP) * STEP)));
    }
  }

  return buf;
}

function writeImage(name, width, height, seed, variant, brandRgb) {
  const pixels = renderComposition(width, height, seed, variant, brandRgb);
  const png = encodePng(width, height, pixels);
  const filePath = path.join(outDir, name);
  writeFileSync(filePath, png);
  const sizeKb = statSync(filePath).size / 1024;
  console.log(`[gen-stock] wrote ${name} (${width}x${height}, ${sizeKb.toFixed(1)} KB)`);
  if (sizeKb > 250) {
    console.warn(`[gen-stock] WARNING: ${name} exceeds 250 KB budget`);
  }
}

function writeFavicon(brandRgb) {
  const size = 32;
  const pixels = renderComposition(size, size, 777, 2, brandRgb);
  const png = encodePng(size, size, pixels);

  const header = Buffer.alloc(6);
  header.writeUInt16LE(0, 0); // reserved
  header.writeUInt16LE(1, 2); // type: icon
  header.writeUInt16LE(1, 4); // 1 image

  const entry = Buffer.alloc(16);
  entry.writeUInt8(size, 0); // width
  entry.writeUInt8(size, 1); // height
  entry.writeUInt8(0, 2); // palette
  entry.writeUInt8(0, 3); // reserved
  entry.writeUInt16LE(1, 4); // color planes
  entry.writeUInt16LE(32, 6); // bits per pixel
  entry.writeUInt32LE(png.length, 8); // image data size
  entry.writeUInt32LE(header.length + entry.length, 12); // offset

  const ico = Buffer.concat([header, entry, png]);
  const icoPath = path.join(templateRoot, 'public', 'favicon.ico');
  const stockIcoPath = path.join(outDir, 'favicon.ico');
  writeFileSync(icoPath, ico);
  writeFileSync(stockIcoPath, ico);
  console.log(`[gen-stock] wrote favicon.ico (${(ico.length / 1024).toFixed(1)} KB)`);
}

function main() {
  const start = Date.now();
  const brandColor = readBrandColor();

  if (isUpToDate(brandColor)) {
    console.log(`[gen-stock] up to date for ${brandColor} — skipping (${FILES.length} files present)`);
    return;
  }

  const brandRgb = hexToRgb(brandColor);

  for (let i = 0; i < 4; i++) {
    const n = i + 1;
    const seed = 1000 + n * 97;
    writeImage(`hero-0${n}.png`, 1600, 1000, seed, i, brandRgb);
    writeImage(`hero-0${n}-sm.png`, 800, 500, seed + 1, i, brandRgb);
  }

  // One texture asset (used as a decorative fill/background element).
  writeImage('texture-01.png', 800, 500, 4242, 1, brandRgb);

  writeFavicon(brandRgb);

  writeFileSync(
    path.join(outDir, 'LICENSE.md'),
    `# Stock imagery — licensing notes

All images in this directory (\`hero-01..04.png\`, \`hero-01..04-sm.png\`,
\`texture-01.png\`, \`favicon.ico\`) are procedurally generated in-repo by
\`scripts/gen-stock.mjs\` — layered gradients in the business's brand color,
soft radial blooms, a bold geometric arc, and film grain, rendered with pure
Node stdlib (no canvas, no sharp, no external model, no downloaded or
scraped photography).

No third-party photography, stock library assets, or scraped images are
used anywhere in this template. These generated assets are owned outright
by the operator (ProdCraft) and may be reused across any number of preview
sites without licensing risk.

Regenerated automatically by \`npm run build\` (idempotent — a no-op when
\`primary_color\` hasn't changed and all files are present) or on demand
with \`npm run gen-stock\`.
`
  );
  console.log('[gen-stock] wrote LICENSE.md');

  writeFileSync(
    MANIFEST_PATH,
    JSON.stringify({ primary_color: brandColor, files: FILES, generated_at: new Date().toISOString() }, null, 2)
  );

  const elapsedMs = Date.now() - start;
  console.log(`[gen-stock] done in ${elapsedMs}ms for brand color ${brandColor}`);
}

main();
