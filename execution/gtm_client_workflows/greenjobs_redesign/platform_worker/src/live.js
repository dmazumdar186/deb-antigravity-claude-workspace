// The ONE definition of a live job (eye review 2026-11-20 B1): status 'live' AND the closing date has not
// passed, compared as UTC calendar days (closing day itself is still live). Every public reader uses it:
// the board list, filters, sector pages, the jobs sitemap, /api/jobs (both views), /api/stats, the job page,
// /api/apply and the alert digests. build_site.is_live() and lib.js isLive() are the same rule for the static
// boards; tests/greenjobs_redesign/platform/live_consistency.test.mjs proves each reader agrees with it.

/** SQL predicate for table alias `a` (or none) with the UTC date (YYYY-MM-DD) bound at parameter `p`. */
export function liveWhere(a, p) {
  const c = a ? `${a}.` : '';
  return `${c}status = 'live' AND (${c}closing_at IS NULL OR substr(${c}closing_at, 1, 10) >= ${p})`;
}

/** The same rule in JS, for a D1 row ({status, closing_at}) or a board job ({status, closing}). */
export function isLive(row, today) {
  if (!row || row.status !== 'live') return false;
  const c = String(row.closing_at ?? row.closing ?? '').slice(0, 10);
  return !c || c >= String(today).slice(0, 10);
}
