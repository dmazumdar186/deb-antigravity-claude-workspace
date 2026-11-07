-- Canonical idempotent upserts (D1 prepared statements, ?N params). The Worker and the
-- import emitter use exactly these shapes. Re-running any of them converges on the same row.

-- employers: keyed on id
INSERT INTO employers (id, site, source, source_id, name, name_norm, contact_name, contact_email, phone, website, logo_key, last_active_at, created_at, updated_at)
VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?13)
ON CONFLICT (id) DO UPDATE SET
  name = excluded.name, name_norm = excluded.name_norm, contact_name = excluded.contact_name,
  contact_email = excluded.contact_email, phone = excluded.phone, website = excluded.website,
  logo_key = COALESCE(excluded.logo_key, employers.logo_key),
  last_active_at = NULLIF(MAX(COALESCE(employers.last_active_at, ''), COALESCE(excluded.last_active_at, '')), ''),
  updated_at = excluded.updated_at
WHERE employers.name IS NOT excluded.name OR employers.contact_email IS NOT excluded.contact_email
   OR employers.last_active_at IS NOT excluded.last_active_at OR employers.website IS NOT excluded.website;

-- jobs (import): keyed on id; never resurrects a job staff closed in the console
INSERT INTO jobs (id, site, source, source_id, employer_id, title, location, region, job_type, sal_min, sal_max, currency, period, sal_text, sectors_json, summary, description, apply_mode, apply_email, apply_url, status, posted_at, closing_at, created_by, created_at, updated_at)
VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?17, ?18, ?19, ?20, ?21, ?22, ?23, ?24, ?25, ?25)
ON CONFLICT (id) DO UPDATE SET
  title = excluded.title, location = excluded.location, region = excluded.region, job_type = excluded.job_type,
  sal_min = excluded.sal_min, sal_max = excluded.sal_max, currency = excluded.currency, period = excluded.period,
  sal_text = excluded.sal_text, sectors_json = excluded.sectors_json, summary = excluded.summary,
  description = excluded.description, closing_at = excluded.closing_at,
  status = CASE WHEN jobs.status = 'closed' THEN 'closed' ELSE excluded.status END,
  version = jobs.version + 1, updated_at = excluded.updated_at
WHERE jobs.source = 'strategies';  -- console-owned rows are never overwritten by an import

-- jobs (console edit): optimistic lock; 0 rows changed = stale version -> HTTP 409
UPDATE jobs SET title = ?3, location = ?4, description = ?5, closing_at = ?6, apply_mode = ?7, apply_email = ?8,
  apply_url = ?9, sal_min = ?10, sal_max = ?11, currency = ?12, sal_text = ?13, status = ?14,
  version = version + 1, updated_at = ?15
WHERE id = ?1 AND version = ?2;

-- jobs (console close): idempotent; closing a closed job changes nothing
UPDATE jobs SET status = 'closed', closed_at = ?2, version = version + 1, updated_at = ?2
WHERE id = ?1 AND status <> 'closed';

-- candidates: keyed on (site, email_norm); registration + profile reports merge into one row
INSERT INTO candidates (id, site, source, source_id, email_norm, first_name, last_name, phone, location, headline, sectors_json, consent_marketing, consent_at, registered_at, last_active_at, created_at, updated_at)
VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?16)
ON CONFLICT (site, email_norm) DO UPDATE SET
  first_name = COALESCE(excluded.first_name, candidates.first_name),
  last_name = COALESCE(excluded.last_name, candidates.last_name),
  phone = COALESCE(excluded.phone, candidates.phone),
  location = COALESCE(excluded.location, candidates.location),
  headline = COALESCE(excluded.headline, candidates.headline),
  sectors_json = CASE WHEN excluded.sectors_json <> '[]' THEN excluded.sectors_json ELSE candidates.sectors_json END,
  last_active_at = NULLIF(MAX(COALESCE(candidates.last_active_at, ''), COALESCE(excluded.last_active_at, '')), ''),
  updated_at = excluded.updated_at;

-- applications: dedupe_key makes a double submit (or a re-imported CSV) a no-op
INSERT INTO applications (id, site, source, source_id, job_id, candidate_id, applicant_name, applicant_email, phone, cover_note, cv_key, routed_to, delivery_status, dedupe_key, submitted_at, created_at, updated_at)
VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?16)
ON CONFLICT (dedupe_key) DO NOTHING;

-- alert_subscriptions: keyed on (site, email_norm, query_hash)
INSERT INTO alert_subscriptions (id, site, email_norm, query_json, query_hash, frequency, status, confirm_token_hash, unsub_token_hash, consent_at, created_at, updated_at)
VALUES (?1, ?2, ?3, ?4, ?5, ?6, 'pending', ?7, ?8, ?9, ?10, ?10)
ON CONFLICT (site, email_norm, query_hash) DO UPDATE SET frequency = excluded.frequency, updated_at = excluded.updated_at
WHERE alert_subscriptions.status <> 'unsubscribed';  -- an unsubscribe is never silently undone

-- audit_log: replayed request_id adds no row
INSERT OR IGNORE INTO audit_log (at, actor, action, entity, entity_id, request_id, detail_json)
VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7);

-- import_batches: skip-if-done
INSERT OR IGNORE INTO import_batches (sha256, site, report_type, rows_in, rows_kept, imported_at)
VALUES (?1, ?2, ?3, ?4, ?5, ?6);
