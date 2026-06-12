# Remotion Render — Directive

## Goal

Render a Remotion composition to video using the correct codec preset for
the intended use case. Two primary presets: **overlay** (alpha-channel output
for DaVinci Resolve compositing) and **final** (delivery-ready H.264 MP4).

**Local render is free.** Lambda parallel render requires an AWS account plus a
Remotion company license at >3 developer seats — out of scope for v1.

## When to use

- User says "render the video", "export to ProRes", "export to WebM", "export
  to MP4", or asks to produce a final file from a Remotion composition.
- User needs an alpha-channel file to drop into DaVinci Resolve on V2.

## Inputs

| Input | Source |
|---|---|
| Composition ID | From `src/Root.tsx` — the `id` field on the `<Composition>` element |
| Project slug | From `project.json` — used to name the output file |
| Target preset | User intent: overlay (alpha) or final (delivery) |

## Outputs

| Preset | File | Use |
|---|---|---|
| Overlay ProRes 4444 | `out/{slug}.mov` | DaVinci Resolve V2 — alpha preserved |
| Overlay WebM-alpha | `out/{slug}.webm` | Chrome-based QA players — alpha preserved |
| Final H.264 | `out/{slug}.mp4` | Delivery, upload, social |

## Steps

### 1. Confirm alpha before rendering (Studio preview)

Before running any render command, open Remotion Studio and **toggle the
checkered-background button** (top-right corner of the canvas preview area).
If the background turns to a grey checkerboard pattern, the transparent pixels
are confirmed. If it stays solid, the composition is not alpha-capable — check
that:
- `backgroundColor` is not set on the root `<div>` (remove it or set to
  `transparent`)
- For Three.js scenes: `gl={{ alpha: true }}` is set on `<ThreeCanvas>` (see
  `remotion_three.md`)

Do not run a render expecting alpha output until the Studio checkered toggle
visually confirms transparency.

### 2. Render — overlay preset (ProRes 4444 alpha)

Use this when the output will be composited over other footage in DaVinci
Resolve or a similar NLE.

```bash
npx remotion render <CompositionId> out/<slug>.mov \
  --codec=prores \
  --prores-profile=4444 \
  --pixel-format=yuva444p10le
```

- `prores-profile=4444` — enables the alpha channel in the ProRes container
- `pixel-format=yuva444p10le` — 10-bit YUV with full alpha plane
- Output is a `.mov` file; Resolve reads it natively

### 3. Render — overlay preset (WebM-alpha)

Use this as a secondary alpha deliverable for QA in browser-based players (e.g.
Chrome) or as a lightweight backup when ProRes is not available.

```bash
npx remotion render <CompositionId> out/<slug>.webm \
  --codec=vp9 \
  --pixel-format=yuva420p
```

- `yuva420p` — YUV 4:2:0 with alpha plane; smaller than ProRes, lossier
- WebM-alpha plays in Chrome and Chrome-based Electron players; does NOT play
  in Safari or QuickTime without a codec pack

### 4. Render — final preset (H.264 MP4)

Use this for the finished deliverable: upload, social, client handoff.

```bash
npx remotion render <CompositionId> out/<slug>.mp4 \
  --codec=h264 \
  --crf=18
```

- `crf=18` — near-lossless quality. Range: 0 (lossless) to 51 (worst).
  18 is visually transparent for motion graphics. Use 23 for smaller files if
  size matters.
- No alpha channel in H.264. If you need the alpha preserved, render ProRes
  4444 first.

### 5. DaVinci Resolve import

1. Drag the `.mov` (ProRes 4444) onto **V2** in the Resolve timeline, above
   your main footage on V1.
2. Resolve reads the alpha channel automatically from the ProRes 4444
   container — no manual keying or matte operations needed.
3. For WebM-alpha QA: drag the `.webm` into a Chrome tab or Chrome-based
   player. The checkerboard shows where the alpha is transparent.

**Note on WebM in Resolve:** DaVinci Resolve does not natively decode VP9/WebM
on Windows without the WebM codec pack. Use the `.mov` for Resolve; keep the
`.webm` for browser-based QA only.

### 6. Render a single frame for testing

To test alpha output without waiting for a full render:

```bash
npx remotion render <CompositionId> out/alpha_test.png \
  --frame=15 \
  --codec=png
```

A PNG with RGBA channels. Verify the alpha plane with any image viewer that
renders transparency (e.g. Photoshop, GIMP, or the Python check in the
smoke-test protocol in `remotion_bootstrap.md`).

## Exit Criteria

A render is complete only when ALL of the following predicates are true:

| Predicate | Check |
|-----------|-------|
| Output file exists | `out/{slug}.{ext}` is present on disk (`.mov`, `.webm`, or `.mp4` depending on preset) |
| File size > 1 MB | `Get-Item out/{slug}.{ext} \| Select-Object -ExpandProperty Length` returns > 1048576 bytes. Suspiciously small files indicate a corrupt render or a composition that produced no frames. |
| ffprobe duration > 0 | `ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 out/{slug}.{ext}` returns a positive float. A duration of 0 or N/A means the container is corrupt. |
| Frame count > 0 | `ffprobe -v error -select_streams v:0 -count_frames -show_entries stream=nb_read_frames -of default=noprint_wrappers=1:nokey=1 out/{slug}.{ext}` returns a positive integer. |
| Audio track present (if expected) | If the composition includes audio, `ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 out/{slug}.{ext}` must return a non-empty codec name. Skip this check for silent compositions. |

If any predicate fails, the render is NOT done. Common fixes:
- File size = 0: `out/` directory was missing at render time. Run `mkdir out` and re-render.
- Duration = 0 / N/A: The composition produced no frames. Check for unhandled promise rejections in the component with `--log=verbose`.
- Frame count = 0 but file > 0 bytes: container header written but frames dropped — often a Chromium crash mid-render. Re-run with `--concurrency=1` to serialize frame rendering.

## Edge Cases

| Case | Handling |
|---|---|
| Render fails with "Chromium not found" | Run `npx remotion browser ensure` to download the bundled Chromium (~150-300 MB). This is also done during `/remotion preflight`. |
| ProRes render very slow | ProRes 4444 is CPU-intensive. For long compositions (>5 min) consider `--concurrency=4` to parallelize frame rendering across CPU cores. |
| Output `.mov` shows black background in Resolve | The composition is not alpha-capable. Go back to Studio, toggle the checkered button, and fix the composition before re-rendering. |
| `out/` directory missing | Create it: `mkdir out`. Remotion does not auto-create the output directory. |
| CRF 18 produces large files | For delivery, use `--crf=23`. For archival or intermediate files, keep 18. |
| Render exits with non-zero and no visible error | Add `--log=verbose` to the render command to see the full Puppeteer/Chromium trace. Common culprit: an unhandled promise rejection in a composition component. |
| Lambda render mentioned | Out of scope for v1. Requires AWS account + Remotion company license at >3 dev seats. Use local render. |
