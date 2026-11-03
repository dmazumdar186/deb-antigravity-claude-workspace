#!/usr/bin/env node
// scripts/check_content.mjs — safety net that runs FIRST on every Cloudflare
// build (package.json "prebuild"). No dependencies.
//
// Jitendra edits src/content/*.json through Pages CMS. If a save produces
// something the site cannot build from, this script stops the build with a
// plain bilingual message ("PROBLÈME / PROBLEM: ...") that names the page to
// fix, instead of a cryptic stack trace. The live site keeps the last good
// version until the problem is fixed.
//
// Checks:
//   (a) every src/content/*.json parses (line/column on failure)
//   (b) for files listed in .pages.yml: top-level keys the site code relies
//       on still exist with the same kind (string/array/object/number/
//       boolean) as in scripts/content_schema.json. Lists of objects are
//       checked loosely (missing item keys = warning only).
//   (c) no file under public/assets is larger than 24 MiB (Cloudflare Pages
//       hard limit is 25 MiB per file)
//   (d) image/audio/video paths in content that do not exist under public/
//       -> WARNING only
//
// Usage:
//   node scripts/check_content.mjs                 # check (exit 1 on failure)
//   node scripts/check_content.mjs --write-schema  # snapshot current files
//   node scripts/check_content.mjs --root <dir>    # check another checkout

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const args = process.argv.slice(2);
const rootIdx = args.indexOf('--root');
const ROOT = rootIdx >= 0
  ? path.resolve(args[rootIdx + 1])
  : path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const WRITE_SCHEMA = args.includes('--write-schema');

const CONTENT_DIR = path.join(ROOT, 'src', 'content');
const SCHEMA_PATH = path.join(ROOT, 'scripts', 'content_schema.json');
const PAGES_YML = path.join(ROOT, '.pages.yml');
const PUBLIC_DIR = path.join(ROOT, 'public');
const ASSETS_DIR = path.join(PUBLIC_DIR, 'assets');
const MAX_BYTES = 24 * 1024 * 1024;
const MEDIA_EXT = /\.(jpe?g|png|webp|avif|gif|svg|mp4|webm|mov|mp3|m4a|ogg|wav)$/i;

const failures = [];
const warnings = [];
const rel = (p) => path.relative(ROOT, p).split(path.sep).join('/');

const FIX_HINT =
  '  -> FR : ouvrez cette page dans l\'éditeur (Pages CMS), corrigez-la ou revenez à la version précédente avec l\'icône horloge, puis Enregistrer.\n' +
  '  -> EN : open this page in the editor (Pages CMS), fix it or go back to the previous version with the clock icon, then Save.';

function kindOf(v) {
  if (v === null) return 'null';
  if (Array.isArray(v)) return 'array';
  return typeof v; // string | number | boolean | object
}

const KIND_WORDS = {
  string: 'text / texte',
  array: 'list / liste',
  object: 'group of fields / groupe de champs',
  number: 'number / nombre',
  boolean: 'on-off switch / interrupteur',
  null: 'empty (null) / vide (null)',
  undefined: 'missing / absent',
};

// --- .pages.yml: file -> page label, field name -> field label -----------
// Tiny regex reader (no YAML dependency). Each content entry starts with
// "- name:" at column 0; its own label/path sit at 2-space indent and its
// top-level fields at "  - name:" / "    label:".
function readPagesYml() {
  const pages = new Map();
  if (!fs.existsSync(PAGES_YML)) return pages;
  const text = fs.readFileSync(PAGES_YML, 'utf8');
  const blocks = text.split(/^- name:/m).slice(1);
  for (const block of blocks) {
    const label = (block.match(/^ {2}label:\s*(.+?)\s*$/m) || [])[1];
    const p = (block.match(/^ {2}path:\s*(.+?)\s*$/m) || [])[1];
    if (!p) continue;
    const fields = {};
    const re = /^ {2}- name:\s*(\S+)\s*\n {4}label:\s*(.+?)\s*$/gm;
    let m;
    while ((m = re.exec(block))) fields[m[1]] = m[2].replace(/^['"]|['"]$/g, '');
    pages.set(p.replace(/^['"]|['"]$/g, ''), {
      label: (label || p).replace(/^['"]|['"]$/g, ''),
      fields,
    });
  }
  return pages;
}

const PAGES = readPagesYml();

function pageName(relPath) {
  const page = PAGES.get(relPath);
  return page
    ? `the page / la page '${page.label}' (${relPath})`
    : `the file / le fichier ${relPath}`;
}

function fieldName(relPath, key) {
  const label = PAGES.get(relPath)?.fields?.[key];
  return label ? `'${label}' (${key})` : `'${key}'`;
}

function fail(msg) { failures.push(msg); }
function warn(msg) { warnings.push(msg); }

// --- (a) parse every content JSON ----------------------------------------
function lineCol(text, pos) {
  const before = text.slice(0, pos);
  const line = before.split('\n').length;
  const col = pos - before.lastIndexOf('\n');
  return { line, col };
}

function parseAll() {
  const parsed = new Map();
  if (!fs.existsSync(CONTENT_DIR)) return parsed;
  for (const name of fs.readdirSync(CONTENT_DIR).sort()) {
    if (!name.endsWith('.json')) continue;
    const abs = path.join(CONTENT_DIR, name);
    const r = rel(abs);
    const text = fs.readFileSync(abs, 'utf8');
    try {
      parsed.set(r, JSON.parse(text.replace(/^﻿/, '')));
    } catch (err) {
      const msg = String(err && err.message || err);
      let where = '';
      const lc = msg.match(/line (\d+) column (\d+)/);
      const pos = msg.match(/position (\d+)/);
      if (lc) where = `line / ligne ${lc[1]}, column / colonne ${lc[2]}`;
      else if (pos) {
        const { line, col } = lineCol(text, Number(pos[1]));
        where = `line / ligne ${line}, column / colonne ${col}`;
      } else if (/end of JSON|Unexpected end/i.test(msg)) {
        where = 'end of the file / fin du fichier';
      }
      fail(
        `PROBLÈME / PROBLEM: ${pageName(r)} is damaged and cannot be read / est abîmé(e) et illisible` +
        (where ? ` — near / vers ${where}` : '') + `.\n  (technical detail: ${msg})\n` + FIX_HINT,
      );
    }
  }
  return parsed;
}

// --- schema snapshot ------------------------------------------------------
// Keys "relied on" = key names that appear as a word in the site code
// (src/**/*.astro|ts|js|mjs, outside src/content). Others are optional.
function codeCorpus() {
  const out = [];
  const walk = (dir) => {
    for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
      const abs = path.join(dir, ent.name);
      if (ent.isDirectory()) {
        if (abs === CONTENT_DIR) continue;
        walk(abs);
      } else if (/\.(astro|ts|tsx|js|mjs)$/.test(ent.name)) {
        out.push(fs.readFileSync(abs, 'utf8'));
      }
    }
  };
  walk(path.join(ROOT, 'src'));
  return out.join('\n');
}

function describe(value) {
  const kind = kindOf(value);
  const node = { kind };
  if (kind === 'object') {
    node.keys = Object.fromEntries(Object.entries(value).map(([k, v]) => [k, kindOf(v)]));
  } else if (kind === 'array' && value.length) {
    const kinds = [...new Set(value.map(kindOf))];
    node.item_kind = kinds.length === 1 ? kinds[0] : 'mixed';
    if (node.item_kind === 'object') {
      // keys present in EVERY current item = expected item keys
      let common = Object.keys(value[0]);
      for (const it of value.slice(1)) common = common.filter((k) => k in it);
      node.item_keys = common;
    }
  }
  return node;
}

function writeSchema(parsed) {
  const corpus = codeCorpus();
  const schema = {
    _comment: 'Generated by `node scripts/check_content.mjs --write-schema`. Snapshot of the content files listed in .pages.yml: kind of each top-level key, and whether the site code relies on it (required). Regenerate after a developer changes the content structure.',
    files: {},
  };
  for (const [r] of PAGES) {
    const data = parsed.get(r);
    if (!data || kindOf(data) !== 'object') continue;
    const keys = {};
    // A file the site code never imports cannot break the build.
    const fileUsed = corpus.includes(path.basename(r));
    for (const [k, v] of Object.entries(data)) {
      const required = fileUsed && !k.startsWith('_') && new RegExp(`\\b${k.replace(/[$]/g, '\\$&')}\\b`).test(corpus);
      keys[k] = { ...describe(v), required };
    }
    schema.files[r] = keys;
  }
  fs.writeFileSync(SCHEMA_PATH, JSON.stringify(schema, null, 2) + '\n');
  console.log(`Wrote ${rel(SCHEMA_PATH)} (${Object.keys(schema.files).length} files).`);
}

// --- (b) structure check ---------------------------------------------------
function checkStructure(parsed) {
  if (!fs.existsSync(SCHEMA_PATH)) {
    warn(`WARNING: ${rel(SCHEMA_PATH)} not found — structure check skipped.`);
    return;
  }
  const schema = JSON.parse(fs.readFileSync(SCHEMA_PATH, 'utf8'));
  for (const [r, keys] of Object.entries(schema.files || {})) {
    if (!parsed.has(r)) {
      if (!fs.existsSync(path.join(ROOT, r))) {
        fail(`PROBLÈME / PROBLEM: ${pageName(r)} has been deleted / a été supprimé(e).\n${FIX_HINT}`);
      }
      continue; // unreadable file already reported in (a)
    }
    const data = parsed.get(r);
    if (kindOf(data) !== 'object') {
      fail(`PROBLÈME / PROBLEM: ${pageName(r)} no longer has its normal shape / n'a plus sa forme normale.\n${FIX_HINT}`);
      continue;
    }
    for (const [k, spec] of Object.entries(keys)) {
      const f = fieldName(r, k);
      const has = Object.prototype.hasOwnProperty.call(data, k);
      const actual = has ? kindOf(data[k]) : 'undefined';
      if (!has) {
        if (spec.required) {
          fail(`PROBLÈME / PROBLEM: ${pageName(r)} lost the field / a perdu le champ ${f}.\n${FIX_HINT}`);
        } else {
          warn(`WARNING / ATTENTION: ${pageName(r)} has no field / n'a pas de champ ${f} (optional / facultatif).`);
        }
        continue;
      }
      if (actual === spec.kind) {
        checkInside(r, k, spec, data[k]);
        continue;
      }
      const msg =
        `${pageName(r)}: the field / le champ ${f} should be a ${KIND_WORDS[spec.kind] || spec.kind}` +
        ` but is now / mais est maintenant: ${KIND_WORDS[actual] || actual}.`;
      // Empty (null) text/number/switch is survivable; a null group or list,
      // or any other kind change, breaks the page.
      if (actual === 'null' && !['object', 'array'].includes(spec.kind)) {
        warn(`WARNING / ATTENTION: ${msg}`);
      } else if (spec.required) {
        fail(`PROBLÈME / PROBLEM: ${msg}\n${FIX_HINT}`);
      } else {
        warn(`WARNING / ATTENTION: ${msg}`);
      }
    }
  }
}

function checkInside(r, k, spec, value) {
  const f = fieldName(r, k);
  if (spec.kind === 'object' && spec.keys) {
    for (const [sub, subKind] of Object.entries(spec.keys)) {
      if (!(sub in value)) {
        warn(`WARNING / ATTENTION: ${pageName(r)}: ${f} has no sub-field / n'a pas de sous-champ '${sub}'.`);
      } else if (subKind !== 'null' && kindOf(value[sub]) !== subKind) {
        warn(`WARNING / ATTENTION: ${pageName(r)}: ${f} → '${sub}' should be a ${KIND_WORDS[subKind] || subKind} but is / mais est: ${KIND_WORDS[kindOf(value[sub])]}.`);
      }
    }
  }
  if (spec.kind === 'array') {
    value.forEach((item, i) => {
      const n = i + 1;
      if (spec.item_kind === 'object') {
        if (item === null || kindOf(item) !== 'object') {
          if (item === null) {
            fail(`PROBLÈME / PROBLEM: ${pageName(r)}: entry / élément n°${n} of the list / de la liste ${f} is empty (null) / est vide (null).\n${FIX_HINT}`);
          } else {
            warn(`WARNING / ATTENTION: ${pageName(r)}: entry / élément n°${n} of the list / de la liste ${f} is a ${KIND_WORDS[kindOf(item)]}, expected / attendu: ${KIND_WORDS.object}.`);
          }
          return;
        }
        for (const ik of spec.item_keys || []) {
          if (!(ik in item)) {
            warn(`WARNING / ATTENTION: ${pageName(r)}: entry / élément n°${n} of the list / de la liste ${f} has no '${ik}' / n'a pas de '${ik}'.`);
          }
        }
      } else if (spec.item_kind && spec.item_kind !== 'mixed' && kindOf(item) !== spec.item_kind) {
        warn(`WARNING / ATTENTION: ${pageName(r)}: entry / élément n°${n} of the list / de la liste ${f} is a ${KIND_WORDS[kindOf(item)]}, expected / attendu: ${KIND_WORDS[spec.item_kind]}.`);
      }
    });
  }
}

// --- (c) file sizes --------------------------------------------------------
function checkSizes() {
  if (!fs.existsSync(ASSETS_DIR)) return;
  const walk = (dir) => {
    for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
      const abs = path.join(dir, ent.name);
      if (ent.isDirectory()) walk(abs);
      else if (ent.isFile()) {
        const size = fs.statSync(abs).size;
        if (size > MAX_BYTES) {
          const mb = (size / 1024 / 1024).toFixed(1);
          fail(
            `PROBLÈME / PROBLEM: this file is too big for Cloudflare (max 25 MB): ${rel(abs)} (${mb} MB) — make it smaller or delete it in Media.\n` +
            `  -> FR : ce fichier est trop lourd pour Cloudflare (max 25 Mo) : ${rel(abs)} (${mb} Mo) — réduisez-le ou supprimez-le dans Media.`,
          );
        }
      }
    }
  };
  walk(ASSETS_DIR);
}

// --- (d) media references --------------------------------------------------
function checkMediaRefs(parsed) {
  for (const [r, data] of parsed) {
    const visit = (v, trail) => {
      if (typeof v === 'string') {
        const s = v.trim();
        if (!s.startsWith('/') || s.startsWith('//') || !MEDIA_EXT.test(s.split(/[?#]/)[0])) return;
        let p = s.split(/[?#]/)[0];
        try { p = decodeURIComponent(p); } catch { /* keep raw */ }
        if (!fs.existsSync(path.join(PUBLIC_DIR, p))) {
          warn(`WARNING / ATTENTION: ${pageName(r)}: field / champ '${trail}' points to a missing file / pointe vers un fichier absent: ${s} (public${p}).`);
        }
      } else if (Array.isArray(v)) {
        v.forEach((x, i) => visit(x, `${trail}[${i + 1}]`));
      } else if (v && typeof v === 'object') {
        for (const [k, x] of Object.entries(v)) visit(x, trail ? `${trail}.${k}` : k);
      }
    };
    visit(data, '');
  }
}

// --- main ------------------------------------------------------------------
const parsed = parseAll();
if (WRITE_SCHEMA) {
  if (failures.length) {
    console.error(failures.join('\n\n'));
    process.exit(1);
  }
  writeSchema(parsed);
  process.exit(0);
}
checkStructure(parsed);
checkSizes();
checkMediaRefs(parsed);

if (warnings.length) {
  console.warn(warnings.join('\n'));
  console.warn('');
}
if (failures.length) {
  console.error('='.repeat(72));
  console.error(`check_content: ${failures.length} problem(s) — the website was NOT updated / le site n'a PAS été mis à jour.`);
  console.error('The live website keeps its previous version until this is fixed. / Le site en ligne garde sa version précédente.');
  console.error('='.repeat(72));
  console.error(failures.join('\n\n'));
  process.exit(1);
}
console.log(`check_content: OK — ${parsed.size} content files checked, ${warnings.length} warning(s).`);
