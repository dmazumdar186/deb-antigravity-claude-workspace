-- Annexe B — Logique de sélection. Date de référence : 2026-10-12.
-- Runs as written on SQLite (LIKE only, no REGEXP). For MariaDB replace date(d,'-N years') by DATE_SUB(d, INTERVAL N YEAR). CSV loaded unchanged as `profils`.

-- 0. DÉDOUBLONNAGE. Le brief annonce 500 membres ; le fichier en contient 525.
--    Les 25 lignes M0501..M0525 sont des doublons de personnes déjà présentes
--    (nom en MAJUSCULES ou composé, prénom tronqué "Man.", e-mail gmail, même poste et même date de début).
--    Règle : même prénom (3 premières lettres), nom contenu l'un dans l'autre, ET même date de début de poste.
--    On conserve la fiche la plus récemment mise à jour.
CREATE TABLE membres AS
WITH p AS (
  SELECT *,
    lower(substr(prenom,1,3))                                   AS pn,
    lower(replace(replace(replace(nom,'-',''),' ',''),'.',''))  AS nn
  FROM profils
),
doublons AS (
  SELECT a.member_id AS keep_id, b.member_id AS drop_id
  FROM p a JOIN p b
    ON a.member_id <> b.member_id
   AND a.pn = b.pn
   AND (instr(a.nn, b.nn) > 0 OR instr(b.nn, a.nn) > 0)
   AND a.date_debut_poste = b.date_debut_poste          -- même date de début : évite Martin/Martinez (même poste, dates différentes)
   AND (a.date_maj_profil > b.date_maj_profil
        OR (a.date_maj_profil = b.date_maj_profil AND a.member_id < b.member_id))
)
SELECT * FROM p WHERE member_id NOT IN (SELECT drop_id FROM doublons);

-- 1. NORMALISATION : déterministe, par table de correspondance. Aucun appel au modèle, aucune donnée ne sort.
CREATE TABLE membres_norm AS
SELECT m.*,
  -- "Londres" existe sous 8 graphies (london, LONDON, Londres, Greater London, London - Canary Wharf, ...)
  CASE WHEN lower(ville) LIKE '%london%' OR lower(ville) LIKE '%londres%' OR lower(ville) LIKE '%canary wharf%'
       THEN 'London' ELSE ville END                                          AS ville_norm,
  -- le pays existe sous 3 graphies et manque 42 fois ; on le déduit de la ville quand il manque
  CASE WHEN lower(trim(coalesce(pays,''))) IN ('uk','united kingdom','royaume-uni','england','angleterre') THEN 'GB'
       WHEN pays IS NULL AND (lower(ville) LIKE '%london%' OR lower(ville) LIKE '%londres%') THEN 'GB'
       ELSE pays END                                                         AS pays_norm,
  -- "finance" réconcilié à partir de 3 sources, par ordre de confiance :
  --   secteur déclaré (manque 182 fois) > référentiel entreprise > mots-clés du poste
  CASE
    WHEN secteur_declare IN ('Finance','Banque','Finance / Assurance') THEN 'finance:declare'
    WHEN entreprise IN ('Amundi','AXA IM','Barclays','BNP Paribas','Crédit Agricole CIB','Deutsche Bank','Goldman Sachs',
                        'HSBC','J.P. Morgan','Lazard','Morgan Stanley','Natixis','Rothschild & Co','Société Générale','UBS')
         THEN 'finance:entreprise'
    WHEN (lower(poste) LIKE '%financ%' OR lower(poste) LIKE '%m&a%' OR lower(poste) LIKE '%investment bank%' OR lower(poste) LIKE '%ib analyst%' OR lower(poste) LIKE '%trader%' OR lower(poste) LIKE '%quant%' OR lower(poste) LIKE '%portfolio%' OR lower(poste) LIKE '%asset manag%' OR lower(poste) LIKE '%opcvm%' OR lower(poste) LIKE '%private equity%' OR lower(poste) LIKE '%equity research%' OR lower(poste) LIKE '%treasury%' OR lower(poste) LIKE '%credit risk%' OR lower(poste) LIKE '%risk manager%' OR lower(poste) LIKE '%contrôleur de gestion%' OR lower(poste) LIKE '%fp&a%' OR lower(poste) LIKE '%banquier%' OR lower(poste) LIKE '%conformité bancaire%' OR lower(poste) LIKE '%auditeur financier%' OR lower(poste) LIKE '%chargé d''affaires%' OR lower(poste) LIKE '%gestionnaire de portefeuille%' OR lower(poste) LIKE '%directeur financier%')
         THEN 'finance:poste'
    ELSE 'non' END                                                            AS finance_src,
  -- FRAÎCHEUR : ce que les données permettent réellement de dire sur "est-ce encore vrai ?"
  --   A = profil mis à jour < 2 ans OU connexion < 1 an ; B = mis à jour entre 2 et 4 ans ; C = plus vieux
  -- 60 members carry a last-login date in the future (export defect): a future date is ignored, never trusted
  -- Bornes : A = [0, 2 ans) depuis la mise à jour OU [0, 1 an) depuis la connexion ; B = [2, 4 ans) ; C = 4 ans et plus ou date absente
  CASE WHEN date_maj_profil > date('2026-10-12','-2 years')
         OR (derniere_connexion > date('2026-10-12','-1 year') AND derniere_connexion <= '2026-10-12') THEN 'A'
       WHEN date_maj_profil > date('2026-10-12','-4 years') THEN 'B'
       ELSE 'C' END                                                          AS fraicheur
FROM membres m;

-- 2. SÉLECTION
SELECT member_id, poste, entreprise, finance_src, ville, pays, date_debut_poste, date_maj_profil,
       derniere_connexion, cotisant, fraicheur
FROM membres_norm
WHERE ville_norm = 'London'                                   -- "à Londres" : ville normalisée
  AND (pays_norm = 'GB')                                      -- garde-fou pays : exclut un London (Ontario) si le pays est renseigné
  AND finance_src <> 'non'                                    -- "dans la finance" : 3 sources réconciliées
  AND date_debut_poste <= date('2026-10-12','-3 years')       -- "depuis plus de trois ans" : proxy = ancienneté dans le poste actuel
  AND CAST(promo AS INTEGER) <= 2026                          -- "diplômés" : tous le sont ici (promos 2005-2024) ; CAST pour un import texte
ORDER BY fraicheur, date_debut_poste;
