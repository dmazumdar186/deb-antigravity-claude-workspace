# Hero footage brief (Higgsfield, run from the local machine)

The GreenJobs hero accepts generated footage as a drop-in. No code changes: put the files below in
`deliverables/greenjobs_redesign_2026-09-22/src/assets/hero/`, rebuild, deploy. Until they exist the
procedurally drawn living landscape is the hero; once they exist the video plays over it (poster
first, canvas as the fallback while the first frame loads, paused under reduced motion / off-screen).

## Files

| File | Size | Use |
|---|---|---|
| `ie.mp4` | 1920×1080, 8–12 s seamless loop, H.264, no audio, ≤ 6 MB | Ireland desktop |
| `ie-m.mp4` | 1080×1350 portrait, same loop, ≤ 4 MB | Ireland phones (< 800 px) |
| `ie-poster.webp` | 1920×1080 first frame | Poster / Save-Data / reduced motion |
| `uk.mp4`, `uk-m.mp4`, `uk-poster.webp` | as above | UK edition |

Run `python3 execution/gtm_client_workflows/greenjobs_redesign/build_site.py --src … --out … --edition both`
then `bash execution/gtm_client_workflows/greenjobs_redesign/deploy_cloudflare.sh`.

## Prompts (Higgsfield MCP, `cinematic-image-to-video` or text-to-video; model with EU/US jurisdiction; `--sensitivity public`, no people's faces)

Common style line, append to each: "warm late-afternoon light, golden hour, soft haze, muted earth palette
(cream, ochre, terracotta, sage), gentle slow camera drift, no text, no logos, no people close-up,
photoreal, seamless loop, 24 fps."

1. **ie.mp4 — Ireland.** "Slow aerial drift over green Irish hills toward a small onshore wind farm,
   turbines turning slowly, a river catching the light in the valley, dry-stone walls, a distant
   Atlantic coastline, a few birds crossing the frame."
2. **uk.mp4 — UK.** "Slow aerial drift over a chalk-downland river valley in southern England,
   a solar farm on one slope, a line of wind turbines on the ridge, a restored wetland with reeds
   and a heron lifting off, hedgerows and a country lane."
3. **Portrait variants** (`-m.mp4`): same prompts, framed vertically, the turbines or heron in the
   upper third so the search bar overlays the lower two-thirds cleanly.

Pick the take with the least motion in the lower half of the frame (the search bar sits there).
Export the first frame as the poster. Keep the credit spend to one generation per prompt; a second
take only if the first has visible artefacts in the sky or water.

## Why footage, and why these scenes

Keith's first impression: the green felt impersonal and the page bland. The scenes show the actual
work the board carries (wind, water, solar, ecology, built environment) in the warm register of
B Corp brands, moving slowly, with the two-field search and the Post a job button on top.
