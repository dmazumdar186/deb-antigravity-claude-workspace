# Lens 6: Nick Saraev (automation maturity and boundaries)

**Verdict: NOT CLEAR.** The boundary is right; two cheap human gates are still open.

**Rungs.** Triage code: scaffold, dry-run only (live path raises `NotImplementedError`, `reply_classifier.py` 145-151). Film pipeline: agent-built, human-approved (51 s build, 31 min end to end). That's the right rung. Production isn't the bottleneck; operator review is.

## Findings (severity-ranked)

1. **HIGH: posting gates open.** BUILD_LOG ends "Operator watch: _pending_" and FACTS.md has no `Signed off:` line. Fix: sign FACTS (and correct F21 to 99-107), watch muted and with sound on mobile, then post by hand. Keep the fact sheet, the final watch and the posting human. Don't schedule an auto-post.
2. **HIGH (system): opt-outs can be lost or invented.** OOO is checked before stop (`classify`, 99-117), so "Away until Monday, please remove me" returns `auto_reply_or_OOO`. Patterns also run on the whole body, quoted thread included, and directive l.243 puts an unsubscribe link in every footer. So a quoted "Can we jump on a call?" can come back `negative`. Fix: strip quoted text, check stop first, add tests for both cases.
3. **MEDIUM: "stop → suppression" is a doc claim, not code.** `classify` returns a label and nothing calls `suppression_writer`. `webhook_receiver.py` doesn't exist. `negative` lumps a legal opt-out with "not interested". Fix: a separate `opt_out` class that writes suppression and is tested end to end.
4. **MEDIUM: rule-caught replies never meet a human.** There's no misclassification sample, and no error channel for classifier exceptions (rule: `service / environment / error / count`). Fix: a weekly human review of 10 auto-handled replies, plus exceptions routed to Telegram.
5. **MEDIUM: boundary breach in the directive.** l.75 auto-sends a Cal.com link to positive replies "with 2-7 min human-timing delay", which is the "book yourself" pattern `automation-boundaries.md` forbids. Fix: hot and positive replies get a human reply within an SLA (l.74 has 3 min to ping; add a reply-by time).
6. **LOW: provenance.** The film labels the code `self_outbound_system/…` (Debanjan's own dry-run build) while the post describes the client's system. Fix: be ready to say "same rule, from my own build".

## Honest gaps

I didn't see the client's code, so I can't verify their CRM update, routing or SLA. I didn't watch the film. The film-vs-card lift is unmeasured, so compare wk02 against wk01 engagement before templating weekly films.
