# LinkedIn scroll-stop — panel lenses 1, 5, 6, 9 (2026-10-25)

Inputs: `docs/reference/linkedin_scroll_stop_evidence_2026-10-25.md` (dossier), `execution/content/prodcraft_50_week_messages.json` W01–W10, cards `deliverables/linkedin_weekly_cards/prodcraft/2026-10-25/png/04,08,10`, Jev headline scores (stop 2.07–2.75 / 4; self-relevance 0.19–0.46; generic 0.60–0.78 for 9 of 10, W08 0.25).

Operator's challenge: a founder/CSO on the commute sees ~50 items; why stop on a cream typographic card, follow a hashtag, open the profile, read the ProdCraft page, and book?

Card observation (all three PNGs): the top ~32% of the 1080×1350 canvas holds only the logo and "wk NN"; the headline starts at roughly y=470–550. On a phone feed the first visible band is empty paper. No number, no face, no named role.

---

## Lens 1 — Karpathy (measurement)

The operator is right that nothing here is a guarantee, and the dossier says why: no study isolates typographic cards vs photos on LinkedIn, no consultant funnel (impressions → profile → call) is published, and the profile-visit (ConnectSafely 1–3%) and booking (Bullock 0.5–2%) rates are low-confidence practitioner ranges. Multiply them at AuthoredUp's median 1,006 impressions/post and you get 0.05–0.6 conversations per post, i.e. one per several thousand impressions. Ten weeks of single images is therefore a sample of ~0–6 calls — unmeasurable. Against the operator's plan: hashtags are the one lever with measured data, and it is zero to negative (AuthoredUp 621k posts: no impact, >6 hurts; LinkedIn's Jobanputra: feed "not really used"). Against our cards: the only measured image signal is portrait > square (+11%, AuthoredUp 368k), and Growtempo flags text-as-image as the weakest class; Jev's 0.60–0.78 "generic" matches LinkedIn's 94%-precision generic-content classifier risk. What falsifies anything is tracked dwell/profile views per post, not opinion.

Honest gaps: no Jev calibration against real LinkedIn outcomes; medians are cross-account, not this account; no 4:5-card-vs-carousel A/B exists.

## Lens 5 — Hormozi (offer & unit economics)

Value = dream outcome × likelihood ÷ (delay × effort). Nine of ten headlines state a principle, not an outcome; none name a buyer, a number, or a risk reversal. Only W08 ("Bring one repetitive task") is an offer, and Jev agrees (generic 0.25). The buyer evidence rewards specificity: Edelman-LinkedIn 2024 (n=3,484) says 73% trust thought leadership over marketing material, 60% pay a premium, 70% of C-suite questioned a supplier because of it — but the 2025 edition adds 86% want content that challenges assumptions and 57% want quick takeaways. "A roadmap item is not a business outcome" challenges nothing a director doesn't already nod at. Against the operator's plan: the 95:5 rule (Dawes/LinkedIn B2B Institute) means ~95% of viewers cannot book this quarter whatever the card says; a call-booking funnel from cold impressions is the wrong unit; the economic job is to be the remembered name when the 5% turns over. Against our cards: no proof element (a before/after count, a cost, a failure rate), so "perceived likelihood" is zero on the image.

Honest gaps: no ProdCraft pricing/LTV in evidence; no measured close rate from any channel; Edelman samples are enterprise-weighted, not EU SMB.

## Lens 6 — Saraev (automation maturity)

We automated the wrong rung. Fifty weekly cards were generated before a single manual card proved it could earn a profile visit — the opposite of "start at the end". The bottleneck per the dossier is not production volume but dwell and reach: LinkedIn ranks on a normalised long-dwell classifier (Engineering, Oct 2024) and demotes "repetitive, low-substance" posts (newsroom, Mar 2026); a 50-card series with identical layout, no number and no voice is exactly the repetitive shape the 94%-precision classifier was trained on. Format data points the other way: documents 7.00% vs single image 5.30% ER (Socialinsider 2.45M posts), carousels 1,451 vs image ~600 impressions (Metricool 673k), reach 1.45x vs 1.18x (AuthoredUp 995k). Cadence evidence (Buffer 2M posts: the big step is 1 → 2–5/week; AuthoredUp medians fall at 8+) says a weekly card alone under-posts. Against the operator's plan: "hashtags bring traffic" is an unmeasured assumption inside the pipeline. Fix: ship 4 hand-made posts, measure, then template only the winner.

Honest gaps: no evidence the operator's cadence or series format has been penalised yet; classifier behaviour on branded typographic series is undocumented.

## Lens 9 — Murati (product/UX on the phone)

What the CSO sees at 23:00: 72% of activity is mobile (van der Blom 1.8M posts), the image is cropped in the feed, and NN/g's F-pattern says the eye lands on the top-left band first — which on our cards is blank cream and a small logo. By Nielsen's 20–28% reading share, a 3-line serif headline plus four boxes is read as "ProdCraft … workflow … CRM" and skipped. The eye-tracking rows (faces drew gaze before text; 91.7% of face ads outperformed; author photos up to +50%, all low confidence) all point the same way: a face stops, type explains. Jev's self-relevance 0.19–0.46 confirms the headlines are about workflows in general, not "my" pipeline. Against the operator's plan: a profile → ProdCraft page → call path has three taps and a link penalty of −16 to −27% wherever the link sits (MagicPost 567k; Metricool); the card never shows what happens on the call. Against our cards: nothing tells the reader who it is for, and W08's "more in the post" asks for a tap the format gives no reason to make.

Honest gaps: no LinkedIn-specific legibility test for 1080×1350; face evidence is ads/branding pages, not organic B2B feeds; no thumb-test on a real phone done.

---

## Quantitative redesign spec (12 lines)

1. Format: default to document carousel (Socialinsider 7.00% vs 5.30%; Metricool 1,451 vs ~600 impr; AuthoredUp 1.45x vs 1.18x); keep single 4:5 image only for weeks where the message is one number. Mixed: 3 carousels + 1 image per 4 posts [judgement on the ratio].
2. Top 20% of the image (feed crop, F-pattern) carries the hook: a role word + a number ("CSO: 3 of 5 AI pilots stall on handoffs"). First 3 words name the reader or the number; the logo moves to the footer.
3. Face: include the founder photo on slide 1 / the single card (eye-tracking + Van der Blom +50%, low confidence) — the cheapest test with the largest claimed effect; rotate 2 face / 2 no-face in the first 4 weeks to measure.
4. Text density ceiling: ≤12 words on the first frame, ≤30 per inner slide (Nielsen 20–28% read share; no LinkedIn limit exists, so this is a cap to test, not a finding) [judgement].
5. Every image carries one datum (count, before/after, cost); no quote-only cards (Growtempo).
6. Caption 800–1,000 characters, written in first person about one real case (AuthoredUp 1.04x; Edelman 65% prefer human tone; LinkedIn "own voice" rule). Caption, not image, carries the keywords.
7. Hashtags: 0–3 topic-exact, never traffic (AuthoredUp zero/negative; LinkedIn hashtag feed phased out). Delete "hashtags bring traffic" from the plan.
8. Links: none in body or first comment (MagicPost −16 to −21%; Metricool −27%). Profile headline + Featured section is the only link; ProdCraft URL goes there.
9. Closing: a genuine question (−4%) never "comment X" (−52%, MagicPost 684k). No pods.
10. Cadence: 2–3 posts/week, max 1/day (Buffer; AuthoredUp; Van der Blom Oct 2025), plus 8–12 real comments/day on target-ICP posts (Van der Blom, low-med).
11. Track per post at 72h: impressions, ER, saves, profile views (LinkedIn analytics), DMs, calls booked; log format, face/no-face, number/no-number, first-3-words. After 4 weeks (8–12 posts): continue a variant only if median impressions ≥1,006 and profile views/impressions ≥1% (ConnectSafely low bound); drop any variant below 0.5%.
12. Falsifiable prediction: carousels with a face + number on frame 1 beat the current typographic cards by ≥30% median impressions and ≥2x profile views per 1k impressions within 4 weeks; if they do not, the format is not the bottleneck and the offer (W08-type) is the next variable [judgement on the thresholds; direction from Socialinsider/AuthoredUp/Metricool].
