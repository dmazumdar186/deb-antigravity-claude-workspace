# LinkedIn Weekly Cards — ProdCraft 50-week series

Scripts: `execution/content/linkedin_weekly_cards.py` (render) + `execution/content/linkedin_weekly_validate.py` (gate).
Spec: `docs/reference/prodcraft_linkedin_50_week_messaging_pack_2026-10-25.md` (sections 3, 4, 5, 7). Supersedes `linkedin_banners.md` for new posts.

## Goal

One 1080x1350 feed card per week: headline + one supporting line + at most one diagram. Small text wordmark, no QR, no link footer, no batch counter. Earn attention; ask for a call on 4-6 weeks only. Never publish automatically.

## Inputs

- `execution/content/prodcraft_50_week_messages.json` — source of truth, copy verbatim from the pack. `fallback_supporting_line` only on weeks with a numeric claim (W15, W25).
- `execution/content/prodcraft_claim_registry.json` — every numeric/contractual claim: status, source, date range, denominator, definition, attribution, disclosure permission, approved wording, `match` patterns.
- Fonts: `.tmp/banners/fonts/fonts_local.css` if present, else system fallbacks (Charter/FreeSerif, Inter, JetBrains Mono).

## Run

```
python3 execution/content/linkedin_weekly_cards.py            # all 50 -> deliverables/linkedin_weekly_cards/prodcraft/<date>/
python3 execution/content/linkedin_weekly_cards.py --weeks 15,25
python3 execution/content/linkedin_weekly_validate.py [--out <dir>] [--scores manual.json] [--no-jev]
```

## Outputs (`deliverables/linkedin_weekly_cards/prodcraft/<date>/`)

`png/NN_week_slug.png`, `html/`, `messages.json` (rendered copy + layout), `captions.md` (angle, CTA, link only for offer/demo weeks, guardrail), `proof_checklist.md`, `contact_sheet.png` (10x5), `manifest.json`, `validation_report.md|json`.

## Claim governance (pack section 4)

- A digit, percent or currency in headline/supporting line must match an `approved` registry claim for that week; otherwise the renderer uses `fallback_supporting_line` and the validator FAILs any number left on the card.
- Retired stretched values (48k, $1M+, +45%, -55%, $10K/wk, 100+ hrs) always FAIL.
- A proof card ships only with source, date range, denominator, definition, attribution, disclosure permission and exact wording. Missing any field -> non-numeric card. Contract terms (W20, W47) and the live demo (W46) render but stay flagged in `proof_checklist.md` until confirmed.
- To approve a number: fill every field in the registry, set `status: approved`, re-render, re-validate.

## Layout families

`visual_direction` maps to: minimal_editorial, annotated_workflow (3-5 nodes from the supporting line, generic labels only), failure_checklist, before_after, code_to_outcome (dark, pseudo-code labelled illustrative), founder_note (only place for the handwritten mark; max 8), case_receipt (number only when approved), offer_card. A family never runs 3x in a row; the third is reassigned with a warning.

## Gate

PUBLISHABLE = claims pass + no overflow + Jev review >= 24/30 (six criteria x 0-5). Claims/overflow failures exit 1; score shortfalls are HOLD (copy is operator-owned). Jev failure -> `--scores` file or the week is `unscored`, never a silent pass.

## Edge cases

- prodcraft.fyi/logo.png returned 404 (2026-10-25): text wordmark used.
- Hyphenated numbers ("40-slide") broke across lines; headlines use non-breaking hyphens.
- Single-fragment supporting lines make thin diagrams: flows pad with generic "Input" / "Owner + next step", code blocks with generic step names.
- Rhetorical numbers ("40-slide", W08) need an approved registry entry or the numeric gate fails them.
- First run: Jev scored the bank median 19.3/30, 1 of 50 >= 24 (cost $0.0019). Jev is harsh on headline-only state; treat as a ranking, have the operator score manually before publish.
- Playwright `file://` URIs need absolute paths (`.resolve()`).
