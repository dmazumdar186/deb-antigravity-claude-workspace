# Remotion Template Overlay

This directory contains files that `execution/video/remotion_bootstrap.py` copies
**on top of** a freshly-scaffolded `npx create-video@latest {slug} --yes --three`
project. Files here overwrite their upstream counterparts where both exist (e.g.
`src/Root.tsx`). Files not present here are left as-is from the upstream template.

---

## Why node_modules is symlinked

OneDrive syncs every file it can see. The `node_modules` tree for a Remotion project
contains 100,000+ small files — syncing them causes a sustained "sync storm" that
pegs disk I/O, inflates OneDrive quota, and makes the first project install extremely
slow.

The bootstrap script creates a **directory junction** (Windows equivalent of a symlink)
pointing `{project}/node_modules` at
`C:\Users\deban\dev\remotion-node-cache\{slug}\node_modules`.
That cache directory is **outside OneDrive** so it is never synced.

- The project source files (`.tsx`, `project.json`, `assets/`) live inside OneDrive
  and sync normally.
- `node_modules` is excluded from OneDrive via the junction.
- If you delete the cache directory, re-run `npm install` inside the project folder
  to repopulate it. The junction itself is preserved by the bootstrap script.

---

## Windows Defender note

Windows Defender (and some third-party AV products) occasionally quarantine native
binaries inside `node_modules` — specifically:

- `remotion.exe` inside `@remotion/compositor-win32-x64-msvc`
- `ffmpeg.exe` inside `@remotion/compositor-win32-x64-msvc`

These binaries are used by Remotion for frame rendering and video encoding. If a
render fails with a "file not found" or "access denied" error pointing at one of
those paths, AV quarantine is the likely cause.

**Fix:** Add `C:\Users\deban\dev\remotion-node-cache\` as an exclusion in
Windows Defender:

1. Open **Windows Security** → **Virus & threat protection** → **Manage settings**
2. Scroll to **Exclusions** → **Add or remove exclusions**
3. Add a **Folder** exclusion: `C:\Users\deban\dev\remotion-node-cache\`

---

## Mac caveat

The directory junction (`node_modules`) is a Windows-only construct. If this
workspace is ever cloned on macOS, the junction will appear as an empty directory
rather than pointing to the cache.

To fix on macOS:
1. `cd execution/video/remotion-projects/{slug}`
2. `rm -rf node_modules` (removes the broken junction stub)
3. `npm install` (re-populates `node_modules` locally)

The project will work correctly after that — macOS just won't benefit from the
OneDrive-bypass behavior.

---

## Previewing alpha

`CompositionWithAlpha` is the alpha-channel proof composition registered in
`src/Root.tsx`. It renders a translucent radial gradient and an animated
brand-orange square against a transparent background.

To verify alpha works before committing to a full render:

1. Start the Remotion Studio: `npx remotion studio` inside the project directory.
2. Select **CompositionWithAlpha** in the left sidebar.
3. In the top-right of the preview canvas, click the **checkered-background button**
   to toggle transparency view. You should see the checkerboard show through the
   areas not covered by the gradient or square.

If the checkerboard is visible, alpha is working. If you see a solid black or white
background instead, check that `src/Root.tsx` has not had a `backgroundColor` added
to the `<AbsoluteFill>` in `CompositionWithAlpha.tsx`.

---

## Rendering

For render commands (ProRes 4444 alpha, H.264 MP4, WebM-alpha) and DaVinci Resolve
import conventions, see:

`directives/video/remotion_render.md`

That directive contains the exact CLI flags for both presets and notes on how to
import alpha-channel footage into DaVinci on V2.
