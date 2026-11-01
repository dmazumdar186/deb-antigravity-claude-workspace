# Lens 3 (Amodei): honesty, safety, legal exposure

**Verdict: NOT CLEAR.** One label change (#1) makes it CLEAR. Everything else is a fix to the copy or the code, not to the film.

## Findings, most severe first

1. **HIGH: the code shown is not the client's system.** The tab says `self_outbound_system / reply_classifier.py · verbatim` right under a post about "a US outbound consultancy". That file is his own unshipped scaffold. Its live path raises `NotImplementedError` (lines 145–151), and the directive puts it at Phase 3 (30 mailboxes, French ICP, never live). The `€0.00` on screen also gives away that it isn't a US system. Then the "CRM updated" ticks appear next to code that has no CRM. *Fix:* change the tab to **"from my own build, same rules-first pattern · verbatim"**.
2. **MED-HIGH: unsubscribe handling is incomplete in the code shown.** The OOO check runs before the stop check. I tested "Automatic reply: I am out of office. Also please remove me" and got `auto_reply_or_OOO`, so the opt-out is lost. `reply_classifier` also never calls `suppression_writer`, so a "negative" label doesn't stop the sequence. The film only shows a label, not suppression, so it overclaims nothing. *Fix:* don't add any "unsubscribes handled" claim. Separately, move the stop check before OOO and connect it to suppression.
3. **MED: the client details don't match across weeks.** wk 01 says "a founder at an SMB Acquisition firm, 15–20 a day" (the card says 12, per the brief). wk 02 says "a US outbound consultancy" and "continues in the same context". *Fix:* use one description in the wk 02 copy (the copy is the operator's to change).
4. **MED-LOW: "0.99" reads like a measured confidence.** It is a constant set in the code. `hot · 0.90` only comes back in dry-run; in live mode it goes to the unimplemented path. *Fix:* label the cards "rule match" or "fixed in code". The verbatim code can keep 0.99.
5. **LOW: publishing the volume.** 800 a day over 32 inboxes is about 25 per inbox. That's legal under CAN-SPAM if every email has an opt-out (honoured within 10 business days), a postal address and honest headers. Google/Yahoo require spam below 0.3% for every sender, and one-click unsubscribe above 5k a day per domain. Some readers will see inbox rotation as a way around filters. *Fix:* make no compliance claims.
6. **LOW: AI labelling.** Article 50's obligations on deployers cover deepfakes and AI-written text on public-interest matters. Neither applies here. CREDITS is accurate: only CC0, OFL and MIT material, with no CC BY that would need attribution. *Optional:* make the end card read "Made in code with an AI coding agent" to match CREDITS and the MP4 metadata.

## Honest gaps

- I didn't open the wk 01 card, so "12 a day" comes from the brief.
- I can't check anything about the client's system: its CRM, routing, unsubscribe handling or where its recipients are.
- I didn't check the GDPR/PECR exposure for EU recipients.
