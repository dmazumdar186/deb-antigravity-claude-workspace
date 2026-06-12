# Remotion Bootstrap — Directive

## Goal

Scaffold a new Remotion project with `@remotion/three` pre-wired, overlay the
workspace's authoring conventions (project config, alpha composition, easing
presets, script placeholder), junction-symlink `node_modules` outside OneDrive,
and register the project in `execution/video/registry.json`.

This directive is invoked by `/remotion new {slug}` (see `.claude/skills/remotion/SKILL.md`).
The orchestration layer calls `execution/video/remotion_bootstrap.py`.

## When to use

- User says "/remotion new {slug}" or "create a new Remotion project called {slug}".
- User wants to start a motion graphics or 3D video project from scratch.

## Inputs

| Input | Source |
|---|---|
| `--slug {slug}` | Required. Project identifier. Lowercase alphanumeric + hyphens only. |
| `--dry-run` | Optional. Prints planned paths and would_* actions without creating anything. |

## Tools / Scripts

| File | Purpose |
|---|---|
| `execution/video/remotion_bootstrap.py` | Python orchestrator — runs `npx create-video`, applies overlay, creates junction |
| `execution/video/registry.json` | Created on first project; tracks all Remotion projects in this workspace |
| `execution/video/remotion_template_overlay/` | Files overlaid on top of the official template (see Overlay section below) |

## Outputs

- `execution/video/remotion-projects/{slug}/` — full Remotion project
- `C:\Users\deban\dev\remotion-node-cache\{slug}\node_modules\` — actual node_modules (outside OneDrive)
- `execution/video/remotion-projects/{slug}\node_modules` — NTFS junction pointing to the above
- `execution/video/registry.json` — entry appended

## Steps

### 1. Validate slug

The Python script checks the slug before any filesystem work:
- Allowed characters: `[a-z0-9-]`
- Max length: 50 characters
- Path traversal guard: resolves the full project path and asserts it is relative
  to `execution/video/remotion-projects/`. Rejects slugs containing `..`, `/`, or `\`.

If validation fails, the script exits 1 with a clear message — it does not
create partial directories.

### 2. Create junction cache directory

```
C:\Users\deban\dev\remotion-node-cache\{slug}\
```

Created if not present. This path is **outside OneDrive** — essential because
`node_modules` trees contain tens of thousands of small files that saturate
OneDrive's sync queue and trigger Windows Defender scans.

**AV whitelist note:** Add `C:\Users\deban\dev\remotion-node-cache\` to Windows
Defender's exclusion list to prevent scan overhead on `npm install` and render
startup. Path: Windows Security → Virus & threat protection → Manage settings →
Exclusions → Add an exclusion → Folder.

### 3. Run the official template

```bash
npx create-video@latest {slug} --yes --three
```

- `--yes` — skips all interactive prompts (required; without it the subprocess
  hangs waiting for stdin)
- `--three` — selects the `@remotion/three` template (boolean `cliId` in
  `create-video`'s `select-template.js`). **Not** `--template three` — that
  flag is wrong and drops the CLI into an interactive prompt.

The `--three` template installs:
- `@remotion/three` — Remotion-aware Three.js canvas
- `@react-three/fiber` — React renderer for Three.js
- `three` — Three.js core
- A sample `src/Scene.tsx` — torus knot with frame-driven rotation
- A sample `src/Root.tsx` — registers `Scene` using the upstream `RemotionRoot`

This runs in the `execution/video/remotion-projects/` directory so the project
lands at `execution/video/remotion-projects/{slug}/`.

### 4. Move node_modules to cache and create junction

After `create-video` finishes installing:

```bash
# Move the installed node_modules to the cache
move execution\video\remotion-projects\{slug}\node_modules \
     C:\Users\deban\dev\remotion-node-cache\{slug}\node_modules

# Create NTFS junction pointing back
cmd /c mklink /J \
    "execution\video\remotion-projects\{slug}\node_modules" \
    "C:\Users\deban\dev\remotion-node-cache\{slug}\node_modules"
```

The Python script runs this via `subprocess.run(["cmd", "/c", "mklink", "/J", ...], encoding="utf-8", errors="replace")`.

**Mac-clone caveat:** NTFS junctions are Windows-only. If this workspace is
ever cloned on macOS, `node_modules` junctions appear as empty directories.
Run `npm install` inside the project and re-create symlinks via `ln -s` on Mac.
This is a low-likelihood scenario (user is Windows-only).

### 5. Apply the workspace overlay

The overlay files in `execution/video/remotion_template_overlay/` are copied
into the project, **overwriting upstream files where both exist** (most
importantly `src/Root.tsx`). This is intentional — see below.

| Overlay file | Destination | Purpose |
|---|---|---|
| `project.json` | `{slug}/project.json` | Canonical fps / dimensions / duration config |
| `assets/README.md` | `{slug}/assets/README.md` | Instructions: drop voice.mp3 / music.mp3 / images here |
| `src/script.md` | `{slug}/src/script.md` | Voiceover script placeholder with scene-timing format |
| `src/lib/easings.ts` | `{slug}/src/lib/easings.ts` | Named spring presets (bounce, snappy, gentle, stiff) |
| `src/CompositionWithAlpha.tsx` | `{slug}/src/CompositionWithAlpha.tsx` | Alpha-capable radial gradient composition for Studio preview testing |
| `src/Root.tsx` | `{slug}/src/Root.tsx` | **Overwrites upstream** — registers both upstream `Scene` AND `CompositionWithAlpha` |
| `README.md` | `{slug}/README.md` | AV whitelist note, junction explanation, Mac caveat, Studio checkered-bg instructions |
| `.template-version` | `{slug}/.template-version` | SHA pin of upstream `--three` template tested against |

**Why `Root.tsx` is in the overlay (deliberate overwrite):**
The upstream `--three` template ships a `RemotionRoot` that only registers the
torus knot `Scene` composition. Our overlay replaces it with a `Root.tsx` that
registers BOTH the upstream `Scene` (using the upstream `calculateMetadata`
import pattern) AND `CompositionWithAlpha` (the alpha proof composition). Without
this overwrite, `CompositionWithAlpha` would not appear in Remotion Studio and
could not be rendered by the smoke-test.

The overlay `Root.tsx` imports `Scene` as:

```tsx
import { Scene, myCompSchema } from "./Scene";
```

This matches the upstream `template-three` export path (verified against the
pinned `.template-version` SHA). If upstream renames the export, the bootstrap
script warns and bails rather than producing a broken project.

### 6. Upstream drift check

Before writing the overlay, the bootstrap script checks:

```python
scene_src = (project_path / "src" / "Scene.tsx").read_text(encoding="utf-8")
assert "videoSrc" in scene_src, "Upstream Scene.tsx no longer has videoSrc — template may have changed. Check .template-version."
```

If the assertion fails, the script exits 1 and prints a message with the
`.template-version` SHA and instructions to review the upstream template before
proceeding.

### Visual quality check (added 2026-06-12)

After the smoke-test exports the PNG (single-frame render of `CompositionWithAlpha`
via `npx remotion render CompositionWithAlpha out/alpha_test.png --frame 0`),
verify it is a real frame, not blank or fully transparent:

```python
from PIL import Image, ImageStat
img = Image.open(out_path).convert("RGB")
mean_brightness = sum(ImageStat.Stat(img).mean) / 3
assert mean_brightness > 20, f"smoke-test PNG is too dark/blank: brightness {mean_brightness:.1f}"
assert img.size == (1920, 1080), f"smoke-test PNG wrong size: {img.size}"
```

If this assertion fails, the bootstrap is broken — DO NOT proceed to Step 7.

### 7. Write registry entry

`execution/video/registry.json` is created on first project and appended on
subsequent ones. Schema:

```json
{
  "schema_version": 1,
  "projects": [
    {
      "slug": "pitch-promo",
      "created_at": "2026-06-10T14:32:00Z",
      "template_version": "<sha>",
      "fps": 30,
      "width": 1920,
      "height": 1080,
      "duration_in_frames": 900,
      "project_path": "execution/video/remotion-projects/pitch-promo",
      "node_modules_symlink_target": "C:\\Users\\deban\\dev\\remotion-node-cache\\pitch-promo\\node_modules"
    }
  ]
}
```

The write is guarded by `threading.Lock` (per workspace Python hardening rule #2)
in case the script is ever invoked concurrently.

## Exit Criteria

- `execution/video/remotion-projects/{slug}/` directory exists and contains `project.json`, `src/Root.tsx`, `src/CompositionWithAlpha.tsx`, `src/lib/easings.ts`, and `.template-version`.
- `execution/video/remotion-projects/{slug}/node_modules` is an NTFS junction (not a real directory) pointing to `C:\Users\deban\dev\remotion-node-cache\{slug}\node_modules`.
- Single-frame smoke-test render (`npx remotion render CompositionWithAlpha out/alpha_test.png --frame 0`) exits `0` and the PNG has mean brightness > 20 and dimensions 1920×1080.
- `execution/video/registry.json` contains an entry for the slug with `slug`, `fps`, `width`, `height`, `duration_in_frames`, and `template_version` all populated.
- `py execution/video/remotion_bootstrap.py --slug {slug} --dry-run` exits `0` and prints `would_create_project`, `would_create_junction`, and `would_write_registry_entry` as truthy without touching the filesystem.

## Edge Cases

| Case | Handling |
|---|---|
| Slug already in registry | Script exits 1: "Project {slug} already exists. Choose a different slug or delete the existing project." |
| `npx create-video@latest` hangs | Almost always caused by omitting `--yes`. Confirm the flag is present. Kill the subprocess after 120s timeout and exit 1. |
| `mklink /J` requires elevation | NTFS junctions do NOT require admin rights on Windows 10/11. If `mklink` fails with an access error, confirm the user is not running in a restricted shell. |
| `remotion-node-cache` path not writable | The preflight check (`/remotion preflight`) verifies this. Run preflight first. |
| `.template-version` SHA mismatch on re-bootstrap | The overlay's Root.tsx import paths may diverge from the new upstream template. Read the new `src/Scene.tsx` and update the overlay's `Root.tsx` import line before proceeding. |
| OneDrive syncs partial project before junction is created | The `node_modules` move + junction creation runs immediately after `create-video` finishes, before OneDrive has time to index. Pause OneDrive sync if node_modules appears in OneDrive activity. |
