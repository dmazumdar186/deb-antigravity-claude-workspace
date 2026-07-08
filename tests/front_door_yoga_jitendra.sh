#!/usr/bin/env bash
# Front-door synthetic for yoga_jitendra_site.
# Per ~/.claude/rules/front-door-synthetic.md — hits the live URL like a real
# visitor and asserts the artifact contract.
#
# Usage:
#   bash tests/front_door_yoga_jitendra.sh                                     # default: https://yoga-jitendra.pages.dev
#   bash tests/front_door_yoga_jitendra.sh https://yoga-jitendra.pages.dev
#
# Exit 0 = green; non-zero = deploy/probation count blocked.

set -euo pipefail

URL="${1:-https://yoga-jitendra.pages.dev}"

HTML_FILE="$(mktemp)"
trap 'rm -f "$HTML_FILE"' EXIT

echo ">> Fetching $URL"
HTTP_STATUS=$(curl -sS -L -o "$HTML_FILE" -w "%{http_code}" --max-time 30 "$URL" 2>/dev/null || echo "000")
if [ "$HTTP_STATUS" != "200" ]; then
  echo "FAIL: HTTP $HTTP_STATUS from $URL (may be curl/SSL — try WebFetch or a fresh cache-bust)"
  exit 1
fi

BYTES=$(wc -c < "$HTML_FILE")
echo ">> HTTP 200, ${BYTES} bytes"
if [ "$BYTES" -lt 20000 ]; then
  echo "FAIL: body suspiciously small (${BYTES} bytes)"
  exit 1
fi

FAILS=0
check() {
  local desc="$1"; local pattern="$2"
  if grep -qE "$pattern" "$HTML_FILE"; then
    echo "  OK  $desc"
  else
    echo "  FAIL $desc (pattern: $pattern)" >&2
    FAILS=$((FAILS + 1))
  fi
}
check_absent() {
  local desc="$1"; local pattern="$2"
  if grep -qE "$pattern" "$HTML_FILE"; then
    echo "  FAIL $desc — pattern present (should not be): $pattern" >&2
    FAILS=$((FAILS + 1))
  else
    echo "  OK  $desc"
  fi
}

echo ">> Hero + bilingual"
check "hero FR headline word Respirer"  "Respirer"
check "hero FR headline word Bouger"    "Bouger"
check "hero EN headline word Breathe"   "Breathe"
check "hero EN headline word Move"      "Move"

echo ">> Contact contract"
check "WhatsApp CTA"                    "wa\\.me/33758255583"
check "phone tel link"                  "tel:\\+33758255583"
check "email mailto link"               "jitendranitrr13@gmail.com"
check "studio address"                  "22 rue Eugène Manuel"

echo ">> Lineage / traditional yoga"
check "shloka Devanagari"               "योगश्चित्तवृत्तिनिरोधः"
check "shloka translit"                 "Yogaḥ"
check "shloka source Patañjali"         "Patañjali"
check "Om devanagari symbol"            "ॐ"
check "Ashtanga limbs Prāṇāyāma"        "Prāṇāyāma"
check "Ashtanga limbs Samādhi"          "Samādhi"

echo ">> GLM 5.2 mandala backdrop"
check "hero-backdrop wrapper"           "hero-backdrop"
check "mandala rotation class"          "mandala-spin"

echo ">> Audio (real vocal Om chant + tanpura)"
check "om audio element"                "id=\"om-audio\""
check "om chant asset wired"            "om-aum-chant\\.mp3"
check "tanpura drone builder"           "buildDrone"
check "first-gesture auto-start"        "firstGesture"

echo ">> Today's features (2026-07-08)"
check "lineage yantra backdrop"         "lineage-yantra-bg"
check "enterprise video wired"          "enterprise-yoga\\.mp4"
check "crossfade markup"                "data-crossfade"
check "new studio class image"          "studio-jitendra-class\\.jpg"
check "designer credit FR"              "Conçu par Debanjan"
check "designer credit EN"              "Designed by Debanjan"
check "prodcraft link"                  "prodcraft\\.fyi"
check "all-on-quote (Sur devis)"        "Sur devis"

echo ">> Guardrails (removed / banned strings)"
check "audio mute button restored"         "data-audio-toggle"
check_absent "removed collage montsouris"  "gallery-montsouris"
check_absent "removed collage interiors"   "gallery-studio-interiors"
check_absent "no placeholder tokens"       "\\{\\{"
check_absent "no dead playOm code"         "playOm"
check_absent "no dead flute code"          "playFluteNote"
check_absent "no priceRange schema literal" "\"priceRange\""
check_absent "no euro price 60 €"          "60 €"
check_absent "no dollar price €60"         "€60"

if [ "$FAILS" -gt 0 ]; then
  echo
  echo "FAIL: $FAILS front-door assertion(s) broke. Synthetic NOT green; LIVE-PROBATIONARY count cannot start." >&2
  exit 1
fi

echo
echo "PASS: yoga_jitendra_site front-door synthetic green against $URL"
