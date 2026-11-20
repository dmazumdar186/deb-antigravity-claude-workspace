// GreenJobs legacy redirect Worker (free tier; runs only on legacy path prefixes).
// Routes, both boards, apex and www (Workers routes allow '*' only at the host start and path end):
//   *greenjobs.ie/jobboard/*      *greenjobs.ie/browse-jobs/*
//   *greenjobs.co.uk/jobboard/*   *greenjobs.co.uk/browse-jobs/*
// Recorded *.asp pages (static and job pages) are in the Bulk Redirects list, which runs before Workers.
import table from '../generated/worker_redirects.json';
import { redirectFor } from './redirect_rules.js';

export default {
  async fetch(request) {
    const target = redirectFor(request.url, table);
    if (target) return Response.redirect(target, 301);
    return fetch(request); // not a legacy URL: pass through to the site
  },
};
