// The toolkit's page helper, found through LEMO_OPUSCAR_HOME (bootstrap's lemo.env), then LIB, then the clone two folders up.
import path from 'path'; import { fileURLToPath } from 'url';
const here = path.dirname(fileURLToPath(import.meta.url));
export const LIB = process.env.LEMO_OPUSCAR_HOME || process.env.LIB || path.resolve(here, '../../..');
export const { openDemo, closeServer } = await import(path.join(LIB, 'core/render/page.mjs'));
