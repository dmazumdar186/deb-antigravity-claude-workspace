# Round 2 closure: prodcraft-wk02-replies.mp4 v2

Audited 2026-11-01 against the v2 files (`src/content.json`, `src/out/drawn_text.json`, `src/build.sh`, `src/tools/*`, `SCRIPT.md`, `FACTS.md`, `EVAL_REPORT.md`, `src/out/hashes.txt`, the MP4 itself, git), not against BUILD_LOG claims. Nothing was edited except this file.

Independent checks run: `bash -n src/build.sh` OK; `json.tool` on content.json and drawn_text.json OK; `sha256sum` of the MP4 and poster.png equal `src/out/hashes.txt` (ecf6d307…, 7730a4c0…); `grep -c fillText src/film.js` = 1 (line 56, inside `drawText`); sha256 of reply_classifier.py lines 99–107 (no trailing newline) = 51b50c11… = `src/out/code.json`; motion onset recomputed with ffmpeg+numpy: pixels changed >40 vs frame 0 for frames 0–11 = `[0, 406, 333, 422, 292, 594, 4693, 7029, 7215, …]` (first fill at frame 6 = 0.20 s); ffprobe: High profile, 832 frames, 706 kb/s, comment tag present; `grep '95\|%' drawn_text.json` → only `"x": 995` (a coordinate); no `0.90`, no "sequence stopped"/"suppress" on screen; FACTS.md has no `Signed off:` line; `git ls-files` shows the MP4, poster, logo, stems and the whole `v1/` tree committed in 88526e7.

Status key: FIXED · OPERATOR (only the operator can decide) · OPEN (ours, not done) · OUT-OF-SCOPE (classifier/system code, queued separately).

## Findings table (HIGH and MEDIUM only; LOW/INFO listed where they change a verdict)

| Lens | Finding | Sev | Status | Evidence |
|---|---|---|---|---|
| 01 Karpathy | 0.99 presented as a measured result | HIGH | FIXED | content.json `rules[0].result` = "auto_reply_or_OOO · 0.99 (set by the rule)" / "€0.00 · no model called"; drawn_text.json entries at 9.4 s; SCRIPT row 23 |
| 01 | Code is from a different system than the numbers | HIGH | FIXED | Tab text "from my own build · same rules-first pattern · verbatim" (content.json `code.tab`, drawn at 7.87 s, 31 px); CREDITS "Code shown: The operator's own build (not the client system)" |
| 01 | Figures are targets (800, 24k, 30–60) | MED | OPERATOR | Headline is the operator's card verbatim; FACTS F02 already says "(target)"; 24,000 not on screen; "30–60" shown as "the target" (F18/F19). Only the operator can supply a measured figure or re-word the card |
| 01 | No evaluation exists for the classifier | MED | OUT-OF-SCOPE | Needs ≥200 real client replies; classifier task queued separately |
| 02 Cherny | No content file; wk 03 means forking code | HIGH | FIXED | `src/content.json` (239 lines) holds every week-specific string/number; film.js:9 `fetch('content.json')`, mix.py reads CONTENT, build.sh/master.sh read `meta.name`/`title`/`comment`; grep of film.js/mix.py/tools for "wk 02", "30–60", "800", "unsubscribe", "_OOO_PATTERNS" finds only a docstring in mix.py |
| 02 | House style = tokens plus prose; no `content.schema.json`, no template src | HIGH | OPEN (partial) | house.js now carries GRID/SAFE/TYPE/CHROME/CARD/PANEL/TILE and is byte-identical in both places (`diff` clean); STYLE.md §2 has token tables. But `find . -name content.schema.json` → none; style.json `tokens` key is just a pointer string to house.js; no template `src/` beyond "copy the reference build" (STYLE §11) |
| 02 | Build does not produce the delivered folder | HIGH | FIXED | build.sh:22 `OUTDIR=${OUTDIR:-$(cd "$HERE/.." && pwd)}`; promotion loop at line 69 moves mp4/poster/SCRIPT/contact_sheet/EVAL_REPORT.* into OUTDIR |
| 02 | Rebuild not proven identical (no hashes, SSIM only) | MED | FIXED | build.sh lines 57–66 write `src/out/hashes.txt` (mp4, 3 decoded frames, decoded audio, poster); the file exists and the MP4/poster hashes match the delivered files. The "two builds identical" claim itself is BUILD_LOG-only (not re-run here) |
| 02 | Environment from manual steps (LIB path, venv, fonts without hashes, ffmpeg 6.1) | MED | OPEN (partial) | build.sh:13 `LIB=${LEMO_OPUSCAR_HOME:-${LIB:-}}` and page.mjs/mix.py read `LEMO_OPUSCAR_HOME` (FIXED part). `grep -i sha\|hash src/tools/fonts.py` → none (font hash list still missing); no bootstrap-path build recorded; ffmpeg still 6.1.1 (EVAL_REPORT tool versions) |
| 02 | Directive has no series section, naming rule, checklist; `film_ledger.jsonl`, `TREATMENT.md`, top-level CREDITS missing | MED | OPEN | `grep -in series directives/video/lemo_opuscar.md` → only line 5 "not for series work"; `find . -name film_ledger.jsonl` → none; CREDITS only in `src/`. STYLE.md §11 has a wk 03 checklist, but the directive was not updated |
| 02 | film_eval fails every no-voice film | LOW | FIXED | film_eval 2.1.0: `--srt` optional, "(none)" narration → SKIPPED; EVAL_REPORT.md OVERALL WARN, 0 FAIL, 8 SKIPPED |
| 03 Amodei | Code shown is not the client's system | HIGH | FIXED | Tab wording as above; CREDITS line; FACTS F21 source "code" |
| 03 | Unsubscribe handling incomplete; don't claim "unsubscribes handled" | MED-HIGH | FIXED (film) / OUT-OF-SCOPE (code) | content.json `rules[1].result` = "negative · stop rule · 0.99 · €0.00", note "no 'sequence stopped' claim"; grep for "sequence stopped"/"suppress" in drawn_text.json → none. Stop-before-OOO and suppression wiring are classifier work |
| 03 | Client details differ across weeks | MED | OPERATOR | POST.md is verbatim operator copy (wk 01 "SMB Acquisition firm", wk 02 "US outbound consultancy"); not ours to change |
| 03 | 0.99 reads as measured; hot 0.90 is dry-run only | MED-LOW | FIXED | "(set by the rule)" on screen; 0.90 absent from drawn_text.json and SCRIPT.md; hot result = "hot · meeting request · to a person" |
| 04 Rigor | "hot · 0.90" holds only in dry-run; F10 silent on it | MED | FIXED | FACTS F10 now says "The 0.90 is returned only in dry-run (line 124)… 0.90 is never shown"; content.json `rules[2].note`; no 0.90 on screen |
| 05 Hormozi | No proof of a result, only mechanism | HIGH | OPERATOR | Needs a real CRM count or reuse of the wk 01 claim as a new FACTS operator row; nothing in repo can supply it |
| 05 | CTA has no lead magnet and is hedged; end card has no ask | HIGH | OPERATOR | Changes the post copy and the end card (output contract); end card still shows credits only (drawn_text.json 21.97–27.73 s) |
| 05 | Dream outcome buried (post opening; 30–60 at 18 s; no "30–60" on frame 0) | HIGH | OPERATOR | Frame 0 is the card headline by design (STYLE §1); the post opening is operator copy. "30–60" first drawn at 18.37 s |
| 05 | Film beats the card, code panel costs ~5 s | MED | FIXED / accepted | Panel on screen 7.83–13.2 s; lens itself calls it acceptable |
| 06 Saraev | Posting gates open (no FACTS sign-off, no operator watch) | HIGH | OPERATOR | `grep -in signed FACTS.md` → none; BUILD_LOG v2 ends "Operator watch: _pending_". F21 range already corrected to 99–107 |
| 06 | Opt-outs can be lost or invented (OOO before stop; quoted text) | HIGH | OUT-OF-SCOPE | reply_classifier.py lines 99–117 unchanged (verified by sed); classifier task |
| 06 | "stop → suppression" is a doc claim, not code | MED | OUT-OF-SCOPE | Film makes no suppression claim (see 03); code work queued |
| 06 | Rule-caught replies never meet a human; no error channel | MED | OUT-OF-SCOPE | System process, not the film |
| 06 | Boundary breach in the self_outbound_system directive (auto Cal.com link) | MED | OUT-OF-SCOPE | Lives in that directive; not touched by v2; should be in the queued task |
| 07 D. Amodei | Unsubscribe scored but never shown honoured | HIGH | OPERATOR | v2 deliberately shows only the label (content.json note); adding "sequence stopped" needs the operator to confirm the client system does it and add a FACTS row |
| 07 | Hook leads with volume (32 inboxes, 800) | MED | OPERATOR | Poster is the card headline; the lens's fix is to re-order the post copy |
| 07 | A polite "no" is sent to a person, with "CRM updated" | MED | OPEN | content.json `cards[0]` is still "Not interested, thanks." kind "rest"; at 15.2 s it sits under "to the right person, with context" with the shared "✓ CRM updated" (contact sheet). Replacing it with a second question is a one-line content.json edit; v2 chose to keep it (BUILD_LOG fix 5) because it matches no stop pattern, but lens 12 raises the same objection |
| 08 Sutskever | OOO beats hot; code puts no limit on it | HIGH | OUT-OF-SCOPE | Classifier code unchanged |
| 08 | Film reads as "rules are infallible" | HIGH | FIXED (film) / OPERATOR (post line) | Heading "Rules catch the obvious. Anything else goes to a person." drawn 12.23–17.53 s at 34 px (content.json `headings.limits`); "(set by the rule)" chip. The suggested post sentence is operator copy |
| 08 | Phone regex fires on any run of digits | MED | OUT-OF-SCOPE | Classifier |
| 08 | "hot · 0.90" only in dry-run; film shows scaffold as live | MED | FIXED | 0.90 removed; hot result "to a person"; F10 updated |
| 09 Murati | S1 nothing moves for 2.4 s | HIGH | FIXED | Recomputed from the MP4: first fill at frame 6 (0.20 s), 7,029 px changed by frame 7; events.json first "light" at t=0.133 |
| 09 | S2 result tags ~7 pt, label ~5 pt | HIGH | FIXED | drawn_text.json: results and pattern tags 31 px (11.2 pt), cards 32 px, label 31 px, code 30 px (10.8 pt, 0.2 pt under the proxy, accepted in STYLE §2); EVAL `drawn_text_mobile` WARN lists only chrome, credits and the 30 px code |
| 09 | S3 payoff comes late (18 s) | MED | OPERATOR | Lens says "none required"; 30–60 at 18.37 s unchanged; trade-off noted for the operator |
| 09 | S4 low source bitrate (CRF 18) | MED | FIXED | master.sh: `-crf 14 -maxrate 8M -bufsize 16M -tune animation -profile:v high`; ffprobe 706 kb/s, 3.16 MB (flat graphics; the "3–6 MB" estimate was not reached, but the settings asked for are in place) |
| 09 | S5 upload poster.png as thumbnail | LOW | OPERATOR | Posting step; poster.png re-exported and hash-matched |
| 10 Brockman | Logo not in git (`*.png` ignored) | BLOCKER | FIXED | `git ls-files` shows `src/assets/logo-prodcraft.png`, `poster.png`, `ref/wk02_card.png` tracked (force-added in 88526e7). Still ignored and untracked: `execution/video/lemo_house_styles/prodcraft-notes/styleframe.png` (LOW; not needed to build) |
| 10 | Toolkit lives only in /tmp; bootstrap env var mismatch | HIGH | OPEN (partial) | `LEMO_OPUSCAR_HOME` fallback in build.sh/page.mjs/mix.py (FIXED). No clean-container or bootstrap-path build is recorded; BUILD_LOG still says the deps were hand-built; `LEMO_CACHE` on durable storage not done |
| 10 | No deadline fallback to the static card | HIGH | FIXED (process) | STYLE.md §11 step 1 "Make the static card first: it is the fallback"; `ref/wk02_card.png` now tracked. Not in the directive (see 02 #6) |
| 10 | Build not atomic as a set | MED | FIXED | build.sh: `STAGE=$(mktemp -d "$OUT/stage.XXXXXX")`; master, poster, SCRIPT, contact sheet, blackdetect and film_eval all run on `$STAGE`; promotion only after `set -e` survives |
| 10 | MP4s in git (directive says Drive) | MED | OPEN / OPERATOR | Worse in v2: 88526e7 commits `prodcraft-wk02-replies.mp4` (3.2 MB), `v1/prodcraft-wk02-replies_v1.mp4` (2.4 MB), 3 stems + 3 v1 stems, both posters, logo twice. BUILD_LOG v2 says "Not committed (as instructed)", which contradicts git. Needs a decision on history (Drive upload + keep only sha256) |
| 11 Hassabis | No feedback loop (post_ledger, LinkedIn analytics) | HIGH | OPEN | `find . -name 'post_ledger*'` → none; no script change. Series infrastructure, ours to build, not done in v2 |
| 11 | "numbers checked" ≠ proven by code; label the scaffold | HIGH | FIXED | Tab "from my own build…"; FACTS separates code vs operator sources; 0.99 and 0.0 on screen come from code lines 103/106 (code.json) |
| 11 | Nothing reusable (components inline in film.js) | MED | FIXED (by a different route) | Tokens in house.js, content in content.json; STYLE §10/§11 make the reference `src/` the template. Components are still inline in film.js, but the lens's goal (a week writes only content) is met |
| 11 | Trap: reading as an AI-video account | MED | OPERATOR | Cadence decision (alternate card/film weeks) |
| 12 Audience | Contradiction: copy says "no" is handled automatically; film sends it to a person | (MED) | OPEN | Same as 07 #3; content.json `cards[0]` unchanged |
| 12 | Weak opening, no ask, 30–60 is a target not a result, typos, client description | (MED) | OPERATOR | All in POST.md (operator's verbatim copy) or need a real result |

## Per-lens round-2 verdict (CLEAR = no HIGH/MEDIUM item OPEN)

| Lens | Verdict | Why |
|---|---|---|
| 01 Karpathy | CLEAR | 2 FIXED, 1 OPERATOR, 1 OUT-OF-SCOPE |
| 02 Cherny | NOT CLEAR | OPEN: content.schema.json/template (#2), font hashes + bootstrap-path proof (#5), directive series section + film_ledger (#6) |
| 03 Amodei | CLEAR | film side fixed; code side out of scope; client wording is operator's |
| 04 Rigor | CLEAR | F10 updated, 0.90 gone |
| 05 Hormozi | CLEAR | all three HIGH items are operator decisions (proof, CTA, opening) |
| 06 Saraev | CLEAR (film) | gates are operator's; the four system findings are the queued classifier task |
| 07 D. Amodei | NOT CLEAR | OPEN: "Not interested, thanks." still routed to a person with a CRM tick (#3) |
| 08 Sutskever | CLEAR | film findings fixed; classifier findings out of scope |
| 09 Murati | CLEAR | S1, S2, S4 fixed and independently measured; S3/S5 operator |
| 10 Brockman | NOT CLEAR | OPEN: clean-container/bootstrap build unproven (#2); MP4s and stems now committed, BUILD_LOG says otherwise (#5) |
| 11 Hassabis | NOT CLEAR | OPEN: no post_ledger / feedback loop (#1) |
| 12 Audience | NOT CLEAR | OPEN: the "no → person" contradiction (shared with 07) |

## OPEN items (ours)

1. `cards[0]` "Not interested, thanks." → swap for a second neutral question (content.json one-line edit, rebuild) or keep and have the operator say so (07 #3, 12).
2. `content.schema.json` for content.json and a clean template `src/` in the house-style folder (02 #2).
3. Directive `directives/video/lemo_opuscar.md`: series section, naming rule, weekly checklist, `film_ledger.jsonl`, top-level CREDITS (02 #6, 10 #6).
4. Font hash list in `tools/fonts.py`; one recorded build via `lemo_bootstrap.py install → check → build.sh` in a clean container (02 #5, 10 #2).
5. Binary artefacts in git: decide Drive vs git, fix the "Not committed" line in BUILD_LOG (10 #5).
6. `post_ledger.jsonl` + a LinkedIn analytics intake (11 #1).

LOW, noted: `styleframe.png` still gitignored/untracked; result chips log `vis_max` 0.97 (a few px of glyph box outside the card clip; visually complete at 11.6/12.6/15.2 s on the contact sheet).

## OPERATOR decisions

1. **Sign-off and watch**: add `Signed off: <name>, <date>` to FACTS.md; watch muted and with sound on mobile and desktop (06 #1).
2. **A real result** to cite (booked calls, hot-reply-to-person time, or the wk 01 "met its target" claim) as a FACTS operator row, or accept the film shows only the target (05 #1, 12, 01 #3).
3. **Unsubscribe honoured**: does the client system suppress after "unsubscribe"? If yes, confirm and add a FACTS row so the stop card can say "sequence stopped" (07 #1, 03 #2).
4. **CTA / lead magnet and end-card ask** (05 #2, 12): changes the post copy and the film's end card.
5. **Post copy**: opening line (bottleneck first), one client description across wk 01/02, the "rules are blunt on purpose" sentence, typos (05 #3, 03 #3, 07 #2, 08 #2, 12).
6. **Posting steps**: upload poster.png as the thumbnail; LinkedIn AI-content label; put the static card in the first comment (09 S5, 12).
7. **Cadence**: alternate card weeks and film weeks (11 #4).
8. **Where the MP4 lives**: Drive per the directive, or keep in git (10 #5).

## OUT-OF-SCOPE (queued classifier/system task)

Stop check before OOO; strip quoted text; `_HOT_PATTERNS` checked before returning OOO (or RFC 3834 header); phone regex on digit runs; `opt_out` class wired to `suppression_writer`; weekly human sample + error channel; the Cal.com auto-send boundary in the self_outbound_system directive; a real labelled evaluation set (01 #4, 03 #2, 06 #2–5, 08 #1/#3).
