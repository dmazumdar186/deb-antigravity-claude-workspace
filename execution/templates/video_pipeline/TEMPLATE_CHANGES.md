# Template Changelog

Track material changes to `execution/templates/video_pipeline/`. Existing
scaffolded projects pin their template version in `.template-version` and do
NOT auto-upgrade (per the mobile-apps convention). Bump the version below on
any change that would break an existing project's assumptions.

---

## v0.1.0 — 2026-08-04 (phase-4d)

Initial scaffold.

- `analyze.py` — Gemini-default analysis stage, cribs from `execution/video/youtube_video_analyzer.py`.
- `generate.py` — Higgsfield-MCP + HF-Space-fallback generation stage with hash cache + EUR cost ceiling + kill switch.
- `compose/` — Remotion + @remotion/three project, one reference composition (`MainVideo`).
- `publish.py` — TikTok / YouTube / IG publish stage; falls back to manual-publish bundle when MCP unavailable.
- `config/pipeline.json` — aspect ratio, platforms, brand voice ref, daily EUR ceiling.
- `tests/{unit,integration,acceptance_video.py,front_door_video.sh}` — 4-tier test coverage.
- `.github/workflows/ci.yml` — unit + dry-run integration on push; acceptance behind `VIDEO_LIVE=1`.
- `HARDENING.md` + `HANDOFF.md` — audit-stack + operator-handoff scaffolds.
- Scaffolding CLI at `execution/templates/scaffold_video_pipeline.py`.

Known gaps documented in `HANDOFF.md`.
