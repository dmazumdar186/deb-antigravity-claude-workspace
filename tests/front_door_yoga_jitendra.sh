#!/usr/bin/env bash
# Front-door synthetic for yoga_jitendra_site.
# Per ~/.claude/rules/front-door-synthetic.md — hits the live URL like a real
# visitor and asserts the artifact contract.
#
# Usage:
#   bash tests/front_door_yoga_jitendra.sh                                     # default: https://yogaavecjitendra.fr
#   bash tests/front_door_yoga_jitendra.sh https://yoga-jitendra.pages.dev
#
# Exit 0 = green; non-zero = deploy/probation count blocked.
#
# 2026-09-01: since the SEO v2 i18n restructure the EN home lives at /en/
# (no longer inlined in the FR page), so EN assertions run against a second
# fetch. Default URL is the production custom domain, per
# ~/.claude/rules/live-artifact-acceptance.md (assert what real users hit).

set -euo pipefail

URL="${1:-https://yogaavecjitendra.fr}"

HTML_FILE="$(mktemp)"
HTML_FILE_EN="$(mktemp)"
trap 'rm -f "$HTML_FILE" "$HTML_FILE_EN"' EXIT

fetch() {
  local url="$1"; local out="$2"
  local status
  status=$(curl -sS -L -o "$out" -w "%{http_code}" --max-time 30 "$url" 2>/dev/null || echo "000")
  if [ "$status" != "200" ]; then
    echo "FAIL: HTTP $status from $url (may be curl/SSL — try WebFetch or a fresh cache-bust)"
    exit 1
  fi
  local bytes
  bytes=$(wc -c < "$out")
  echo ">> $url — HTTP 200, ${bytes} bytes"
  if [ "$bytes" -lt 20000 ]; then
    echo "FAIL: body suspiciously small (${bytes} bytes) from $url"
    exit 1
  fi
}

fetch "$URL" "$HTML_FILE"
fetch "$URL/en/" "$HTML_FILE_EN"

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
check_en() {
  local desc="$1"; local pattern="$2"
  if grep -qE "$pattern" "$HTML_FILE_EN"; then
    echo "  OK  $desc"
  else
    echo "  FAIL $desc (pattern: $pattern, page: /en/)" >&2
    FAILS=$((FAILS + 1))
  fi
}

echo ">> Hero + bilingual"
check "hero FR headline word Respirer"  "Respirer"
check "hero FR headline word Bouger"    "Bouger"
check_en "hero EN headline word Breathe" "Breathe"
check_en "hero EN headline word Move"    "Move"

echo ">> Contact contract"
# WhatsApp goes through the /wa-out click-tracking redirect since SEO v2
# (functions/wa-out.ts) — the raw wa.me link no longer appears in markup.
check "WhatsApp CTA via /wa-out"        "/wa-out\\?source="
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

echo ">> Ambient audio (licensed Pixabay bansuri recording, 2026-09-01)"
check "audio element"                   "id=\"om-audio\""
check "bansuri ambient asset wired"     "bansuri-studio\\.mp3"
check_absent "old birds asset gone"     "birds-dawn\\.mp3"
check_absent "old chant asset gone"     "himalayan-chant\\.mp3"
check_absent "old piano asset gone"     "serene-dawn\\.mp3"
check_absent "old synth bansuri gone"   "bansuri-dawn\\.mp3"
check "first-gesture auto-start"        "firstGesture"

# The referenced asset must actually SERVE (a present <audio src> with a 404
# behind it is silent audio — the 2026-08-03 stale-fallback class).
AUDIO_HEAD=$(curl -sSI --max-time 30 "$URL/assets/audio/bansuri-studio.mp3" 2>/dev/null || true)
if echo "$AUDIO_HEAD" | head -1 | grep -q " 200" && echo "$AUDIO_HEAD" | grep -qi "content-type: audio/mpeg"; then
  AUDIO_LEN=$(echo "$AUDIO_HEAD" | grep -i "^content-length:" | tr -dc '0-9')
  if [ "${AUDIO_LEN:-0}" -gt 100000 ]; then
    echo "  OK  ambient mp3 serves live (200, audio/mpeg, ${AUDIO_LEN} bytes)"
  else
    echo "  FAIL ambient mp3 suspiciously small (${AUDIO_LEN:-0} bytes)" >&2
    FAILS=$((FAILS + 1))
  fi
else
  echo "  FAIL ambient mp3 not serving as audio/mpeg 200 at /assets/audio/bansuri-studio.mp3" >&2
  FAILS=$((FAILS + 1))
fi

echo ">> Reviews page (date backfill regression guard, 2026-09-01)"
# Virginie's Google-authoritative date. If the build ever silently falls back
# to the 4-review seed (which has no Google reviews at all), this fails too.
REVIEWS_FILE="$(mktemp)"
curl -sS -L -o "$REVIEWS_FILE" --max-time 30 "$URL/reviews/" 2>/dev/null || true
if grep -q "Virginie E" "$REVIEWS_FILE" && grep -q '"datePublished":"2026-07-14"' "$REVIEWS_FILE"; then
  echo "  OK  reviews page carries backfilled Google review + correct date"
else
  echo "  FAIL reviews page missing Virginie E / datePublished 2026-07-14 (backfill regressed or seed fallback shipped)" >&2
  FAILS=$((FAILS + 1))
fi
rm -f "$REVIEWS_FILE"

echo ">> Today's features (2026-07-08)"
check "lineage yantra backdrop"         "lineage-yantra-bg"
check "enterprise video wired"          "enterprise-yoga\\.mp4"
check "crossfade markup"                "data-crossfade"
check "new studio class image"          "studio-jitendra-class\\.jpg"
check "designer credit FR"              "Conçu par Debanjan"
check_en "designer credit EN"           "Designed by Debanjan"
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
