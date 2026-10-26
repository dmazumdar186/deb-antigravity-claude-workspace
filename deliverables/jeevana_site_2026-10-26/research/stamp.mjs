#!/usr/bin/env node
// Cache-busting: rewrites css/styles.css?v= and js/*.js?v= in every shipped HTML with a short content hash. Idempotent.
// usage: node research/stamp.mjs   (run before deploy)
import { readFileSync, writeFileSync } from 'node:fs'; import { createHash } from 'node:crypto'; import { join } from 'node:path';
const site = new URL('../site/', import.meta.url).pathname;
const h = (f) => createHash('sha256').update(readFileSync(join(site, f))).digest('hex').slice(0, 8);
const assets = ['css/styles.css', 'js/main.js', 'js/i18n.js'];
for (const page of ['index.html', 'privacy/index.html', '404.html']) {
  let s = readFileSync(join(site, page), 'utf8');
  for (const a of assets) s = s.replace(new RegExp('(["/])' + a.replace(/[.]/g, '\\.') + '(\\?v=[0-9a-f]+)?"', 'g'), `$1${a}?v=${h(a)}"`);
  writeFileSync(join(site, page), s);
}
console.log('stamped', assets.map((a) => a + '=' + h(a)).join(' '));
