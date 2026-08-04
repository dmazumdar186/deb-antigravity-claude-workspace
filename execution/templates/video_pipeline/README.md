# Video Pipeline Template

Reference scaffolding for professional-grade video production pipelines. Covers
the full loop: **analyze → generate → compose → publish** with the workspace's
mandatory audit stack baked in from day 1.

Scaffolded by `execution/templates/scaffold_video_pipeline.py`.

---

## Prior-art pass (per `~/.claude/rules/prior-art-first.md`)

Did the 10-minute pass before writing a line. Findings:

| Tool / Repo | What it does | Crib the pattern? | Why / why not |
|---|---|---|---|
| **OpusClip** (SaaS, closed) | Long→short auto-clipping, viral-score reranker | No | Closed source; the useful part (virality heuristics) is what `mcp__higgsfield__virality_predictor` already gives us. |
| **Cinemaker** (SaaS, closed) | Mobile-first AI editor, template-driven | No | Closed source; template model is already Remotion territory. |
| **Editframe** (React SDK) | Programmatic React → MP4 renderer | Superseded | Remotion is the workspace's chosen React-video runtime — same shape, richer ecosystem. |
| **Autoshorts.ai** / **Vidyo.ai** | Same segment as OpusClip | No | See OpusClip. |
| **yt-dlp + Whisper + Remotion** | Common OSS chain (many GitHub repos) | **Yes** | This is the de-facto shape of an OSS video pipeline. Analyze = yt-dlp+Whisper (or `youtube_video_analyzer.py`), compose = Remotion, publish = platform CLIs. |
| **BentoML / Modal video pipelines** | Cloud pipeline shape (job orchestration) | Partial | Modal is already in the workspace. The template stays local-first with a Modal escape hatch in `HANDOFF.md`. |
| **higgsfield.ai/mcp** | Multi-model gen aggregator, OAuth-only, 150 credits/mo free | **Yes — primary generation surface** | Already integrated in the workspace; MCP tool schemas load at runtime. |
| **HF Spaces (Wan-VACE, Chatterbox, ResembleAI/F5)** | €0 model hosting | **Yes — fallback for €0 dogfood** | Per `feedback_check_hf_spaces_first` — always check HF Space before paid infra. |

**Synthesis paragraph.** No existing "video-pipeline-in-a-box" OSS repo solves
the same shape. The de-facto pattern (yt-dlp + Whisper + Remotion + a publish
step) is what this template codifies, plus the workspace's audit discipline
(front-door synthetic, output-acceptance gate, `--dry-run`, EUR cost ceiling,
kill-switch). Higgsfield MCP is the generation primitive; Remotion is the
composition primitive; PySceneDetect + Claude/Gemini vision (via the existing
`youtube_video_analyzer.py`) is the analysis primitive. Nothing is invented
here — the template is a curated composition of prior-art primitives, all
already present in the workspace, wired to the audit stack.

---

## Loop overview

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  analyze.py │──▶│ generate.py │──▶│  compose/   │──▶│ publish.py  │
│ (understand │   │ (Higgsfield │   │ (Remotion + │   │ (TikTok/YT/ │
│  input)     │   │  MCP + HF)  │   │  three.js)  │   │  IG or manual)│
└─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘
       │                 │                 │                 │
       └──▶ manifest.json shared across stages, hash-cached on disk
```

Each stage:
- Is idempotent (hash-based caching under `.tmp/<slug>/`)
- Supports `--dry-run` (returns cost estimate + `would_*` counters, zero paid API calls)
- Logs to a shared `run_log.jsonl` with EUR cost, elapsed_ms, model, prompt
- Is independently testable (unit + integration + acceptance)

---

## Quickstart

```bash
# 1. Scaffold a new project from this template
py execution/templates/scaffold_video_pipeline.py --slug my_first_short

# 2. Cd into it
cd execution/personal_workflows/my_first_short_video/

# 3. Configure
cp .env.example .env
# edit .env — HIGGSFIELD_MCP is OAuth (interactive session), no key needed here

# 4. Dry-run (€0)
py analyze.py --input <youtube-url-or-file> --dry-run
py generate.py --plan .tmp/my_first_short/analysis.json --dry-run
cd compose && npm install && npx remotion render MainVideo out/preview.mp4

# 5. Live run (spends credits — respects config/pipeline.json daily_cost_ceiling_eur)
py analyze.py --input <url>
py generate.py --plan .tmp/my_first_short/analysis.json --live
cd compose && npx remotion render MainVideo out/final.mp4
py publish.py --video compose/out/final.mp4 --platforms tiktok,youtube --dry-run

# 6. Audit stack (see HARDENING.md for full flow)
py -m pytest tests/ -v
bash tests/front_door_video.sh
py tests/acceptance_video.py
```

---

## How to add a new composition

1. Add a new `.tsx` file under `compose/src/compositions/`.
2. Register it in `compose/src/Root.tsx` inside the `<Composition>` list.
3. Add an integration test in `tests/integration/` that renders a single frame
   of the new composition and asserts basic properties (non-zero file size,
   correct dimensions).
4. Update `config/pipeline.json` if the composition has different aspect ratio
   / duration defaults.

---

## How to swap the analysis LLM (Gemini vs Claude)

Default is **Gemini 2.5 Flash** (free tier, per `~/.claude/rules/model-tier.md`).
To swap:

```bash
py analyze.py --input <url> --provider anthropic --tier balanced
# or
py analyze.py --input <url> --provider gemini-direct   # default, explicit
```

Runtime provider resolution goes through `execution/modules/model_registry.py`
so the family stays fresh (auto-picks latest Gemini / Claude version).

---

## How to add a new publish target

1. Add a handler function to `publish.py`: `def _publish_<platform>(video_path, metadata) -> dict`.
2. Register it in the `PLATFORMS` dict at the top of `publish.py`.
3. Add a `<platform>_metadata.json` example under `config/publish_examples/`.
4. If the platform has an MCP integration (e.g. `mcp__higgsfield__tiktok_publish`),
   use it. Otherwise, emit a manual-publish bundle (renamed file + metadata JSON)
   under `.tmp/<slug>/publish/<platform>/`.

---

## How to monitor cost

Every generation logs to `.tmp/<slug>/run_log.jsonl`:

```json
{"ts":"2026-08-04T12:34:56Z","stage":"generate","model":"veo3_1_lite",
 "prompt":"...","cost_eur":0.37,"elapsed_ms":8420,"cache":"miss",
 "output":"/.tmp/my_first_short/assets/gen_a1b2c3.mp4"}
```

Kill switch: if the day's cumulative `cost_eur` for the slug exceeds
`config.pipeline.daily_cost_ceiling_eur` (default €5.00), the pipeline exits
with `DAILY_COST_CEILING_HIT`. Reset by editing the ceiling or waiting for the
next UTC day.

`spend_log.jsonl` at workspace level (`.tmp/video/spend_log.jsonl`) tracks
cross-slug spend for the operator's daily view.

---

## Audit stack (mandatory before "shipped")

See `HARDENING.md`. Six auditors must fire in one parallel batch:

1. **Front-door synthetic** — `bash tests/front_door_video.sh`
2. **Customer-POV acceptance** — `py tests/acceptance_video.py`
3. **Anneal audit** — `py -m anneal.cli classic --diff-file <patch> --repo <this>`
4. **Panel-pass 4-lens** — 4 real sub-agent spawns (not narration)
5. **Test suite** — `py -m pytest tests/ -v`
6. **Adversarial** — `py -m anneal.cli adversarial <base-ref>` OR pipeline-auditor sub-agent

Any single FAIL blocks the "shipped" claim. Log the combined verdict table in
`HARDENING.md` per `~/.claude/rules/mandatory-audit-stack.md`.
