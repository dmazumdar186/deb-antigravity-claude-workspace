# Lens 5: Hormozi (offer and unit economics)

**Verdict: NOT CLEAR.** The proof is strong: their own file, 2 → 26 → 49 → 6, and a user verbatim. But the film never names the dream outcome, gives no risk reversal, and ends on a product name instead of the ask.

## Findings

**HIGH: the dream outcome is missing and the ending is a name.** The closest line is "Get a segment you can trust" (F19). Slide 8's thesis, "not building the list. It is believing it", never appears. The film closes on "Trusted Segments" (SCRIPT 01:11.67–01:16.25). *Fix:* add slide 8's line to FACTS as F24. Use it in place of the bare title card: "The problem isn't building the list. It's believing it." Then a 2 s hand-off: "Here's the quarter that fixes it."

**HIGH: 76 s is too long, which hurts the time-delay term.** Our own teardown says 30–40 s, and warns that anything over 45 s before the substance reads as a gimmick (LEMO_TEARDOWN §9a). *Fix:* cut L03–L05 (the 525/8/25 setup is on slide 3 anyway) and shorten L12. Aim for about 45 s. The `--q` re-render plus mux takes about 5 min, not a re-author.

**MED: the upside is buried.** "6 can be e-mailed today" lands as a loss (6 of 49). The 43 "to reactivate" are where the money is (slide 7: the reactivation loop is the only priced part, tied to dues). *Fix:* one line: "43 to win back." Then the ask has a value lever.

**MED: no risk reversal.** The stop criteria (week 12: under 30 % use; week 17: under 10 % come back) are on slide 7 only. That's fine for an opener, but the film must not overclaim. *Fix:* keep the claims as they are. Make slide 8 repeat "two kill switches" next to the ask.

**LOW: cost per film isn't fully measured.** We have 49 min 11 s of agent wall-clock (BUILD_LOG). Tokens and human review time are not logged. A variant costs render 124 s + mux 107 s + encode 70 s + checks about 88 s, so roughly 6.5 min. A static image takes minutes; a Loom takes about 10 min of a human. *Fix:* log tokens and human review minutes on the next film.

## Unit economics

A film pays off as a **template × a small number of high-value accounts**. It doesn't pay off at volume. Per-prospect variants lose to a Loom.

Per-school explainer as a customer-success asset: the expensive part is running the 2/26/49/6 analysis on the school's own file. The film is close to free on top of that.

My pricing assumption (no price data in this folder): free for the 10 pilot tenants, because it is their proof. After that, bundle it into a paid data-health audit rather than selling the film alone.

## Three offers

1. **Candidate ABM, "Your list, 45 s".** For the top 10–20 targets, a film built on their public data, sent as a poster/GIF link (Instantly can't embed video).
   - Dream outcome: they see their problem quantified.
   - Proof: their own numbers.
   - Metric: replies compared with a text-only control.
   - Kill criterion: stop if after 20 sends replies are under 2× the control, or human time is over 30 min per account.
2. **AlumnForce QBR, "Your segment health".** A per-school variant showing their file's naive count vs the trusted count.
   - Dream outcome: the board believes the list.
   - Proof: their file.
   - Metric: the film is forwarded to leadership, and the pilot converts.
   - Kill criterion: stop if under 3 of 10 pilot tenants forward it, or on one fact-check failure.
3. **School "Confirm / Correct" campaign.** Mid-century Cartoon in the school's house style, linked from the F20 prompt.
   - Dream outcome: profiles fresh before the dues drive.
   - Proof: "last updated 4 years ago".
   - Metric: confirm/correct rate vs a static email.
   - Kill criterion: stop if lift is under 10 %, the same bar as week 17.

## What NOT to do

- No per-recipient personalisation at volume.
- No paid-ad volume (`ad-creative` is the volume tool; one hero ad per angle at most).
- No embedding in cold email.
- No real alumni faces or school logos without written rights.
- No AI-made ad claims without disclosure.
- No fundraising figures outside a FACTS file.

## Honest gaps

- Token cost per film is unknown. Human review minutes were not logged.
- The `--q` variant path is untested here.
- There are no reply-rate or open-rate baselines for video vs static in the candidate's outbound or schools' campaigns.
- Pricing is my assumption.
- I didn't watch the MP4. This review is from the script and timings only.
