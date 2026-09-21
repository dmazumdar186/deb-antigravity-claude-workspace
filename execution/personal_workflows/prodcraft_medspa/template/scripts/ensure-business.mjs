#!/usr/bin/env node
// scripts/ensure-business.mjs
// description: Copies business.example.json to business.json if no business.json
//   exists yet at the template root, so `npm run build` works out of the box for
//   local dev / CI without requiring the Python builder to have run first.
// inputs: business.example.json (committed)
// outputs: business.json (gitignored; overwritten by the Python builder in prod)

import { existsSync, copyFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const target = path.join(root, 'business.json');
const source = path.join(root, 'business.example.json');

if (!existsSync(target)) {
  copyFileSync(source, target);
  console.log('[ensure-business] business.json not found — copied business.example.json');
} else {
  console.log('[ensure-business] business.json already present, leaving as-is');
}
