# Panel lens 2 — Boris Cherny (tooling craft)

**Verdict: PASS with directive fixes.** The test harness is scripted, deterministic and secret-free (43/43 reproduced in a fresh shell). A fresh session could not rebuild the photo frames from the directive alone, and it would not know how to serve the site.

## Findings
1. **functional.mjs reproduces.** `node research/serve_csp.mjs site 8794 & node research/functional.mjs http://localhost:8794/` gives `43/43 passed`, with /api mocked (functional.mjs:6). The directive says "40 assertions" (jeevana_site.md:24) and its step 2 runs `node research/functional.mjs` with no URL or server (jeevana_site.md:38). Run bare, the script exits 2 (functional.mjs:9). Fix: put the serve + URL command into step 2 and change the count to 43, or say "N/N".
2. **screens.mjs has the same gap.** It needs a base URL (screens.mjs:3), but step 3 calls it bare (jeevana_site.md:39).
3. **The ingest command is not reproducible.** Step `--sequence sn-01=…` is elided (jeevana_site.md:21). The manifest also records `zoom: 1.3` on sn-03 and sn-10, and neither photos.md nor the directive mentions `--zoom`. A re-run from the docs would silently drop that crop. Fix: write the full command into photos.md, including `--zoom` and any `--focus`.
4. **The sequence map matches.** All 12 `src` values in manifest.json equal photos.md:8-19, including the documented reuse (05/08, 03/10, 02/11).
5. **`--help` works.** The usage text is complete, and the docstring states that the focus estimate is deterministic (ingest_photos.py:5-13).
6. **Every named path exists.** That covers the skill scripts (gen_backdrop.py, render_hero_video.mjs, site_check.mjs, deploy.sh), `functions/api/{subscribe,register,export}.ts` plus `_lib.ts`, and the KV id in wrangler.toml. `_raw_assets` is gitignored, as the directive claims (22 files).
7. **Path base is ambiguous.** Steps 2-3 use `research/...`, which is relative to the deliverable. Steps 2 and 4 use `.claude/skills/...`, which is relative to the repo root. The directive needs one stated cwd.
8. **Secrets step is fine.** Step 5 is idempotent (`secret put` overwrites), but it is narrated as "once" with no check. `wrangler pages secret list` would make it verifiable.

## Honest gaps
- I did not run site_check.mjs, screens.mjs (PNG output not read), deploy.sh, the ingest re-run (I did not compare its output byte-for-byte), or the Functions (no wrangler dev, and KV and the secrets are absent).
- I did not check that functional.mjs is stable across repeated runs (one run only).
