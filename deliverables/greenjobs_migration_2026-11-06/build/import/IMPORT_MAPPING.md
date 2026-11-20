# Strategies CSV import mapping (GreenJobs migration)

Written 2026-11-07, rewritten 2026-11-20 on the client's real header rows. Internal. Source of truth is
`execution/gtm_client_workflows/greenjobs_redesign/strategies_mapping.json`; the tables below are generated from it plus
the rules in `strategies_import.py`. Schema contract: `build/d1/schema.sql` (+ `d1/migrations/`), upserts:
`build/d1/upserts.sql`.

**Source of the headers:** `REAL_HEADERS_2026-11-19.json` in this folder: the header rows of every Strategies report,
IE and UK, from Diana Lupu's email of 19 Nov 2026 (header rows only, no data rows). Every alias below is one of those
exact names. Still unverified until the first data export: date formats, boolean spellings (`Consent`, `Marketing`),
`SiteTag` / `SiteFK` / `JobStatus` values, and whether `JobDescription` is HTML.

IE and UK differ in two ways, both handled: the Jobs column order (same set of columns), and the profile report's
`sPreferredWorkRegionDesc` (IE) vs `sPreferredWorkLocationDesc` (UK); several profile columns are also ordered
differently. Recruiters, registration, Jobs By Email and Applications are identical. Both Jobs exports list
`ReferralAmount` twice.

## Rules common to every report

- **Stable id:** `'{site}:strat:{strategies_id}'` (e.g. `ie:strat:11501460`); a Strategies id is unique per site only.
- **Encoding / format:** UTF-8 (BOM stripped), else Windows-1252. Delimiter from the first non-blank line (`,` `;` tab `|`).
  CRLF ok. A quoted header line (the UK Jobs header: first field bare, the rest in double quotes) parses as usual.
  NUL bytes removed and counted. Rows with a different cell count from the header are rejected (`ragged_row`).
- **Dates:** day-first only (`06/11/2026`, `06/11/2026 14:32`, `2026-11-06`, `6 Nov 2026` ...). Stored as ISO UTC.
- **Retention:** keep a row only if its activity date (first non-empty field in the report's chain) is on or after
  `--as-of` minus `--retention-months` (default 24; allowed 6..84). No date at all: excluded `no_activity_date`.
- **Hostile input:** formula cells (`= + - @`, leading tab/CR) are flagged (warning `formula_injection_flagged`,
  masked evidence); in text fields the raw text is kept unchanged in D1 (no leading `'` on the live board), in typed
  fields (email, id, date, url, filename) they are invalid. Neutralising happens only when a CSV is written: this
  script writes no CSV (SQL + JSON report only); the Worker's `toCsvCell()` (`src/validate.js`) neutralises on export. `-` or `+353 1 ...` (numbers,
  phones) are not flagged. Prompt-injection / script phrases are flagged, kept, escaped on render. File-name fields
  containing `..` `/` `\` `:` `~` (also URL-encoded) are unsafe. Control chars stripped. Max lengths enforced.
- **Rejects** carry `{file, row, column, reason, evidence}`; evidence is ≤ 40 chars, emails masked (`j***@example.com`),
  names/phones shown only as shape (`len=12 lead='='`). No full email, name or phone appears in any output.
- **Header matching:** by NAME only, never by column position (IE and UK Jobs list the same columns in a different
  order). Case, spaces and punctuation are ignored (`JobPk` = `JobPK` = `job_pk`). A header that appears twice
  (`ReferralAmount` in both Jobs exports) is never mapped: both copies are ignored and the run warns
  `duplicate_header_ignored` once per file. A required field whose only header is duplicated stops the run (exit 2).
- **Site markers:** `SiteTag` (recruiters, registration) and `SiteFK` (jobs) are counted per file
  (`files[].site_tags`); `--expect-site-tag VALUE` excludes rows with any other value (`other_site_tag`). The values
  have not been seen yet, so no filter is applied by default.
- **Duplicates across batch files** collapse to the latest activity date (ties: the later file wins).

## Field mapping

### recruiters (Recruiters) → `employers`

Dedupe: site + strategies_id (ClientPK); warn on duplicate name_norm. Activity date chain: last_job_live → registered.

| Field | D1 column | Type / max | Req | On invalid | Real header (IE / UK) |
|---|---|---|---|---|---|
| strategies_id | `source_id` | id / 40 | yes | reject row | `ClientPK` |
| site_tag | (read, not stored) | text / 40 |  | reject row; truncate if long | `SiteTag` (site marker; values counted per file (--expect-site-tag filters)) |
| name | `name` | text / 200 | yes | reject row | `CompanyName` |
| contact_name | `contact_name` | text / 120 |  | reject row | `contactName` |
| contact_email | `contact_email` | email / 254 |  | drop value | `email` |
| phone | `phone` | text / 40 |  | reject row | `telephone` |
| website | `website` | url / 300 |  | drop value | `website` |
| registered | (read, not stored) | date |  | drop value | `CreateDate` |
| last_job_live | `last_active_at` | date |  | drop value | `LastJobLiveDate` |

At least one header of each group must exist: last_job_live / registered.

Real columns deliberately not imported (22): `expiryEmail`, `Pending`, `fax`, `address1`, `address2`, `address3`, `address4`, `postcode`, `country`, `RemotePostID`, `featureScore`, `FeaturedAllowance`, `AdAccess`, `AdExpiry`, `CVAccess`, `CVExpiry`, `NoJobs`, `NoLiveJobs`, `NoApps`, `JobCredits`, `CVCredits`, `LastJobPK`.

### candidates (Members registration details) → `candidates`

Dedupe: site + lower(trim(email)); same CandidatePK with a different email keeps the latest and warns. Activity date chain: last_login → registered.

| Field | D1 column | Type / max | Req | On invalid | Real header (IE / UK) |
|---|---|---|---|---|---|
| strategies_id | `source_id` | id / 40 | yes | reject row | `CandidatePK` |
| site_tag | (read, not stored) | text / 40 |  | reject row; truncate if long | `SiteTag` (site marker; values counted per file (--expect-site-tag filters)) |
| email | `email_norm` | email / 254 | yes | reject row | `email` |
| first_name | `first_name` | text / 60 |  | reject row | `FirstName` |
| last_name | `last_name` | text / 60 |  | reject row | `LastName` |
| full_name | (read, not stored) | text / 120 |  | reject row; truncate if long | `FullName` (read, not stored; FirstName/LastName are stored) |
| phone | `phone` | text / 40 |  | reject row | `Mobile`, `HomePhone` |
| location | `location` | text / 120 |  | reject row; truncate if long | `town`, `county` |
| consent_marketing | `consent_marketing` | bool |  | drop value | `Marketing` (gates any marketing email) |
| consent | `strategies_consent` | bool |  | drop value | `Consent` (Strategies 'Consent' flag carried as-is (1/0/NULL); 0 excludes the candidate's alerts and gates any later emailing) |
| has_alerts | (read, not stored) | bool |  | drop value | `HasJobsByEmail` (informational; the alerts report carries the subscriptions) |
| cv_filename | (read, not stored) | filename / 200 |  | reject row | `CVName` |
| registered | `registered_at` | date |  | drop value | `registerDate` |
| last_login | `last_active_at` | date |  | drop value | `LastLoggedIn` |

At least one header of each group must exist: last_login / registered.

Real columns deliberately not imported (10): `ReferenceNo`, `address1`, `address2`, `county`, `postcode`, `country`, `HomePhone`, `anon`, `HTML`, `HasCV`.

### profiles (Members profile data) → `candidates`

Dedupe: site + CandidatePK, latest wins. Activity date chain: updated → registered.

| Field | D1 column | Type / max | Req | On invalid | Real header (IE / UK) |
|---|---|---|---|---|---|
| candidate_id | `source_id` | id / 40 | yes | reject row | `CandidatePK` |
| email | `email_norm` | email / 254 |  | reject row | `sEmail` |
| headline | `headline` | text / 200 |  | reject row; truncate if long | `sCurrentJobTitleDesc`, `sDesiredJobTitleDesc` |
| location | `location` | text / 120 |  | reject row; truncate if long | `sPreferredWorkRegionDesc`, `sPreferredWorkLocationDesc` (IE sPreferredWorkRegionDesc = UK sPreferredWorkLocationDesc. The preferred work area, not the home address (data minimisation)) |
| sectors | `sectors_json` | list / 2000 |  | reject row | `sPreferredIndustrySectorDesc` |
| cv_filename | (read, not stored) | filename / 200 |  | reject row | `sCVName` |
| updated | `last_active_at` | date |  | drop value | `dLastLoggedIn` |
| registered | (read, not stored) | date |  | drop value | `dRegisterDate` |

At least one header of each group must exist: updated / registered.

Real columns deliberately not imported (56): `FullName`, `FirstName`, `LastName`, `sAddress1`, `sAddress2`, `sTown`, `sCounty`, `sPostCode`, `sCountry`, `sHomePhone`, `sMobile`, `nSalaryMin`, `nSalaryMax`, `nSalaryFrame`, `sSynopsis`, `sSalary`, `sReferenceNo`, `bAnon`, `bMarketing`, `bHasCV`, `bActive`, `bnew_marketingVal`, `bukEligableVal`, `sCareerLevelDesc`, `beuEligableVal`, `sWhereHeardAboutDesc`, `sManagementExperienceDesc`, `scareer_experience_sectorDesc`, `scareer_experience_job_categoryDesc`, `sEducationLevelDesc`, `sInstitutionDesc`, `sCourseTitleDesc`, `sLastYearofStudyDesc`, `sCertification_1Desc`, `sAwardingBodyCollege_1Desc`, `sDateAwarded_1Desc`, `sCertification_2Desc`, `sAwardingBodyCollege_2Desc`, `sDateAwarded_2Desc`, `sCertification_3Desc`, `sAwardingBodyCollege_3Desc`, `sDateAwarded_3Desc`, `sProfessionalAssociationsDesc`, `sDesiredJobTitleDesc`, `scurrent_job_typeDesc`, `sTimeInCurrentRoleDesc`, `sCurrentSalaryDesc`, `sOrganisationNameDesc`, `scurrent_regionDesc`, `scurrent_vicinityDesc`, `sDesiredJobTypeDesc`, `sPreferredSalaryDesc`, `sPreferredWorkVicinityDesc`, `sPreferredJobCategoryDesc`, `sNoticePeriodDesc`, `bWillingToRelocateVal`.

### jobs (Jobs (All jobs only)) → `jobs`

Dedupe: site + JobPK, latest wins. Activity date chain: updated → posted → closing.

| Field | D1 column | Type / max | Req | On invalid | Real header (IE / UK) |
|---|---|---|---|---|---|
| strategies_id | `source_id` | id / 40 | yes | reject row | `JobPK` |
| employer_id | `employer_id` | id / 40 |  | drop value | `ClientFK` |
| site_tag | (read, not stored) | text / 40 |  | reject row; truncate if long | `SiteFK` (site marker) |
| title | `title` | text / 160 | yes | reject row | `JobTitle` |
| location | `location` | text / 120 |  | reject row; truncate if long | `sVicinityDesc` (falls back to sRegionDesc when empty) |
| region | `region` | text / 80 |  | reject row; truncate if long | `sRegionDesc` |
| job_type | `job_type` | text / 40 |  | reject row; truncate if long | `sJobTypeDesc` |
| sal_min | `sal_min` | money |  | drop value | `SalaryMin` |
| sal_max | `sal_max` | money |  | drop value | `SalaryMax` |
| period | `period` | text / 20 |  | reject row; truncate if long | `SalaryFrame` |
| sal_text | `sal_text` | text / 120 |  | reject row; truncate if long | `SalaryDesc` |
| sectors | `sectors_json` | list / 2000 |  | reject row | `sIndustrySectorDesc` |
| description | `description` | text / 20000 | yes | reject row | `JobDescription` |
| apply_email | `apply_email` | email / 254 |  | drop value | `Email` (apply-mode source (client 19 Nov): used when AppLink is empty) |
| apply_url | `apply_url` | url / 500 |  | drop value | `AppLink` (apply-mode source: https -> link mode; http/javascript:/data: dropped) |
| job_status | (read, not stored) | text / 40 |  | reject row; truncate if long | `JobStatus` (values unseen; status comes from ExpiryDate) |
| job_ref | (read, not stored) | text / 80 |  | reject row; truncate if long | `JobRef` |
| company_name | (read, not stored) | text / 200 |  | reject row; truncate if long | `CompanyName` (the employer row comes from ClientFK) |
| posted | `posted_at` | date |  | drop value | `LiveDate`, `CreateDate` |
| closing | `closing_at` | date |  | drop value | `ExpiryDate` |
| updated | (read, not stored) | date |  | drop value | `LastChange` |

At least one header of each group must exist: updated / posted / closing; location / region.

Real columns deliberately not imported (18): `FeatureScore`, `FeaturedAdvert`, `PremiumJob`, `CreateDate`, `HideContactDetails`, `JobLogo`, `nIndustrySectorVal`, `nEducationLevelVal`, `sEducationLevelDesc`, `nRegionVal`, `nJobTypeVal`, `nVicinityVal`, `nJobCategoryVal`, `sJobCategoryDesc`, `NoApplications`, `NoSearches`, `NoViews`, `EditedBy`.

### applications (Job Applications) → `applications`

Dedupe: dedupe_key = sha256(site|job_id|CandEmail), job_id = '{site}:strat:{JobPk}'; latest ApplicationDate wins. No CV file in the export.. Activity date chain: submitted.

| Field | D1 column | Type / max | Req | On invalid | Real header (IE / UK) |
|---|---|---|---|---|---|
| job_id | `job_id` | id / 40 | yes | reject row | `JobPk` |
| applicant_name | `applicant_name` | text / 120 | yes | reject row | `Name` |
| applicant_email | `applicant_email` | email / 254 | yes | reject row | `CandEmail` |
| submitted | `submitted_at` | date |  | drop value | `ApplicationDate` |

At least one header of each group must exist: submitted.

Real columns deliberately not imported (4): `JobTitle`, `JobRef`, `CompanyName`, `ExpiryDate`.

### alerts (Jobs By Email) → `alert_subscriptions`

Dedupe: site + email + query_hash; imported as status 'pending' (double opt-in before any send); candidate Consent=0 excluded. Activity date: the candidate's (from `--candidates-csv`).

| Field | D1 column | Type / max | Req | On invalid | Real header (IE / UK) |
|---|---|---|---|---|---|
| candidate_id | (read, not stored) | id / 40 | yes | reject row | `CandidatePK` |
| email | `email_norm` | email / 254 | yes | reject row | `Email` |
| name | (read, not stored) | text / 120 |  | reject row; truncate if long | `Name` (not stored) |
| search_name | (read, not stored) | text / 120 |  | reject row; truncate if long | `SearchName` |
| keywords | (read, not stored) | text / 200 |  | reject row; truncate if long | `Keywords` |
| sal_min | (read, not stored) | money |  | drop value | `SalaryMin` |
| sal_max | (read, not stored) | money |  | drop value | `SalaryMax` |
| period | (read, not stored) | text / 20 |  | reject row; truncate if long | `SalaryFrame` |
| job_type | (read, not stored) | text / 40 |  | reject row; truncate if long | `sJobTypeDesc` |
| sectors | (read, not stored) | list / 2000 |  | reject row | `sIndustrySectorDesc` |
| category | (read, not stored) | text / 80 |  | reject row; truncate if long | `sJobCategoryDesc` |
| region | (read, not stored) | text / 80 |  | reject row; truncate if long | `sRegionDesc` |
| vicinity | (read, not stored) | text / 80 |  | reject row; truncate if long | `sVicinityDesc` |

Derived values and rules:
- **Keys across reports:** `ClientPK` (Recruiters) = `ClientFK` (Jobs) → `jobs.employer_id = '{site}:strat:{ClientFK}'`
  (a sub-select: an employer not imported gives NULL, never a foreign-key error). `JobPK` (Jobs) = `JobPk`
  (Applications, note the case) → `applications.job_id`. `CandidatePK` joins registration, profile and Jobs By Email.
- **Apply mode (jobs, client 19 Nov):** `AppLink` non-empty and https → `apply_mode='link'`, `apply_url=AppLink`,
  `apply_email` NULL. Otherwise `Email` valid → `apply_mode='email'`, routed to that address. Otherwise `email` with
  NULL `apply_email` → the site default inbox (`APPLY_ROUTING`). An `http:`, `javascript:` or `data:` AppLink is
  dropped (warning `invalid_url_dropped`) and the row falls through to `Email`. A row with both keeps the link and
  drops the email (warning `apply_email_dropped_link_mode`). The schema CHECK enforces one target per mode.
- **jobs:** `location` = `sVicinityDesc`, else `sRegionDesc` (a row with neither is rejected). `status` = `live` if
  `ExpiryDate` ≥ `--as-of`, else `closed` (`JobStatus` values are unseen, so it is read but not used). Currency
  defaults to the site (EUR ie, GBP uk) when a salary is present. `sal_min > sal_max` drops both. The upsert never
  overwrites console rows and never reopens a closed job; on Strategies rows it refreshes the apply fields.
  All live jobs are posted by hand in Strategies (client, 19 Nov): there is no Broadbean or other feed to import.
- **candidates (registration):** `Marketing` → `consent_marketing` and `Consent` → `strategies_consent` (1 / 0 / NULL
  when blank or unreadable), carried as exported; `consent_at` stays NULL (no consent timestamp in the export). Both gate
  any later emailing: nothing is mailed to a candidate on the strength of the import alone. `Mobile` is preferred to
  `HomePhone`; `town` to `county`. CV files are not in any export (`CVName` is validated only).
- **profiles:** merged into `candidates` by `CandidatePK` → email (from `--candidates-csv` kept rows) or the profile's
  own `sEmail`. Unresolved: rejected `unknown_candidate`. IE `sPreferredWorkRegionDesc` and UK
  `sPreferredWorkLocationDesc` are the same field and both fill `location` (the preferred work area); home address,
  phone and the education/career history are not imported (data minimisation).
- **applications:** no application id and no CV in the export, only `Name` + `CandEmail`. `job_id` =
  `'{site}:strat:{JobPk}'`; `dedupe_key = sha256(site|job_id|CandEmail)` (the key the Worker uses); the row id is
  derived from it. `candidate_id` is a sub-select on (site, email). `delivery_status = 'imported'`. Without
  `--jobs-csv` / `--known-job-ids` the orphan check is skipped with a warning and `--emit-sql` is refused.
- **alerts (Jobs By Email, 13 columns) → `alert_subscriptions`:** needs `--candidates-csv` (the export has no date
  column, so retention and the Consent gate come from the candidate row). A candidate outside retention or unknown is
  excluded (`candidate_not_retained`); `Consent = 0` is excluded (`candidate_consent_0`). `query_json` holds the search
  (`SearchName` as label, keywords, salary, type, sectors, category, region, vicinity), `query_hash` its sha256. Every
  imported row is `status='pending'`: it is re-confirmed (double opt-in) before any send, and `ALERTS_ENABLED="0"` at
  go-live. `Name` is read, never stored.

## Gates (per input file)

| Gate | Default | Bound | Failure |
|---|---|---|---|
| Yield floor: rows_kept / rows_in | ≥ 0.05 | 0..1, `--allow-low-yield` overrides | exit 3 with exclusion counts + first 5 rejects |
| Reject ceiling: rejected / rows_in | ≤ 0.20 | 0..1 | exit 3 with first 5 rejects |
| Retention months | 24 | 6..84 | exit 2 |
| Required header missing (or only duplicated) | n/a | n/a | exit 2, prints headers seen (masked if they look like data) |
| Zero data rows | n/a | n/a | no-op, exit 0, nothing written |

On a gate failure no SQL is written.

## Check a file before importing: `--sniff`

```bash
python3 $S --report jobs --sniff ~/gj/ie_jobs.csv
```

Reads only the header row and the first data row (at most 1 MiB). Prints the encoding, BOM, delimiter, every header
with a verdict (`mapped` + field, `ignored`, `duplicate`, `unmapped`), the required fields with no header (with their
aliases), the unknown headers, and the first row's cell count against the header width (a wrong delimiter shows up as
`width_matches: false`). No cell value is ever printed; a header that looks like data (an email or a digit run, i.e.
a file with no header row) is masked. Exit 0 when every required field maps, 2 otherwise. Never writes a file.

## How to run

CSVs stay in GreenJobs' own storage (outside the repo). Never in git, never in `.tmp/`.

```bash
S=execution/gtm_client_workflows/greenjobs_redesign/strategies_import.py
# 1. dry run (default) per report and site, all date batches together
python3 $S --report candidates --sniff ~/gj/ie_cand_2025a.csv      # 0. headers only, no values
python3 $S --site ie --report candidates --csv ~/gj/ie_cand_2025a.csv --csv ~/gj/ie_cand_2025b.csv --as-of 2026-11-20
# 2. emit SQL (path outside the repo), in this order:
python3 $S --site ie --report recruiters --csv ~/gj/ie_recruiters.csv --emit-sql ~/gj/sql/ie_1_recruiters.sql
python3 $S --site ie --report jobs --csv ~/gj/ie_jobs.csv --emit-sql ~/gj/sql/ie_2_jobs.sql
python3 $S --site ie --report candidates --csv ~/gj/ie_cand_*.csv --emit-sql ~/gj/sql/ie_3_candidates.sql
python3 $S --site ie --report profiles --csv ~/gj/ie_profiles.csv --candidates-csv ~/gj/ie_cand_2025a.csv --emit-sql ~/gj/sql/ie_4_profiles.sql
python3 $S --site ie --report applications --csv ~/gj/ie_apps.csv --jobs-csv ~/gj/ie_jobs.csv --emit-sql ~/gj/sql/ie_5_applications.sql
python3 $S --site ie --report alerts --csv ~/gj/ie_jobs_by_email.csv --candidates-csv ~/gj/ie_cand.csv --emit-sql ~/gj/sql/ie_6_alerts.sql
# 3. operator applies each file
npx wrangler@4 d1 execute greenjobs --file=~/gj/sql/ie_1_recruiters.sql
```

`--report-out PATH` saves the full JSON summary (no PII; may be under `<repo>/.tmp/`). Skip files already imported:
export `SELECT sha256 FROM import_batches` to a text file and pass `--done-sha256 FILE`. Each emitted file ends with
an `INSERT OR IGNORE INTO import_batches` row per input file; the same file passed twice in one run is skipped.
Re-applying a file converges (same row counts). Apply batches oldest to newest: an older batch applied later can
overwrite a newer employer name.

## When a header changes

1. `--sniff` the file. A required field with no header is listed with its aliases; `unknown_headers` lists every
   header that is neither mapped nor in `ignored_headers`.
2. Add the new header text to that field's `aliases` in `strategies_mapping.json` (earlier aliases win when two fields
   could claim one header), or to the report's `ignored_headers` if it is deliberately not imported. If the dates are
   not day-first, add the format to `date_formats`.
3. Add a fixture (fake data only) and run `bash deliverables/greenjobs_migration_2026-11-06/build/run_tests.sh`.
   `test_strategies_real_headers.py` fails if any real header in `REAL_HEADERS_2026-11-19.json` is left unaccounted for
   or if an alias is not a real header name.
