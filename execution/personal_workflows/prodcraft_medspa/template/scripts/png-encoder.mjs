// scripts/png-encoder.mjs
// description: A minimal, dependency-free PNG encoder (no canvas/sharp — pure
//   Node stdlib: zlib for DEFLATE compression, a hand-rolled CRC32 table for
//   chunk checksums). Encodes 8-bit RGB truecolor PNGs from a flat pixel buffer.
// inputs: width, height, RGB pixel buffer (width*height*3 bytes, row-major)
// outputs: Buffer containing a valid PNG file

import zlib from 'node:zlib';

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) {
      c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
    table[n] = c >>> 0;
  }
  return table;
})();

function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) {
    c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  }
  return (c ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const typeBuf = Buffer.from(type, 'ascii');
  const lenBuf = Buffer.alloc(4);
  lenBuf.writeUInt32BE(data.length, 0);
  const crcBuf = Buffer.alloc(4);
  crcBuf.writeUInt32BE(crc32(Buffer.concat([typeBuf, data])), 0);
  return Buffer.concat([lenBuf, typeBuf, data, crcBuf]);
}

const PNG_SIGNATURE = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);

/**
 * Encodes an 8-bit RGB truecolor PNG.
 * @param {number} width
 * @param {number} height
 * @param {Uint8Array|Buffer} rgb - width*height*3 bytes, row-major, top-to-bottom
 * @returns {Buffer}
 */
export function encodePng(width, height, rgb) {
  if (rgb.length !== width * height * 3) {
    throw new Error(`encodePng: expected ${width * height * 3} bytes, got ${rgb.length}`);
  }

  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr.writeUInt8(8, 8); // bit depth
  ihdr.writeUInt8(2, 9); // color type: truecolor (RGB)
  ihdr.writeUInt8(0, 10); // compression
  ihdr.writeUInt8(0, 11); // filter
  ihdr.writeUInt8(0, 12); // interlace

  // Raw scanlines: each row picks the filter (None/Sub/Up/Average/Paeth) whose
  // output has the smallest sum of absolute signed bytes (the libpng
  // heuristic). Lossless: pixels are identical, only DEFLATE input changes.
  // Up-only output pushed hero-01 to 317 KB vs the 250 KB budget (2026-11-19).
  const stride = width * 3;
  const bpp = 3;
  const src = Buffer.isBuffer(rgb) ? rgb : Buffer.from(rgb.buffer, rgb.byteOffset, rgb.byteLength);
  const raw = Buffer.alloc((stride + 1) * height);
  const cand = [0, 1, 2, 3, 4].map(() => Buffer.alloc(stride));
  for (let y = 0; y < height; y++) {
    const cur = y * stride;
    const prev = cur - stride;
    let best = 0;
    let bestScore = Infinity;
    for (let f = 0; f <= 4; f++) {
      const out = cand[f];
      let score = 0;
      for (let i = 0; i < stride; i++) {
        const x = src[cur + i];
        const a = i >= bpp ? src[cur + i - bpp] : 0;
        const b = y > 0 ? src[prev + i] : 0;
        const c = y > 0 && i >= bpp ? src[prev + i - bpp] : 0;
        let pred = 0;
        if (f === 1) pred = a;
        else if (f === 2) pred = b;
        else if (f === 3) pred = (a + b) >> 1;
        else if (f === 4) {
          const pa = Math.abs(b - c);
          const pb = Math.abs(a - c);
          const pc = Math.abs(a + b - 2 * c);
          pred = pa <= pb && pa <= pc ? a : pb <= pc ? b : c;
        }
        const v = (x - pred) & 0xff;
        out[i] = v;
        score += v < 128 ? v : 256 - v;
      }
      if (score < bestScore) {
        bestScore = score;
        best = f;
      }
    }
    const rowStart = y * (stride + 1);
    raw[rowStart] = best;
    cand[best].copy(raw, rowStart + 1);
  }

  const idatData = zlib.deflateSync(raw, { level: 9 });

  return Buffer.concat([
    PNG_SIGNATURE,
    chunk('IHDR', ihdr),
    chunk('IDAT', idatData),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}
