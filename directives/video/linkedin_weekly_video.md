# Directive: ProdCraft weekly notes — one LinkedIn video a week

## Goal
Every week, one ~30 s code-rendered video plus its LinkedIn post for Debanjan's profile
(https://www.linkedin.com/in/dmazumdar/), in the "ProdCraft weekly notes · wk NN" series. Each episode
shows one real system ProdCraft built, so recruiters / agency owners / founders think "that is what he does".
Operator decision 2026-11-05: "from now on make such LinkedIn videos to post every week".

## Outputs (fixed contract)
- `deliverables/linkedin_videos/<slug>_<YYYY-MM-DD>/`: `prodcraft-wkNN-<slug>.mp4` (1080×1350, 30 fps, ~30 s,
  original score, no voice), `SCRIPT.md` (beats + post text + decisions), `FACTS.md` (every on-screen claim → source line),
  `film_src/` (index.html, main.js, mix.py, fonts.css).
  Not committed (regenerate before re-rendering): the woff2 font files referenced by `fonts/fonts.css` and `events.json` (written by the render step); `film_src/` alone does not reproduce the film.
- One line to the operator: episode number, title, path, gate status. The operator posts by hand; we never post.

## Inputs
- Topic: one shipped system from the last weeks of work (git log, `deliverables/`, `execution/`). No repeats of a
  previous episode's system (list them below). Prefer what the operator is selling now (recruiter outreach systems,
  lead-gen pipelines, client sites).
- Episode number: last `wk NN` in the log below + 1.

## Tools/Scripts
- `execution/video/linkedin_weekly_video_setup.sh` — idempotent toolkit setup (lemo-opuscar clone, npm, venv, CC0 packs, ffmpeg ≥7, env file).
- `execution/infrastructure/redteam_gate.py` (`/redteam`) — grounding + 4 lenses on post and on-screen text.
- lemo-opuscar `core/render/{still,readcheck,video}.mjs`, `core/audio/sampler.py`.

## Steps
1. `bash execution/video/linkedin_weekly_video_setup.sh && source /home/user/tools/lemo_env.sh` (idempotent; ~700 MB samples on a fresh container).
2. Fact sheet: a worker maps the system and writes a blocklist (client, people, employers, places, sector, URLs, internal names) to `.tmp/<slug>/system_facts.md`.
3. Script: hook → the counted funnel → the rule → what the user receives → payoff + offer → loop. Copy the beat grammar of the last episode's `SCRIPT.md`.
4. `/redteam` the post + on-screen text (draft in `.tmp/redteam/drafts/`), max 3 fix rounds; stop early when lens objections start contradicting each other and report the residual to the operator.
5. Render: copy the last episode's `film_src/` as the template; same look (paper #EFEDE6, ink, one gold accent, Newsreader + IBM Plex Mono, header `ProdCraft · wk NN`, footer `ProdCraft · weekly notes · NN`). Commands: `docs/reference/lemo_opuscar_toolchain.md` — `node core/render/video.mjs $F --size 1080x1350 --fps 30`, mix with `sampler.py` (vsco2ce + vcsl only, CC0), loudnorm −14 LUFS, set title/comment metadata.
6. QA: stills read by a worker (never the main context); frame 0 must show the full headline (LinkedIn thumbnail); grep film text against the blocklist (whole word) — zero hits.
7. Commit, push branch, merge to `main`, push `main`.

## Hard rules (learned in wk 03)
- Never name or hint at a client (name, city, country, sector, firm type); people appear only as "Candidate A/B/C" or similar.
- Never show code written inside a client engagement (no IP terms on record). Show the rule in plain words instead. Code from ProdCraft's own systems is fine.
- No client feedback quotes. Do not reproduce a client deliverable's wording.
- Never publish a rate or count that a client was given differently (wk 03: 25% first-run drop vs 0.9% later run). When in doubt, show the rule, not the rate.
- One number, one meaning per episode (wk 03: "148 claims" vs "148 profiles" confused every lens).
- No integration or free-work promises in the CTA; "my DMs are open" is the default.
- Credits line: "Made in code with lemo-opuscar (MIT) · music: original, CC0 samples (Versilian Studios)".

## Edge cases
- The redteam Bash hook refuses code-running commands that name a >2 MB file: run ffprobe/mux without the mp4 path inside python/sh, or call ffmpeg directly.
- System ffmpeg 6.1 breaks `mux.sh`; the setup script installs ffmpeg ≥7.
- No topic worth showing that week → render nothing and tell the operator; do not pad.

## Episode log
| wk | Date | System | Folder |
|---|---|---|---|
| 02 | 2026-10 | Reply triage for 800 sends/day (own outbound system) | (made locally) |
| 03 | 2026-11-05 | Evidence-checked candidate shortlist for recruiters | `deliverables/linkedin_videos/recruiter_outreach_2026-11-05/` |
