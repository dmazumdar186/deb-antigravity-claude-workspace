# Hero footage prompts — GTM People v4 opening (2026-10-06)

The opening (`site/index.html` → `<section id="top" class="opening">`) runs four beats over a pipeline canvas. A
Kling/Higgsfield loop can sit behind all four. Rules for every clip: abstract, light palette (white → #F5F3FF, violet
#7C3AED, soft mint #06D6A0 accents), **no people, no faces, no hands, no text, no logos**, slow continuous motion that
loops seamlessly at 10 s, both 16:9 (1280×720 drop-in) and 9:16 (1080×1920 crop for < 800 px). Shown at opacity .35
under a white→#F5F3FF gradient, so contrast matters less than calm motion; the left half of the frame stays quiet
because the copy sits there.

| Beat | File(s) | Prompt |
|---|---|---|
| 1 — We hire your founding GTM team | `site/assets/hero.mp4`, `site/assets/hero-m.mp4` (**the ones the page loads**) | Hundreds of tiny translucent violet spheres drifting in a loose cloud, slowly funnelling through a narrow glass neck into a single orderly line, five of them turning mint green as they emerge, one gliding forward and settling with a soft ripple of light. |
| 2 — Built by someone who's been in the seat | `site/assets/hero-b2.mp4`, `hero-b2-m.mp4` (optional, not wired) | Slow dolly across a sunlit minimalist desk surface at dawn, pale paper, a faint violet reflection moving across frosted glass, soft bokeh, a hint of mint light at the edge, cinematic, unhurried. |
| 3 — From brief to shortlist. Five days | `site/assets/hero-b3.mp4`, `hero-b3-m.mp4` (optional) | A thin luminous violet line drawing itself left to right across a pale surface, blooming into six soft glowing nodes in turn, gentle mint sparks at each node, macro depth, continuous smooth motion. |
| 4 — Seed to Series C. London-based, placing globally | `site/assets/hero-b4.mp4`, `hero-b4-m.mp4` (optional) | Abstract globe made of fine violet dots slowly rotating, thin glowing arcs rising from one bright mint point and landing softly on distant points, pale white background, cartographic, serene. |

Style suffix appended to every prompt (in the script): *Soft diffuse studio light, pale palette of white, lavender
#F5F3FF and light violet #7C3AED with small mint #06D6A0 accents, slow continuous motion that reads as a seamless
loop, abstract, no text, no logos, no people, no faces, no hands, shallow depth of field, calm, the left half of the
frame quiet and uncluttered.*

## Command (local, needs `HF_API_TOKEN=key_id:secret` in `.env`; never run in cloud — no key there)

```bash
# estimate only (no spend)
python3 deliverables/gtm_people_redesign_2026-10-06/research/generate_hero_footage.py --beat 1 --env-file .env
# generate beat 1 (≈ $1 for 10 s Kling 3.0 std), cut hero.mp4 + hero-m.mp4, flip assets/hero.json to "ready": true
python3 deliverables/gtm_people_redesign_2026-10-06/research/generate_hero_footage.py --beat 1 --env-file .env --go --max-usd 1.50
# optional extra loops (not loaded by the page unless hero.json is pointed at them)
python3 deliverables/gtm_people_redesign_2026-10-06/research/generate_hero_footage.py --beat 3 --env-file .env --go
```

## How the page loads it

`<video class="opening__video" data-hero-video muted loop playsinline autoplay preload="none">` has no `src`. At boot
`js/main.js` GETs `assets/hero.json` (shipped with `"ready": false`, so there is never a 404 in the console — a HEAD
probe of a missing `hero.mp4` would log one in Chromium). Only when `ready` is `true` does it set `src`
(`hero-m.mp4` under 800 px), play, fade the video to .35 and dim the canvas to .5. Skipped under
`prefers-reduced-motion` and `prefers-reduced-data`. Dropping files by hand: copy them in and set `"ready": true`.
