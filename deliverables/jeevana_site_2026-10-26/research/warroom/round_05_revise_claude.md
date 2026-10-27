# Round 5 revise by anthropic/claude-opus-5.5

Strip rebuilt on one pixel coordinate system. JS measures the track, sets the card width and the centring padding in px, and recomputes them on resize. The column count and peek follow the orientation matrix. Card width is capped by the viewport height minus a caption allowance, so phone landscape keeps 3:4 photos with the caption underneath; the split-card layout is gone.

Strip behaviour:
- go() sets the active card immediately and blocks scroll-readback until the scroll settles, so arrows, keys, the progress ring and both backdrop arcs stay in sync.
- Prev/Next use aria-disabled instead of disabled, so they stay clickable.
- Autoplay loops and pauses on hover/focus of the strip and arrows (not the play button), off-screen tabs, drag and reduced motion.

Other fixes:
- Fast scroll (>140 px per frame) reveals arriving content instantly.
- Touch devices get a 44Ã44 checkbox hit area with a 20 px visible box.
- Honeypots are visibility:hidden, not enlarged.
- Errors are linked to their fields with aria-describedby.
- Chips no longer sit over the body: hero chip top-left, practice captions below the frames, Paris chip below its frame.
- Removed the fixed caption min-heights.
- Fixed the invalid JSON-LD.
- aria-roledescription is localised.

Open items (outside these files):
- screens_v4.mjs still needs its missing selector fixed.
- The OG 1200Ã630 image needs generating; it currently points to hero@1400.
- Gates and both eye-review rounds must be rerun before any preview.
- The design credit stays in English, verbatim per the brief.

Files: site/index.html (41235 B), site/css/styles.css (34751 B), site/js/main.js (13173 B), site/js/i18n.js (18995 B)

Usage: {'prompt_tokens': 83855, 'completion_tokens': 72016, 'total_tokens': 155871, 'cost': 1.77574, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 1.77574, 'upstream_inference_prompt_cost': 0.33542, 'upstream_inference_completions_cost': 1.44032}, 'completion_tokens_details': {'reasoning_tokens': 19504, 'image_tokens': 0, 'audio_tokens': 0}, 'wall_s': 528.6, 'gen': 'gen-1793096625-bpbuLqWIQD2XJZRsaVCx', 'finish': 'stop'}
