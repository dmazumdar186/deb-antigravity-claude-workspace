# LinkedIn Weekly Cards — ProdCraft 50-week series

Scripts: `execution/content/linkedin_weekly_cards.py` (render) + `execution/content/linkedin_weekly_validate.py` (gate).
Spec: `docs/reference/prodcraft_linkedin_50_week_messaging_pack_2026-10-25.md` (sections 3, 4, 5, 7). Supersedes `linkedin_banners.md` for new posts.

## Goal

One 1080x1350 feed card per week: headline + one supporting line + at most one diagram. Small text wordmark, no QR, no link footer, no batch counter. Earn attention; ask for a call on 4-6 weeks only. Never publish automatically.

## Inputs

- `execution/content/prodcraft_50_week_messages.json` — source of truth, copy verbatim from the pack. `fallback_supporting_line` only on weeks with a numeric claim (W15, W25).
- `execution/content/prodcraft_claim_registry.json` — every numeric/contractual claim: status, source, date range, denominator, definition, attribution, disclosure permission, approved wording, `match` patterns.
- Fonts: `.tmp/banners/fonts/fonts_local.css` (Newsreader, Geist, JetBrains Mono, Caveat; `url(` rewritten to `file://`). Missing fonts print a loud WARN and the run reports `fonts_loaded` in `manifest.json` from `document.fonts` — anything short of all four means the cards are in fallback faces; do not ship them.
- Logo: `execution/content/assets/prodcraft_logo_ink.png` (flat ink silhouette of the operator's mark; `_brass.png` and the colour original `prodcraft_logo.png` also available via `--logo-style`), embedded as a data URI at 40px tall next to the Newsreader wordmark. Never stretched. (The prodcraft.fyi logo URL 404s; nothing is fetched.)

## Run

```
python3 execution/content/linkedin_weekly_cards.py            # all 50 -> deliverables/linkedin_weekly_cards/prodcraft/<date>/
python3 execution/content/linkedin_weekly_cards.py --weeks 1-10 --out deliverables/linkedin_weekly_cards/prodcraft/2026-10-25   # batch 1; ranges and lists accepted
python3 execution/content/linkedin_weekly_validate.py [--out <dir>] [--weeks 1-10] [--scores manual.json] [--no-jev]
```

## Outputs (`deliverables/linkedin_weekly_cards/prodcraft/<date>/`)

`png/NN_week_slug.png`, `html/`, `messages.json` (rendered copy + layout for all 50, so a `--weeks` subset never shifts the family assignment), `captions.md` (angle, CTA, link only for offer/demo weeks, guardrail), `proof_checklist.md`, `contact_sheet.png`, `manifest.json`, `index.html` (review contact sheet: 540px cards, week/theme/family, per-PNG download, zip link, no trackers), `prodcraft_weekly_cards_<batchN>.zip` (PNGs only), `validation_report.md|json`.

Design system (2026-10-25, rev 2 after the three-reviewer pass on W01-10): paper `#f3f1ec` with a faint SVG grain, ink `#17191d`, 96px margins. **Vertical grid (every card):** lockup at y=96 (flat ink mark 40px tall, 12px gap, "ProdCraft" Newsreader 500 26px, mark bottom at the wordmark baseline −2px; "wk NN" JetBrains Mono 15px +0.08em right, same baseline); kicker = theme name, mono 15px uppercase, at y=232; headline block bottom-anchored at y=712 (so 2-, 3- and 4-line headlines share rhythm; block top never above y≈440), Newsreader 500, 84px for 2 lines / 76px for 3 / 68px for 4 (fitted in-page), leading 1.05, −0.018em, `&nbsp;` before the last word (no widows), non-breaking hyphens, word-joiner after em dashes; content zone y=720-1120 (32px air at the top) for the supporting line (Geist 400 36px, 640px measure) + one visual; footer rule 1px at 25% ink at y=1210 with the series label "ProdCraft · weekly notes" (CTA text instead on offer weeks; prodcraft.fyi never appears on non-offer weeks) left and the week numeral right. **Diagram grammar:** all strokes 1.5px ink, nodes 10px circles, rules 1px 25% ink, no arrowheads, no shadows, boxes sized to content +48px padding with left edges aligned to the margin or to each other, lists use mono numerals 01/02/03 (fixed labels, not gated) on 1px rules, generic checklists 36px squares 1.5px stroke. **Brass is exactly one terminal element per card:** the last chain node, the brass strip box, the founder signature, or (when the visual has none) the footer numeral. **Visuals add information, never repeat the headline, never invent:** words come only from `supporting_line` + `companion_post`; weeks 01-10 are hand-specified in `custom_visual()` and every word drawn on the diagram is written to `messages.json` as `visual_words`, which the validator gates like copy. founder_note signs "— Debanjan, ProdCraft" in Newsreader Italic 30px brass; Caveat/handwriting is retired. Logo: `--logo-style ink|brass|color` (default ink) picks `prodcraft_logo_ink.png` / `_brass.png` (derived in PIL from the original raster by luminance+saturation mask — the source has an opaque grey background, so alpha alone is useless — cropped to bbox, 4% pad) or the colour raster; `--logo <png>` overrides and must be a real PNG (magic bytes) else WARN + wordmark only.

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
- (2026-10-25 audit) Claim gate is exact, not substring: a token passes only if its normalised form (strip `$ , + − - %` and spaces, lowercase) equals the numeric core of an approved match phrase for that week AND the full phrase is in the text. Word numbers (one..ninety, dozen, hundred, thousand, million, billion, double, triple, half, quarter) and `²³¹¼½¾` are numeric tokens too; idiomatic counts in pack copy ("one real case", "three tabs") are registry entries of `type: rhetoric` (`wNN_word_count_idiom`).
- Gated fields = everything that reaches the image: headline, rendered supporting line, theme, CTA text (`30-minute` is a registry match), receipt row values. Fixed template labels (`note 01`, `wk 15`) are not gated.
- NUM_RE pitfalls: a trailing "." was eaten ("15."), and the `m` suffix ate "01 May" -> "01 M"; suffixes now need a non-letter after them.
- Unapproved claim + no `fallback_supporting_line` (or unapproved number in the headline) -> no card; messages.json gets a `verdict: blocked` row and the validator FAILs it.
- case_receipt with fallback renders `RECEIPT_FALLBACK` rows (pack's own words, W15 reply routing/lead ownership/follow-up, W25 checkout/payment edge cases/onboarding); "evidence: non-numeric" lives only in manifest `non_numeric_receipts`. New case_receipt numeric weeks need a RECEIPT_FALLBACK entry.
- No backslashes inside f-string `{}` (SyntaxError on cloud Python 3.11); `NBH` is module-level.
- `--weeks` subset: unrendered html is skipped with a note, not an overflow FAIL. Headlines > 140 chars WARN. `--weeks` rejects `10-1`, `a-b`, `0`, `51` (argparse error) and exits 2 if a requested week is not in the messages file; stale png/html from weeks outside the run are deleted so zip, contact sheet (5 columns for ≤10 cards) and manifest `count` describe only this run.
- Overflow gotcha: a flex child with `flex-shrink` inside the fixed content zone reports `scrollHeight > clientHeight` and FAILs the validator even when the pixels look fine; `.vis` is `flex:0 0 auto`.
