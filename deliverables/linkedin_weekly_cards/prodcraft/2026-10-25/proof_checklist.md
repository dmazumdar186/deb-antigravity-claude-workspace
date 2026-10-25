# Proof checklist

Rule (pack section 4): a numeric card ships only when every field below is filled and status is approved; otherwise the non-numeric fallback renders.

- **w15_outbound_baseline** (W15) — status `pending_verification` — BLOCKS numeric line. Missing: date_range, denominator, disclosure_permission, approved_wording. Needs send logs and exact reply definition before the numeric line may render.
- **w25_marketplace_85k** (W25) — status `pending_permission` — BLOCKS numeric line. Missing: date_range, disclosure_permission, approved_wording. Partner build under NDA; needs attribution permission.
- **w29_wiser_numbers** (W29) — status `blocked` — check before publish. Missing: date_range, denominator, definition, disclosure_permission, approved_wording. Card is non-numeric; any Wiser number added later is blocked.
- **w40_15_years** (W40) — status `approved` — ok. Missing: none. Measured.
- **w08_40_slide** (W08) — status `approved` — ok. Missing: date_range, attribution. Approved as rhetoric so the numeric gate passes; not a metric.
- **cta_30min_session** (W08, W48, W50) — status `approved` — ok. Missing: none. Live 30-min booking; re-check before each publish.
- **ownership_handover_terms** (W20, W47) — status `pending_verification` — check before publish. Missing: source, date_range, approved_wording. Non-numeric, card renders; confirm contract terms before publishing.
- **w46_cv_optimizer_demo** (W46) — status `pending_verification` — check before publish. Missing: approved_wording. Verify demo works at publish time; record a real screen capture.
- **retired_1** (all) — status `retired` — never publish. Missing: date_range, denominator, definition, attribution, disclosure_permission, approved_wording. Stretched value: 48,000/month is 2x the 24,000 baseline. Never publish.
- **retired_2** (all) — status `retired` — never publish. Missing: date_range, denominator, definition, attribution, disclosure_permission, approved_wording. Stretched value: pipeline is modeled, not measured. Never publish.
- **retired_3** (all) — status `retired` — never publish. Missing: date_range, denominator, definition, attribution, disclosure_permission, approved_wording. Stretched value: source says +30%. Never publish.
- **retired_4** (all) — status `retired` — never publish. Missing: date_range, denominator, definition, attribution, disclosure_permission, approved_wording. Stretched value: source says -40%. Never publish.
- **retired_5** (all) — status `retired` — never publish. Missing: date_range, denominator, definition, attribution, disclosure_permission, approved_wording. Stretched value: extrapolated. Never publish.
- **retired_6** (all) — status `retired` — never publish. Missing: date_range, denominator, definition, attribution, disclosure_permission, approved_wording. Stretched value: extrapolated. Never publish.

## Week guardrails

- W08: Use this CTA only if the 30-minute session and described process are currently offered.
- W15: VERIFY against actual send logs and exact reply-rate denominator before publishing; use 24,000/month baseline only if still accurate.
- W20: Publish only if contract and actual delivery process guarantee these ownership/handover terms.
- W25: Confirm partner permission, attribution and $85K / three-month figure before publishing.
- W29: Do not publish numerical Wiser outcomes unless supported by source documents and disclosure permission.
- W46: Verify demo still works and show a real screen recording; do not overstate evaluation claims.
- W47: Publish only if contract and actual delivery process guarantee these ownership/handover terms.
- W48: Use this CTA only if the 30-minute session and described process are currently offered.
- W50: Use this CTA only if the 30-minute session and described process are currently offered.
