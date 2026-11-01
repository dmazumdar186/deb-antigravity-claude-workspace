# Lens 6: Saraev (automation maturity and boundaries)

**Verdict: NOT CLEAR** for a campaign pipeline. The talk film can ship once the operator has watched it.

**Rung today: prompt, one film.** Nobody has watched it; the only review was the agent reading its own contact sheets.

## Findings

**HIGH 1: No proven manual output.** One film, no recorded human watch, eval verdict FAIL.
Fix: the operator watches v1 with sound and logs the verdict. Nothing moves up a rung before that.

**HIGH 2: The eval gate is not calibrated.**
- Most FAILs are false positives. Cue IDs (`S02`), `1920×1080`, `M0475` and labels like "8 spellings" are flagged.
- Its loudness target is −16 LUFS; the directive masters to −14.

Fix: scan only narration, subtitles and on-screen text, and allow ID patterns. Check its verdicts against human verdicts on 5 films before it blocks anything.

**HIGH 3: Too much is fuzzy, and there is no template.** Each film is about 430 new lines of code plus a new script.
Fix: freeze one human-approved film per client as the house template. Variants change only a few named slots (`school_name`, `segment_sentence`, fact ids) via `--q content=…json`.

**MED 4: The bottleneck is facts and review, not render.** Render, mix and encode take about 5 of the 49 minutes. Each account needs its own verified fact sheet.
Fix: size the campaign by fact curation plus about 3 minutes of watching per film.

**MED 5: No error channel.** A film_eval exit 1 goes nowhere, Jev fails open (`answers == {}`), and the directive has no failure branch.
Fix:
- Gates fail closed.
- Failed builds go to `.tmp/film_quarantine/`.
- Failures post `service / env / error / count` to the operator's channel.
- Wiring is done only after a sample message has been seen.

**LOW 6: The boundary is unstated.** `automation-boundaries.md` says producing the final creative is "NOT OK to automate".
Fix: the directive says "never post, send or schedule; a human ships".

## Human gates

1. Fact sheet sign-off, before any tokens are spent.
2. Treatment plus 6 stills.
3. Final watch of every customer-facing film, at every rung.

**Deterministic:** setup, TTS, ASR check, reading check, render, mix, mux, encode, eval, upload.
**Fuzzy:** script, treatment, design and code, style pick. Jev may pick the style (cheap to undo).

## Rung path

| Rung | Move up when |
|---|---|
| Prompt (v1) | Operator watch passes; the recalibrated eval passes v1 |
| Skill (directive + gates) | 5 hand-briefed films, each watched by a human; eval agrees with the human 5/5; minutes and tokens logged |
| Loop (template variants) | 10 variants with 0 fact defects missed by the eval; error channel tested |
| Routine (per account → review queue) | Never publishes; a dead-man check watches the queue |

**Never automate:** the fact sheet, the final watch, rights clearance, real member data or faces, publishing.

## Honest gaps

- I did not watch the MP4.
- Token cost per film is unmeasured.
- I judged the false positives from the report; I did not re-run the eval.
