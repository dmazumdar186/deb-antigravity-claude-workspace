// Legacy-URL fallback rules for GreenJobs (pure; no I/O). The Cloudflare Bulk Redirects list
// (ops/generated/bulk_redirects.json) runs first; this Worker only sees what it missed.
// Table: ops/generated/worker_redirects.json (python3 ops/redirects.py build). Returns a 301 target URL or null.

const slug = (s) => String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');

export function redirectFor(urlString, table) {
  let u;
  try {
    u = new URL(urlString);
  } catch {
    return null;
  }
  const ed = Object.prototype.hasOwnProperty.call(table.hosts, u.hostname.toLowerCase()) ? table.hosts[u.hostname.toLowerCase()] : null;
  if (!ed) return null;
  const base = table.canonical[ed];
  const path = u.pathname;
  const lower = path.toLowerCase();
  const q = u.searchParams;
  const live = new Set(table.live_ids[ed] || []);
  const job = (id) => (id && /^[A-Za-z0-9_-]+$/.test(id) && live.has(id) ? `${base}/jobs/${id}/` : `${base}/jobs/`);

  if (lower === '/jobboard/cands/jobresults.asp') {
    const r = q.get('lstVicinity') || q.get('lstRegion');
    const regions = table.regions[ed] || {};
    const key = slug(r);
    const canon = r && Object.prototype.hasOwnProperty.call(regions, key) ? regions[key] : null;
    return canon ? `${base}/jobs/?region=${canon}` : `${base}/jobs/`;
  }
  if (lower === '/jobboard/cands/jobview.asp') return job(q.get('v'));
  let m = path.match(/^\/jobs\/([A-Za-z0-9_-]+)\/[^/]+\.asp$/i);
  if (m) return job(m[1]);
  m = path.match(/^\/browse-jobs\/([A-Za-z0-9_.-]+)\/?$/i);
  if (m) {
    const canonical = `/browse-jobs/${m[1].toLowerCase()}/`;
    // One normalising hop (the bulk list holds the lowercase form); an already-canonical miss goes to the board.
    return path !== canonical ? `https://${u.hostname.toLowerCase()}${canonical}` : `${base}/jobs/`;
  }
  if (lower.startsWith('/browse-jobs/')) return `${base}/jobs/`;
  if (lower.startsWith('/jobboard/') || lower.endsWith('.asp')) return `${base}/`;
  return null;
}
