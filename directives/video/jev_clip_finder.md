# Jev Clip Finder

## Purpose

Turn one long recording (podcast, interview, webinar) into a short list of the moments worth
posting as shorts. Jev scores every ~30 s candidate window for hook, value, standalone sense
and clip type in one typed call each (hundreds of candidates in seconds, fractions of a cent),
then code ranks, dedupes and returns the top N. RoboNuggets "19 Jev use cases" #4.

## When to invoke

- Operator prompt: "Find the 10 best short clips in <transcript/video>".
- Any long-form recording that needs a shortlist before editing (e.g. before `prodcraft_shorts_pipeline.md`).

## Inputs

- `--transcript`: path — `.srt`, `.vtt`, `.json` (`[{start, end, text}]`, seconds, or `{"segments": [...]}`),
  or plain text with `[mm:ss]` / `[hh:mm:ss]` markers.
- `--youtube`: URL — fetches auto-subs with `yt-dlp --write-auto-sub --skip-download` into `.tmp/jev_clips/`.
  Exits 2 with a message if yt-dlp is missing or blocked (always the case in cloud sessions; download
  the captions locally and pass `--transcript`).
- `--window 30 --stride 15` seconds; windows extend up to 1.5x to end on a sentence boundary.
- `--min-words 20`, `--top 10`, `--workers 8`, `--limit N` (test on a few), `--dry-run` (windows only, no API).
- `--weights hook,value,self_contained` (default `0.4,0.4,0.2`, auto-normalised).
- env `OPENROUTER_API_KEY` (or `OPENROUTER_API_TOKEN` / `OPENROUTER_API_TOEKN`).

## Outputs

- `--output` JSON (default `<input>.clips.json`): top clips with start/end, text, hook (0-3), value (0-3),
  self_contained (0-1), clip_type, score (0-1).
- `--md` markdown shortlist (`mm:ss–mm:ss`, type, score, first 120 chars); `--csv-out` CSV.
- stdout summary (candidates, wall time, cost); ledger row `caller: jev_clip_finder` in `.tmp/jev_ledger.jsonl`.

## Weights tuning

- Composite = `w_hook*hook/3 + w_value*value/3 + w_sc*self_contained`, normalised to 0-1.
- Hook-driven feeds (TikTok/Reels): `0.5,0.3,0.2`. Educational/LinkedIn: `0.3,0.5,0.2`.
  Raise `self_contained` (e.g. `0.35,0.35,0.3`) if picks start mid-thought.
- Windows that open with filler still score well if the payoff lands inside; trim the opening in the editor,
  or lower `--stride` (e.g. 10) for tighter start points at more calls.

## Exit Criteria (declarative — read this before claiming "done")

- Output JSON exists with `len(clips) == min(--top, deduped candidates)` and `errors < candidates`.
- No two returned clips overlap by more than 50% of the shorter clip.
- Markdown shortlist exists if `--md` was given; ledger row appended.

## Scripts (Layer 3)

- `execution/video/jev_clip_finder.py` (client: `execution/modules/jev_client.py`)
- Tests: `tests/test_jev_clip_finder.py`

## Edge cases

- Jev call fails → that candidate is dropped (fail open); all fail → exit 1 with the first error.
- VTT auto-subs repeat rolling lines → consecutive duplicate cues are merged.
- Plain text has no end times → each segment ends at the next marker.
- No candidates (short transcript / high `--min-words`) → exit 2.
- Cost: ~$0.00003 per candidate (8-min sample: 18 candidates ≈ $0.0005, ~2 s).

## Changelog

- 2026-10-06: Created (use case 4). Live run on a synthetic 8-minute interview (28 candidates, 2.6 s, $0.0008) ranked three of four planted strong moments top 5; the how-to was pushed out by a 50%-overlap near-duplicate (dedupe drops only >50%).
- 2026-10-06: overlap dedupe is now >= 50% (a 50/50 duplicate story made the top 5).
