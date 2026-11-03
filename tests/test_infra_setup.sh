#!/usr/bin/env bash
# tests/test_infra_setup.sh — 6-tier QA for the self-hosted setup scripts
#   execution/infrastructure/setup_freellmapi.sh
#   execution/infrastructure/setup_pentagi.sh
#
# Non-destructive: everything runs in a throwaway $SANDBOX with *_DIR overrides;
# nothing touches $HOME/dev, the network, or Docker. Tests that genuinely need a
# Docker daemon are SKIPped (counted, not failed) when none is reachable.
#
# Exit 0 if all pass, 1 if any fail.

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FREE="$ROOT/execution/infrastructure/setup_freellmapi.sh"
PENT="$ROOT/execution/infrastructure/setup_pentagi.sh"
SANDBOX="$(mktemp -d)"
trap 'rm -rf "$SANDBOX"' EXIT

PASS=0; FAIL=0; SKIP=0
declare -A TPASS TFAIL
cur=""
tier() { cur="$1"; printf '\n=== %s ===\n' "$1"; }
pass() { PASS=$((PASS+1)); TPASS[$cur]=$(( ${TPASS[$cur]:-0} + 1 )); printf 'PASS  %s\n' "$1"; }
fail() { FAIL=$((FAIL+1)); TFAIL[$cur]=$(( ${TFAIL[$cur]:-0} + 1 )); printf 'FAIL  %s\n' "$1"; }
skip() { SKIP=$((SKIP+1)); printf 'SKIP  %s\n' "$1"; }

# assert_eq LABEL EXPECTED ACTUAL
assert_eq() { if [ "$2" = "$3" ]; then pass "$1"; else fail "$1 — expected [$2] got [$3]"; fi; }
# assert_contains LABEL NEEDLE HAYSTACK
assert_contains() { case "$3" in *"$2"*) pass "$1";; *) fail "$1 — missing [$2]";; esac; }
# assert_not_contains LABEL NEEDLE HAYSTACK
assert_not_contains() { case "$3" in *"$2"*) fail "$1 — unexpectedly found [$2]";; *) pass "$1";; esac; }

docker_up() { command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; }

# Extract a self-contained function definition from a script and echo it (for unit tests).
extract_fn() { sed -n "/^$2()/,/^}/p" "$1"; }

# ───────────────────────── TIER 1: UNIT ─────────────────────────
tier "TIER 1: UNIT TESTS"

# gen_key / gen_secret: 64 hex chars, random
k1=$(bash -c "$(extract_fn "$FREE" gen_key); have(){ command -v \"\$1\" >/dev/null 2>&1; }; gen_key")
k2=$(bash -c "$(extract_fn "$FREE" gen_key); have(){ command -v \"\$1\" >/dev/null 2>&1; }; gen_key")
if printf '%s' "$k1" | grep -qE '^[0-9a-f]{64}$'; then pass "freellmapi gen_key: 64 hex chars"; else fail "freellmapi gen_key: got [$k1]"; fi
[ "$k1" != "$k2" ] && pass "freellmapi gen_key: differs across calls (random)" || fail "freellmapi gen_key: repeated same value"

s1=$(bash -c "$(extract_fn "$PENT" gen_secret); have(){ command -v \"\$1\" >/dev/null 2>&1; }; gen_secret")
if printf '%s' "$s1" | grep -qE '^[0-9a-f]{64}$'; then pass "pentagi gen_secret: 64 hex chars"; else fail "pentagi gen_secret: got [$s1]"; fi

# set_env / replace_default (pentagi) — the real .env mutation logic
mk_setenv_harness() {
  { extract_fn "$PENT" set_env; extract_fn "$PENT" replace_default; } > "$SANDBOX/envfns.sh"
}
mk_setenv_harness
run_envfn() { # ENV_FILE_CONTENTS ; commands... ; prints resulting file
  local ef="$SANDBOX/ef.$RANDOM"; printf '%s' "$1" > "$ef"; shift
  DRY_RUN=0 ENV_FILE="$ef" bash -c "source '$SANDBOX/envfns.sh'
log(){ :; }; $*" >/dev/null 2>&1
  cat "$ef"; rm -f "$ef"
}

out=$(run_envfn $'FOO=bar\n' 'set_env BAZ qux')
assert_contains "set_env: appends new key" "BAZ=qux" "$out"
assert_contains "set_env: keeps existing key" "FOO=bar" "$out"

out=$(run_envfn $'FOO=old\n' 'set_env FOO new')
assert_contains "set_env: replaces existing value" "FOO=new" "$out"
assert_not_contains "set_env: old value gone after replace" "FOO=old" "$out"

# value with sed/shell metacharacters must be stored verbatim, not interpreted
out=$(run_envfn $'URL=x\n' "set_env URL 'https://a.b/c?d=1&e=2|f'")
assert_contains "set_env: value with / & | stored verbatim" "URL=https://a.b/c?d=1&e=2|f" "$out"

# replace_default only fires when the value still equals the insecure default (or is blank)
out=$(run_envfn $'COOKIE_SIGNING_SALT=salt\n' 'replace_default COOKIE_SIGNING_SALT salt GENERATED123')
assert_contains "replace_default: replaces when at insecure default" "COOKIE_SIGNING_SALT=GENERATED123" "$out"

out=$(run_envfn $'COOKIE_SIGNING_SALT=my-own-secret\n' 'replace_default COOKIE_SIGNING_SALT salt GENERATED123')
assert_contains "replace_default: preserves operator-set custom value" "COOKIE_SIGNING_SALT=my-own-secret" "$out"
assert_not_contains "replace_default: does not clobber custom with generated" "GENERATED123" "$out"

# ───────────────────────── TIER 2: INTEGRATION ─────────────────────────
tier "TIER 2: INTEGRATION TESTS"

# freellmapi auto mode-selection: no docker daemon => node branch chosen, dry-run prints node steps
out=$(FREELLMAPI_DIR="$SANDBOX/fa" bash "$FREE" --dry-run 2>&1); rc=$?
assert_eq "freellmapi --dry-run exit code" "0" "$rc"
assert_contains "freellmapi --dry-run: picks node mode (no docker)" "Mode: node" "$out"
assert_contains "freellmapi --dry-run: plans git clone" "git clone" "$out"

# pentagi secret + LLM wiring flow against a stand-in .env.example (no clone/network)
mkdir -p "$SANDBOX/pe"
: > "$SANDBOX/pe/.git"  # presence marker only; we drive env fns directly below
cat > "$SANDBOX/pe_env" <<'E'
COOKIE_SIGNING_SALT=salt
PENTAGI_POSTGRES_PASSWORD=postgres
NEO4J_PASSWORD=devpassword
E
int_out=$(DRY_RUN=0 ENV_FILE="$SANDBOX/pe_env" bash -c "source '$SANDBOX/envfns.sh'
log(){ :; }
gen_secret(){ echo RANDOMSECRET\$1; }
replace_default COOKIE_SIGNING_SALT salt \$(gen_secret A)
replace_default PENTAGI_POSTGRES_PASSWORD postgres \$(gen_secret B)
replace_default NEO4J_PASSWORD devpassword \$(gen_secret C)
set_env LLM_SERVER_URL https://openrouter.ai/api/v1
set_env LLM_SERVER_KEY sk-or-test" 2>&1; cat "$SANDBOX/pe_env")
assert_contains "pentagi integ: salt replaced" "COOKIE_SIGNING_SALT=RANDOMSECRETA" "$int_out"
assert_contains "pentagi integ: pg password replaced" "PENTAGI_POSTGRES_PASSWORD=RANDOMSECRETB" "$int_out"
assert_contains "pentagi integ: neo4j password replaced" "NEO4J_PASSWORD=RANDOMSECRETC" "$int_out"
assert_contains "pentagi integ: OpenRouter URL wired" "LLM_SERVER_URL=https://openrouter.ai/api/v1" "$int_out"
assert_not_contains "pentagi integ: no insecure default left (salt)" "COOKIE_SIGNING_SALT=salt" "$int_out"

# ───────────────────────── TIER 3: END-TO-END ─────────────────────────
tier "TIER 3: END-TO-END TESTS"

# freellmapi --help
out=$(bash "$FREE" --help 2>&1); rc=$?
assert_eq "freellmapi --help exit 0" "0" "$rc"
assert_contains "freellmapi --help shows usage" "Usage:" "$out"

# freellmapi --down on a dir that doesn't exist
out=$(FREELLMAPI_DIR="$SANDBOX/none" bash "$FREE" --down 2>&1); rc=$?
assert_eq "freellmapi --down (absent dir) exit 0" "0" "$rc"
assert_contains "freellmapi --down (absent dir) message" "Nothing to stop" "$out"

# freellmapi --dry-run must not create the clone dir or an .env
FREELLMAPI_DIR="$SANDBOX/fa2" bash "$FREE" --dry-run >/dev/null 2>&1
[ ! -e "$SANDBOX/fa2" ] && pass "freellmapi --dry-run: creates no files" || fail "freellmapi --dry-run: created $SANDBOX/fa2"

# pentagi --help
out=$(bash "$PENT" --help 2>&1); rc=$?
assert_eq "pentagi --help exit 0" "0" "$rc"
assert_contains "pentagi --help shows usage" "Usage:" "$out"
assert_contains "pentagi --help carries authorized-targets warning" "AUTHORIZED TARGETS ONLY" "$out"

# pentagi --down absent dir (needs docker only to actually compose-down; absent dir short-circuits first)
out=$(PENTAGI_DIR="$SANDBOX/none2" bash "$PENT" --down 2>&1); rc=$?
assert_eq "pentagi --down (absent dir) exit 0" "0" "$rc"
assert_contains "pentagi --down (absent dir) message" "Nothing to stop" "$out"

# pentagi --dry-run should be an offline preview (no Docker required)
out=$(PENTAGI_DIR="$SANDBOX/pe3" bash "$PENT" --dry-run 2>&1); rc=$?
assert_eq "pentagi --dry-run exit 0 without docker" "0" "$rc"
assert_contains "pentagi --dry-run: plans clone/compose" "docker compose" "$out"
[ ! -e "$SANDBOX/pe3" ] && pass "pentagi --dry-run: creates no files" || fail "pentagi --dry-run: created $SANDBOX/pe3"

# ───────────────────────── TIER 4: SANITY ─────────────────────────
tier "TIER 4: SANITY TESTS"
for s in "$FREE" "$PENT"; do
  n=$(basename "$s")
  bash -n "$s" 2>/dev/null && pass "$n: bash -n syntax ok" || fail "$n: syntax error"
  head -1 "$s" | grep -q '^#!/usr/bin/env bash' && pass "$n: has bash shebang" || fail "$n: missing shebang"
  grep -q 'set -euo pipefail' "$s" && pass "$n: strict mode" || fail "$n: no 'set -euo pipefail'"
  if command -v shellcheck >/dev/null 2>&1; then
    shellcheck -S error "$s" >/dev/null 2>&1 && pass "$n: shellcheck (errors) clean" || fail "$n: shellcheck reported errors"
  else
    skip "$n: shellcheck not installed"
  fi
done

# ───────────────────────── TIER 5: PERFORMANCE ─────────────────────────
tier "TIER 5: PERFORMANCE TESTS"
t0=$(date +%s.%N); FREELLMAPI_DIR="$SANDBOX/perf1" bash "$FREE" --dry-run >/dev/null 2>&1; t1=$(date +%s.%N)
d=$(awk "BEGIN{print $t1-$t0}")
awk "BEGIN{exit !($d<5)}" && pass "PERF freellmapi --dry-run ${d}s (<5s)" || fail "PERF freellmapi --dry-run ${d}s (>=5s)"
t0=$(date +%s.%N); PENTAGI_DIR="$SANDBOX/perf2" bash "$PENT" --dry-run >/dev/null 2>&1; t1=$(date +%s.%N)
d=$(awk "BEGIN{print $t1-$t0}")
awk "BEGIN{exit !($d<5)}" && pass "PERF pentagi --dry-run ${d}s (<5s)" || fail "PERF pentagi --dry-run ${d}s (>=5s)"

# ───────────────────────── TIER 6: MONKEY ─────────────────────────
tier "TIER 6: MONKEY TESTS"

# unknown flag -> exit 2 on both
out=$(bash "$FREE" --bogus 2>&1); rc=$?; assert_eq "freellmapi unknown flag exit 2" "2" "$rc"
out=$(bash "$PENT" --bogus 2>&1); rc=$?; assert_eq "pentagi unknown flag exit 2" "2" "$rc"

# garbage FREELLMAPI_MODE -> die exit 1
out=$(FREELLMAPI_MODE=banana FREELLMAPI_DIR="$SANDBOX/g" bash "$FREE" --dry-run 2>&1); rc=$?
assert_eq "freellmapi FREELLMAPI_MODE=garbage exit 1" "1" "$rc"
assert_contains "freellmapi garbage mode: clear error" "must be docker or node" "$out"

# adversarial PORT value should not crash dry-run (it is only echoed, never eval'd)
out=$(PORT='9999; rm -rf /tmp/should-not-happen' FREELLMAPI_DIR="$SANDBOX/g2" bash "$FREE" --dry-run 2>&1); rc=$?
assert_eq "freellmapi injection-in-PORT dry-run still exits 0" "0" "$rc"
[ ! -e /tmp/should-not-happen ] && pass "freellmapi: PORT injection did not execute" || fail "freellmapi: PORT injection executed!"

# set_env value with shell metacharacters + path traversal stored literally, not executed
touch "$SANDBOX/canary"
out=$(run_envfn $'X=1\n' "set_env EVIL '\$(rm -f $SANDBOX/canary)'")
[ -e "$SANDBOX/canary" ] && pass "set_env: command-substitution value not executed" || fail "set_env: command substitution executed!"
assert_contains "set_env: metachar value stored literally" 'EVIL=$(rm -f' "$out"

# empty-string flag and doubled flags
out=$(bash "$FREE" --dry-run --dry-run 2>&1); rc=$?; assert_eq "freellmapi doubled --dry-run exit 0" "0" "$rc"

# ───────────────────────── SUMMARY ─────────────────────────
printf '\n=======================================\n'
printf '          FULL TEST SUMMARY\n'
printf '=======================================\n'
for t in "TIER 1: UNIT TESTS" "TIER 2: INTEGRATION TESTS" "TIER 3: END-TO-END TESTS" "TIER 4: SANITY TESTS" "TIER 5: PERFORMANCE TESTS" "TIER 6: MONKEY TESTS"; do
  printf '  %-26s %s passed, %s failed\n' "$t" "${TPASS[$t]:-0}" "${TFAIL[$t]:-0}"
done
printf '  ─────────────────────────────────\n'
printf '  TOTAL: %s passed, %s failed, %s skipped\n' "$PASS" "$FAIL" "$SKIP"
if [ "$FAIL" -eq 0 ]; then printf '  VERDICT: ALL PASS\n'; exit 0; else printf '  VERDICT: %s FAILURES\n' "$FAIL"; exit 1; fi
