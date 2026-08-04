# assets/

Placeholder directory. The template intentionally ships without binary assets — you supply your own.

Required files before first EAS build:

- `icon.png` — 1024x1024, no alpha, no rounded corners (stores add them)
- `android-icon-foreground.png` — 1024x1024, transparent bg, foreground image only
- `android-icon-background.png` — 1024x1024, solid color layer (used behind foreground)
- `android-icon-monochrome.png` — 1024x1024, single-color glyph (Android themed icons)
- `favicon.png` — 48x48 (web target)
- `splash.png` — recommended 1284x2778, transparent bg allowed

Generation options:

1. `npx expo install expo-splash-screen && npx expo customize` — Expo scaffolds default assets.
2. `execution/image_generation/` — the workspace's image-gen scripts (GLM 5.2 for concept, then downscale via Sharp).
3. Any design tool (Figma, Sketch, Excalidraw).

**Do NOT commit real icons at scaffold time** — every app gets its own visual identity. This README serves as the reminder.
