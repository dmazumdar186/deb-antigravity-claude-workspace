---
name: test-suite
description: |
  Run comprehensive multi-tier testing on any project, system, script, or
  feature the user has built or is building. Triggers when the user says
  "run tests", "test this", "QA this", or asks for validation of new work.
allowed-tools: Read, Grep, Glob, Bash, Edit, Write, Agent
user_invocable: true
---

# Test Suite — Full QA Pipeline

Run a 6-layer test pyramid on any new project, system, script, or feature.
Think like a developer for unit tests, a QA engineer for integration and E2E,
and a chaos engineer for monkey and performance tests.

## When to Trigger

**Positive triggers:**
- User says "run tests", "test this", "QA this", "validate this"
- User says "I just built X — make sure it works"
- User finishes building a new project or feature and wants verification
- User invokes `/test-suite`

**Negative triggers — do NOT auto-trigger:**
- Minor edits (typo fixes, comment changes, config tweaks)
- User is still mid-implementation and hasn't asked for testing yet
- Exploratory/research conversations with no deliverable

## Process

### Step 0: Reconnaissance

Before writing a single test, understand what you're testing:

1. **Read all source files** involved in the project/feature
2. **Identify the tech stack** (Python, JS, Bash, API endpoints, etc.)
3. **Map the dependency graph** — what calls what, what depends on what
4. **Identify external dependencies** — APIs, databases, file system, network
5. **Find existing tests** — check for `tests/`, `test_*.py`, `*.test.js`, etc.
6. **Read any directive** (`directives/`) or documentation for the feature

Produce a mental model of the system before proceeding.

### Step 1: Unit Tests

**Role: Developer**

Test individual functions, classes, and modules in isolation.

**What to test:**
- Every public function/method with at least one happy-path and one edge-case
- Input validation: null, empty, wrong type, boundary values
- Return values and side effects
- Error handling: does it raise/return the right error for bad input?
- Pure logic: calculations, transformations, string formatting
- Configuration parsing and defaults

**How to test:**
- For Python: use `pytest` or plain `assert` statements in a test script
- For Bash: use conditional checks with `exit 1` on failure
- For JS/TS: use the project's existing test framework, or plain assertions
- Mock external dependencies (APIs, databases, file I/O) at this tier only
- Each assertion must print PASS/FAIL with a descriptive label

**Output format per assertion:**
```
PASS  function_name: handles empty input gracefully
FAIL  function_name: expected 42, got None
```

### Step 2: Integration Tests

**Role: QA Engineer**

Test how components work together. No mocks — use real connections where safe.

**What to test:**
- Module A calls Module B — does data flow correctly end-to-end?
- Database read/write round-trips (if applicable)
- File I/O chains: write then read back, verify content
- API client → real endpoint (use test/sandbox endpoints when available)
- Hook chains: does hook A fire, then hook B processes the result?
- Configuration loading: does .env → dotenv → script config resolve correctly?
- Import chains: do all modules import without circular dependency errors?

**How to test:**
- Use real dependencies where safe (local files, local DB, free API tiers)
- Use sandbox/test endpoints for paid APIs
- Test with realistic data, not toy examples
- Verify both the happy path and the most common failure mode

### Step 3: End-to-End Tests

**Role: QA Engineer**

Test the complete user journey from input to final output.

**What to test:**
- The full workflow the user would execute, start to finish
- Input → processing → output: is the final deliverable correct?
- CLI tools: does `python script.py --arg value` produce expected output?
- Web endpoints: does the request → response cycle work?
- File-based workflows: input file → script → output file, verify output
- Multi-step pipelines: step 1 output feeds step 2, feeds step 3 — all correct?

**How to test:**
- Run the actual commands the user would run
- Verify output files exist, have correct format, contain expected data
- Check exit codes
- For UI: describe what to manually verify (or use headless browser if available)

### Step 4: Sanity Tests

**Role: QA Engineer**

Quick smoke tests to verify the system hasn't regressed on core functionality.

**What to test:**
- Can the main entry point run without crashing? (exit code 0)
- Do all imports resolve? (`python -c "import module"`)
- Are all required files present? (config, templates, assets)
- Are all required environment variables set?
- Do all external services respond? (ping/health-check endpoints)
- Does the help/usage flag work? (`--help`, `-h`)
- Is the output format still correct? (JSON parses, CSV has headers, PDF opens)

### Step 5: Performance Tests

**Role: Performance Engineer**

Verify the system performs within acceptable bounds.

**What to test:**
- **Execution time**: Run the main operation, measure wall-clock time. Flag if >2x expected.
- **Memory**: For data-heavy scripts, check peak memory usage (`/usr/bin/time -v` on Linux, `Measure-Command` on Windows, or Python's `tracemalloc`)
- **File size**: Are output files within expected size range? (catch runaway generation)
- **API call count**: Count external API calls. Flag if significantly more than expected.
- **Concurrency**: If the system handles multiple inputs, test with 2-3 concurrent runs
- **Scalability sniff test**: Run with 1x, 5x, 10x input size — does time scale linearly or explode?

**How to report:**
```
PERF  script.py execution time: 2.3s (threshold: <5s) — PASS
PERF  output file size: 142KB (threshold: <1MB) — PASS
PERF  API calls made: 3 (expected: 3) — PASS
```

### Step 6: Monkey Tests (Chaos/Negative Testing)

**Role: Chaos Engineer**

Throw unexpected, malformed, and adversarial inputs at the system.

**What to test:**
- **Garbage input**: random strings, binary data, extremely long strings (10KB+)
- **Empty input**: empty files, empty strings, null values, missing arguments
- **Wrong types**: string where int expected, list where dict expected
- **Boundary values**: 0, -1, MAX_INT, empty list, single-element list
- **Missing dependencies**: what happens if a required file is missing? (rename it temporarily, run, restore)
- **Malformed config**: invalid JSON in config files, missing required keys
- **Injection attempts**: SQL injection strings, shell metacharacters, path traversal (`../../../etc/passwd`)
- **Encoding**: Unicode, emoji, null bytes, mixed encodings
- **Interrupted operations**: what happens if the script is killed mid-execution? (check for leftover temp files)

**How to test:**
- The system should NEVER crash with an unhandled exception on bad input
- It should return a clear error message or gracefully degrade
- It should not corrupt existing data
- It should not leave orphaned temp files or locks

**IMPORTANT: Be non-destructive.** Monkey tests must restore original state:
- Copy files before modifying, restore after
- Use temp directories for generated test artifacts
- Never modify production data or configs permanently

## Output Format

```
=== RECONNAISSANCE ===
System: [name]
Stack: [languages/frameworks]
Components: [list]
External deps: [list]
Existing tests: [found/none]

=== TIER 1: UNIT TESTS ===
PASS  [component]: [description]
FAIL  [component]: [description] — expected [X], got [Y]
...
Unit: [N] passed, [M] failed

=== TIER 2: INTEGRATION TESTS ===
PASS  [interaction]: [description]
FAIL  [interaction]: [description]
...
Integration: [N] passed, [M] failed

=== TIER 3: END-TO-END TESTS ===
PASS  [workflow]: [description]
FAIL  [workflow]: [description]
...
E2E: [N] passed, [M] failed

=== TIER 4: SANITY TESTS ===
PASS  [check]: [description]
...
Sanity: [N] passed, [M] failed

=== TIER 5: PERFORMANCE TESTS ===
PERF  [metric]: [value] (threshold: [limit]) — PASS/FAIL
...
Performance: [N] passed, [M] failed

=== TIER 6: MONKEY TESTS ===
CHAOS [input type]: [what happened] — PASS/FAIL
...
Monkey: [N] passed, [M] failed

=======================================
          FULL TEST SUMMARY
=======================================
  Unit:         [N] passed, [M] failed
  Integration:  [N] passed, [M] failed
  E2E:          [N] passed, [M] failed
  Sanity:       [N] passed, [M] failed
  Performance:  [N] passed, [M] failed
  Monkey:       [N] passed, [M] failed
  ─────────────────────────────────
  TOTAL:        [N] passed, [M] failed
  VERDICT:      ALL PASS / [M] FAILURES
```

## Rules

- **Always run Reconnaissance first.** Never write tests without understanding the system.
- **Adapt test count to project size.** A 50-line script gets 10-15 tests. A multi-file system gets 40+.
- **Use sub-agents for parallelism.** Spawn separate agents for independent test tiers when the project is large.
- **Non-destructive.** Every test must clean up after itself. Never corrupt the user's data or config.
- **Real dependencies over mocks** at integration tier and above. Only mock at unit tier.
- **Report failures with actionable detail.** "FAIL" alone is useless. Include expected vs actual, file path, line number.
- **Fix failures if asked.** After reporting, if the user says "fix it", fix the code — not the tests (unless the test is wrong).
- **Save the test script.** Write tests to `tests/` directory so they can be re-run. Name: `tests/test_{project_name}.sh` or `tests/test_{project_name}.py`.
- **Performance thresholds are guidelines.** If no baseline exists, establish one on first run and note it.
- **For paid APIs**: use the minimum calls needed. Never run performance/monkey tests against paid endpoints without asking the user first.
- **Security tests go in monkey tier.** Injection, path traversal, and encoding attacks are chaos tests.
- **Exit code 0** if all pass, **exit code 1** if any fail.
