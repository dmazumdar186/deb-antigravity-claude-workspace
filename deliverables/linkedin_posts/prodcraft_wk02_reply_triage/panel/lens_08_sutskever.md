# Lens 8: Sutskever (capability and failure modes)

**Verdict: NOT CLEAR.** The film pipeline is sound. The claim it makes is not bounded: the snippet on screen shows `if ooo_hits: return`, and nothing in the film admits that a rule can misfire.

## Findings (by severity)

1. **HIGH: OOO beats hot, and the code puts no limit on it.** I ran `classify()` on these replies:
   - "I'm out of office until Monday, call me at 555…" → `auto_reply_or_OOO 0.99`
   - "I was absent last week but ready to start now." → OOO 0.99
   - "Will return your call Thursday, can we jump on a call?" → OOO 0.99
   - "Our legal team is on vacation; meanwhile can we do a call?" → OOO 0.99

   That is the worst plausible output: a buyer filed away at 0.99 that no person ever sees, which is the exact failure the post says the system prevents. **Fix (code):** before returning OOO, run `_HOT_PATTERNS`. If both match, send the reply to a person. Prefer the `Auto-Submitted` header (RFC 3834) over body regex.
2. **HIGH: the film reads as "rules are infallible."** All six illustrative cards land cleanly, and "0.99" looks like a measured accuracy. It is a constant the code sets (lines 103 and 113). **Fix (post, one line):** *"The rules are blunt on purpose: the 0.99 is a value I set, not a measured accuracy, and a reply that says both 'out of office' and 'call me' should go to a person, not a rule."* Ship that line only once fix 1 is live. Until then, use only the first clause.
3. **MED: the phone regex fires on any run of digits.** "Re: order 2024-11-0457, not interested." → `hot 0.90`. "Please don't remove me… ready to sign" → `negative`.
4. **MED: "hot · 0.90" only happens in dry-run.** In `--live` the hot branch falls through to the unimplemented model path (lines 121–131). The film shows the scaffold's behaviour as if it were the live system.
5. **LOW: gaps in the French and English rules.** "Merci, je ne suis pas intéressé", "Please stop", "Out-of-office: back Monday" and "OOO until 4th" all come back as neutral. "en congé…, mais rappelez-moi: intéressé" comes back as OOO.
6. **LOW: BUILD_LOG.md is stale.** It says "on-screen 13/13" and "tag coverage 10/10". EVAL_REPORT.md says 11/11 and 8/8.

## Film pipeline

- **No drawn string escaped the check.** `fillText` appears once (film.js:47), and every call goes through `drawText()`, which logs it. index.html has no text in the page. The only other drawing is the raster logo and shapes.
- **The FAIL verdict is a calibration problem, not a defect in the film.** `speech_rate` counts the placeholder "(none)" as one word (2.6 wpm), and `captions_parsed` fails on an SRT that is empty on purpose. Both should be marked N/A when a film has no narration.

## Honest gaps

- The client's production classifier is not in this repo. Every finding above applies to the scaffold the film quotes.
- I did not watch the MP4, so legibility at rest is unchecked: the manifest stores the first-frame position, and "verbatim" sits at x=2002.
- quote_fidelity does not check the wording of labels.
