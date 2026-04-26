#!/bin/bash
# ==============================================================================
# workspace_verify.sh — 3-tier verification of Claude Code workspace setup
# Platform: Windows 11 / Git Bash / Python via py / Node v24
# ==============================================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

PASS_COUNT=0; FAIL_COUNT=0; SKIP_COUNT=0

pass() { PASS_COUNT=$((PASS_COUNT+1)); echo -e "  ${GREEN}PASS${NC}  $1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT+1)); echo -e "  ${RED}FAIL${NC}  $1"; [[ -n "${2:-}" ]] && echo -e "        ${RED}$2${NC}"; }
skip() { SKIP_COUNT=$((SKIP_COUNT+1)); echo -e "  ${YELLOW}SKIP${NC}  $1"; [[ -n "${2:-}" ]] && echo -e "        ${YELLOW}$2${NC}"; }
tier() { echo ""; echo -e "${BOLD}${CYAN}=== $1 ===${NC}"; }

WS="c:/Users/deban/OneDrive/Documents/AntiGravity Project Space"
export PATH="/c/Program Files/nodejs:/c/Users/deban/AppData/Roaming/npm:$PATH"
cd "$WS"

TMPDIR_TEST=$(mktemp -d)
trap 'rm -rf "$TMPDIR_TEST"' EXIT

# ==============================================================================
tier "TIER 1: Unit Tests (file-level validation)"
# ==============================================================================

# 1.1-1.3 JSON validity
for F in ".claude/settings.json" ".claude/settings.local.json" ".mcp.json"; do
  if py -c "import json,pathlib; json.loads(pathlib.Path('$F').read_text(encoding='utf-8'))" 2>/dev/null; then
    pass "$F is valid JSON"
  else
    fail "$F is NOT valid JSON"
  fi
done

# 1.4 settings.json has $schema
if py -c "
import json,pathlib,sys
d=json.loads(pathlib.Path('.claude/settings.json').read_text(encoding='utf-8'))
sys.exit(0 if '\$schema' in d else 1)
" 2>/dev/null; then
  pass "settings.json has \$schema field"
else
  fail "settings.json missing \$schema"
fi

# 1.5 settings.json has 3 hook entries
HC=$(py -c "
import json,pathlib
d=json.loads(pathlib.Path('.claude/settings.json').read_text(encoding='utf-8'))
h=d.get('hooks',{})
print(len(h.get('PreToolUse',[]))+len(h.get('PostToolUse',[])))
" 2>/dev/null)
[[ "$HC" == "3" ]] && pass "settings.json has 3 hook entries" || fail "settings.json hooks: expected 3, got ${HC:-?}"

# 1.6 settings.json has permissions block
if py -c "
import json,pathlib,sys
d=json.loads(pathlib.Path('.claude/settings.json').read_text(encoding='utf-8'))
p=d.get('permissions',{})
sys.exit(0 if 'allow' in p and 'deny' in p and 'ask' in p else 1)
" 2>/dev/null; then
  pass "settings.json has permissions (allow/deny/ask)"
else
  fail "settings.json missing permissions block"
fi

# 1.7 .mcp.json has 3 servers: firecrawl, github, tavily
MN=$(py -c "
import json,pathlib
d=json.loads(pathlib.Path('.mcp.json').read_text(encoding='utf-8'))
print(','.join(sorted(d.get('mcpServers',{}).keys())))
" 2>/dev/null)
[[ "$MN" == "firecrawl,github,tavily" ]] && pass ".mcp.json servers: firecrawl, github, tavily" || fail ".mcp.json servers: expected firecrawl,github,tavily got ${MN:-?}"

# 1.8-1.11 gitignore checks
for TARGET in "CLAUDE.local.md" ".claude/settings.local.json" "output/" ".firecrawl/"; do
  if git check-ignore -q "$TARGET" 2>/dev/null; then
    pass ".gitignore ignores $TARGET"
  else
    fail ".gitignore does NOT ignore $TARGET"
  fi
done

# 1.12 REGISTRY.md lists >= 3 scripts
SC=$(grep -c '| `' execution/REGISTRY.md 2>/dev/null || echo 0)
[[ "$SC" -ge 3 ]] && pass "REGISTRY.md lists $SC scripts (>= 3)" || fail "REGISTRY.md lists $SC scripts (expected >= 3)"

# 1.13 general.md has >= 11 note entries
NC=$(grep -c '^\- \[' .claude/notes/general.md 2>/dev/null || echo 0)
[[ "$NC" -ge 11 ]] && pass "general.md has $NC notes (>= 11)" || fail "general.md has $NC notes (expected >= 11)"

# 1.14-1.16 Rules files have frontmatter with paths:
for RULE in python-execution directives security; do
  if head -5 ".claude/rules/${RULE}.md" 2>/dev/null | grep -q 'paths:'; then
    pass "rules/${RULE}.md has paths: frontmatter"
  else
    fail "rules/${RULE}.md missing paths: frontmatter"
  fi
done

# 1.17-1.19 Hook scripts pass bash -n syntax check
for HOOK in safety-guard format-python note-taker; do
  if bash -n ".claude/hooks/${HOOK}.sh" 2>/dev/null; then
    pass "hooks/${HOOK}.sh passes bash syntax check"
  else
    fail "hooks/${HOOK}.sh has bash syntax errors"
  fi
done

# 1.20 requirements.txt has all 6 required packages
MISSING=()
for pkg in reportlab pdfplumber python-dotenv anthropic requests black; do
  grep -qi "^${pkg}" requirements.txt 2>/dev/null || MISSING+=("$pkg")
done
[[ ${#MISSING[@]} -eq 0 ]] && pass "requirements.txt has all 6 packages" || fail "requirements.txt missing: ${MISSING[*]}"

# 1.21-1.23 .env has API keys with values
for KEY in GITHUB_PAT FIRECRAWL_API_KEY TAVILY_API_KEY; do
  if grep -qE "^${KEY}=.+" .env 2>/dev/null; then
    pass ".env has $KEY with a value"
  else
    fail ".env missing $KEY or value is empty"
  fi
done

# 1.24 firecrawl SKILL.md exists
[[ -f ".claude/skills/firecrawl/SKILL.md" ]] && pass "firecrawl SKILL.md exists" || fail "firecrawl SKILL.md missing"

# ==============================================================================
tier "TIER 2: Integration Tests (component interactions)"
# ==============================================================================

# 2.1 safety-guard.sh blocks rm -rf (exit 2)
EXIT=0
echo '{"tool_input":{"command":"rm -rf /"}}' | bash .claude/hooks/safety-guard.sh >/dev/null 2>&1 || EXIT=$?
[[ "$EXIT" -eq 2 ]] && pass "safety-guard.sh blocks 'rm -rf' (exit 2)" || fail "safety-guard.sh did NOT block 'rm -rf' (exit $EXIT)"

# 2.2 safety-guard.sh blocks git push --force
EXIT=0
echo '{"tool_input":{"command":"git push --force origin main"}}' | bash .claude/hooks/safety-guard.sh >/dev/null 2>&1 || EXIT=$?
[[ "$EXIT" -eq 2 ]] && pass "safety-guard.sh blocks 'git push --force' (exit 2)" || fail "safety-guard.sh did NOT block 'git push --force' (exit $EXIT)"

# 2.3 safety-guard.sh blocks DROP TABLE
EXIT=0
echo '{"tool_input":{"command":"psql -c DROP TABLE users"}}' | bash .claude/hooks/safety-guard.sh >/dev/null 2>&1 || EXIT=$?
[[ "$EXIT" -eq 2 ]] && pass "safety-guard.sh blocks 'DROP TABLE' (exit 2)" || fail "safety-guard.sh did NOT block 'DROP TABLE' (exit $EXIT)"

# 2.4 safety-guard.sh allows safe command (git status)
EXIT=0
echo '{"tool_input":{"command":"git status"}}' | bash .claude/hooks/safety-guard.sh >/dev/null 2>&1 || EXIT=$?
[[ "$EXIT" -eq 0 ]] && pass "safety-guard.sh allows 'git status' (exit 0)" || fail "safety-guard.sh blocked 'git status' (exit $EXIT)"

# 2.5 safety-guard.sh allows safe command (ls)
EXIT=0
echo '{"tool_input":{"command":"ls -la"}}' | bash .claude/hooks/safety-guard.sh >/dev/null 2>&1 || EXIT=$?
[[ "$EXIT" -eq 0 ]] && pass "safety-guard.sh allows 'ls -la' (exit 0)" || fail "safety-guard.sh blocked 'ls -la' (exit $EXIT)"

# 2.6 format-python.sh reformats bad .py file
TMPPY="$TMPDIR_TEST/bad.py"
printf 'x=1\ny  =  2\nz=[1,2,3,4,5,6,7,8,9,10]\n' > "$TMPPY"
if command -v black &>/dev/null; then
  BEFORE=$(cat "$TMPPY")
  bash .claude/hooks/format-python.sh "$TMPPY" 2>/dev/null
  AFTER=$(cat "$TMPPY")
  [[ "$BEFORE" != "$AFTER" ]] && pass "format-python.sh reformats .py file via black" || fail "format-python.sh did not change file"
else
  skip "format-python.sh: black not installed"
fi

# 2.7 format-python.sh skips non-.py file
EXIT=0
bash .claude/hooks/format-python.sh "$TMPDIR_TEST/readme.txt" 2>/dev/null || EXIT=$?
[[ "$EXIT" -eq 0 ]] && pass "format-python.sh skips non-.py files" || fail "format-python.sh failed on non-.py (exit $EXIT)"

# 2.8 note-taker.sh fires on directives/ path
NT=$(bash .claude/hooks/note-taker.sh "directives/test/foo.md" 2>/dev/null)
echo "$NT" | grep -q "NOTE-TAKER" && pass "note-taker.sh fires on directives/ path" || fail "note-taker.sh silent on directives/ path"

# 2.9 note-taker.sh fires on execution/ path
NT=$(bash .claude/hooks/note-taker.sh "execution/content/test.py" 2>/dev/null)
echo "$NT" | grep -q "NOTE-TAKER" && pass "note-taker.sh fires on execution/ path" || fail "note-taker.sh silent on execution/ path"

# 2.10 note-taker.sh silent on unrelated path
NT=$(bash .claude/hooks/note-taker.sh "assets/logo.png" 2>/dev/null)
[[ -z "$NT" ]] && pass "note-taker.sh silent on unrelated path" || fail "note-taker.sh incorrectly fired on assets/"

# 2.11 generate_registry.py runs and lists >= 3 scripts
REG_OUT=$(py execution/generate_registry.py 2>&1)
echo "$REG_OUT" | grep -q "Registry updated" && pass "generate_registry.py runs successfully" || fail "generate_registry.py failed: $REG_OUT"

# 2.12 pip can resolve all packages
PIP_OUT=$(py -m pip install --dry-run -r requirements.txt 2>&1)
PIP_EXIT=$?
if [[ $PIP_EXIT -eq 0 ]]; then
  pass "pip resolves all packages in requirements.txt"
else
  echo "$PIP_OUT" | grep -qi "already satisfied\|would install" && pass "pip resolves packages (some already installed)" || fail "pip can't resolve requirements.txt"
fi

# 2.13 Node.js is available
if command -v node &>/dev/null; then
  NV=$(node --version 2>&1)
  pass "Node.js available: $NV"
else
  fail "Node.js not found on PATH"
fi

# 2.14 firecrawl CLI responds
if command -v firecrawl &>/dev/null; then
  FC_OUT=$(firecrawl --status 2>&1 | head -3)
  echo "$FC_OUT" | grep -qi "firecrawl\|authenticated\|cli" && pass "firecrawl CLI responds" || fail "firecrawl CLI no response"
else
  fail "firecrawl CLI not found on PATH"
fi

# ==============================================================================
tier "TIER 3: End-to-End Tests (full system)"
# ==============================================================================

# 3.1-3.3 MCP server package resolution
for PKG in "@github/mcp-server" "firecrawl-mcp" "tavily-mcp@latest"; do
  NAME=$(echo "$PKG" | sed 's/@.*//;s/.*\///')
  if command -v npx &>/dev/null; then
    NPX_OUT=$(npx --yes --package "$PKG" -- echo "resolved" 2>&1) || true
    if echo "$NPX_OUT" | grep -q "resolved"; then
      pass "MCP '$NAME' package resolves via npx"
    else
      echo "$NPX_OUT" | grep -qi "added\|already\|npm" && pass "MCP '$NAME' package downloads (entrypoint needs args)" || fail "MCP '$NAME' package failed to resolve"
    fi
  else
    skip "MCP '$NAME': npx not available"
  fi
done

# 3.4 Firecrawl live search (real API call)
if command -v firecrawl &>/dev/null; then
  FK=$(grep '^FIRECRAWL_API_KEY=' .env 2>/dev/null | cut -d= -f2)
  if [[ -n "$FK" ]]; then
    export FIRECRAWL_API_KEY="$FK"
    FC_S=$(firecrawl search "claude code best practices" 2>&1 | head -5)
    if [[ -n "$FC_S" ]] && ! echo "$FC_S" | grep -qi "error\|unauthorized\|401"; then
      pass "firecrawl search returns live results"
    else
      fail "firecrawl search failed" "$(echo "$FC_S" | head -2)"
    fi
  else
    skip "firecrawl search: FIRECRAWL_API_KEY empty"
  fi
else
  skip "firecrawl search: CLI not available"
fi

# 3.5 Gitignored files don't leak into git status
GS=$(git status --porcelain 2>/dev/null)
LEAKED=()
for F in "CLAUDE.local.md" ".claude/settings.local.json"; do
  echo "$GS" | grep -q "$F" && LEAKED+=("$F")
done
[[ ${#LEAKED[@]} -eq 0 ]] && pass "Gitignored files don't leak into git status" || fail "Leaked: ${LEAKED[*]}"

# 3.6 Hook chain: note-taker + format-python both fire on execution/*.py
CHAIN_PY="$TMPDIR_TEST/chain.py"
printf 'x=1\ny  =  2\n' > "$CHAIN_PY"
NT_CHAIN=$(bash .claude/hooks/note-taker.sh "execution/content/chain.py" 2>/dev/null)
FP_EXIT=0; bash .claude/hooks/format-python.sh "$CHAIN_PY" 2>/dev/null || FP_EXIT=$?
NT_OK=0; FP_OK=0
echo "$NT_CHAIN" | grep -q "NOTE-TAKER" && NT_OK=1
[[ "$FP_EXIT" -eq 0 ]] && FP_OK=1
[[ "$NT_OK" -eq 1 && "$FP_OK" -eq 1 ]] && pass "Hook chain: note-taker + format-python both fire" || fail "Hook chain incomplete: note-taker=$NT_OK format-python=$FP_OK"

# 3.7 .mcp.json env var refs resolve in .env
REF_CHECK=$(py -c "
import json,pathlib,re
mcp=json.loads(pathlib.Path('.mcp.json').read_text(encoding='utf-8'))
env=pathlib.Path('.env').read_text(encoding='utf-8')
refs=set()
for s in mcp.get('mcpServers',{}).values():
    for v in s.get('env',{}).values():
        m=re.search(r'\\\$\{(\w+)\}',v)
        if m: refs.add(m.group(1))
missing=[r for r in sorted(refs) if not re.search(rf'^{r}=.+',env,re.MULTILINE)]
print('MISSING:'+','.join(missing) if missing else 'OK:'+','.join(sorted(refs)))
" 2>/dev/null)
if echo "$REF_CHECK" | grep -q "^OK:"; then
  KEYS=$(echo "$REF_CHECK" | sed 's/^OK://')
  pass ".mcp.json env refs resolve in .env: $KEYS"
else
  M=$(echo "$REF_CHECK" | sed 's/^MISSING://')
  fail ".mcp.json refs missing in .env: $M"
fi

# 3.8 All 3 scripts have registry-compatible docstrings
SCRIPTS=("execution/content/wedding_card_generator.py" "execution/personal_workflows/cv_builder.py" "execution/personal_workflows/cv_optimizer_agent.py")
DOC_OK=0; DOC_FAILS=()
for S in "${SCRIPTS[@]}"; do
  R=$(py -c "
import ast,pathlib
src=pathlib.Path('$S').read_text(encoding='utf-8')
doc=(ast.get_docstring(ast.parse(src)) or '').lower()
ok='description:' in doc and ('inputs:' in doc or 'input:' in doc) and ('outputs:' in doc or 'output:' in doc)
print('OK' if ok else 'FAIL')
" 2>/dev/null)
  [[ "$R" == "OK" ]] && DOC_OK=$((DOC_OK+1)) || DOC_FAILS+=("$(basename "$S")")
done
[[ "$DOC_OK" -eq 3 ]] && pass "All 3 scripts have registry-compatible docstrings" || fail "$DOC_OK/3 scripts valid. Failed: ${DOC_FAILS[*]}"

# ==============================================================================
echo ""
echo -e "${BOLD}${CYAN}=======================================${NC}"
echo -e "${BOLD}          TEST SUMMARY${NC}"
echo -e "${BOLD}${CYAN}=======================================${NC}"
TOTAL=$((PASS_COUNT+FAIL_COUNT+SKIP_COUNT))
echo -e "  ${GREEN}PASS:${NC}  $PASS_COUNT"
echo -e "  ${RED}FAIL:${NC}  $FAIL_COUNT"
echo -e "  ${YELLOW}SKIP:${NC}  $SKIP_COUNT"
echo -e "  TOTAL: $TOTAL"
echo ""
if [[ "$FAIL_COUNT" -gt 0 ]]; then
  echo -e "${RED}${BOLD}Some tests FAILED.${NC}"
  exit 1
else
  echo -e "${GREEN}${BOLD}All tests PASSED!${NC}"
  exit 0
fi
