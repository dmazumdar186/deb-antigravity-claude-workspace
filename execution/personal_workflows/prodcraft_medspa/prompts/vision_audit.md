# Vision audit — "dated design" scoring

Used by: `audit/vision.py` (step 5.1.8 of `PROJECT_SPEC.md`). Model: `claude-fable-5-1`, `temperature=0`.
Feeds `audit/scoring.py` signal `dated_design` (15 pts, fail if `vision_dated_score >= 7`).

## Inputs

- Two images, attached to this call: (1) mobile full-page screenshot, (2) desktop hero screenshot (first
  viewport only), both of the business's live current website.
- `{{business_name}}` — the business's name, plain text.
- `{{final_url}}` — the resolved URL the screenshots were taken from (after redirects).

## Instructions

You are scoring **only** how dated the design is against the fixed anchor scale below. You are not rating taste,
not rating the business, not rating photo quality beyond what the anchors name. Judge the two images as given;
do not infer content that isn't visible. Do not use aesthetic-preference words ("ugly", "unprofessional",
"tacky", "outdated", "bad", "old") anywhere in your output — describe only the concrete visual signals listed
in the anchors below. Be deterministic: two runs on the same pair of images must land on the same score and
same signal list.

### 0–10 anchor scale (score the WORSE of the two images if they disagree by more than 1 point)

- **0–2 — modern**: generous whitespace, large legible type (headings clearly >24px equivalent), real
  photography (not stock clip-art or illustration-only), a sticky or persistently-visible booking CTA, clean
  grid layout, no visual clutter above the fold.
- **3–4 — mostly modern**: modern layout overall with one or two minor dated elements (e.g. a slightly small
  type scale, or a static rather than sticky CTA), but still whitespace-driven and photo-led.
- **5–6 — mixed**: roughly even split of modern and dated signals — e.g. decent photography but a cluttered
  top nav, or clean type paired with a carousel hero.
- **7–8 — dated**: two or more of: cluttered/overcrowded navigation, small body type, stock clip-art or
  generic icon-only imagery in place of real photos, centered text blocks stacked vertically, visible
  gradients or button bevels/drop-shadows (2000s-era skeuomorphism), an auto-rotating image carousel as the
  hero, or a layout with no distinct mobile treatment (desktop layout simply shrunk).
- **9–10 — broken or abandoned**: layout visibly breaks (overlapping elements, text cut off, horizontal
  scroll on mobile), placeholder/lorem-ipsum content visible, broken images, or the page is clearly years
  stale (dead promotional banners, expired-looking content).

### Signals

List only the concrete anchor-scale items you actually observed (from the bullet lists above), each as a short
noun phrase (e.g. `"carousel hero"`, `"small body type"`, `"no mobile layout"`). Do not invent signals outside
those lists. Empty list is valid for scores 0–2.

## Output — strict JSON only

Return **only** a single JSON object. No prose, no markdown code fences, no explanation before or after.

```json
{"dated_score": 0, "rationale": "<one sentence, factual, no taste words>", "signals": ["..."]}
```

- `dated_score`: integer 0–10 per the anchor scale above.
- `rationale`: exactly one sentence, states which anchor band and why, using only the concrete signal
  vocabulary above (e.g. "Scores 8: cluttered nav, small type, and a carousel hero with no distinct mobile
  layout.").
- `signals`: array of strings, each a short noun phrase from the anchor bullets that applied; `[]` if none.

Business: {{business_name}} — {{final_url}}
