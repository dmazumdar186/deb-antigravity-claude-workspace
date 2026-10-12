-- Annexe B — Logique de sélection. Date de référence : 2026-10-12.
-- Exécuté tel quel sur SQLite, profils-exercice-PM.csv chargé sans modification dans la table `profils`.

-- 0. DÉDOUBLONNAGE. Le brief annonce 500 membres ; le fichier en contient 525.
--    Les 25 lignes M0501..M0525 sont des doublons de personnes déjà présentes
--    (nom en MAJUSCULES ou composé, prénom tronqué "Man.", e-mail gmail, même poste et même date de début).
--    Règle : même prénom (3 premières lettres), nom contenu l'un dans l'autre, même date de début OU même poste.
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
   AND (a.date_debut_poste = b.date_debut_poste OR a.poste = b.poste)
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
  CASE WHEN lower(trim(coalesce(pays,''))) IN ('uk','united kingdom','royaume-uni') THEN 'GB'
       WHEN pays IS NULL AND (lower(ville) LIKE '%london%' OR lower(ville) LIKE '%londres%') THEN 'GB'
       ELSE pays END                                                         AS pays_norm,
  -- "finance" réconcilié à partir de 3 sources, par ordre de confiance :
  --   secteur déclaré (manque 182 fois) > référentiel entreprise > mots-clés du poste
  CASE
    WHEN secteur_declare IN ('Finance','Banque','Finance / Assurance') THEN 'finance:declare'
    WHEN entreprise IN ('Amundi','AXA IM','Barclays','BNP Paribas','Crédit Agricole CIB','Deutsche Bank','Goldman Sachs',
                        'HSBC','J.P. Morgan','Lazard','Morgan Stanley','Natixis','Rothschild & Co','Société Générale','UBS')
         THEN 'finance:entreprise'
    WHEN lower(poste) REGEXP 'financ|m&a|investment bank|ib analyst|trader|quant|portfolio|asset manag|opcvm|private equity|equity research|treasury|credit risk|risk manager|contrôleur de gestion|fp&a|banquier|conformité bancaire|auditeur financier|chargé d.affaires|gestionnaire de portefeuille|directeur financier'
         THEN 'finance:poste'
    ELSE 'non' END                                                            AS finance_src,
  -- FRAÎCHEUR : ce que les données permettent réellement de dire sur "est-ce encore vrai ?"
  --   A = profil mis à jour < 2 ans OU connexion < 1 an ; B = mis à jour entre 2 et 4 ans ; C = plus vieux
  CASE WHEN date_maj_profil >= date('2026-10-12','-2 years') OR derniere_connexion >= date('2026-10-12','-1 year') THEN 'A'
       WHEN date_maj_profil >= date('2026-10-12','-4 years') THEN 'B'
       ELSE 'C' END                                                          AS fraicheur
FROM membres m;

-- 2. SÉLECTION
SELECT member_id, poste, entreprise, finance_src, ville, pays, date_debut_poste, date_maj_profil,
       derniere_connexion, cotisant, fraicheur
FROM membres_norm
WHERE ville_norm = 'London'                                   -- "à Londres" : ville normalisée
  AND finance_src <> 'non'                                    -- "dans la finance" : 3 sources réconciliées
  AND date_debut_poste <= date('2026-10-12','-3 years')       -- "depuis plus de trois ans" : proxy = ancienneté dans le poste actuel
  AND promo <= 2026                                           -- "diplômés" : tous le sont ici (promos 2005-2024)
ORDER BY fraicheur, date_debut_poste;
