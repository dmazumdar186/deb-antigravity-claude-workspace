# Lens 9: Mira Murati (product and UX): phone feed, muted, at scroll speed

**Verdict: NOT CLEAR.** One fix blocks posting (S1). The rest are cheap.

## Findings (most severe first)

**S1: nothing moves for the first 2.4 s.** I diffed the frames. From frame 0 to frame 72, no pixel changes by more than 8/255, which is encoder noise. The first visible motion is at frame 73 (2.43 s), when the envelopes fly. In autoplay the film looks the same as a static card, so most people will scroll past before anything happens. *Fix:* keep frame 0 as it is (it is the poster and the loop seam) and start small motion by about 0.3 s. For example, one tile turns gold and a reply count starts ticking.

**S2: the result tags are too small.** I measured them in the 12 s frame. Tags such as `auto_reply_or_OOO · 0.99 · €0.00 · no model called` have about 15 px of ink in the 1080 px frame. On a 390 pt wide screen that is about 7 pt. The "illustrative replies" label is about 5 pt. Code lines and reply text come out at about 10 pt, which is readable but tight. The tags carry the main point of the post, and they are the smallest text on screen. *Fix:* make tags at least 30 px and the label at least 24 px, or cut the tag to `OOO · €0.00`.

**S3: the payoff comes late.** "30–60" appears at 18.1 s. 27.7 s is a reasonable length for LinkedIn, but people who leave in the first 10 s never see the reframe. Muted viewers can follow the sort itself through the gold bars and card order. *Fix (needs the operator's agreement):* none required. Just note the trade-off.

**S4: the source bitrate is low.** The video stream is 489 kb/s at CRF 18 (671 kb/s for the whole file). Flat cream shows little banding risk, but small mono type will soften after LinkedIn re-encodes it. *Fix:* re-export at CRF 12 with `-maxrate 8M -bufsize 16M`, `-tune animation`, and yuv420p. That should land at roughly 3–6 MB.

**S5: thumbnail and crop.** Frame 0 makes a clean cover. It matches the card's header, headline and footer, but its body is the envelope grid, not the card's code panel. *Fix:* upload `poster.png` as the custom thumbnail. 4:5 is supported in the mobile feed.

**Series continuity: holds.** The cream background, serif headline, `wk 0N` mark and mono footer all match wk 01 and wk 02.

## Alt text

Silent animation on a cream background. Headline: "32 inboxes, 800 sends. Who replied?" 32 envelope icons scatter into seven example replies, including an out-of-office, an unsubscribe and a request for a call. Code from reply_classifier.py appears. Out-of-office replies are tagged "auto_reply_or_OOO, 0.99, €0.00, no model called", the unsubscribe is tagged negative, and the call request is tagged hot. The remaining replies are marked "CRM updated". Closing text: "The target was never 800 sends a day for its own sake. It was 30–60 positive conversations a month, with booked calls tracked in the CRM."

## Honest gaps

I have not checked LinkedIn's current transcode ladder, its desktop crop, or whether native video takes alt text. If it does not, put this text in the first comment. I did not view the film on a real phone, and the pt sizes are estimates from scaling.
