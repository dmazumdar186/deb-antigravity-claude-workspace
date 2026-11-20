// Write-time facets for console posts (migration 0002, table job_facets). Staff pick sectors, region,
// job type and workplace from taxonomy.json dropdowns; this module validates the picks against the
// frozen vocabulary and derives the rest with the same rules the static build uses (contract from the
// job type, level from the title, agency from the employer name, salary_label in the site currency).
// Imports and feeds write the same table from the Python classifier; the Worker never classifies on read.

import { TAXONOMY, edition, isAgency, levelOf, salaryLabel } from './render/lib.js';
import { descriptionHtml, stripTags } from './render/sanitise.js';
import { renderDescription } from './validate.js';

export const SQL_FACETS_UPSERT = `INSERT INTO job_facets (job_id, sectors_json, regions_json, job_type, workplace, contract_json, loc_class, level, is_agency, salary_display, unverified_cur, taxonomy_version, set_by, updated_at, search_text)
VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15)
ON CONFLICT (job_id) DO UPDATE SET search_text = excluded.search_text,
  sectors_json = excluded.sectors_json, regions_json = excluded.regions_json, job_type = excluded.job_type, workplace = excluded.workplace,
  contract_json = excluded.contract_json, loc_class = excluded.loc_class, level = excluded.level, is_agency = excluded.is_agency,
  salary_display = excluded.salary_display, unverified_cur = excluded.unverified_cur, taxonomy_version = excluded.taxonomy_version,
  set_by = excluded.set_by, updated_at = excluded.updated_at`;

const SECTOR_NAMES = new Set(TAXONOMY.sectors.map((s) => s.name));
export const CONSOLE_TYPES = TAXONOMY.job_types.console;
export const WORKPLACES = Object.keys(TAXONOMY.workplace);
// lib.js TYPE_ALIAS: the job type folds into one contract tag (Home Based -> workplace remote instead).
const TYPE_TO_CONTRACT = { Permanent: 'permanent', Contract: 'contract', 'Fixed-term': 'fixed-term', 'Full-time': 'full-time', 'Part-time': 'part-time', Volunteer: 'volunteer' };

/** The region vocabulary of a site: its map regions plus the nationwide/remote and elsewhere buckets. */
export function regionChoices(site) {
  const ed = edition(site);
  return [...ed.regions, ed.none, ed.elsewhere];
}

/** Validate the taxonomy picks. Returns {ok, value:{sectors, region, job_type, workplace}, errors}. */
export function validatePicks(input, site) {
  const errors = [];
  const sectors = input.sectors ?? [];
  if (!Array.isArray(sectors) || sectors.length < 1 || sectors.length > 3 || new Set(sectors).size !== sectors.length || !sectors.every((s) => SECTOR_NAMES.has(s))) errors.push('sectors');
  const region = input.region === undefined || input.region === null || input.region === '' ? edition(site).none : input.region;
  if (!regionChoices(site).includes(region)) errors.push('region');
  const jobType = input.job_type === undefined || input.job_type === null || input.job_type === '' ? null : input.job_type;
  if (jobType !== null && !CONSOLE_TYPES.includes(jobType)) errors.push('job_type');
  const workplace = input.workplace === undefined || input.workplace === null || input.workplace === '' ? (jobType === 'Home Based' ? 'remote' : 'unspecified') : input.workplace;
  if (!WORKPLACES.includes(workplace)) errors.push('workplace');
  return { ok: errors.length === 0, value: { sectors, region, job_type: jobType, workplace }, errors };
}

/** loc_class from the staff region pick: a mapped region is the site's own country (NI on the UK board),
 * the nationwide bucket is remote when the workplace is remote, the elsewhere bucket is international. */
export function locClassFor(site, region, workplace) {
  const ed = edition(site);
  if (region === 'Northern Ireland') return 'ni';
  if (ed.regions.includes(region)) return site;
  if (region === ed.elsewhere) return 'intl';
  return workplace === 'remote' ? 'remote' : site;
}

/** The job_facets row for a console write. job: validated job (title, employer, sal_*, currency, period, sal_text). */
export function consoleFacets(site, job, picks) {
  const contract = picks.job_type && TYPE_TO_CONTRACT[picks.job_type] ? [TYPE_TO_CONTRACT[picks.job_type]] : [];
  const sal = salaryLabel({ sal_min: job.sal_min, sal_max: job.sal_max, cur: job.currency, period: job.period, sal_text: job.sal_text }, edition(site).currency);
  return {
    sectors: picks.sectors, regions: [picks.region], job_type: picks.job_type, workplace: picks.workplace, contract,
    loc_class: locClassFor(site, picks.region, picks.workplace), level: levelOf(job.title), is_agency: isAgency(job.employer) ? 1 : 0,
    salary_display: sal || null,
    search_text: stripTags(descriptionHtml(job.description, 'https://greenjobs.invalid/', renderDescription)).slice(0, 1500),
  };
}

export function facetsParams(jobId, f, setBy, ts) {
  return [jobId, JSON.stringify(f.sectors), JSON.stringify(f.regions), f.job_type, f.workplace,
    JSON.stringify(f.contract), f.loc_class, f.level, f.is_agency, f.salary_display, 0, TAXONOMY.version, setBy, ts, f.search_text ?? null];
}

export function facetsStmt(db, jobId, f, setBy, ts) {
  return db.prepare(SQL_FACETS_UPSERT).bind(...facetsParams(jobId, f, setBy, ts));
}
