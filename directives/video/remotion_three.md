# Remotion Three.js — Directive

## Goal

Author `@remotion/three` compositions that run 3D scenes (React Three Fiber)
inside a Remotion `<Composition>`. Outputs are frame-driven — no
requestAnimationFrame loop — so they render correctly headlessly. Integrates
with the workspace's ProRes 4444 / WebM-alpha render pipeline for alpha
overlays in DaVinci Resolve.

## When to use

- User wants a 3D object (product shot, device mockup, abstract geometry) in a
  Remotion video.
- User wants to compose a Three.js scene on the same timeline as 2D motion
  graphics.
- User asks for "3D video with Three.js", "3D animation with Remotion", or
  "three.js in react".

## Inputs

Same project contract as `remotion_authoring.md`:
- `project.json` — fps, width, height, duration_in_frames
- `src/Root.tsx` — composition registry
- `assets/` — 3D model files (`.glb`, `.gltf`), video-as-texture sources

## Tools / Scripts

| File | Purpose |
|---|---|
| `src/Scene.tsx` | Upstream `--three` template scene — torus knot demo, R3F wired |
| `src/Root.tsx` | Composition registry (overlay copy registers both `Scene` and `CompositionWithAlpha`) |
| `src/CompositionWithAlpha.tsx` | Alpha composition template showing `<ThreeCanvas gl={{alpha: true}}>` pattern |

**Dependencies (already present in the `--three` template):**

```
@remotion/three
@react-three/fiber
three
@react-three/drei    # optional — convenient helpers (OrbitControls, Environment, etc.)
```

## Outputs

- `src/{SceneName}.tsx` — the authored 3D composition
- `src/Root.tsx` — updated registration
- Render artifacts via `remotion_render.md` (ProRes 4444 alpha or H.264 MP4)

## Steps

### 1. Wrap the canvas with `<ThreeCanvas>`

`<ThreeCanvas>` is `@remotion/three`'s drop-in replacement for `<Canvas>` from
`@react-three/fiber`. It makes the R3F renderer **frame-driven** instead of
RAF-driven, so headless rendering produces correct per-frame images.

```tsx
import { ThreeCanvas } from "@remotion/three";
import { useCurrentFrame, useVideoConfig } from "remotion";

export const MyScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  return (
    <ThreeCanvas
      width={width}
      height={height}
      gl={{ alpha: true }}           // required for alpha-channel output
    >
      <ambientLight intensity={0.8} />
      <pointLight position={[10, 10, 10]} />
      <RotatingBox frame={frame} />
    </ThreeCanvas>
  );
};
```

**Alpha enabled at the canvas level** — `gl={{ alpha: true }}` is required.
Without it the canvas background is opaque black even if no background color is
set in the scene.

### 2. Drive 3D animation with `useCurrentFrame()`, NOT `useFrame`

`useFrame` from `@react-three/fiber` fires on requestAnimationFrame — it does
NOT fire during headless render. All 3D animation must be derived from
`useCurrentFrame()`:

```tsx
// CORRECT — frame-driven
const RotatingBox: React.FC<{ frame: number }> = ({ frame }) => {
  const rotation = frame * 0.05; // radians per frame
  return (
    <mesh rotation={[rotation, rotation, 0]}>
      <boxGeometry />
      <meshStandardMaterial color="#ff6030" transparent opacity={0.9} />
    </mesh>
  );
};

// WRONG — RAF-driven, silent failure in headless render
const BadBox: React.FC = () => {
  const meshRef = useRef<THREE.Mesh>(null);
  useFrame(() => {
    if (meshRef.current) meshRef.current.rotation.x += 0.05; // never fires in render
  });
  return <mesh ref={meshRef}>...</mesh>;
};
```

Pass `frame` as a prop from the parent component that called `useCurrentFrame()`.

### 3. Nest Sequences with `layout="none"`

When wrapping a `<ThreeCanvas>` inside a `<Sequence>`, use `layout="none"` to
prevent Remotion from injecting a `position: absolute` wrapper div that breaks
the canvas size:

```tsx
<Sequence from={0} durationInFrames={150} layout="none">
  <ThreeCanvas width={width} height={height} gl={{ alpha: true }}>
    ...
  </ThreeCanvas>
</Sequence>
```

Without `layout="none"`, the canvas renders at 0×0 or clips unexpectedly.

### 4. Video-as-texture (`useOffthreadVideoTexture`)

To use a video file as a Three.js texture (e.g. screen content on a device
mockup, environment projection):

```tsx
import { useOffthreadVideoTexture, staticFile } from "remotion";
import { useCurrentFrame } from "remotion";
import * as THREE from "three";

const ScreenMesh: React.FC = () => {
  const frame = useCurrentFrame();
  const videoTexture = useOffthreadVideoTexture({
    src: staticFile("video/screen_content.mp4"),
  });

  return (
    <mesh>
      <planeGeometry args={[16, 9]} />
      <meshStandardMaterial map={videoTexture} />
    </mesh>
  );
};
```

`useOffthreadVideoTexture` decodes each video frame off the main thread and
returns a `THREE.Texture` that updates per Remotion frame. Do NOT use
`<video>` elements or `THREE.VideoTexture` directly — they are RAF-dependent.

### 5. SSR / headless render config

When rendering headlessly (`npx remotion render`), add the `gl: "angle"` option
to `remotion.config.ts` to avoid native OpenGL context failures on some
headless environments:

```ts
// remotion.config.ts
import { Config } from "@remotion/cli/config";

Config.setChromiumOpenGlRenderer("angle");
```

This is a global config applied to all renders in the project. Chromium's ANGLE
renderer emulates OpenGL via Direct3D on Windows — more reliable than the
default native path in CI or headless shells.

### 6. Combine 2D and 3D on the same timeline

Layer 2D Remotion elements on top of a `<ThreeCanvas>` using absolute
positioning:

```tsx
export const ProductHeroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [30, 60], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div style={{ width, height, position: "relative" }}>
      {/* 3D layer — fills container */}
      <ThreeCanvas width={width} height={height} gl={{ alpha: true }}>
        <ambientLight />
        <RotatingProduct frame={frame} fps={fps} />
      </ThreeCanvas>

      {/* 2D layer — absolutely positioned on top */}
      <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "flex-end", padding: 80 }}>
        <h1 style={{ color: "#fff", opacity: titleOpacity, fontSize: 72 }}>Product Name</h1>
      </div>
    </div>
  );
};
```

## Edge Cases

| Case | Handling |
|---|---|
| `useFrame` used instead of `useCurrentFrame()` | Rename: derive animation state from the `frame` prop. Animation will be static in headless render if `useFrame` remains |
| `gl={{ alpha: true }}` omitted | Canvas background defaults to black. Alpha is not composite-able. Add the prop and re-render |
| `<Sequence>` without `layout="none"` inside canvas | Canvas renders 0×0. Add `layout="none"` to all `<Sequence>` wrappers that are direct parents of `<ThreeCanvas>` |
| 3D model (.glb) not loading | Use `@react-three/drei`'s `useGLTF` with `staticFile("models/model.glb")`. Confirm the file is in `public/` (Remotion's static root) or `assets/` with a symlink — `staticFile` resolves from the project root |
| Transparent mesh showing wrong blending | Set `depthWrite={false}` on `meshStandardMaterial` for transparent objects. Render order matters in Three.js: opaque geometry first, transparent last |
| SSR render fails with `GLContextError` | Add `Config.setChromiumOpenGlRenderer("angle")` to `remotion.config.ts` (see step 5) |
| Frame count mismatch between 2D and 3D layers | Both layers use the same `useCurrentFrame()` and `useVideoConfig()` — they share one frame clock. The mismatch is a logic bug in the offset math, not a clock drift |
| `useOffthreadVideoTexture` returns null on first frame | This is expected during initialization. Guard with `if (!videoTexture) return null` or provide a fallback material |
