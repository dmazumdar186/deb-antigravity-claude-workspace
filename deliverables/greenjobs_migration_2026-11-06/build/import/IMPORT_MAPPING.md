# Strategies CSV import mapping (GreenJobs migration)

Written 2026-11-07. Internal. Source of truth is
`execution/gtm_client_workflows/greenjobs_redesign/strategies_mapping.json`; this page is generated from it plus the
rules in `strategies_import.py`. Schema contract: `build/d1/schema.sql`, upserts: `build/d1/upserts.sql`.

**Assumption:** no real Strategies export has been seen yet. Every header below is a plausible alias, matched
case-, space- and punctuation-insensitively (`E-mail Address` = `email address` = `EmailAddress`). A required
field that matches no header stops the run (exit 2) and prints the headers it saw.

## Rules common to every report

- **Stable id:** `'{site}:strat:{strategies_id}'` (e.g. `ie:strat:11501460`); a Strategies id is unique per site only.
- **Encoding / format:** UTF-8 (BOM ok), else Windows-1252. Delimiter from the header line (`,` `;` tab `|`). CRLF ok.
  NUL bytes removed and counted. Rows with a different cell count from the header are rejected (`ragged_row`).
- **Dates:** day-first only (`06/11/2026`, `06/11/2026 14:32`, `2026-11-06`, `6 Nov 2026` ...). Stored as ISO UTC.
- **Retention:** keep a row only if its activity date (first non-empty field in the report's chain) is on or after
  `--as-of` minus `--retention-months` (default 24; allowed 6..84). No date at all: excluded `no_activity_date`.
- **Hostile input:** formula cells (`= + - @`, leading tab/CR) are flagged; in text fields they are kept with a
  leading `'`, in typed fields (email, id, date, url, filename) they are invalid. `-` or `+353 1 ...` (numbers,
  phones) are not flagged. Prompt-injection / script phrases are flagged, kept, escaped on render. File-name fields
  containing `..` `/` `\` `:` `~` (also URL-encoded) are unsafe. Control chars stripped. Max lengths enforced.
- **Rejects** carry `{file, row, column, reason, evidence}`; evidence is ≤ 40 chars, emails masked (`j***@example.com`),
  names/phones shown only as shape (`len=12 lead='='`). No full email, name or phone appears in any output.
- **Duplicates across batch files** collapse to the latest activity date (ties: the later file wins).

## Field mapping

### recruiters → `employers`

Dedupe: site + strategies_id; warn on duplicate name_norm. Activity date chain: last_login → updated → registered.

| Field | D1 column | Type / max | Req | On invalid | Strategies header aliases |
|---|---|---|---|---|---|
| strategies_id | source_id | id / 40 | yes | reject row | Recruiter ID, RecruiterID, Client ID, Advertiser ID, Company ID, Employer ID, ID, Account ID |
| name | name | text / 200 | yes | reject row | Company Name, Company, Recruiter Name, Recruiter, Organisation, Organization, Employer, Employer Name, Client Name |
| contact_name | contact_name | text / 120 |  | reject row | Contact Name, Contact, Full Name, Name, Main Contact |
| contact_first_name | (date chain / derived) | text / 60 |  | reject row | Contact First Name, First Name, Forename, FirstName |
| contact_last_name | (date chain / derived) | text / 60 |  | reject row | Contact Last Name, Contact Surname, Last Name, Surname, LastName |
| contact_email | contact_email | email / 254 |  | drop value | Email, Email Address, E-mail, Contact Email, Recruiter Email, Login Email, Username |
| phone | phone | text / 40 |  | reject row | Phone, Telephone, Tel, Phone Number, Contact Number, Mobile |
| website | website | url / 300 |  | drop value | Website, Web Site, URL, Web Address, Company Website, Homepage |
| logo | logo_key | filename / 200 |  | drop value | Logo, Logo File, Logo Filename, Logo Image, Company Logo, Image |
| last_login | last_active_at | date |  | drop value | Last Login, Last Logged In, Last Login Date, Last Visit, Last Active, Last Activity |
| updated | (date chain / derived) | date |  | drop value | Last Updated, Updated, Date Updated, Modified, Date Modified, Last Modified |
| registered | (date chain / derived) | date |  | drop value | Date Registered, Registered, Registration Date, Date Created, Created, Created Date, Join Date, Date Joined |

### candidates → `candidates`

Dedupe: site + lower(trim(email)); same strategies_id with a different email keeps the latest and warns. Activity date chain: last_login → updated → registered.

| Field | D1 column | Type / max | Req | On invalid | Strategies header aliases |
|---|---|---|---|---|---|
| strategies_id | source_id | id / 40 | yes | reject row | Candidate ID, CandidateID, Jobseeker ID, Job Seeker ID, Member ID, User ID, Registration ID, ID |
| email | email_norm | email / 254 | yes | reject row | Email, Email Address, E-mail, E-mail Address, Candidate Email, Login Email, Username |
| first_name | first_name | text / 60 |  | reject row | First Name, Forename, FirstName, Given Name, Christian Name |
| last_name | last_name | text / 60 |  | reject row | Last Name, Surname, LastName, Family Name |
| phone | phone | text / 40 |  | reject row | Phone, Telephone, Tel, Phone Number, Mobile, Mobile Number, Contact Number |
| location | location | text / 120 |  | reject row; truncate if long | Location, Town, City, Town/City, County, Area, Address |
| sectors | sectors_json | list / 2000 |  | reject row | Sectors, Sector, Job Sectors, Categories, Category, Industries, Industry |
| consent_marketing | consent_marketing | bool |  | drop value | Newsletter, Receive Newsletter, Opt In, Opt-in, Marketing, Marketing Consent, Job Alerts, Subscribe |
| cv_filename | (date chain / derived) | filename / 200 |  | reject row | CV, CV File, CV Filename, Resume, CV Name, Attachment |
| registered | registered_at | date |  | drop value | Date Registered, Registered, Registration Date, Date Created, Created, Join Date, Date Joined |
| last_login | last_active_at | date |  | drop value | Last Login, Last Logged In, Last Login Date, Last Visit, Last Active, Last Activity |
| updated | (date chain / derived) | date |  | drop value | Last Updated, Updated, Date Updated, Modified, Date Modified, Last Modified |

### profiles → `candidates`

Dedupe: site + candidate strategies_id, latest wins. Activity date chain: updated → registered.

| Field | D1 column | Type / max | Req | On invalid | Strategies header aliases |
|---|---|---|---|---|---|
| candidate_id | source_id | id / 40 | yes | reject row | Candidate ID, CandidateID, Jobseeker ID, Member ID, User ID, ID |
| email | email_norm | email / 254 |  | reject row | Email, Email Address, E-mail, Candidate Email |
| headline | headline | text / 200 |  | reject row; truncate if long | Headline, Profile Title, Title, Profile Headline, Current Job Title, Job Title, Summary |
| location | location | text / 120 |  | reject row; truncate if long | Location, Preferred Location, Town, City, Region |
| sectors | sectors_json | list / 2000 |  | reject row | Sectors, Sector, Preferred Sectors, Categories, Category, Industries |
| cv_filename | (date chain / derived) | filename / 200 |  | reject row | CV, CV File, CV Filename, Resume, Attachment |
| updated | last_active_at | date |  | drop value | Last Updated, Updated, Date Updated, Profile Updated, Modified, Date Modified |
| registered | (date chain / derived) | date |  | drop value | Date Created, Created, Date Registered, Registered |

### jobs → `jobs`

Dedupe: site + strategies job id, latest wins. Activity date chain: updated → posted → closing.

| Field | D1 column | Type / max | Req | On invalid | Strategies header aliases |
|---|---|---|---|---|---|
| strategies_id | source_id | id / 40 | yes | reject row | Job ID, JobID, Vacancy ID, Job Ref ID, Advert ID, ID |
| employer_id | employer_id | id / 40 |  | drop value | Recruiter ID, RecruiterID, Client ID, Advertiser ID, Company ID, Employer ID |
| title | title | text / 160 (min 3) | yes | reject row | Job Title, Title, Position, Vacancy Title, Role |
| location | location | text / 120 | yes | reject row; truncate if long | Location, Job Location, Town, City, Place |
| region | region | text / 80 |  | reject row; truncate if long | Region, County, Area |
| job_type | job_type | text / 40 |  | reject row; truncate if long | Job Type, Type, Contract Type, Employment Type, Hours |
| sal_min | sal_min | money |  | drop value | Salary From, Salary Min, Min Salary, Minimum Salary, Salary Low |
| sal_max | sal_max | money |  | drop value | Salary To, Salary Max, Max Salary, Maximum Salary, Salary High |
| currency | currency | text / 8 |  | reject row; truncate if long | Currency, Salary Currency |
| period | period | text / 20 |  | reject row; truncate if long | Salary Period, Period, Per, Salary Per, Pay Period |
| sal_text | sal_text | text / 120 |  | reject row; truncate if long | Salary, Salary Text, Salary Description, Pay, Remuneration |
| sectors | sectors_json | list / 2000 |  | reject row | Sectors, Sector, Categories, Category, Job Sectors, Industry |
| summary | summary | text / 500 |  | reject row; truncate if long | Summary, Short Description, Job Summary, Intro, Teaser |
| description | description | text / 20000 (min 20) | yes | reject row | Description, Job Description, Full Description, Details, Body, Advert Text |
| apply_email | apply_email | email / 254 |  | drop value | Apply Email, Application Email, Contact Email, Email, Response Email |
| apply_url | apply_url | url / 500 |  | drop value | Apply URL, Application URL, External URL, Apply Link, Redirect URL |
| posted | posted_at | date |  | drop value | Date Posted, Posted, Posted Date, Start Date, Live Date, Date Created, Created |
| closing | closing_at | date |  | drop value | Closing Date, Close Date, Expiry Date, Expires, End Date, Deadline |
| updated | (date chain / derived) | date |  | drop value | Last Updated, Updated, Date Updated, Modified, Date Modified |

### applications → `applications`

Dedupe: dedupe_key = sha256(site|job_id|applicant_email_norm), job_id = the D1 job id '{site}:strat:{job id}'; latest submitted wins. Activity date chain: submitted.

| Field | D1 column | Type / max | Req | On invalid | Strategies header aliases |
|---|---|---|---|---|---|
| strategies_id | source_id | id / 40 |  | drop value | Application ID, ApplicationID, Response ID, Apply ID, ID |
| job_id | job_id | id / 40 | yes | reject row | Job ID, JobID, Vacancy ID, Advert ID |
| applicant_name | applicant_name | text / 120 |  | reject row | Name, Applicant Name, Candidate Name, Full Name, Applicant |
| first_name | (date chain / derived) | text / 60 |  | reject row | First Name, Forename, FirstName |
| last_name | (date chain / derived) | text / 60 |  | reject row | Last Name, Surname, LastName |
| applicant_email | applicant_email | email / 254 | yes | reject row | Email, Email Address, E-mail, Applicant Email, Candidate Email |
| phone | phone | text / 40 |  | reject row | Phone, Telephone, Tel, Phone Number, Mobile, Contact Number |
| cover_note | cover_note | text / 5000 |  | reject row; truncate if long | Cover Letter, Cover Note, Covering Letter, Message, Comments, Notes |
| cv_filename | (date chain / derived) | filename / 200 |  | reject row | CV, CV File, CV Filename, Resume, Attachment |
| submitted | submitted_at | date |  | drop value | Date Applied, Applied, Application Date, Date Submitted, Submitted, Date, Response Date, Created |

Derived values:
- employers: `name_norm` = lower-case, punctuation and `ltd|limited|plc` removed. `logo_key` =
  `strategies/{site}/logos/{filename}`: upload the logo files to R2 under that key before go-live.
- candidates: `consent_marketing` is imported as exported; `consent_at` stays NULL (Strategies has no consent
  timestamp). Re-confirm before any marketing send. CV filenames are validated only; CV files are not in the exports.
- profiles: merged into `candidates` by candidate id → email (from `--candidates-csv`, kept rows only) or the
  profile's own email column. Unresolved: rejected `unknown_candidate`.
- jobs: `status` = `live` if closing date ≥ `--as-of`, else `closed` (no closing date = closed). `employer_id` is a
  sub-select, so an employer not yet imported gives NULL instead of a foreign-key error. Currency defaults to the site
  (EUR for ie, GBP for uk) when a salary is present. `sal_min > sal_max` drops both. `apply_url` must be https.
  `created_by = 'import'`. The upsert never overwrites console rows and never reopens a closed job.
- applications: `job_id` = `'{site}:strat:{job id}'`; `dedupe_key = sha256(site|job_id|applicant_email_norm)` using
  that D1 job id (the same key the Worker uses). `candidate_id` is a sub-select on (site, email). `delivery_status =
  'imported'`. Without `--jobs-csv` / `--known-job-ids` the orphan check is skipped with a warning, and `--emit-sql`
  is refused.

## Gates (per input file)

| Gate | Default | Bound | Failure |
|---|---|---|---|
| Yield floor: rows_kept / rows_in | ≥ 0.05 | 0..1, `--allow-low-yield` overrides | exit 3 with exclusion counts + first 5 rejects |
| Reject ceiling: rejected / rows_in | ≤ 0.20 | 0..1 | exit 3 with first 5 rejects |
| Retention months | 24 | 6..84 | exit 2 |
| Required header missing | n/a | n/a | exit 2, prints headers seen |
| Zero data rows | n/a | n/a | no-op, exit 0, nothing written |

On a gate failure no SQL is written.

## How to run

CSVs stay in GreenJobs' own storage (outside the repo). Never in git, never in `.tmp/`.

```bash
S=execution/gtm_client_workflows/greenjobs_redesign/strategies_import.py
# 1. dry run (default) per report and site, all date batches together
python3 $S --site ie --report candidates --csv ~/gj/ie_cand_2025a.csv --csv ~/gj/ie_cand_2025b.csv --as-of 2026-11-20
# 2. emit SQL (path outside the repo), in this order:
python3 $S --site ie --report recruiters --csv ~/gj/ie_recruiters.csv --emit-sql ~/gj/sql/ie_1_recruiters.sql
python3 $S --site ie --report jobs --csv ~/gj/ie_jobs.csv --emit-sql ~/gj/sql/ie_2_jobs.sql
python3 $S --site ie --report candidates --csv ~/gj/ie_cand_*.csv --emit-sql ~/gj/sql/ie_3_candidates.sql
python3 $S --site ie --report profiles --csv ~/gj/ie_profiles.csv --candidates-csv ~/gj/ie_cand_2025a.csv --emit-sql ~/gj/sql/ie_4_profiles.sql
python3 $S --site ie --report applications --csv ~/gj/ie_apps.csv --jobs-csv ~/gj/ie_jobs.csv --emit-sql ~/gj/sql/ie_5_applications.sql
# 3. operator applies each file
npx wrangler@4 d1 execute greenjobs --file=~/gj/sql/ie_1_recruiters.sql
```

`--report-out PATH` saves the full JSON summary (no PII; may be under `<repo>/.tmp/`). Skip files already imported:
export `SELECT sha256 FROM import_batches` to a text file and pass `--done-sha256 FILE`. Each emitted file ends with
an `INSERT OR IGNORE INTO import_batches` row per input file; the same file passed twice in one run is skipped.
Re-applying a file converges (same row counts). Apply batches oldest to newest: an older batch applied later can
overwrite a newer employer name.

## Adding an alias after the first real export

1. Dry-run the real file. If a required field is missing, the error lists the headers seen; `files[].headers.unmapped`
   lists every header not used.
2. Add the real header text to that field's `aliases` in `strategies_mapping.json` (put it first: earlier aliases win
   when two fields could claim one header). If the dates are not day-first, add the format to `date_formats`.
3. Add a fixture row with the new header to `tests/greenjobs_redesign/fixtures/strategies/` (fake data only) and run
   `python3 -m pytest tests/greenjobs_redesign/test_strategies_import.py -q`.
