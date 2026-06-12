# Remotion + @remotion/three Notes

<!-- TODO: The 4 specific R3F headless-render gotchas should be verified and
expanded the next time the remotion_three project is actively worked on.
The entries below are sourced from the 2026-06-11 audit card (in_flight_projects.md)
and the directive itself (directives/video/remotion_three.md). -->

- [technical] R3F headless render — wrong template flag: Use `--three` (boolean cliId in create-video's select-template.js), NOT `--template three`. The latter drops the CLI into an interactive prompt and hangs the subprocess waiting for stdin.
- [technical] R3F headless render — `useCurrentFrame()` not `useFrame`: In headless/compositor render context, always use Remotion's `useCurrentFrame()` hook (from `remotion`) rather than R3F's `useFrame`. Using `useFrame` in a Remotion composition produces incorrect frame timing because R3F's frame loop is disconnected from Remotion's frame clock.
- [constraint] R3F headless render — `layout="none"` on Sequences: Remotion `<Sequence>` components must have `layout="none"` when wrapping a `<ThreeCanvas>`. Without it, the Sequence injects a `position: absolute` wrapper div that breaks the canvas sizing in the headless compositor.
- [technical] R3F headless render — alpha transparency: `<ThreeCanvas>` must receive `gl={{ alpha: true }}` to produce a transparent background. Without this prop, the canvas renders a black background even when the CSS background is transparent, and the smoke-test alpha assertion will fail.
- [learned] Smoke-test PNG visual check: After a single-frame render (`npx remotion render CompositionWithAlpha out/alpha_test.png --frame 0`), verify the PNG is not blank. A silent black/transparent frame passes the file-exists check but indicates the compositor failed or the scene is empty. Use PIL brightness assertion (mean_brightness > 20) and size assertion (1920×1080) — see remotion_bootstrap.md Visual quality check section.
- [learned] Root.tsx overlay rationale: The upstream `--three` template ships a RemotionRoot that only registers the torus knot Scene. The workspace overlay replaces it to also register CompositionWithAlpha. If the upstream template renames Scene exports, the bootstrap exits 1 rather than silently producing a broken Root.tsx.
