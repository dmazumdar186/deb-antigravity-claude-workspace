"""Round-2 update of the Option A section of 26_UAT_Signoff.md (only lines inside that section)."""
import re, sys
p = sys.argv[1]
s = open(p, encoding='utf-8').read()
head, sep, a = s.partition('## Option A: WordPress plugin (WordPress Playground)')
assert sep
a, sep2, tail = a.partition('\n## Extra')
def rep_line(prefix, new):
    global a
    lines = a.split('\n'); hits = [i for i, l in enumerate(lines) if l.startswith(prefix)]
    assert len(hits) == 1, (prefix, hits); lines[hits[0]] = new; a = '\n'.join(lines)

rep_line('| A1.4 |', '| A1.4 | Click « Publier ». | « Publication mise en ligne. » | PASS (hosted too: 1.0 s, no « Connexion perdue » in 3 runs) | r2/evidence/uat-S1-04.png, hosted2-s1-published-1440.png |')
rep_line('| A1.K |', '| A1.K | Keyboard only: steps A1.2 to A1.4. | The congress is published. | PASS | r2/kb2-result.json: 7 Tabs to « Congrès », 9 to « Ajouter un congrès », 38 from the title to « Date de début » (through « Description du congrès », no tab trap), 2/2/1/1 for the other fields, then 22 Shift+Tab to « Publier » and Enter. Result: « Publication mise en ligne. » The focus ring is visible throughout. A11Y-A-005 is fixed (A11Y-A-203). |')
rep_line('Note A1.4:', 'Note A1.4: round 1 saw one « Connexion perdue » on a loaded machine (USAB-A-008). In round 2 autosave is off on the congress editor, and « Publier » worked in every local and hosted run, so USAB-A-008 is closed. New in round 2: « Description du congrès » shows raw block markup (`<!-- wp:paragraph -->`) on the seeded congresses (EYE-A-201, Medium). It does not block any step.')
rep_line('| A2.0 |', '| A2.0 | Open the hosted **visitor** link. | The catalogue opens, logged out. | PASS | PASS | hosted2.log: logged out in 3 of 3 runs (no « Bonjour », no admin bar), no Playground toolbar, catalogue in 13.1–16.5 s at 1440 and 13.1–15.8 s at 390. The hosted chip → card → enquiry also passed (DV-2026-0007). USAB-A-201. |')
rep_line('| A2.1 |', '| A2.1 | Open the catalogue while logged out. | « Catalogue des congrès » and « 12 congrès trouvés ». | PASS | PASS | r2/evidence/uat-S2-01.png. The run showed 13, because A1 had just published one more congress; the fresh seed shows 12 (visitor-01-catalogue-1440.png). |')
rep_line('| A2.K |', '| A2.K | Keyboard only: Tab to the « Cardiologie » chip, press Enter, then Tab to the first card and press Enter. | The details page opens, with a visible focus ring. | PASS | n/a | r2/kb2-result.json (12 + 24 Tabs) |')
rep_line('| A3.4 |', '| A3.4 | Correct the form (2 passengers, return 30/08/2027) and click « Envoyer ma demande » once. | « Merci, votre demande a bien été envoyée. » and « Votre référence : DV-2026-NNNN ». | PASS | PASS | DV-2026-0007 (1440), DV-2026-0008 (390); hosted DV-2026-0007 |')
rep_line('| A3.K |', '| A3.K | Keyboard only: fill and send the form. | A reference is shown. | PASS | n/a | r2/kb2-result.json |')
rep_line('| A4.5 |', '| A4.5 | Go back to « Tableau de bord ». | « Nouvelle » has gone down by 1. | PASS | r2/evidence/uat-S4-05.png (4 → 3) |')
rep_line('| A4.K |', '| A4.K | Keyboard only: steps A4.2 to A4.3. | The status is saved. | PASS | r2/kb2-result.json (31 + 24 + 3 Tabs). Hosted, mouse: equipe changed DV-2026-0006 to « Qualifiée » (hosted2-s4-1440.png). |')
rep_line('| A5.K |', '| A5.K | Keyboard only: request, approve and reveal. | All three succeed. | PASS | r2/kb2-result.json (15/23/1, 44, 15/23 Tabs). Hosted, mouse: request, approve, reveal, and masked again after reload (hosted2-s5-reveal-1440.png). |')
a = re.sub(r'\*\*Result, Option A:\*\*[^\n]*',
  '**Result, Option A (round 2, 6 Nov 2026):** 51 of 51 local mouse steps pass (A1 10, A2 12, A3 10, A4 8, A5 11). All five keyboard-only stories pass, including A1.K publish. The hosted walk passes 11 of 11 steps, and A2.0 passes. Round 1\'s two failures (A2.0, A1.K) are fixed. One item is still open outside the WordPress demo itself: the demo hub (`site/demo/index.html`) says in Task 4, « Your enquiry from task 3 is at the top ». On the hosted links it is not there, because the visitor link and the admin link are separate in-browser sites (USAB-A-207, Major, hub copy). Also open: EYE-A-201 (raw block markup in the description field, Medium), USAB-A-208 (hub copy, Minor) and EYE-A-202 (revealed code wraps, Minor). Details are in `qa/register/A_ux.md`.', a)
a = re.sub(r'\| A \| 1\. Create and edit a congress \|[^\n]*',
              '| A | 1. Create and edit a congress | « Internal UAT (ProdCraft) » | 06/11/2026 | PASS (10/10 + keyboard + hosted) | EYE-A-201 (medium, raw markup in description) | |', a)
a = re.sub(r'\| A \| 2\. Catalogue, search, filters, details \|[^\n]*',
              '| A | 2. Catalogue, search, filters, details | « Internal UAT (ProdCraft) » | 06/11/2026 | PASS (12/12 + A2.0 hosted + keyboard) | none | |', a)
a = re.sub(r'\| A \| 3\. Flight enquiry \|[^\n]*',
              '| A | 3. Flight enquiry | « Internal UAT (ProdCraft) » | 06/11/2026 | PASS (10/10 + keyboard + hosted) | none | |', a)
a = re.sub(r'\| A \| 4\. Team receives, tracks, updates \|[^\n]*',
              '| A | 4. Team receives, tracks, updates | « Internal UAT (ProdCraft) » | 06/11/2026 | PASS (8/8 + keyboard + hosted) | USAB-A-207 (major, demo hub Task 4 copy), USAB-A-208 (minor) | |', a)
a = re.sub(r'\| A \| 5\. GM&E codes and authorisation \|[^\n]*',
              '| A | 5. GM&E codes and authorisation | « Internal UAT (ProdCraft) » | 06/11/2026 | PASS (11/11 + keyboard + hosted) | EYE-A-202 (minor), USAB-A-208 (hub Task 5 path) | |', a)
print([l[:60] for l in a.split("\n") if l.startswith("| A |")])
open(p, 'w', encoding='utf-8').write(head + sep + a + sep2 + tail)
print('ok')
