import { spring, interpolate, type SpringConfig } from "remotion";

// ---------------------------------------------------------------------------
// Named spring presets
// ---------------------------------------------------------------------------

export const SPRINGS = {
  /** Fast, crisp entrance — good for UI elements popping in. */
  snappy: { damping: 200, stiffness: 300, mass: 0.5 } satisfies Partial<SpringConfig>,
  /** Smooth, unhurried — good for background reveals and scale-ups. */
  gentle: { damping: 30, stiffness: 100, mass: 1 } satisfies Partial<SpringConfig>,
  /** Overshoots slightly — good for playful icons and emoji. */
  bouncy: { damping: 12, stiffness: 200, mass: 1 } satisfies Partial<SpringConfig>,
  /** Slow and weighty — good for hero text or large product shots. */
  heavy: { damping: 40, stiffness: 60, mass: 2 } satisfies Partial<SpringConfig>,
} as const;

// ---------------------------------------------------------------------------
// Cubic easing helpers
// ---------------------------------------------------------------------------

/** Smooth-step: ease-in-out in [0, 1]. */
export const easeInOut = (t: number): number => t * t * (3 - 2 * t);

/** Ease-in only (accelerate from zero). */
export const easeIn = (t: number): number => t * t;

/** Ease-out only (decelerate to zero). */
export const easeOut = (t: number): number => t * (2 - t);

// ---------------------------------------------------------------------------
// Opacity helpers
// ---------------------------------------------------------------------------

/**
 * Fade in from 0 → 1 over `durationSec` seconds, starting at `frame`.
 *
 * @example
 *   const opacity = fadeIn(frame, fps, 0.4); // fade in over 0.4 s
 */
export const fadeIn = (
  frame: number,
  fps: number,
  durationSec: number,
  delayFrames = 0,
): number =>
  interpolate(
    frame,
    [delayFrames, delayFrames + durationSec * fps],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

/**
 * Fade out from 1 → 0 over `durationSec` seconds, starting at `startFrame`.
 *
 * @example
 *   const opacity = fadeOut(frame, fps, 60, 0.3); // start fading at frame 60 over 0.3 s
 */
export const fadeOut = (
  frame: number,
  fps: number,
  startFrame: number,
  durationSec: number,
): number =>
  interpolate(
    frame,
    [startFrame, startFrame + durationSec * fps],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

// ---------------------------------------------------------------------------
// Spring-driven slide helper
// ---------------------------------------------------------------------------

/**
 * Returns a Y-offset (pixels) that springs from `fromY` → 0.
 * Use as `transform: \`translateY(${slideUp(frame, fps)}px)\``.
 *
 * @example
 *   const y = slideUp(frame, fps, 40); // slides up 40 px
 */
export const slideUp = (
  frame: number,
  fps: number,
  fromY = 60,
  config: Partial<SpringConfig> = SPRINGS.snappy,
): number => {
  const progress = spring({ frame, fps, config });
  return interpolate(progress, [0, 1], [fromY, 0]);
};
