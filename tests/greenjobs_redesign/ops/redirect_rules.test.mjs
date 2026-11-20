// Worker fallback redirect rules against the generated table (node --test; offline).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { redirectFor } from '../../../execution/gtm_client_workflows/greenjobs_redesign/ops/worker/redirect_rules.js';

const table = JSON.parse(readFileSync(fileURLToPath(new URL('../../../execution/gtm_client_workflows/greenjobs_redesign/ops/generated/worker_redirects.json', import.meta.url)), 'utf8'));
const liveUk = table.live_ids.uk[0];

test('old results page with a region goes to the region filter', () => {
  assert.equal(redirectFor('https://www.greenjobs.co.uk/jobboard/cands/JobResults.asp?c=1&lstRegion=South%20East', table), 'https://www.greenjobs.co.uk/jobs/?region=south-east');
  assert.equal(redirectFor('https://greenjobs.ie/jobboard/cands/jobresults.asp?lstVicinity=Cork', table), 'https://www.greenjobs.ie/jobs/?region=cork');
});

test('unknown region and plain paging go to the board', () => {
  assert.equal(redirectFor('https://www.greenjobs.ie/jobboard/cands/jobresults.asp?lstRegion=Atlantis', table), 'https://www.greenjobs.ie/jobs/');
  assert.equal(redirectFor('https://www.greenjobs.ie/jobboard/cands/jobresults.asp?pg=7', table), 'https://www.greenjobs.ie/jobs/');
});

test('job ids: live ones keep their page, others go to the board', () => {
  assert.equal(redirectFor(`https://www.greenjobs.co.uk/jobboard/cands/jobview.asp?v=${liveUk}`, table), `https://www.greenjobs.co.uk/jobs/${liveUk}/`);
  assert.equal(redirectFor('https://www.greenjobs.co.uk/jobboard/cands/jobview.asp?v=1', table), 'https://www.greenjobs.co.uk/jobs/');
  assert.equal(redirectFor('https://www.greenjobs.co.uk/jobs/1/old-role.asp', table), 'https://www.greenjobs.co.uk/jobs/');
  assert.equal(redirectFor('https://www.greenjobs.co.uk/jobboard/cands/jobview.asp?v=../../x', table), 'https://www.greenjobs.co.uk/jobs/');
});

test('facet case and slash variants take one normalising hop, canonical misses go to the board', () => {
  assert.equal(redirectFor('https://www.greenjobs.ie/browse-jobs/Antrim', table), 'https://www.greenjobs.ie/browse-jobs/antrim/');
  assert.equal(redirectFor('https://www.greenjobs.ie/browse-jobs/antrim/', table), 'https://www.greenjobs.ie/jobs/');
});

test('other legacy .asp goes home; new-site paths and unknown hosts pass through', () => {
  assert.equal(redirectFor('https://www.greenjobs.ie/some-old-page.cms.asp', table), 'https://www.greenjobs.ie/');
  assert.equal(redirectFor('https://www.greenjobs.ie/jobs/', table), null);
  assert.equal(redirectFor('https://www.greenjobs.ie/sectors/wind-energy/', table), null);
  assert.equal(redirectFor('https://evil.example/jobboard/cands/jobview.asp?v=1', table), null);
  assert.equal(redirectFor('not a url', table), null);
  assert.equal(redirectFor('https://www.greenjobs.ie/jobboard/cands/jobresults.asp?lstRegion=__proto__', table), 'https://www.greenjobs.ie/jobs/');
});
