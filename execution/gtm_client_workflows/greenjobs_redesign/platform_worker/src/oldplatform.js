// Links into the retired Strategies platform (eye review 2026-11-20 M3). Once greenjobs.ie / greenjobs.co.uk
// point at the new board, every *.asp page, /browse-jobs/<employer> page and /jobboard/ asset 404s, and the
// strategies hosts go with the contract. Such a URL is never rendered: an apply link to it becomes email mode
// (the job's own address, else the site default inbox) at import time AND at render time; an employer link to
// it becomes the new employer page or is omitted. build_site.is_old_platform_url() is the same rule.

const BOARD_HOSTS = /^(?:www\.)?greenjobs\.(?:ie|co\.uk)$/i;
const STRATEGIES_HOSTS = /(?:^|\.)(?:strategiesuk\.net|strategies\.co\.uk|strategies\.net)$/i;
const OLD_PATH = /(?:\.asp(?:$|[?#])|^\/browse-jobs\/|^\/jobboard\/)/i;

export function isOldPlatformUrl(url) {
  let u;
  try { u = new URL(String(url || '')); } catch { return false; }
  const host = u.hostname.toLowerCase();
  if (STRATEGIES_HOSTS.test(host)) return true;
  return BOARD_HOSTS.test(host) && OLD_PATH.test(u.pathname + (u.search || ''));
}
