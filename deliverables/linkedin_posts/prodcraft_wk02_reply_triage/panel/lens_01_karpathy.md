# Lens 01: Karpathy (measurement)

**Verdict: NOT CLEAR.** Nothing in the post or film is measured. Each number is either a target, a client claim or a hardcoded literal.

## Findings (most severe first)

1. **HIGH: 0.99 is presented as a result.** It is a literal (`reply_classifier.py:103,113`; hot is `0.90` at :127). The result chips "auto_reply_or_OOO · 0.99 · €0.00" read as a measured confidence. I probed the rules with five made-up replies and four were misrouted. *"Interested! I will be back from Lisbon Tuesday, can we jump on a call then?"* came back as OOO with 0.99. *"Remove me from the thread and loop in our CTO, she wants a demo"* came back as negative with 0.99. *"Our budget is 2026 1500 2000… not interested"* came back as hot with 0.90, because the phone regex matched it. The OOO check runs before the hot check, so an interested buyer gets filed away, which is the exact failure the post says it prevents. **Fix:** change the chips to "rule match · €0.00 · no model called". Keep the code panel verbatim.
2. **HIGH: the code comes from a different system than the numbers.** 32/800/24,000/30–60 belong to the client (F01–F03, F18; code not in this repo). The tab shows `self_outbound_system`, Debanjan's own scaffold: 30 mailboxes, dry-run, live model path unimplemented (:143–151). **Fix:** label the tab "the rule layer, from my own build".
3. **MED: the figures are targets.** 800/day is a target (F02). 24,000 is 800×30, but 22 weekdays would give 17,600. 30–60 is a goal and no actual count is given. The wk 01 3–4% comes from the founder's manual sending, sample size unknown. **Fix:** write "target" next to 800, or give an actual figure.
4. **MED: no evaluation exists.** The tests are 15 replies the author wrote himself (`tests/test_reply_classifier.py`), so they share his blind spots. Euros are the wrong argument. At 3–4% of 24k that is roughly 720–960 replies a month. A model call costs cents at most, so the real saving is reading time and response speed.

## What to measure and report next week

Take ≥200 real client replies, hand-labelled blind. Report:
- precision of each rule
- recall on hot and positive replies (buyers missed)
- the share of replies the rules settle
- median time to first response for positive replies
- actual positive conversations per month against the 30–60 target

## Video vs image

LinkedIn has no A/B split, so each week gives one post per format. Confounds: topic, weekday and hour, audience growth, the hook line, and any format boost. Hold day, time and hook style fixed and alternate formats ABBA over 8 or more weeks. Decide the main metric in advance: DMs plus comments per 1k impressions (the post's goal). Use average watch time as a diagnostic. Treat the result as directional.

## Honest gaps

I saw the contact sheet but did not watch the MP4. My probes are invented replies, not real ones. I had no LinkedIn analytics and could not check the client's 32 inboxes against anything.
