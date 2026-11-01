# Lens 7 — Daniela Amodei (operations, people, trust)

**Verdict: NOT CLEAR** for the panel as currently placed; NOT CLEAR for campaign or outreach reuse until the rules below exist.

## High

**H1. The synthetic voice delivers the candidate's best moment.** The SPEAKER_GUIDE sets the order: data line live at min 0–2, then "2 / 26 / 49 / 6" at min 4–7 as "the memorable moment". The film says all of it in a British `bf_emma` voice before Debanjan has spoken. To a panel hiring for judgement, that reads as hiding behind the tool.
*Fix:* open live: thesis plus line 1, about 40 s, no film. Then play the film **with VO** in place of the slide-4 walkthrough at about 4:00, and take back one line live afterwards ("Six. That's the product."). Cut to fit 76 s: slide 4 talk goes from 3:00 to 1:30 (the film already covers 525/500, tenure = staleness and 2/26/49), and the data line comes off slide 1. Don't play it muted with live narration: the subtitles are burned in (SCRIPT.md, S01–S13 "Burned in: yes"), so the panel would read one text while hearing another, and keeping a live voice in sync with a 72 BPM cut is a rehearsal risk he doesn't have time for.

**H2. Reusing the film outside the room leaks AlumnForce's case material.** The 525-row file, the 68 % and the "340 London expats" verbatim (F17) come from their hiring exercise. Sending it in cold outreach to other prospects would breach the panel's trust and hurt the candidate's name.
*Fix:* the panel cut stays private: an unlisted link, shared with the panel only. Outreach gets a separate cut built on synthetic or public numbers.

## Medium

**M1. "Six can be e-mailed today" is a consent claim the data can't back.** The six are judged on freshness only. `annexB.sql` has no opt-in or unsubscribe column, and the film quotes "Two unsubscribed" 9 s earlier. A DPO-minded lead will catch it.
*Fix:* say it live: "six current enough to write to; preferences still apply in the campaign module." The film line should change too, but only with the operator's word.

**M2. Alumni-facing films risk feeling like surveillance.** A film saying "your profile was last updated 4 years ago" is fine when it is the member's own field shown to them. "We noticed you moved" or "you haven't logged in" is not.
*Rules:* only data the member entered; never login activity (F14) or inferred employer or city; never internal labels ("To reactivate" is admin vocabulary, the member sees Confirm / Correct, F20); the school is the sender; one click to correct or to opt out; skip anyone unsubscribed; French narration in a human or disclosed voice, since Kokoro has one French voice (LEMO_TEARDOWN §9b); a visible "voice generated" credit.

**M3. A personalised AI film in cold outreach reads as spam.** Rules: per-segment variants, never per-prospect, and never speak the prospect's name in a synthetic voice; a poster image linking to an MP4 on his own domain (the teardown says video doesn't embed); send from a warmed subdomain with SPF, DKIM and DMARC, low daily volume, an opt-out line, and a sender that is clearly a named person (CNIL B2B rules).

## Low

**L1.** "No member record ever leaves the platform" is absolute, while the Q&A admits sentence text and tenant labels can leave. Keep the line, and have the DPO sentence ready word for word (guide line 4).

**L2. The honest line, said before pressing play:** "I directed an AI agent to build this from the same checked numbers as the deck. The voice is synthetic. Everything after it is me."

## Honest gaps
- I did not watch or listen to the MP4. Judgements on tone come from the script and the build log only.
- I did not check EU AI Act Art. 50 (synthetic audio disclosure) or CNIL prospecting rules against the primary texts.
- The panel's taste for AI theatre is unknown: no BRIEFING evidence either way.
- Timing cuts are not rehearsed.
