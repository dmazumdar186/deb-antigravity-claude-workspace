# Stock imagery — licensing notes

All images in this directory (`hero-01..04.png`, `hero-01..04-sm.png`,
`texture-01.png`, `favicon.ico`) are procedurally generated in-repo by
`scripts/gen-stock.mjs` — layered gradients in the business's brand color,
soft radial blooms, a bold geometric arc, and film grain, rendered with pure
Node stdlib (no canvas, no sharp, no external model, no downloaded or
scraped photography).

No third-party photography, stock library assets, or scraped images are
used anywhere in this template. These generated assets are owned outright
by the operator (ProdCraft) and may be reused across any number of preview
sites without licensing risk.

Regenerated automatically by `npm run build` (idempotent — a no-op when
`primary_color` hasn't changed and all files are present) or on demand
with `npm run gen-stock`.
