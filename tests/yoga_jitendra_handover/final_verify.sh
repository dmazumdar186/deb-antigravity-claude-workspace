#!/usr/bin/env bash
# Re-runnable evidence capture for the Yoga avec Jitendra final delivery + handover.
# Usage: bash tests/yoga_jitendra_handover/final_verify.sh [handover_dir] > report.md
# Exit 0 only if every check passes.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SITE="$ROOT/execution/personal_workflows/yoga_jitendra_site"
HO="${1:-/tmp/handover}"
fail=0
run() { local name="$1"; shift; echo "### $name"; echo '```'; out=$("$@" 2>&1); rc=$?; echo "$out" | tail -6; echo "exit=$rc"; echo '```'; [ $rc -eq 0 ] && echo "RESULT: PASS" || { echo "RESULT: FAIL"; fail=1; }; echo; }
echo "# Final verification evidence — $(date -u +%FT%TZ)"
echo "Scope: live source ($SITE), handover tree ($HO), live URL https://yogaavecjitendra.fr"
echo
run "1. Live source build" bash -c "cd '$SITE' && npm run build"
run "2. Acceptance gate (142 assertions)" python3 "$ROOT/tests/acceptance_yoga_jitendra.py"
run "3. Front-door synthetic vs live" bash "$ROOT/tests/front_door_yoga_jitendra.sh" https://yogaavecjitendra.fr
run "4. Handover build (includes content check)" bash -c "cd '$HO' && npm run build"
run "5. Content-check regression (9 bad-edit cases)" bash -c "cd '$HO' && node scripts/test_check_content.mjs"
run "6. Pages CMS config vs JSON" python3 "$ROOT/tests/yoga_jitendra_handover/check_pages_cms_config.py" "$HO"
run "7. Cutover script dry run (no changes)" python3 "$SITE/scripts/handover_cutover.py"
run "8. No operator identifiers in handover tree" bash -c "! grep -rIn -i -E 'debolshop|debanjan186|4cdf5cdb|9a1473aa|108615156479975841686' --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=.astro --exclude=package-lock.json '$HO'"
run "9. No secrets/env files tracked in handover" bash -c "cd '$HO' && ! git ls-files | grep -E '(^|/)\.env|credentials|token\.json'"
run "10. Parity: today's files identical live vs handover" bash -c "cd '$SITE' && for f in src/components/Corporate.astro src/components/ClientsStrip.astro src/components/TopNav.astro src/pages/index.astro src/pages/en/index.astro src/content/corporate.fr.json src/content/corporate.en.json src/content/hero.fr.json src/content/hero.en.json src/content/clients.json src/content/i18n_ui.fr.json src/content/i18n_ui.en.json src/content/site.json src/content/reviews-seed.json public/assets/logos/believe.svg public/assets/logos/legrand.svg public/assets/logos/caisse-epargne.png public/assets/logos/sciences-po.svg public/assets/logos/fti-consulting.png; do cmp -s \$f '$HO'/\$f || { echo DIFF \$f; exit 1; }; done; echo '19 files identical'"
run "11. Built FR/EN contain section, caption, 12 clients, nav link" python3 - "$SITE/dist" <<'PY'
import sys,json,re,pathlib
d=pathlib.Path(sys.argv[1]); site=d.parent
names=[c["name"] for c in json.load(open(site/"src/content/clients.json",encoding="utf-8"))["clients"]]
ok=True
for page,needles in (("index.html",["id=\"entreprise\"","Le yoga au service du bien-être de vos équipes","notamment dans le cadre de missions via TrainMe","href=\"#entreprise\""]),("en/index.html",["id=\"entreprise\"","Yoga for your teams","assignments through TrainMe","href=\"#entreprise\""])):
    h=(d/page).read_text(encoding="utf-8").replace("&#39;","'").replace("&amp;","&")
    miss=[n for n in needles if n not in h]+[n for n in names if n not in h]
    print(page, "clients:",len(names),"missing:",miss); ok&=not miss
sys.exit(0 if ok else 1)
PY
run "12. Live site serves the new section + new logos" bash -c "h=\$(curl -sSL https://yogaavecjitendra.fr); for n in 'id=\"entreprise\"' 'TrainMe.' believe.svg legrand.svg caisse-epargne.png sciences-po.svg; do echo \"\$h\" | grep -q \"\$n\" && echo \"ok \$n\" || { echo \"MISSING \$n\"; exit 1; }; done"
echo "OVERALL: $([ $fail -eq 0 ] && echo PASS || echo FAIL)"
exit $fail
