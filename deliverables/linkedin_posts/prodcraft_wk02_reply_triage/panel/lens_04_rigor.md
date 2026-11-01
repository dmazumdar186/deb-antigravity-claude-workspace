# Lens 4: research rigor

**Verdict: NOT CLEAR.** One scoping defect needs fixing.

## Findings

1. **MEDIUM: "hot · 0.90" holds only in dry-run mode.** In `reply_classifier.py` the hot return sits inside `if dry_run:` (line 124). Lines 121–123 say live mode would "still LLM-verify"; that path is a stub (145–151). F10 leaves this out. **Fix:** show "hot" with `_HOT_PATTERNS` and drop "· 0.90", or add "(dry run)". Update F10.
2. **LOW: "€0.00" is a hard-coded `0.0`, not a measured cost.** The dry-run stub returns the same value (line 140). For the OOO and stop rules it is still true, because they run a regex and make no API call. The film puts €0.00 only on those two and keeps it off "hot", which is correct. **Fix:** none. If asked, say "no API call".
3. **LOW: "positive" has two meanings.** The film uses the code's class names consistently (`auto_reply_or_OOO`, `negative`, `hot`) and never shows `positive` or `neutral`. But F18's "positive conversations" comes right after a card tagged `hot`. **Fix:** accept it; F18 is the operator's own wording, verbatim.
4. **INFO: the "800 sends" headline leaves out "target" and "a day".** Same as the card; the reframe "800 sends a day" matches the post. 32 inboxes matches across card, film (8×4 tiles) and post. **Fix:** none.
5. **INFO: BUILD_LOG lines 62 and 103 still ask for an F21 change that FACTS already has (lines 99–107).**

## Passing checks
- **Code:** drawn lines equal source lines 99–107 after removing exactly 4 spaces. The sha256 `51b50c11…` recomputes.
- **Replies:** run against the real regex lists, the OOO, stop and hot cards each match. "Tell me more.", "What does pricing look like?" and "Not interested, thanks." match nothing and get no class.
- **"no model called"** appears only on the OOO result.
- **30–60** is framed as the target, verbatim from F18/F19; nothing claims it was reached.
- No "~95%" and no line 98 anywhere.

## Honest gaps
- Frames not checked; based on drawn_text.json, SCRIPT.md and the code.
- F15/F16 (routing, CRM) cannot be checked because the client system is not in this repo.
