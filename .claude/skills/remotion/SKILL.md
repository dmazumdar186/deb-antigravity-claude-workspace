---
name: remotion
user_invocable: true
description: |
  Author, preview, and render Remotion motion-graphics compositions with
  @remotion/three (React Three Fiber) baked in. Directives live in
  directives/video/remotion_*.md; execution scripts in execution/video/.

  Triggers on: "remotion", "/remotion", "animated video", "motion graphics",
  "alpha overlay for davinci", "3d video with three.js",
  "render video from react", "make a video in remotion",
  "new remotion project".

  Sub-commands: preflight, new {slug}
---

# Remotion

Orchestrates the workspace's Remotion video pipeline. Directives live in
`directives/video/`, execution scripts in `execution/video/`, and per-project
source trees at `execution/video/remotion-projects/{slug}/`. Registry of all
projects: `execution/video/registry.json`.

## Always run preflight first

Before any `new` command, run preflight. If preflight is red, stop and show the
user exactly what to fix. Never proceed past a red preflight without explicit
user override.

## Sub-commands

Parse the user's invocation as `/remotion <subcmd> [args]`. Default to
`preflight` if no subcommand was given.

---

### `preflight`

Check that the local environment is ready to create and render Remotion
projects. Run all checks with Bash; do NOT spawn a sub-agent for preflight —
these are short commands.

#### Check 1 — Node.js version

```bash
node --version
```

Required: v18.0.0 or higher. Block all further steps if older:

> "Node.js {version} is below the minimum v18 required by Remotion. Upgrade:
> https://nodejs.org/en/download"

#### Check 2 — npx available

```bash
npx --version
```

`npx` ships with Node.js 18+. If missing, the Node install is corrupted —
reinstall Node.

#### Check 3 — Remotion version (confirms compositor native binary)

Run `npx remotion --version` inside an existing project directory (any project
from `execution/video/remotion-projects/`). If no project exists yet, create a
temporary probe:

```bash
# Only if no project exists yet
cd C:\Users\deban\dev\remotion-node-cache
mkdir _probe_tmp
cd _probe_tmp
npm init -y
npm install remotion @remotion/cli --prefer-offline 2>nul
npx remotion --version
cd ..
rmdir /s /q _probe_tmp
```

What this confirms: `@remotion/compositor-win32-x64-msvc` (the native render
binary) is installed and loadable. A missing or mismatched native binary causes
silent render failures. This is NOT the same as `imageio-ffmpeg` — Remotion
bundles its own compositor.

Expected output: a semver string such as `4.0.xx`. Any version is acceptable —
we are not pinned to a specific release.

If the binary fails to load (error mentions `compositor-win32-x64-msvc` or
`NAPI`), print:
> "The Remotion native binary is not loadable. Try: npm install --force inside
> the project directory, or re-run /remotion new {slug} to scaffold a fresh
> project."

#### Check 4 — Chromium browser

```bash
npx remotion browser ensure
```

Downloads the bundled Chromium instance (~150-300 MB) that Remotion uses for
headless rendering. This is a one-time download per machine; subsequent calls
are instant if Chromium is already present.

Run this even if Chromium appears present — the command is idempotent and
exits quickly if already downloaded. Skipping this step causes first-render
timeout surprises on slow connections or corporate proxies.

#### Check 5 — node-cache path writable

```bash
# PowerShell
$path = "C:\Users\deban\dev\remotion-node-cache"
if (!(Test-Path $path)) { New-Item -ItemType Directory -Path $path | Out-Null }
$testFile = "$path\_preflight_test"
Set-Content -Path $testFile -Value "ok"
Remove-Item $testFile
Write-Host "node-cache writable: OK"
```

If this fails, the `node_modules` junction cannot be created. Fix permissions
on `C:\Users\deban\dev\` before proceeding.

#### Preflight report

Print a summary:

```
Remotion Preflight
==================
Node.js        v22.x.x   OK
npx            10.x.x    OK
Remotion       4.0.xx    OK  (@remotion/compositor-win32-x64-msvc confirmed)
Chromium       present   OK  (downloaded / already present)
node-cache     writable  OK  (C:\Users\deban\dev\remotion-node-cache\)
```

All green → "Preflight passed. Run /remotion new {slug} to scaffold a project."

Any red → list the failing check and stop. Do not proceed to `new`.

---

### `new {slug}`

Scaffold a new Remotion project with `@remotion/three` wired in, apply the
workspace overlay, and register it.

**The slug** must be lowercase alphanumeric + hyphens, max 50 characters.
If the user did not provide a slug, ask: "What slug (short identifier) do
you want for this project? e.g. `pitch-promo`, `product-launch`"

#### Step 1 — Run preflight

Run `/remotion preflight` first (see above). Abort on any red check unless
the user explicitly overrides.

#### Step 2 — Invoke bootstrap script

```bash
py execution/video/remotion_bootstrap.py --slug {slug}
```

For a dry-run preview (no filesystem changes):

```bash
py execution/video/remotion_bootstrap.py --slug {slug} --dry-run
```

The script will:
1. Validate the slug (path-traversal guard)
2. Create `C:\Users\deban\dev\remotion-node-cache\{slug}\`
3. Run `npx create-video@latest {slug} --yes --three` in
   `execution/video/remotion-projects/`
4. Move `node_modules` to the cache and create an NTFS junction
5. Apply the workspace overlay from
   `execution/video/remotion_template_overlay/` (overwrites `src/Root.tsx`)
6. Write a registry entry to `execution/video/registry.json`

**Critical flag:** `--yes --three` (not `--template three`). The `--three` flag
is a boolean `cliId` in `create-video`'s `select-template.js`. Without `--yes`,
the subprocess hangs waiting for stdin.

#### Step 3 — Confirm and surface next steps

After the script exits 0:

1. Confirm the project directory exists:
   `execution/video/remotion-projects/{slug}/`
2. Confirm the junction target exists:
   `C:\Users\deban\dev\remotion-node-cache\{slug}\node_modules\`
3. Confirm registry entry written:
   `execution/video/registry.json` has `{slug}` in `projects`

Then suggest next steps:

```
Project {slug} scaffolded.

Next steps:
1. Start Studio:
   cd execution\video\remotion-projects\{slug}
   npx remotion studio

2. Open http://localhost:3000 — you should see the torus knot (Scene)
   and the alpha gradient (CompositionWithAlpha) in the left panel.

3. Toggle the checkered-background button (top-right of the canvas)
   on CompositionWithAlpha to confirm alpha transparency works.

4. Drop assets into assets/ — voice.mp3, music.mp3, images.
   Edit src/script.md with your scene timing marks.
   Then ask Claude Code to author a composition.

Read directives/video/remotion_authoring.md for frame-math patterns.
Read directives/video/remotion_three.md for 3D scene authoring.
Read directives/video/remotion_render.md for render commands.
```

---

## When NOT to use this skill

- Math / diagram / equation animations — use [Manim](https://www.manim.community/) instead.
  Remotion is React-based; Manim has LaTeX/MathTeX rendering and scene-graph
  manipulation built in.
- Existing native After Effects / Motion Graphics projects — Remotion is not an
  AE import target.
- Production Lambda render (>3 dev seats) — requires a Remotion company license.
  Out of scope for v1. Use local render.

## Common follow-up tasks

After scaffolding, the user may want to:
- **Author a composition** — read `directives/video/remotion_authoring.md`,
  create `src/{CompositionName}.tsx`, register in `Root.tsx`
- **Add a 3D scene** — read `directives/video/remotion_three.md`,
  add `<ThreeCanvas gl={{alpha: true}}>` inside the composition
- **Render** — read `directives/video/remotion_render.md` for exact CLI flags
  for ProRes 4444 alpha, WebM-alpha, or H.264 MP4

## Directives reference

| Directive | Purpose |
|---|---|
| `directives/video/remotion_authoring.md` | Frame math, composition structure, Spring/interpolate patterns, Root.tsx registration |
| `directives/video/remotion_three.md` | `@remotion/three` rules — `<ThreeCanvas>`, `useCurrentFrame()` in R3F, video-as-texture |
| `directives/video/remotion_render.md` | Render CLI commands — ProRes 4444, WebM-alpha, H.264 |
| `directives/video/remotion_bootstrap.md` | Bootstrap protocol — why we use `--yes --three`, what the overlay adds, junction mechanics |
