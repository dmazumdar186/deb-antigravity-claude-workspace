# ProdCraft 0.5 preview — template

Next.js 15 App Router, Tailwind, static export. Renders one business's
"0.5 preview" site from a `business.json` file matching `business.schema.json`.
See `../CONTRACTS.md` for the binding contract and `../PROJECT_SPEC.md` §7 for
the (non-negotiable) content rules this template enforces at build time.

## How the Python builder calls this

`preview/build_preview.py` drives this template as a subprocess, roughly:

```bash
cd execution/personal_workflows/prodcraft_medspa/template
# 1. Write the business's data (overwrites any existing business.json)
python3 -c "import json,sys; json.dump(business_row, open('business.json','w'))"
# 2. Build the static export (validates + content-lints business.json, fails
#    the build loudly on any contract violation)
npm run build
# 3. Upload out/ to the R2 prefix for {slug}-{slug_suffix}
#    (build_preview.py owns the R2 upload step, not this package)
```

If no `business.json` is present, `npm run build` copies
`business.example.json` into place first (`scripts/ensure-business.mjs`) so
`npm run build` always works standalone for local dev / CI.

## Scripts

| Script | What it does |
|---|---|
| `npm run dev` | Local dev server (`next dev`) against whatever `business.json` is present. |
| `npm run build` | `ensure-business` → `gen-stock` (idempotent) → `next build` (static export to `out/`). |
| `npm test` | Vitest unit tests: validator, content linter, color contrast. |
| `npm run typecheck` | `tsc --noEmit`. |
| `npm run gen-stock` | Regenerates `public/stock/*` procedural imagery (pure Node, no deps). |
| `npm run lint` | `next lint`. |

## Data contract

- `business.schema.json` — JSON Schema (draft-07) description of the contract.
- `business.example.json` — synthetic fixture ("Glow Aesthetics") satisfying the schema.
- `lib/validate.ts` — hand-rolled validator (no ajv) run at build time in
  `lib/business.ts`, throwing a single clear error listing every missing/invalid
  field.
- `lib/lint.ts` — forbidden-term / `$`-price content linter, also run at build
  time. Fails the build if any rendered string trips it.
- `lib/color.ts` — derives `--brand-ink` (white or near-black) from
  `primary_color` via a real WCAG contrast check.

## Imagery

`public/stock/` is generated in-repo by `scripts/gen-stock.mjs` — abstract
procedural art (layered gradients + film grain + one geometric arc), not
downloaded or scraped photography. See `public/stock/LICENSE.md`.

## Non-negotiables baked into this template

- `output: 'export'`, `images.unoptimized: true`, `trailingSlash: true` (see `next.config.mjs`).
- `<meta name="robots" content="noindex,nofollow">` unconditionally, `public/robots.txt` disallow-all.
- No logo anywhere; business name renders in plain type only.
- Reviews: rating + count only, linking out to `google_maps_url`. Never review text.
- No prices, no outcome claims, no before/after language (enforced by `lib/lint.ts`).
- The watermark bar (`components/WatermarkBar.tsx`) renders on every page, fixed to
  the top, with the exact `preview.watermark` text, the expiry date, and a
  `data-remove-link` link to `preview.remove_url`.
- `#book` is a fully client-side demo (`components/BookingWidget.tsx`) — no
  network calls, no PII fields, and a disclaimer that appears on "Confirm".
- No external network requests at runtime (system font stack only, no Google Fonts).

## Acceptance

`tests/prodcraft_medspa/acceptance_template.py` (repo root) serves `out/` and
runs Playwright checks at 390×844 and 1440×900 — no horizontal overflow, a
`[data-cta="book"]` inside the first viewport, watermark + remove-link
present, `noindex`, zero console errors, < 1.5 MB transferred, every image has
`alt`/`width`/`height`, no forbidden terms in rendered text, `/expired/`
renders. Run it after `npm run build`:

```bash
pip install playwright
PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers python3 tests/prodcraft_medspa/acceptance_template.py
```
