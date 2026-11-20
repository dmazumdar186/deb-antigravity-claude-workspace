-- Canonical statements for the tables of migrations/0002 + 0003 (feed import, job_facets, review queue,
-- employer self-posting). D1 prepared statements with ?N params. Each statement is preceded by a
-- `-- name: <key>` line; gaia_d1_sync.py / strategies_import.py render them to literal SQL, and
-- platform_worker/src/sql_0003.js holds the same text for the Worker (a node test asserts they are equal).
-- Every write converges on a re-run: upserts on stable ids, WHERE-guarded so an unchanged row is not touched.

-- name: feed_job_upsert
-- Feed jobs (source 'feed', id '{site}:gaia:{wp id}'). Never overwrites a console or Strategies row; never
-- reopens a closed job; never takes a live job back to draft; never overwrites sectors staff decided in review.
-- employer: the board's own Strategies employer of that name when there is one, else the feed employer row.
INSERT INTO jobs (id, site, source, source_id, employer_id, title, location, region, job_type, sal_min, sal_max, currency, period, sal_text, sectors_json, summary, description, apply_mode, apply_email, apply_url, status, posted_at, closing_at, created_by, created_at, updated_at)
VALUES (?1, ?2, 'feed', ?3, COALESCE((SELECT e.id FROM employers e WHERE e.site = ?2 AND e.name_norm = ?5 AND e.source = 'strategies' ORDER BY e.id LIMIT 1), ?4), ?6, ?7, ?8, ?9, NULL, NULL, NULL, NULL, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?17, ?18, ?19, 'feed', ?20, ?20)
ON CONFLICT (id) DO UPDATE SET
  title = excluded.title, location = excluded.location, region = excluded.region, job_type = excluded.job_type,
  sal_text = excluded.sal_text, summary = excluded.summary, description = excluded.description,
  apply_mode = excluded.apply_mode, apply_email = excluded.apply_email, apply_url = excluded.apply_url,
  closing_at = excluded.closing_at,
  sectors_json = CASE WHEN EXISTS (SELECT 1 FROM job_review r WHERE r.job_id = jobs.id AND r.status <> 'queued')
                      THEN jobs.sectors_json ELSE excluded.sectors_json END,
  status = CASE WHEN jobs.status IN ('closed','live') THEN jobs.status ELSE excluded.status END,
  posted_at = COALESCE(jobs.posted_at, excluded.posted_at),
  version = jobs.version + 1, updated_at = excluded.updated_at
WHERE jobs.source = 'feed' AND (
     jobs.title IS NOT excluded.title OR jobs.location IS NOT excluded.location OR jobs.region IS NOT excluded.region
  OR jobs.job_type IS NOT excluded.job_type OR jobs.sal_text IS NOT excluded.sal_text OR jobs.summary IS NOT excluded.summary
  OR jobs.description IS NOT excluded.description OR jobs.apply_mode IS NOT excluded.apply_mode
  OR jobs.apply_email IS NOT excluded.apply_email OR jobs.apply_url IS NOT excluded.apply_url
  OR jobs.closing_at IS NOT excluded.closing_at
  OR (jobs.status = 'draft' AND excluded.status = 'live')
  OR (jobs.sectors_json IS NOT excluded.sectors_json
      AND NOT EXISTS (SELECT 1 FROM job_review r WHERE r.job_id = jobs.id AND r.status <> 'queued')));

-- name: feed_close_missing
-- A job that left the feed is closed, never deleted. ?2 is the source prefix ('gaia:%'), ?4 a JSON array of
-- the source_ids this run kept on this site (a job linked to a board duplicate is not kept, so it closes).
UPDATE jobs SET status = 'closed', closed_at = ?3, version = version + 1, updated_at = ?3
WHERE site = ?1 AND source = 'feed' AND source_id LIKE ?2 AND status <> 'closed'
  AND source_id NOT IN (SELECT value FROM json_each(?4));

-- name: job_facets_upsert
-- THE facet upsert (table: migration 0002). Every writer uses it: console (set_by 'console', classifier columns
-- NULL), the Worker import route and gaia_d1_sync.py ('feed'), strategies_import.py ('import').
-- ?12 = taxonomy.json "version". Sectors staff decided in review are never overwritten by an import/feed re-run.
INSERT INTO job_facets (job_id, sectors_json, regions_json, job_type, workplace, contract_json, loc_class, level, is_agency, salary_display, unverified_cur, taxonomy_version, set_by, updated_at, search_text, source_sectors_json, sector_confidence, sector_method)
VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?17, ?18)
ON CONFLICT (job_id) DO UPDATE SET
  sectors_json = CASE WHEN excluded.set_by <> 'console'
                       AND EXISTS (SELECT 1 FROM job_review r WHERE r.job_id = job_facets.job_id AND r.status <> 'queued')
                      THEN job_facets.sectors_json ELSE excluded.sectors_json END,
  regions_json = excluded.regions_json, job_type = excluded.job_type, workplace = excluded.workplace,
  contract_json = excluded.contract_json, loc_class = excluded.loc_class, level = excluded.level, is_agency = excluded.is_agency,
  salary_display = excluded.salary_display, unverified_cur = excluded.unverified_cur, taxonomy_version = excluded.taxonomy_version,
  set_by = excluded.set_by, updated_at = excluded.updated_at, search_text = excluded.search_text,
  source_sectors_json = excluded.source_sectors_json, sector_confidence = excluded.sector_confidence, sector_method = excluded.sector_method
WHERE job_facets.sectors_json IS NOT excluded.sectors_json OR job_facets.regions_json IS NOT excluded.regions_json
   OR job_facets.job_type IS NOT excluded.job_type OR job_facets.workplace IS NOT excluded.workplace
   OR job_facets.contract_json IS NOT excluded.contract_json OR job_facets.loc_class IS NOT excluded.loc_class
   OR job_facets.level IS NOT excluded.level OR job_facets.is_agency IS NOT excluded.is_agency
   OR job_facets.salary_display IS NOT excluded.salary_display OR job_facets.unverified_cur IS NOT excluded.unverified_cur
   OR job_facets.taxonomy_version IS NOT excluded.taxonomy_version OR job_facets.set_by IS NOT excluded.set_by
   OR job_facets.search_text IS NOT excluded.search_text OR job_facets.source_sectors_json IS NOT excluded.source_sectors_json
   OR job_facets.sector_confidence IS NOT excluded.sector_confidence OR job_facets.sector_method IS NOT excluded.sector_method;

-- name: review_upsert
-- Queue (or refresh) a review row. A decided row is never reopened.
INSERT INTO job_review (job_id, site, reason, suggested_json, confidence, hold, status, created_at, updated_at)
VALUES (?1, ?2, ?3, ?4, ?5, ?6, 'queued', ?7, ?7)
ON CONFLICT (job_id) DO UPDATE SET
  reason = excluded.reason, suggested_json = excluded.suggested_json, confidence = excluded.confidence,
  hold = excluded.hold, updated_at = excluded.updated_at
WHERE job_review.status = 'queued' AND (job_review.reason IS NOT excluded.reason
   OR job_review.suggested_json IS NOT excluded.suggested_json OR job_review.confidence IS NOT excluded.confidence
   OR job_review.hold IS NOT excluded.hold);

-- name: review_clear
-- The classifier is now confident: an undecided row is dropped (a decided one stays as the record).
DELETE FROM job_review WHERE job_id = ?1 AND status = 'queued';

-- name: review_facets
-- The review decision also sets the canonical sectors the boards read (run in the batch BEFORE review_decide).
UPDATE job_facets SET sectors_json = ?2, sector_method = 'staff', sector_confidence = 1.0, updated_at = ?3
WHERE job_id = ?1 AND sectors_json IS NOT ?2
  AND EXISTS (SELECT 1 FROM job_review r WHERE r.job_id = ?1 AND r.status = 'queued');

-- name: review_approve_job
-- One click in the review console: set the sectors and take a held (draft) job live. Only while the review is
-- still queued (run in one batch BEFORE review_decide), never for a closed job.
UPDATE jobs SET sectors_json = ?3, status = CASE WHEN status = 'draft' THEN 'live' ELSE status END,
  posted_at = COALESCE(posted_at, ?4), version = version + 1, updated_at = ?4
WHERE id = ?1 AND site = ?2 AND status <> 'closed'
  AND EXISTS (SELECT 1 FROM job_review r WHERE r.job_id = ?1 AND r.status = 'queued');

-- name: review_decide
UPDATE job_review SET status = ?3, decided_by = ?4, decided_sectors_json = ?5, decided_at = ?6, updated_at = ?6
WHERE job_id = ?1 AND site = ?2 AND status = 'queued'
  AND EXISTS (SELECT 1 FROM jobs j WHERE j.id = ?1 AND j.status <> 'closed');

-- name: link_upsert
INSERT INTO job_links (site, feed_source_id, board_job_id, method, created_at, updated_at)
VALUES (?1, ?2, ?3, ?4, ?5, ?5)
ON CONFLICT (site, feed_source_id, board_job_id) DO UPDATE SET method = excluded.method, updated_at = excluded.updated_at
WHERE job_links.method IS NOT excluded.method AND job_links.method <> 'staff';

-- name: link_prune
-- Links of jobs that left the feed (or are no longer duplicates) go; a staff-made link stays.
-- ?3 is a JSON array of 'feed_source_id|board_job_id' pairs this run kept.
DELETE FROM job_links WHERE site = ?1 AND feed_source_id LIKE ?2 AND method <> 'staff'
  AND (feed_source_id || '|' || board_job_id) NOT IN (SELECT value FROM json_each(?3));

-- name: employer_scope
-- Employer ids an authenticated email may post for on this site (active, not past the contract end).
SELECT ea.employer_id AS employer_id, e.name AS name FROM employer_accounts ea JOIN employers e ON e.id = ea.employer_id
WHERE ea.email_norm = ?1 AND ea.status = 'active' AND (ea.expires_at IS NULL OR ea.expires_at > ?2) AND e.site = ?3
ORDER BY ea.employer_id;

-- name: employer_account_upsert
-- Staff grant / renew / disable an employer login (run with wrangler d1 execute; see platform_worker/README.md).
INSERT INTO employer_accounts (email_norm, employer_id, status, expires_at, created_by, created_at, updated_at)
VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?6)
ON CONFLICT (email_norm, employer_id) DO UPDATE SET status = excluded.status, expires_at = excluded.expires_at,
  updated_at = excluded.updated_at
WHERE employer_accounts.status IS NOT excluded.status OR employer_accounts.expires_at IS NOT excluded.expires_at;

-- name: employer_job_insert
-- Employer self-post: the id is derived from the Idempotency-Key, so a replay converges on one row.
INSERT INTO jobs (id, site, source, source_id, employer_id, title, location, region, job_type, sal_min, sal_max, currency, period, sal_text, sectors_json, summary, description, apply_mode, apply_email, apply_url, status, posted_at, closing_at, created_by, created_at, updated_at)
VALUES (?1, ?2, 'console', NULL, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?17, ?18, ?19, ?20, ?21, ?22, ?23, ?23)
ON CONFLICT (id) DO NOTHING;
