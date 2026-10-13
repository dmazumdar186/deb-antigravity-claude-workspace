-- Annex B — Selection logic. Reference date: 2026-10-12.
-- Runs as written on SQLite (LIKE only, no REGEXP). For MariaDB replace date(d,'-N years') by DATE_SUB(d, INTERVAL N YEAR).
-- The CSV (profils-exercice-PM.csv) is loaded unchanged as table `profils`; its column names are the dataset's own (French).

-- 0. DEDUPLICATION. The brief announces 500 members; the file holds 525 rows.
--    Rows M0501..M0525 are duplicates of people already present
--    (surname in CAPITALS or compound, truncated first name "Man.", gmail address, same job and same start date).
--    Rule: same first name (first 3 letters), surnames contained one in the other, AND same job start date.
--    An earlier "or same job" variant also merged Martin into Martinez, so the start date is required.
--    The most recently updated record is kept.
CREATE TABLE members AS
WITH p AS (
  SELECT *,
    lower(substr(prenom,1,3))                                   AS fn,
    lower(replace(replace(replace(nom,'-',''),' ',''),'.',''))  AS ln
  FROM profils
),
duplicates AS (
  SELECT a.member_id AS keep_id, b.member_id AS drop_id
  FROM p a JOIN p b
    ON a.member_id <> b.member_id
   AND a.fn = b.fn
   AND (instr(a.ln, b.ln) > 0 OR instr(b.ln, a.ln) > 0)
   AND a.date_debut_poste = b.date_debut_poste
   AND (a.date_maj_profil > b.date_maj_profil
        OR (a.date_maj_profil = b.date_maj_profil AND a.member_id < b.member_id))
)
SELECT * FROM p WHERE member_id NOT IN (SELECT drop_id FROM duplicates);

-- 1. NORMALISATION: deterministic, by lookup table. No model call, nothing leaves the platform.
CREATE TABLE members_norm AS
SELECT m.*,
  -- "London" appears in 8 spellings (london, LONDON, Londres, Greater London, London - Canary Wharf, ...)
  CASE WHEN lower(ville) LIKE '%london%' OR lower(ville) LIKE '%londres%' OR lower(ville) LIKE '%canary wharf%'
       THEN 'London' ELSE ville END                                          AS city_norm,
  -- the country appears in 3 spellings and is missing 41 times; inferred from the city when missing
  CASE WHEN lower(trim(coalesce(pays,''))) IN ('uk','united kingdom','royaume-uni','england','angleterre') THEN 'GB'
       WHEN pays IS NULL AND (lower(ville) LIKE '%london%' OR lower(ville) LIKE '%londres%') THEN 'GB'
       ELSE pays END                                                         AS country_norm,
  -- "finance" reconciled from 3 sources, in order of confidence:
  --   declared sector (missing 174 times) > employer reference list > job-title keywords (French, because the data is)
  CASE
    WHEN secteur_declare IN ('Finance','Banque','Finance / Assurance') THEN 'finance:declared'
    WHEN entreprise IN ('Amundi','AXA IM','Barclays','BNP Paribas','Crédit Agricole CIB','Deutsche Bank','Goldman Sachs',
                        'HSBC','J.P. Morgan','Lazard','Morgan Stanley','Natixis','Rothschild & Co','Société Générale','UBS')
         THEN 'finance:employer'
    WHEN (lower(poste) LIKE '%financ%' OR lower(poste) LIKE '%m&a%' OR lower(poste) LIKE '%investment bank%' OR lower(poste) LIKE '%ib analyst%' OR lower(poste) LIKE '%trader%' OR lower(poste) LIKE '%quant%' OR lower(poste) LIKE '%portfolio%' OR lower(poste) LIKE '%asset manag%' OR lower(poste) LIKE '%opcvm%' OR lower(poste) LIKE '%private equity%' OR lower(poste) LIKE '%equity research%' OR lower(poste) LIKE '%treasury%' OR lower(poste) LIKE '%credit risk%' OR lower(poste) LIKE '%risk manager%' OR lower(poste) LIKE '%contrôleur de gestion%' OR lower(poste) LIKE '%fp&a%' OR lower(poste) LIKE '%banquier%' OR lower(poste) LIKE '%conformité bancaire%' OR lower(poste) LIKE '%auditeur financier%' OR lower(poste) LIKE '%chargé d''affaires%' OR lower(poste) LIKE '%gestionnaire de portefeuille%' OR lower(poste) LIKE '%directeur financier%')
         THEN 'finance:title'
    ELSE 'none' END                                                           AS finance_src,
  -- RELIABILITY: what the data can actually say about "is this still true?"
  --   A = current: profile updated within [0, 2 y) OR login within [0, 1 y)
  --   B = to confirm: profile updated within [2, 4 y)
  --   C = to reactivate: older, or no date at all
  --   60 members carry a last-login date in the future (export defect): a future date is ignored, never trusted
  CASE WHEN date_maj_profil > date('2026-10-12','-2 years')
         OR (derniere_connexion > date('2026-10-12','-1 year') AND derniere_connexion <= '2026-10-12') THEN 'A'
       WHEN date_maj_profil > date('2026-10-12','-4 years') THEN 'B'
       ELSE 'C' END                                                          AS reliability
FROM members m;

-- 2. SELECTION
SELECT member_id, poste, entreprise, finance_src, ville, pays, date_debut_poste, date_maj_profil,
       derniere_connexion, cotisant, reliability
FROM members_norm
WHERE city_norm = 'London'                                   -- "in London": normalised city
  AND country_norm = 'GB'                                     -- country gate: excludes a London (Ontario) when the country is filled
  AND finance_src <> 'none'                                   -- "working in finance": 3 reconciled sources
  AND date_debut_poste <= date('2026-10-12','-3 years')       -- "for more than three years": proxy = tenure in the current job
  AND CAST(promo AS INTEGER) <= 2026                          -- "graduates": all are (class years 2005-2024); CAST survives a text import
ORDER BY reliability, date_debut_poste;
