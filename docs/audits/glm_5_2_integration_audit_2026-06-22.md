# GLM 5.2 / Personal-Mode Infra Audit — 2026-06-22

**Scope:** the workspace's GLM 5.2 / Chinese-model integration shipped 2026-06-22 evening: registry, dispatcher, launchers, directives, rule additions, SAST guardrails.

**Method:** read-only inspection. Each axis below names the file(s)/lines audited and renders a verdict.

**Headline:** **PASS overall** — sensitivity guard is correctly two-layered, personal-mode remap order is correct, all launchers are ASCII-clean, the auto-latest GLM resolver works as designed, the SAST guardrails the prior session marked "owed" are in fact already shipped, and no callsite distinguishes data-residency by route. One **documentation discrepancy** (the brief expected `call_model` in `llm_client.py`; it lives in `model_router.py`) is a stale-memory issue, not a code defect. Two **LOW-severity observations** worth tracking.

---

## Axis a — Sensitivity guard correctness — **PASS**

[execution/modules/model_router.py:122-127](execution/modules/model_router.py#L122-L127) and [execution/modules/model_router.py:137-141](execution/modules/model_router.py#L137-L141) implement a **two-layer** guard:

1. **First layer (personal × sensitive):** if `mode='personal'` AND `sensitivity='sensitive'`, raise `RuntimeError` BEFORE any remap. This is the load-bearing guard for the design — it ensures sensitive data can never get silently downgraded to GLM.
2. **Second layer (alias × sensitive):** after the optional personal-mode remap (L128-131), the alias-level guard fires if `sensitivity='sensitive'` AND the resolved alias's `sensitivity == 'public'`. This catches the client-mode-direct-to-GLM path too (e.g. someone explicitly passes `call_model('glm', sensitivity='sensitive')`).

Both guards present = defense in depth. Even if the personal-mode guard were removed in a refactor, the alias-level guard would still trip after remap because `_PERSONAL_REMAP['sonnet'] = 'glm'` and `ALIASES['glm'].sensitivity == 'public'`.

Trace of `call_model('sonnet', mode='personal', sensitivity='sensitive')`:
- L116 `key='sonnet'` (valid alias).
- L122-127 trips → `RuntimeError("personal-mode rejected: sensitive payload …")`. Never reaches the remap. ✅

Trace of `call_model('glm', mode='client', sensitivity='sensitive')`:
- L122 skipped (mode≠personal).
- L128 skipped (key not in `_PERSONAL_REMAP`).
- L133 `a = ALIASES['glm']` → `sensitivity='public'`.
- L137-141 trips → `RuntimeError("alias 'glm' is public-only …")`. ✅

---

## Axis b — Personal-mode remap correctness — **PASS**

`_PERSONAL_REMAP` ([model_router.py:69-77](execution/modules/model_router.py#L69-L77)) remaps `opus`, `sonnet`, `gpt`, `gpt4o`, `o1` → `glm`. `gemini` / `gemini-pro` pass through unchanged (already free/cheap). `glm` / `glm-5.2` / `glm-4.7` pass through unchanged (already the target).

**Haiku is not in `ALIASES`** at all ([model_router.py:43-58](execution/modules/model_router.py#L43-L58)). Banned workspace-wide per `~/.claude/rules/model-tier.md`. ✅ correct.

**Order of operations** (L122 → L128 → L137):

1. Reject personal-mode-with-sensitive **first** (cheapest fail, clearest error message).
2. Apply personal-mode remap **second** (so the user sees `personal-mode remap: sonnet → glm` in logs).
3. Apply alias-level sensitivity guard **third** (catches any path that reaches a public-only alias).

This is the correct order. If the remap fired before the personal-mode-sensitivity check, the user would see `alias 'glm' is public-only` for a `mode='personal'` call — confusing root-cause attribution. The current order names the mode misuse explicitly. ✅

---

## Axis c — Windows-launcher ASCII-only compliance — **PASS**

All 16 launchers under `execution/infrastructure/launchers/` (10 `.ps1` + 6 `.sh`) verified ASCII-clean via byte-level scan. No file contains any byte > 0x7F, and no file is BOM-flagged (none need to be — they're pure ASCII).

Per `~/.claude/rules/powershell-ascii-only.md` this is the right state for PowerShell 5.1 compatibility. ✅

---

## Axis d — Auto-latest GLM versioning — **PASS with one LOW-severity nit**

`_resolve_openrouter('glm')` at [model_registry.py:446-455](execution/modules/model_registry.py#L446-L455) uses `_best_glm_family` ([model_registry.py:380-396](execution/modules/model_registry.py#L380-L396)), which:

- Matches `z-ai/glm-X.Y` exactly via `_OR_GLM_RE = r"^z-ai/glm-(\d+(?:\.\d+)?)$"` ([line 266](execution/modules/model_registry.py#L266)).
- Picks the highest `(major, minor)` tuple. Today: `(5, 2)`. When OR lists `z-ai/glm-5.3` or `z-ai/glm-6.0`, this auto-picks it with no code change. ✅
- The trailing `$` in the regex correctly excludes variants like `z-ai/glm-5.2-air`, `z-ai/glm-4.7-flash`, `z-ai/glm-5.0-turbo`, `z-ai/glm-4.5v` — keeping the main `glm` tier on the flagship line. ✅

**Failure path** (catalog fetch fails AND cache is stale):
1. `_resolve_openrouter` raises `RuntimeError` ([line 311](execution/modules/model_registry.py#L311)) on HTTP error.
2. `resolve_model` ([line 563-569](execution/modules/model_registry.py#L563-L569)) catches and falls through to the stale-cache path ([L572-582](execution/modules/model_registry.py#L572-L582)).
3. If `.tmp/model_registry.json` exists but is older than 7 days, stale cache is still used (logged as `WARNING`).
4. If no cache at all, falls to `LAST_KNOWN_GOOD["openrouter"]["glm"] = "z-ai/glm-5.2"` ([line 62](execution/modules/model_registry.py#L62)).

**LOW-severity nit:** `LAST_KNOWN_GOOD` has to be manually edited when GLM-6 releases. The current cadence comment ("Updated manually ~quarterly when logs show stale models being picked") is the right policy — but as new GLM versions ship faster than quarterly, the literal could drift. **Suggested follow-up:** in the next ~3-month review, check whether `z-ai/glm-5.2` is still the safest LKG fallback, or whether `z-ai/glm-5` (family root) should be used instead.

Not a bug today.

---

## Axis e — NIM vs OR data residency claim — **PASS**

Audit reads `_call_openrouter` ([model_router.py:249-278](execution/modules/model_router.py#L249-L278)) as the single point where any `z-ai/*` call flows out. The only thing that distinguishes routes is the `provider_label` string for telemetry (L272-277), set from `base_url`:

```python
if base_url and "z.ai" in base_url:
    provider_label = "z-ai-direct"
elif base_url and "nvidia" in base_url:
    provider_label = "nvidia-nim"
```

No callsite in the workspace uses these `base_url` overrides today (NIM not wired in; Z.AI direct deferred per the directive). So the claim "GLM is treated identically whether via NIM or OR" holds — both routes funnel through the same dispatcher, the same alias-level sensitivity guard, the same `_PERSONAL_REMAP`. The operative concern (legal/IP exposure to Z.AI) is correctly framed as route-independent. ✅

---

## Axis f — SAST owed-work — **PASS (already shipped)**

The brief's worry that `personal-mode-with-pii` SAST is "documented but not yet implemented" is **out of date**. [workspace_sast.py:626](execution/infrastructure/workspace_sast.py#L626) implements `_rule_personal_mode_with_pii` and [workspace_sast.py:720](execution/infrastructure/workspace_sast.py#L720) implements `_rule_ps1_non_ascii`. Both rules are registered in the rule dispatch table at [L790-791](execution/infrastructure/workspace_sast.py#L790-L791).

`HARDENING_BACKLOG.md` (Update 2026-06-22 late evening) confirms:
- `personal-mode-with-pii`: AST-based, function-scope joint detection of `mode='personal'` × PII keyword. 0 findings on the workspace.
- `ps1-non-ascii`: byte-scan with BOM-flagged-file skip. 1 historical finding (now fixed) at `install_shortcut.ps1`.

✅ shipped, validated against synthetic offender, re-scan clean.

---

## Documentation discrepancy (NOT a code bug)

The session brief (Task 1 wording) says:

> `call_model()` dispatcher in `execution/modules/llm_client.py`

The actual location is `execution/modules/model_router.py`. `llm_client.py` is the thin OpenRouter wrapper (`chat_completion`) that `_call_openrouter` calls under the hood ([model_router.py:263-265](execution/modules/model_router.py#L263-L265)).

This is a **stale-brief** issue — `MEMORY.md` and `project_glm_5_2.md` should be updated so future sessions don't waste time hunting in the wrong file. Recommend: edit `memory/project_glm_5_2.md` to read "dispatcher in `execution/modules/model_router.py` (NOT `llm_client.py`)."

---

## Additional observations

**Observation 1 — `call_model` API gap for structured-output callers (LOW)**

`call_model` ([model_router.py:80-158](execution/modules/model_router.py#L80-L158)) accepts `system`, `user`, `max_tokens`, `temperature`, `via_openrouter`, `mode`, `sensitivity`. It does NOT accept `response_mime_type` / `response_schema` (Gemini-only structured-output) nor pass `temperature` through to the OR route ([L259](execution/modules/model_router.py#L259) `_ = temperature` discards it).

Callers that need JSON-mode output (e.g. `prodcraft_living_prd_plan_gen.py`, `prodcraft_script_gen.py`) currently bypass `call_model` entirely and instantiate `google.genai.Client` directly. When refactored to use `call_model` for the GLM path, they'll need to rely on strict-prompt JSON instructions + robust extraction (strip ```json fences) instead of structured-output enforcement.

This is the right tradeoff (GLM 5.2 / OR don't have native structured-output enforcement anyway), but worth noting that the refactor pattern can't be "1:1 swap."

**Observation 2 — `chat_completion` swallows OR temperature (LOW)**

`chat_completion` in [llm_client.py:36-77](execution/modules/llm_client.py#L36-L77) doesn't accept `temperature` as a parameter. `_call_openrouter` notices this (L259 comment) but the workaround is just to drop it. If/when a personal-mode caller needs deterministic JSON (`temperature=0.0`), this is a one-line gap. Track in HARDENING_BACKLOG, not a blocker.

---

## Verdict

| Axis | Verdict |
|---|---|
| a. Sensitivity guard correctness | PASS |
| b. Personal-mode remap correctness | PASS |
| c. Launcher ASCII compliance | PASS |
| d. Auto-latest GLM versioning | PASS (1 LOW nit) |
| e. NIM vs OR data residency | PASS |
| f. SAST owed-work | PASS (already shipped) |
| Documentation accuracy | DRIFT — `MEMORY.md` says `llm_client.py`, code lives in `model_router.py` |

**Overall: PASS.** Safe to proceed with Task 2 (ProdCraft refactor) and Task 3 (e2e dogfood) against this infra.

No HIGH-severity findings. No blockers.
