# Lens 6: Saraev (automation maturity and boundaries)

**Verdict: NOT CLEAR** for a campaign pipeline. The one-off talk film can ship once the operator has watched it.

**Rung today: prompt (n = 1).** The output has not been proven good yet. Nobody has watched the film end to end: BUILD_LOG's only review was the agent reading its own contact sheets ("Review round 1"), and `EVAL_REPORT_v1.md` says **Overall: FAIL**.

## Findings

**HIGH 1: "Start at the end" is not met.**
- Evidence: one film, no human watch logged, and the eval verdict is FAIL.
- Fix: the operator watches v1 full length with sound before the talk, and the verdict goes into a ledger (`film, watcher, pass/defects`). Nothing moves up a rung until then.

**HIGH 2: The gate is not calibrated.**
- Evidence: most FAILs are false positives. Cue IDs (`S02`), `1920×1080`, `M0475` and on-screen labels such as "8 spellings" are flagged as wrong numbers or misquotes.
- The harness also breaks its own rules. `jev_supported` says "no fact line < 0.5", yet the lines at 0.32 and 0.19 only WARN. Its LUFS target is −16, while the directive masters to −14.
- A gate that fails a good film gets bypassed, and that kills the gate.
- Fix:
  - Scan only the narration, subtitle and on-screen-text columns.
  - Allow ID patterns, and accept labels built from fact values.
  - Validate against the human verdicts on 5 films (Jev skill rule 5) before film_eval blocks anything.

**HIGH 3: Too much is fuzzy, and there is no template.**
- Evidence: every film is about 430 new lines of `film.js` plus a fresh script. The teardown itself says "Rebuild yes, re-create no", and the draft directive says "One hero piece, not a series".
- Fix: per client, freeze one human-approved film as the house template. Variants use `--q content=content_<v>.json` with a few named slots (`school_name`, `segment_sentence`, fact ids). A variant never re-authors code.

**MED 4: The bottleneck is facts and review, not render.**
- Evidence: frames, mux and encode take about 5 minutes. Authoring plus the fix round takes about 17 minutes, out of 49 minutes in total.
- Every account needs its own verified FACTS.md. This one came from VERIFICATION.md, and no school has an equivalent.
- Fix: plan capacity around fact curation plus a watch of about 3 minutes per film.

**MED 5: There is no error channel.**
- Evidence: film_eval's exit 1 goes nowhere. Jev fails open (`answers == {}`). The directive's Steps have no failure branch.
- Fix:
  - Gates fail closed.
  - Failed builds go to `.tmp/film_quarantine/`.
  - Failures are posted as `service / env / error / count` to the operator's channel. Wiring counts as done only after a sample message has been seen there.
  - Same error 3 or more times: self-heal the directive's Learnings.

**LOW 6: The customer-facing boundary is unstated.**
- Evidence: `automation-boundaries.md` says final creative production is "NOT OK to automate". The directive auto-uploads to Drive but says nothing about publishing.
- Fix: add one line to the directive: "never post, send or schedule; a human ships".

## Where the human gates sit

1. **Fact sheet sign-off.** Before any tokens are spent. This is the highest-leverage gate.
2. **Treatment plus 6 stills.** About 2 minutes, and it catches a wrong design before 49 minutes are spent.
3. **Final watch.** Every customer-facing film, at every rung, forever.

Deterministic steps: setup/fetch, TTS, asr_check, readcheck, render, mix, mux, encode, film_eval, upload.

Fuzzy steps: script, treatment, design and code, and style pick. Jev may pick the style: it is low-stakes and can be undone.

## Rung path

| Rung | Scope | Move up when |
|---|---|---|
| Prompt | v1 | Operator watch passes; the recalibrated film_eval passes v1 or names only real defects |
| Skill | Directive, setup script, gates | 5 hand-briefed films in different styles, each with a human watch; film_eval agrees with the human 5/5; fix rounds, minutes and tokens logged |
| Loop | Variants from one approved template | 10 variants with 0 fact defects that the human caught and film_eval missed; the error channel has had a sample message |
| Routine | New account → render, eval, review queue | Never publishes. Dead-man check on the queue. |

**Never automate:**
- writing or verifying FACTS
- the final watch
- clearing logo and brand rights
- any real member data or faces
- publishing or sending

## Honest gaps

- I did not watch the MP4, so I cannot say the film is good, only that nobody has shown it is.
- Token cost per film and how often the fix round converges are unmeasured.
- I did not re-run film_eval to confirm which FAILs are false positives. That judgement comes from reading the report.
