#!/usr/bin/env node
/* serve_csp.mjs <site> <port> — static server that applies the site's _headers (CSP etc.) like Cloudflare Pages. */
import http from 'node:http'; import { readFileSync, existsSync, statSync } from 'node:fs'; import { join, extname, resolve } from 'node:path';
const site = resolve(process.argv[2] || '../site'), port = +(process.argv[3] || 8794);
const hdr = {}; readFileSync(join(site, '_headers'), 'utf8').split('\n').forEach((l) => { const m = l.match(/^\s+([\w-]+):\s*(.+)$/); if (m) hdr[m[1]] = m[2]; });
const types = { '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript', '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.woff2': 'font/woff2', '.mp4': 'video/mp4', '.webm': 'video/webm', '.json': 'application/json', '.ico': 'image/x-icon', '.txt': 'text/plain' };
http.createServer((q, r) => { let p = decodeURIComponent(q.url.split('?')[0]); let f = join(site, p); if (existsSync(f) && statSync(f).isDirectory()) f = join(f, 'index.html');
  if (!f.startsWith(site) || !existsSync(f)) { r.writeHead(404); return r.end('404'); }
  r.writeHead(200, { ...hdr, 'Content-Type': types[extname(f)] || 'application/octet-stream' }); r.end(readFileSync(f)); }).listen(port, () => console.log('serving', site, 'on', port));
