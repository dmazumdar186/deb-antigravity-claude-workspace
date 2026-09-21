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

  // Raw scanlines: row 0 uses filter type None, subsequent rows use filter
  // type Up (byte = raw - prior, mod 256) which compresses our smooth
  // gradient content far better than None does.
  const stride = width * 3;
  const src = Buffer.isBuffer(rgb) ? rgb : Buffer.from(rgb.buffer, rgb.byteOffset, rgb.byteLength);
  const raw = Buffer.alloc((stride + 1) * height);
  for (let y = 0; y < height; y++) {
    const rowStart = y * (stride + 1);
    const srcStart = y * stride;
    if (y === 0) {
      raw[rowStart] = 0; // None
      src.copy(raw, rowStart + 1, srcStart, srcStart + stride);
    } else {
      raw[rowStart] = 2; // Up
      const priorStart = srcStart - stride;
      for (let i = 0; i < stride; i++) {
        raw[rowStart + 1 + i] = (src[srcStart + i] - src[priorStart + i]) & 0xff;
      }
    }
  }

  const idatData = zlib.deflateSync(raw, { level: 9 });

  return Buffer.concat([
    PNG_SIGNATURE,
    chunk('IHDR', ihdr),
    chunk('IDAT', idatData),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}
