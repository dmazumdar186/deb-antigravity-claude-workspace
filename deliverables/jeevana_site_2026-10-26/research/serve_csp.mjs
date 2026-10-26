// Static server that applies the site's _headers (CSP etc.) so local checks match Cloudflare Pages.
import { createServer } from 'node:http'; import { readFileSync, existsSync, statSync } from 'node:fs'; import { join, extname } from 'node:path';
const root = process.argv[2]; const port = +(process.argv[3] || 8794);
const hdrTxt = existsSync(join(root, '_headers')) ? readFileSync(join(root, '_headers'), 'utf8') : '';
const rules = []; let cur = null; for (const line of hdrTxt.split('\n')) { if (!line.trim()) continue; if (!line.startsWith(' ')) { cur = { pat: line.trim(), h: [] }; rules.push(cur); } else if (cur) { const i = line.indexOf(':'); cur.h.push([line.slice(0, i).trim(), line.slice(i + 1).trim()]); } }
const types = { '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json', '.webmanifest': 'application/manifest+json', '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.svg': 'image/svg+xml', '.mp4': 'video/mp4', '.webm': 'video/webm', '.ico': 'image/x-icon', '.txt': 'text/plain', '.xml': 'application/xml' };
createServer((req, res) => { let p = decodeURIComponent(req.url.split('?')[0]); if (p.endsWith('/')) p += 'index.html'; let f = join(root, p); if (!existsSync(f) || statSync(f).isDirectory()) { f = join(root, '404.html'); res.statusCode = 404; }
  for (const r of rules) { const re = new RegExp('^' + r.pat.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$'); if (re.test(p)) for (const [k, v] of r.h) res.setHeader(k, v); }
  res.setHeader('Content-Type', types[extname(f)] || 'application/octet-stream'); res.end(readFileSync(f)); }).listen(port, () => console.log('csp server on', port));
