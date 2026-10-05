# LinkedIn Banners — ProdCraft editorial set

Script: `execution/content/linkedin_banners.py`. Replaces the 2026-08-31 `/ad-creative` output (dark indigo gradient, Manrope, pill CTA, no logo, no proof, no links) which the operator rejected as "looks AI-generated".

## Goal

20 brand-matched, humanized posters for https://www.linkedin.com/in/dmazumdar/ that carry real receipts, the ProdCraft logo, and a link strategy that actually works on LinkedIn.

## Inputs

- Brand tokens pulled from prodcraft.fyi (2026-10-01): bone `#f7f3ec`, ink `#16181c`, brass `#c8a35c` / `#aa8638`, fonts Newsreader + Geist + JetBrains Mono (+ Caveat for hand-written marginalia). Logo: `https://prodcraft.fyi/logo.png`.
- Proof points: only numbers published on prodcraft.fyi. Never add others.
- Links: cal.com/debanjan-mazumdar-ben5rd/30min · prodcraft.fyi · github.com/dmazumdar186.
- Fonts cached locally in `.tmp/banners/fonts/` (cloud chromium cannot reach Google Fonts through the proxy reliably). Re-download with the curl in the 2026-10-01 session if missing.

## Run

```bash
pip install playwright pillow "qrcode[pil]"   # chromium is pre-installed in cloud at /opt/pw-browsers
python3 execution/content/linkedin_banners.py --animate 3
```

## Outputs — `deliverables/linkedin_banners/prodcraft/<date>/`

- `png/NN_slug.png` — 1080×1350 (4:5 portrait, max feed height).
- `carousel.pdf` — 20 pages, each with 4 clickable link annotations (LinkedIn document posts keep hyperlinks; image posts do not).
- `animated/NN.gif|mp4` — 3-second staggered-reveal hero cards (post as video; LinkedIn strips GIF animation).
- `captions.md` — post text with the three links for the first comment.
- `review.html`, `manifest.json`, `logo.png`.

## Why images "weren't clickable" and the fix

LinkedIn never makes image pixels clickable. Three layers now cover it: (1) link rail printed on every banner, (2) QR to the booking page on every banner, (3) PDF carousel with real hyperlinks + captions with links for the first comment.

## Edge cases

- `Page.pdf` dies ("string longer than 0x1fffffe8") if each page inlines the fonts and the paper-noise filter. Build the PDF from the rendered PNGs with overlay anchors instead.
- Playwright pip wheel will not find chromium: launch with `executable_path=/opt/pw-browsers/chromium-*/chrome-linux/chrome`.
- Hand-written notes live inside `.body` (bottom-right), never in the link rail — they collide with the QR there.

## Campaigns (2026-10-05)

`--campaign <json>` loads variants from `execution/content/campaigns/*.json` (`title`, `dark` indices, `variants`). Four-offers set: `four_offers_2026-10-05.json`, deployed with `wrangler pages deploy <out> --project-name prodcraft-banners --branch four-offers` (copy `review.html` to `index.html` first). Layout fixes: heads >48 chars get a 74px h1 (`.card.long`); bignum underline and cta circle are now flow-anchored, not absolute.
