#!/usr/bin/env python3
"""Compose the 12 Sūrya Namaskāra keyframes: cut-out figure on a dawn-sky plate, graded and grounded.
description: builds research/keyframes/dawn/frame-NN.jpg (1080x1440) from _raw_assets/cutouts_v3 + cutouts.json.
  Parameters at the top (rim, haze, shadow, grade) are the knobs; the plate is procedural (gradient + glow + grain).
inputs: --out DIR (default research/keyframes/dawn). outputs: frame-01..12.jpg, plate.jpg."""
# (starting point written by the brain 2026-10-26; the compositor worker iterates the knobs to an art-director GO)
