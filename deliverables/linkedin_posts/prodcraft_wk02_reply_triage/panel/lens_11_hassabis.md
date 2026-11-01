# Lens 11: Hassabis (systems, long horizon). Does the loop compound?

**Verdict: NOT CLEAR.** wk 02 is sound for one film. The series does not compound yet: it has no loop that turns results into data, no reusable parts, and a moat that is narrower than it claims.

## Findings (severity-ranked)

1. **HIGH: no feedback loop.** No script logs per-post LinkedIn analytics (grep of `execution/` finds none). `jev_comment_buyers.py` maps only TikTok, Instagram and YouTube Apify items (l.127), so LinkedIn comments can only come in through `--input` CSV. **Fix:** keep a `post_ledger.jsonl`, one row per week: impressions, comments, DMs, and Jev buyer tags from the CSV. Rule: the next topic is the pipeline stage that drew the most buyer-intent comments and DMs. Impressions don't decide it.
2. **HIGH: "numbers checked" mostly means consistent with FACTS, not proven by code.** On-screen numbers pass 11/11 (EVAL_REPORT), but 32, 800, 24,000 and 30–60 are operator rows. Only 0.99 and 0.0 come from code. The code shown is the `self_outbound_system` scaffold, not the client's system, and its model path raises `NotImplementedError` (l.143–151). **Fix:** label it "my reference build". Every film carries at least one number that comes from code.
3. **MED: nothing is reusable.** The chrome (l.74), envelope (l.97), code panel (l.135), sort-lane ledger (l.168) and credits (l.289) are all written inline in a 339-line `film.js`. **Fix:** move them into `prodcraft-notes/` as modules. Each week then writes only `timeline.js` and FACTS.
4. **MED: the trap is reading as an AI-video account.** **Fix:** alternate card weeks and film weeks. Use film only where a real process moves. Never post a film about the films. Keep his own voice in the copy and the credit line small.

## Arc, wk 03–06 (each fact comes from code)

wk 01 asked "What if something went wrong?" That question is wk 03.

| wk | Topic | Fact source |
|---|---|---|
| 03 | Guardrails | `acceptance.py` l.218–220: bounce <5%, unsub <0.3%, complaints = 0; killswitch never auto-resumes; canary checks inbox placement |
| 04 | Targeting | `icp_filter.py` plus a frozen corpus: 20 bad must reject, 12 good must pass, an independent oracle |
| 05 | Opt-outs | `suppression_writer.py`: idempotent, lock file, GDPR |
| 06 | Reading the comments | Jev typed decision per comment, aggregate counts only |

## Honest gaps

I saw no analytics for wk 01. The client's code is not in the repo. Token cost per film was never logged (CAMPAIGNS.md). I did not check the wk 03–06 thresholds against live runs.
