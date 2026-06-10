# Remotion Authoring — Directive

## Goal

Author Remotion compositions inside a workspace project, wire them into the
React timeline, and preview them live in the browser. The output is
a Remotion composition that renders to video via `remotion_render.md`.

**Coherence note:** this directive assumes projects bootstrapped via
`/remotion new {slug}`. A bootstrapped project has `project.json`,
`assets/`, `src/script.md`, `src/lib/easings.ts`, and
`src/CompositionWithAlpha.tsx` already present. If `project.json` is missing,
ask the user whether to re-bootstrap (run `/remotion new`) or adapt manually
before continuing.

**Alternative for diagram/math videos:** if the deliverable is a math
derivation, algorithm animation, or data-structure visualization — where
equations and scene-graph manipulation matter more than motion graphics — use
[Manim](https://www.manim.community/) instead of Remotion. Remotion is the
right tool for React-based motion graphics, UI animations, 3D product shots
(`@remotion/three`), and narrated video essays. Manim is better for
mathematical notation and diagram-driven explainers.

## When to use

- User asks to "make a video", "animate this", "build a Remotion comp", or
  provides assets (script, audio, images) and asks for a motion graphic.
- User wants to update an existing Remotion project's composition or timing.
- User wants to register a new composition in `Root.tsx`.

## Inputs

### Project config (`project.json`)

Read this file before authoring. It defines the composition contract:

```json
{
  "slug": "pitch-promo",
  "title": "Pitch Promo",
  "fps": 30,
  "width": 1920,
  "height": 1080,
  "duration_in_frames": 900
}
```

| Field | Purpose |
|---|---|
| `slug` | Project identifier — matches the folder name under `execution/video/remotion-projects/` |
| `fps` | Frames per second. 30 for most outputs; 24 for cinematic feel |
| `width` / `height` | Canvas dimensions. 1920×1080 for 16:9; 1080×1920 for vertical |
| `duration_in_frames` | Total frame count. `fps × seconds` — e.g. 30fps × 30s = 900 |

### Script file (`src/script.md`)

Voiceover script with rough timing marks:

```markdown
## Scene 1 (0:00–0:05)
Intro line here.

## Scene 2 (0:05–0:12)
...
```

Convert timing marks to frame ranges before writing `interpolate` calls:
`frame = seconds × fps` (e.g. 0:05 @ 30fps = frame 150).

### Assets (`assets/`)

| File pattern | Purpose |
|---|---|
| `assets/audio/voice.mp3` | Voiceover. Playback via `<Audio src={staticFile(...)} />` |
| `assets/audio/music.mp3` | Background music. Lower volume via `volume={0.2}` |
| `assets/images/*.{jpg,png}` | Still images. Load via `staticFile(...)` |
| `assets/video/*.mp4` | B-roll. Use `useOffthreadVideoTexture` in Three.js context (see `remotion_three.md`), or `<OffthreadVideo>` in 2D context |

## Tools / Scripts

| File | Purpose |
|---|---|
| `execution/video/remotion_bootstrap.py` | Scaffold new project (see `remotion_bootstrap.md`) |
| `src/Root.tsx` | Composition registry — add all compositions here |
| `src/CompositionWithAlpha.tsx` | Alpha-capable composition template |
| `src/lib/easings.ts` | Named spring presets (bounce, snappy, gentle, stiff) |

## Outputs

- `src/{CompositionName}.tsx` — the authored composition
- `src/Root.tsx` — updated to register the new composition
- Live preview at `http://localhost:3000` via `npx remotion studio`

## Steps

### 1. Read project config

```
project.json  →  fps, width, height, duration_in_frames
src/script.md →  scene timing marks
assets/       →  available audio, images, video
```

### 2. Convert timing marks to frame ranges

```ts
// seconds to frames
const SCENE_1_START = 0;           // frame 0
const SCENE_1_END   = 5 * fps;     // frame 150 at 30fps
const SCENE_2_START = SCENE_1_END; // frame 150
const SCENE_2_END   = 12 * fps;    // frame 360
```

### 3. Author the composition file

Create `src/{CompositionName}.tsx`. Canonical structure:

```tsx
import { useCurrentFrame, useVideoConfig, interpolate, spring, Audio, staticFile } from "remotion";

export const MyComposition: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();

  // --- opacity: fade in title over frames 0-20 ---
  const titleOpacity = interpolate(frame, [0, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // --- spring: slide up on entry ---
  const titleY = spring({
    frame,
    fps,
    config: { damping: 200 },
    durationInFrames: 30,
  });

  return (
    <div style={{ width, height, background: "#0f0f0f" }}>
      <Audio src={staticFile("audio/voice.mp3")} />
      <h1 style={{ opacity: titleOpacity, transform: `translateY(${(1 - titleY) * 50}px)` }}>
        Title
      </h1>
    </div>
  );
};
```

### 4. Frame math quick-reference

| Pattern | Code |
|---|---|
| Linear fade in/out | `interpolate(frame, [startFrame, endFrame], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })` |
| Springy entry | `spring({ frame, fps, config: { damping: 200 }, durationInFrames: 30 })` — returns 0→1 |
| Springy bounce | `spring({ frame, fps, config: { damping: 8, stiffness: 100 }, durationInFrames: 30 })` |
| Offset timing | Pass `frame - sceneStartFrame` to `interpolate`/`spring` so each scene is self-contained |
| Hold (no change) | `interpolate(frame, [0, 1], [v, v])` or conditional: `frame < startFrame ? 0 : 1` |

Use the named presets in `src/lib/easings.ts` for consistent feel across scenes.

### 5. Sequence multiple scenes

```tsx
import { Sequence } from "remotion";

// each Sequence is offset in time; children receive frame relative to their own start
<Sequence from={0} durationInFrames={150}>
  <SceneOne />
</Sequence>
<Sequence from={150} durationInFrames={210}>
  <SceneTwo />
</Sequence>
```

Inside `<SceneOne>`, `useCurrentFrame()` returns 0 at frame 0 of the global
timeline — Remotion resets the frame counter for each `<Sequence>`.

### 6. Register in Root.tsx

Open `src/Root.tsx` and add a `<Composition>` entry alongside existing ones:

```tsx
<Composition
  id="MyComposition"
  component={MyComposition}
  durationInFrames={durationInFrames}
  fps={fps}
  width={width}
  height={height}
/>
```

Import `fps`, `width`, `height`, `durationInFrames` from `project.json` so all
compositions share one source of truth for canvas dimensions.

### 7. Start Studio and preview

```bash
# from the project directory
npx remotion studio
```

Open `http://localhost:3000`, select the composition from the left panel, and
scrub the timeline. The checkered-background toggle (top-right of canvas) proves
alpha transparency — use it before rendering any alpha-channel composition.

### 8. Render

See `remotion_render.md` for exact CLI commands and codec presets.

## Edge Cases

| Case | Handling |
|---|---|
| `project.json` missing | Ask user to run `/remotion new {slug}` or provide the missing fields manually before authoring |
| `useVideoConfig()` returns wrong fps | Check `project.json` is wired into the `<Composition>` registration in `Root.tsx` — upstream defaults are 30fps/1080p |
| spring returns values >1 on bounce configs | Clamp with `Math.min(1, spring(...))` if the overshoot is not intentional |
| Audio file format not supported | Remotion supports `.mp3`, `.wav`, `.aac`. Convert others to `.mp3` via ffmpeg before adding to assets |
| Composition not appearing in Studio | Confirm it is registered in `Root.tsx` with a unique `id`. Restart `npx remotion studio` after `Root.tsx` changes |
| Large images cause memory pressure | Downscale to 1920×1080 before import; Remotion renders per-frame so full-resolution images are reloaded on every frame |
| OneDrive sync races with hot-reload | OneDrive may hold write locks briefly during save. If hot-reload is erratic, pause OneDrive sync while authoring |

## Roadmap

### v1.1

- `execution/video/remotion_render.py` — wrapper around the render CLI so
  Claude can invoke a render without copy-pasting flags. Deferred until one real
  project proves manual flags are painful.
- `/remotion list` — lists registered compositions from `Root.tsx` + registry
- `/remotion compose` — interactive scene-by-scene scripting prompt

### v2

- Lambda parallel render (requires AWS account + Remotion company license
  at >3 dev seats — skip until warranted)
- AI script generation from topic + brand brief
- TTS voice-over synthesis
- Auto caption sync (Whisper alignment)
- Lipsync via Wav2Lip or equivalent
