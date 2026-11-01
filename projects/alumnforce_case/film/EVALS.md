# lemo-opuscar: evals for Debanjan (technical, AI and business)

Subject: lemo-opuscar (open-source films drawn in code, tuned for Opus 5.5), pinned at `bebbbe1`, judged on the *Trusted Segments* evidence film for the AlumnForce talk. 2026-11-01. Claims cite their source file; unmeasured things are marked.

## 1. Verdict in 5 lines

1. **Value:** it turns a verified fact sheet into a 61 s evidence film in about 90 minutes of agent time, with automated checks on every number heard or seen. What you show the panel is the method: facts, then checks, then human review.
2. **Best use:** one hero film for an audience that matters, where the numbers are the message. Here that means your answer to the AI-usage question in Q&A (Annex A), not the opening of the talk (`PLAYBOOK.md`).
3. **What it can't do:** check its own meaning. The checks proved every number, but the AI scorer Jev rated "Six can be e-mailed today" as supported (0.93). Only human lenses caught the overclaim. A person has to watch every film.
4. **Status:** the v2 eval has WARNs and no FAILs (`EVAL_REPORT_v2.md`). Visual QA round 2 is PASS-WITH-FIXES. A v2.1 polish is rendering, results pending. You haven't watched it yet, so it is still a draft.
5. **Cost:** measured wall clock was 49 min (v1) + 41 min (v2). Machine time is about 3 min per master. Each Jev run costs $0.004. Tokens and your review minutes were never logged.

## 2. Technical eval

### 2.1 Scorecard

v1 is shown as re-scored with the v2 harness (film_eval 2.0, delta table in `EVAL_REPORT_v2.md`), so both columns use the same ruler. The original v1 run (`EVAL_REPORT_v1.md`, film_eval 1.0) was an overall FAIL, mostly because of harness false positives.

| Metric | v1 | v2 | Threshold | Source of threshold | v2 verdict |
|---|---|---|---|---|---|
| Duration | 76.25 s | 61.375 s | ≥ last caption; opener advice ≤ 45 s | `LEMO_TEARDOWN.md` §9a (judgement) | PASS; over the advice |
| File size | 23.18 MB | 19.5 MB | ≤ 25 MB | Gmail attachment limit | PASS |
| Loudness | −14 LUFS (FAIL) | −16 LUFS | −16 ± 1 | AES TD1004/1008, EBU R128 | PASS |
| True peak | −1.2 dBTP | −1.7 dBTP | ≤ −1.0 | EBU R128 / AES | PASS |
| Frozen frames | 4.29 s (WARN) | 0 s | ≤ 4 s | guess | PASS |
| Number fidelity: narration / on-screen / SRT / drawn | 20/20, 29/30, 15/15, n/a | 20/20, 30/30, 15/15, 42/42 | every number in FACTS | FACTS.md | PASS |
| Drawn text ≥ 28 px | n/a | 185/185 | ≥ 28 px at 1080p | guess | PASS |
| Quote fidelity | 13/30 exact | 14/40 exact, 1 altered label | exact | exact = standard; 0.6 cut = guess | WARN |
| Tag coverage / consistency | 100 % / 2 | 96 % / 1 | 100 % / 0 | guess | WARN |
| Speech rate | 137.4 wpm | 148.7 wpm | 130–170 | guess (BBC-bounded) | PASS |
| Captions: cps / chars per line / sub-2-frame gaps | 19.5 / 78 / 14 | 16.9 / 42 / 0 | ≤ 17 / ≤ 42 / 0 | Netflix TTSG | PASS |
| ASR WER, final mix | 3.73 % | 0.72 % | ≤ 5 % | guess | PASS |
| Spoken numbers heard | 15/15 | 15/15 | all | (0 checked = SKIPPED) | PASS |
| Jev entailment | 0.868 (FAIL) | 0.896 | each line ≥ 0.705 | calibrated, AUROC 0.99 | PASS |
| Jev contradiction | 0 | 0 (max 0.13) | < 0.288 | calibrated, AUROC 1.00 | PASS |
| PII scan | 0 | 0 | 0 | FACTS hard rules | PASS |
| **Overall** | FAIL | **WARN** | | | |

Two caveats:
- The lemo directive requires `OVERALL: PASS` (`directives/video/lemo_opuscar.md`, Exit Criteria). film_eval allows each WARN to be accepted in writing (`film_eval.md` Step 4). The v2 WARNs are an untagged end card, "500" tagged F13 instead of F02, and one altered label. Fix them or accept them in writing.
- The directives disagree on loudness. The lemo directive still says −14 LUFS; film_eval and the film use −16.

### 2.2 Reliability and reproducibility

| Item | State (evidence) |
|---|---|
| Toolkit pin | `bebbbe1`; `build.sh` refuses any other SHA (`BUILD_LOG.md` v2) |
| `lemo_bootstrap.py doctor` (run today) | OK; ffmpeg 6.1.1 is a WARN (7+ recommended) |
| `check --target` on the clone that built the film (run today) | **OK**: files match the pin; 47 hashed pip pins match the venv; npm 1.63.0 / 0.170.0; 4 packs match sha256; Whisper `small.en` at rev `d1d751a5f827`. Two WARNs: the venv was hand-built (hashes not enforced at install); no manifest |
| `check` at the default target | FAIL: `install` has never been run |
| Fresh-container install; `build.sh` end to end | **not evidenced** ("not run end to end in one go", `BUILD_LOG.md` v2) |
| Not pinned | authoring model id (log says only "standard tier"), brief hash, ffmpeg, Node, Chromium (comes with the container), Python minor version |
| Byte-identical rebuild | not guaranteed (x264 threads, Whisper timings); compare with SSIM (`lemo_opuscar.md`) |

### 2.3 Cost and time per film (measured, `BUILD_LOG.md`)

| | v1 | v2 |
|---|---|---|
| Guides, treatment, reading | 189 s (+51.5 s setup) | ~4 min |
| Voice passes (TTS + trim + ASR) | 20–61 s each | 5 passes, 290 s |
| Page authoring + fix round | 665 + ~326 s | 936 s + ~3 min |
| Render + master + encode | 124 + 107 + 70 s | ~96 + 70 s per master, ×2 masters |
| **Total wall clock** | **49 min 11 s** | **40 min 47 s** |
| Jev cost | $0.0007 | $0.0039 (calibration $0.017) |
| Tokens / your review minutes | **not measured** | **not measured** |

Render, mix and encode take about 5 minutes; writing and fixing take the rest.

### 2.4 Failure modes found and fixed

| Failure | Caught by | Fix |
|---|---|---|
| Count-ups drew numbers not in FACTS ("13", "×2.5") | self-review | values land only as fact values; drawn-text manifest (42/42) |
| Label over the previous step's value | visual QA #1 | one `STEPS` table (closed in `VISUAL_QA_v2.md`) |
| Real ID next to an invented city (M0475) | lenses 3, 4, 12 | real record M0271 (F26); no IDs on background cards |
| "6 can be e-mailed today" | lenses 3, 7, 12 (Jev missed it) | "Six worth contacting today" |
| Kokoro "Segments" tail; "two" heard as "too" | ASR check | trim after the sibilant; rewrites |
| readcheck failure hidden by `&&`; `ffmpeg -y` overwrote the delivered film | lenses 2, 10 | check on its own line; temp file, then `mv` |
| Spoken-number check passed at 0/0 | lenses 1, 4, 8 | number words → digits; 0 checked = SKIPPED |
| **v2 eval first said FAIL: 288 wpm, WER 50 %** | the eval | SCRIPT.md nested the captions table under `## Narration`, so the narration was counted twice. Captions got their own section. **This input format is fragile: the harness should warn when narration duplicates caption text** |
| **Jev flagged "One sentence. Four answers." (0.16)** | Jev | the line is sourced (slide 3's title, "Same sentence, four answers"), but the fact was missing from the sheet. F28 added; it then passed. **Jev found a gap in the fact sheet, not a bad line** |

## 3. AI eval metrics

### 3.1 Fidelity

| Metric | v2 | Proves | Doesn't prove |
|---|---|---|---|
| Number fidelity (4 sources) | 107/107 | every digit heard, captioned or drawn is in FACTS | that the words around it are fair |
| Quote fidelity | 14/40 exact; 26 labels info only | F01, F17, F24 quoted exactly | wording of labels |
| Drawn-text fidelity | 42/42; one `fillText` call in the page | everything drawn is logged and checked | the log is the builder's own; no independent OCR |
| ASR WER | 0.72 % (1 edit in 138 tokens) | the voice survives the mix | a wrong number can hide inside a low WER |
| Spoken numbers heard | 15/15 | each caption number is heard | numbers that appear only on screen |

### 3.2 Jev calibration (`jev_support_calibration.md`)

| Question | n (pos/neg) | AUROC | Threshold | TP | FP | FN | TN |
|---|---|---|---|---|---|---|---|
| Is it a claim? | 67 (49/18) | 1.000 | 0.368 | 49 | 0 | 0 | 18 |
| Is it stated in the sheet? | 49 (24/25) | 0.990 | 0.705 | 24 | 1 | 0 | 24 |
| Does it contradict the sheet? | 49 (14/35) | 1.000 | 0.288 | 14 | 0 | 0 | 35 |

- **The miss.** "Six can be e-mailed today" scored 0.93 supported. In the table it shows as a false positive. For the gate it is a false negative: a bad line got through. Three human lenses caught it, so **Jev can't be the only check on wording.** It does catch wrong numbers (mean 0.02 on that category) and gaps in the sheet (F28).
- **Spread.** In calibration the mean spread was 0.0084 (max 0.10). On the v2 film it was 0.019 (max 0.040), over N = 3. Snapshot `typesafe/jev-1.13-20260917`, prompt hash `23ed4e21bcad3a8b`.
- **Limits.** The thresholds were picked on the same 67 lines they are scored on (no held-out set). There is one fact sheet and one labeller, and only 6 "hard" items. The directive calls the set "easy" (`film_eval.md`). Read AUROC 0.99 as an upper bound.

### 3.3 Model dependence and nondeterminism

- **The same brief gives a different film.** Only `src/` reproduces this one, and no seed recreates it (`BUILD_LOG.md` v2; `LEMO_TEARDOWN.md` §1).
- **Tuned for Opus 5.5.** The log records only "standard tier" (Opus 5.5 per CLAUDE.md), with no model id. Fable and Sonnet are untested.
- **Other variation.** Whisper timings drive every cue, x264 varies with threads (lens 2), and Jev adds 0.02–0.04. No drift monitor exists yet (lens 8 proposes a monthly re-render with planted mutations).

### 3.4 Standard vs guess

| Standard (cited) | Calibrated on our data | Guess |
|---|---|---|
| Loudness and true peak (AES/EBU); captions: 42 chars, 2 lines, 7 s max, 2-frame gap (Netflix); 17 cps (Netflix *children's* limit; adults 20); WCAG 4.5:1 contrast (visual QA) | Jev thresholds (n = 67, in-sample) | WER 5 %, 130–170 wpm, freeze/silence/black limits, 28 px, tag coverage, 0.6 quote cut, resolution and bitrate floors |

### 3.5 Not measured: does a viewer understand it?

Every metric tests the file; none tests a viewer (lens 1). Lens 1 test design:
- **Arms:** 6 PMs per arm. The film vs a static slide with the same facts for 61 s.
- **Score:** recall of 2 → 26 → 49 → 6 in order, plus why each number changes (0–8). Ask "Why 6, not 49?" Retest at 24 h.
- **Falsifier:** the film scores no better than the slide, or a 35 s cut scores the same.
- **Power:** six per arm only catches misreadings. A 40 % → 80 % recall gain needs about 23 per arm. With only six people this week, show all six the film and treat any wrong "Why 6?" answer as a defect.

## 4. Business eval

### 4.1 For the AlumnForce talk (`PLAYBOOK.md`; lenses 7, 9, 12)

| | |
|---|---|
| Value | Shows how an AI PM works: fact sheet, deterministic checks, a calibrated AI check, human review, honest disclosure. The loupe on M0271 and the 2 → 26 → 49 climb read without sound (lens 9). |
| Risk | A synthetic voice delivers your best moment (lens 7). It can read as a gimmick to a panel wary of AI decks (lens 12). The honest line is false until you've watched it. Sound can fail in a call. Case material leaks if the film is reused outside the room. |
| Placement | **Not in the 20-minute talk.** Play it once in Q&A as your answer to the AI-usage question (net cost about 1 min), or offer it at 38:00. If there's no sound or under 4 min remain, send an unlisted link to the clean master plus FACTS.md the same day. |
| Open | `SPEAKER_GUIDE.md` and the deck's Annex A still don't mention the film (checked today). The guide edits in `PLAYBOOK.md` §1 are yours to make. |

### 4.2 For your campaigns (effects are hypotheses; base rates are industry-typical, not yours)

| Channel | Fit | Cost per asset | Hypothesis | Test | Kill criterion |
|---|---|---|---|---|---|
| ABM, top 10–20 targets | good | ~45 min agent + fact sheet + 3-min watch | replies ≥ 2× a text-only control | poster link vs text, 20 sends each | under 2× after 20, or over 30 min of your time per account |
| Cold email (Instantly) | limited: no embedding | ~6.5 min machine per segment variant (untested) | positive replies 3 % → 4 % | text / static image / GIF poster + link, ~5,300 per arm, spam placement as a guardrail | no lift at the planned sample, or worse placement |
| LinkedIn organic, 4:5 | good | ~45 min agent, made for the feed | more dwell and comments than a static carousel | 4 paired posts | no difference after 4 pairs |
| LinkedIn / paid ads | limited: one hero per angle; `ad-creative` does volume | ~45 min | CTR 0.5 % → 0.65 % | ~40k impressions per arm | no lift, or an AI-label penalty |
| Per-prospect personalisation | **don't**: a Loom wins | — | — | — | — |

### 4.3 AlumnForce product idea: a data-health film for each school

- **Pitch.** A yearly recap of each school's naive vs trusted count, aggregates only, ending on "Confirm / Correct", so the film helps refresh the data (lens 11).
- **Moat and trap.** The moat is the trust layer on data only AlumnForce holds; the MIT visuals are no moat. The trap: with 68 % of profiles stale, an auto-made film can broadcast stale numbers, so show only "current" counts.
- **Gates.** A signed-off FACTS file and a human watch per school; no per-tenant leaks. A static report first; Q3 at the earliest.
- **Kill criterion.** Fewer than 3 of 10 pilot schools forward it, or one fact-check failure (lens 5).
- **Not built yet.** `film.js` hard-codes the counts; there is no `content.json`, house style or ledger (checked).

### 4.4 Unit economics and the automation ladder

- **Cost.** Each film costs the agent session (tokens unknown), plus fact curation (the real cost), about 8 min of machine time for a full rebuild, $0.004 of Jev and your watch. It pays off as a template for a few high-value accounts, not at volume (lens 5). A hundred variants would take about 8 h of rendering (lens 11).
- **Ladder** (`lemo_opuscar.md`; `CAMPAIGNS.md` §4):
  1. Prompt, one film. You are here and haven't passed it: no watch is logged.
  2. Skill: 5 films watched by a human, the eval agreeing with the human 5/5, and minutes and tokens logged.
  3. Loop: 10 variants with 0 fact defects missed by the eval, and a tested error channel.
  4. Routine: never publishes.
- **Never automate:** the fact sheet, the final watch, rights, faces or member data, publishing.

## 5. What cannot be done

| Hard limits | Soft limits |
|---|---|
| No live action, generated video, stock footage, photoreal people or real lip sync (`LEMO_TEARDOWN.md` §6) | Short-form 30–60 s; cost multiplies past 2–3 min |
| No product screenshots; no editing of existing video; no timeline editor | One French voice; edge-tts banned for member or paid work |
| No identical re-creation from the brief | Tuned for Opus 5.5; other models untested |
| Not in claude.ai chat; Windows only through WSL | Software WebGL about 6× slower (Canvas 2D is fine) |
| Can't judge meaning or consent | Token cost unknown; one fix round by design |

**Legal and labelling duties** (`CAMPAIGNS.md` §7; `lemo_opuscar.md`; lens 3):
- **Disclosure.** Put "Made with AI · synthetic voice" on every outbound film, add AI metadata, and use platform labels. EU AI Act Art. 50 duties apply from 2 Aug 2026.
- **Voices.** No cloned real voice without written consent (French Penal Code art. 226-8).
- **Credits.** The CC BY 3.0 Salamander credit with its URL goes on the end card (present in v2). Ads use CC0 instruments only.
- **Alumni.** The school sends; only data the member entered; one-click correct or opt-out.
- **Cold email.** Named sender, opt-out, SPF/DKIM/DMARC (CNIL).
- **Maps.** Override DIRECTOR §13.
- **AlumnForce's material stays with the panel.**

## 6. Panel scoreboard

Status is judged only from the v2 files (`BUILD_LOG.md` v2, `EVAL_REPORT_v2.md`, `VISUAL_QA_v2.md`, `FACTS.md`, `PLAYBOOK.md`, directives). "Open" means the v2 files don't show it was fixed.

| Lens | Round 1 | Top finding | After v2 |
|---|---|---|---|
| 1 Karpathy | NOT CLEAR | no viewer outcome; 0/0 audibility | **partly**: audibility 15/15; viewer test open; 61 s > 45 s |
| 2 Cherny | NOT CLEAR | hidden readcheck failure; no one-command rebuild; determinism unproven | **partly**: readcheck and SHA guard fixed; `check` OK; never built end to end; no hash manifest |
| 3 Amodei | NOT CLEAR | real ID next to an invented city; CC BY credit missing | **partly**: both fixed and the overclaim too; Annex A open |
| 4 Rigor | NOT CLEAR | authoring model not recorded | **partly**: tier and CLI recorded, no model id or brief hash; Jev repeats fixed; 68 % query untraced |
| 5 Hormozi | NOT CLEAR | no dream outcome; 76 s | **partly**: F24 thesis and 330 px "6"; 61 s vs ~45 s; tokens unlogged |
| 6 Saraev | NOT CLEAR | no human watch | **open**: no watch logged; eval vs human 5/5 not started |
| 7 Daniela | NOT CLEAR | synthetic voice delivers your best moment | **partly**: PLAYBOOK moves it to Q&A; not adopted; guide unchanged |
| 8 Sutskever | NOT CLEAR | picture unchecked | **fixed**: drawn manifest 42/42 plus visual QA; no OCR; no drift monitor |
| 9 Murati | NOT CLEAR | caption misquoted F01; no call plan | **partly**: F01 exact; call checklist untested; slide-1 brand hand-off open |
| 10 Brockman | NOT CLEAR | no bootstrap, lock or cache | **partly**: bootstrap, hashed lock and Whisper revision exist; fresh install never run; ffmpeg 6.1 |
| 11 Hassabis | NOT CLEAR | eval noise; counts hard-coded | **partly**: noise fixed; no `content.json`, house style or ledger |
| 12 AlumnForce panel | NOT CLEAR as opener | "can be e-mailed"; guide silent on the film | **partly**: wording fixed; guide still silent; no "exercise file" tag |
| Visual QA r1 | PASS-WITH-FIXES | label/value desync | **fixed**: 14/15 closed; contrast only partly fixed |
| Visual QA r2 | PASS-WITH-FIXES | invented cities in the loupe (N1); thesis over the cards (N2) | **open**: the v2.1 fixes are pending |

**v2.1 (rendering now; no results claimed)** targets N1, N2, left-side contrast at 4.2–4.8:1 (N3), ghost text (N5, N6) and "win back" vs "reactivate" (N7). Treat all five as open until its eval and visual QA land.

## 7. Honest gaps and next steps (prioritised)

1. **Watch the final cut yourself**, with sound, start to end, on your playback setup. Log `Operator watch: <date> <PASS|notes>` in `BUILD_LOG.md`. This is the human gate: without it the film is a draft and the honest line is false.
2. **Land v2.1 and re-run** film_eval and visual QA. Clear or accept the three WARNs, and tag "500" as F02.
3. **Decide on the Annex A line** (`PLAYBOOK.md` §5) and make the SPEAKER_GUIDE edits ("safely email" → "worth contacting today").
4. **Re-verify F13–F15 (68 %, 77 %, 112 days) on the raw CSV on your machine.** It isn't in the repo. Then add the `Signed off:` line FACTS.md lacks.
5. **Run the 6-person audience test** (§3.5) before you call the film effective.
6. Test the call share on a second device. Rename the SRT so VLC can't auto-load it (N8).
7. Align loudness: −14 in `lemo_opuscar.md` vs −16 in film_eval and the film.
8. Harness: warn when narration duplicates captions. Add consent and capability wording ("can be e-mailed") to the Jev set, with a held-out split.
9. Log tokens and your review minutes on the next film. Without them there are no unit economics.
10. Before any campaign: run a fresh `lemo_bootstrap.py install`, run `build.sh` end to end, record the model id, and build the `content.json` template and `film_ledger.jsonl`.
