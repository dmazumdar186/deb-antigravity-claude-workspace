# youtube_video_analyzer.py — Workspace-Side Notes

Wrapper script at `execution/video/youtube_video_analyzer.py` delegates to the public repo
at `C:\Users\deban\dev\youtube-video-analyzer\`. These notes cover workspace-side integration
quirks; see the repo's own notes for internal implementation details.

- [technical] yt-dlp rate-limit: yt-dlp will back off with HTTP 429 when multiple URLs are
  downloaded in quick succession. Batch mode (`--urls-file`) sleeps 2–5 s between downloads
  (configurable). Do NOT reduce the inter-URL delay below 2 s — YouTube detects the pattern.
  If 429 persists, rotate the `--cookies-from-browser` source or add a longer delay.

- [technical] PySceneDetect Windows install: `pip install scenedetect[opencv]` is required
  (not plain `scenedetect`). The OpenCV binding is a separate optional dep that is NOT pulled
  in by the base package on Windows. Without it, scene detection silently falls back to
  fixed-interval frame sampling, producing far fewer scene cuts and lower-quality frame grids.
  Verify install: `py -c "import scenedetect; from scenedetect.detectors import ContentDetector"`.

- [technical] Creator-profile cache TTL: creator profiles are cached to `.tmp/creator_profiles/`
  with a default TTL of 30 days. If a creator has rebranded or shifted content style, delete
  the cache file to force a refresh. File naming: `{channel_slug}.json`. TTL is configurable
  via `--profile-ttl-days` flag.

- [pattern] Gemini-free path: use `--provider gemini` + `GEMINI_API_KEY` for zero-credit
  frame analysis. Gemini 2.0 Flash handles the 3×3 frame grids well. Recommended for bulk
  batch jobs where Anthropic token spend matters.

- [constraint] PySceneDetect memory: on Windows with large videos (>30 min, 1080p), PySceneDetect
  may OOM during frame extraction. Workaround: pass `--max-duration 600` to limit processing
  to the first 10 minutes, or downsample with `--resolution 480`.

- [learned] Batch mode threading: as of v4 (2026-05-18), batch mode is still sequential.
  Adding `ThreadPoolExecutor(max_workers=2)` is the planned upgrade (INDEX row 32), capped
  low due to yt-dlp rate limits. If parallelism is added, a `threading.Lock` on
  creator-profile cache writes is required.

## See also

- C:\Users\deban\dev\youtube-video-analyzer\ (actual repo)
- .claude/upgrades/other_categories.md (audit findings)
- .claude/upgrades/external/youtube_video_analyzer.md (full audit card)
