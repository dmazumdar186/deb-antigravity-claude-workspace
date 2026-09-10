# Fuzzy variables — two personalization slots

Used by: `outreach/draft_email.py`. Model: `claude-sonnet-5`, `temperature=0`.
Methodology: `directives/personalization/fuzzy_variables.md`. Slots are woven into the human-written templates
in `email_touch_1_{a,b,c}.md`, `email_touch_2.md`, `email_touch_3.md`. Read every row; never sample; vary
wording row-to-row even when source data repeats (see distinctness rule below).

## Inputs

- `{{gaps_json}}` — ordered list of `human_phrase` strings from `audit/scoring.py`'s `gaps` array (highest
  points first), e.g. `["clients can't book without calling", "the site doesn't work well on a phone"]`.
- `{{booking_widget}}` — detected booking widget name, or `null`/empty if none found.
- `{{has_cta_above_fold}}` — boolean.
- `{{psi_mobile}}` — PageSpeed Insights mobile performance score, 0–100, or `null`.
- `{{is_mobile_friendly}}` — boolean.
- `{{business_name}}` — plain text.
- `{{services_json}}` — the `services[]` array produced by `extract_services.md` (list of `{name, blurb, icon}`).
- `{{suburb}}` — the business's suburb/city, plain text.

## Output — strict JSON only

Return **only** a single JSON object. No prose, no markdown code fences, no explanation before or after.

```json
{
  "oneSentenceSpecificBookingGapObservedOnTheirSite": "...",
  "fiveWordPlainDescriptionOfTheirBusiness": "..."
}
```

### `oneSentenceSpecificBookingGapObservedOnTheirSite`

- **14 words or fewer.** Present tense. One sentence, no trailing period-then-more.
- Built from `{{gaps_json}}` (use the top 1–2 entries), `{{booking_widget}}`, `{{has_cta_above_fold}}`,
  `{{psi_mobile}}`, `{{is_mobile_friendly}}` — describe what a *visitor trying to book* actually experiences,
  never a comment on visual design.
- Topic is **always lost/blocked bookings** — never site appearance, never "outdated", never a quality
  judgment. Good: `"visitors can't book online after hours and have to call during business hours"`. Bad:
  `"the site looks outdated and needs a redesign"`.
- **Forbidden words** (case-insensitive, anywhere in this value): `outdated`, `bad`, `ugly`, `unprofessional`,
  `old`.

### `fiveWordPlainDescriptionOfTheirBusiness`

- **6 words or fewer**, lowercase, plain factual description built from `{{business_name}}`,
  `{{services_json}}`, `{{suburb}}` — e.g. `"med spa in winnetka offering botox"`.
- No adjectives that editorialize quality or status: forbidden words include `premier`, `best`, `top`,
  `leading`, `luxury`, `boutique` (as a puffery adjective), `#1`.

### Distinctness

If this call is generating for a batch, or is re-run for the same business across touches, vary sentence
structure and word choice — do not reuse the same clause shape or lookup phrase every time. Never output a
placeholder, an empty string, or a value that merely repeats an input field verbatim without turning it into a
natural sentence.

Business: {{business_name}}, {{suburb}}
Booking widget: {{booking_widget}} | Above-fold CTA: {{has_cta_above_fold}} | PSI mobile: {{psi_mobile}} |
Mobile-friendly: {{is_mobile_friendly}}

Gaps (ordered, highest points first):
{{gaps_json}}

Services:
{{services_json}}
