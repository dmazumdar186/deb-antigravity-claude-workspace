// lib/motion.ts
// description: Pure scroll-scrub math for the hero / folio / drum motion
//   effects. The TECHNIQUE (section scroll progress -> per-element state) is
//   ported from a reference exhibit site's vanilla JS; the numbers below are
//   re-derived, not copied. No DOM access and no dependencies here — this is
//   consumed by the client-only components/MotionController.tsx, which reads
//   getBoundingClientRect() and writes the results back as CSS custom
//   properties (rAF-scheduled, passive scroll listener — see that file).
// inputs: plain numbers (scroll positions, rects, indices)
// outputs: plain numbers/objects describing where an element should sit

export function clamp01(value: number): number {
  return Math.min(1, Math.max(0, Number(value) || 0));
}

export interface ProgressRect {
  top: number;
  height: number;
}

/** 0..1 progress through a tall section as it scrolls past a sticky viewport. */
export function sectionProgress(rect: ProgressRect, viewportHeight: number): number {
  const range = Math.max(rect.height - viewportHeight, 1);
  return clamp01(-rect.top / range);
}

/** Which of `count` steps is "active" at a given 0..1 progress. */
export function activeStepIndex(progress: number, count: number): number {
  if (count <= 1) return 0;
  return Math.min(count - 1, Math.floor(clamp01(progress) * count));
}

export interface FolioCardState {
  xPercent: number;
  yPercent: number;
  rotationDeg: number;
  scale: number;
  opacity: number;
  captionOpacity: number;
  zIndex: number;
}

/**
 * Fans a stacked folio card out and away as the sticky section's progress
 * carries it past its "turn". Cards below the current position sit in a
 * shallow, receding stack (small offset/scale/opacity falloff by depth);
 * once progress reaches a card's turn it exits diagonally (alternating
 * left/right by index parity) while fading and losing its caption.
 */
export function folioCardState(progress: number, index: number, count: number): FolioCardState {
  const position = clamp01(progress) * Math.max(count - 1, 0);
  const offset = index - position;
  const direction = index % 2 === 0 ? 1 : -1;
  const exit = clamp01((-offset - 0.08) / 0.82);
  const depth = Math.max(0, Math.min(4, offset));
  return {
    xPercent: exit > 0 ? direction * 36 * exit : direction * depth * 2.8,
    yPercent: exit > 0 ? -76 * exit : depth * 3.2,
    rotationDeg: exit > 0 ? direction * 3.5 * exit : direction * depth * 0.8,
    scale: exit > 0 ? 1 - 0.03 * exit : Math.max(0.9, 1 - depth * 0.028),
    opacity: exit > 0 ? 1 - 0.96 * exit : Math.max(0.58, 1 - depth * 0.1),
    // The front card keeps legible text until it actually exits (text-only cards have no
    // imagery to carry them, so a midpoint fade-to-zero read as a blank stage); deeper cards
    // dim by depth but never below 0.35.
    captionOpacity: exit > 0 ? 1 - exit : Math.max(0.35, 1 - depth * 0.35),
    zIndex: count - index,
  };
}

export interface DrumStepState {
  isActive: boolean;
  rotationX: number;
  yPercent: number;
  scale: number;
  opacity: number;
}

/**
 * Rotates a numbered step through a small vertical "drum" window: the active
 * step sits flat and centered, neighbors tilt away in 3D (rotateX) and fade
 * with distance, like a flip-clock digit wheel.
 */
export function drumStepState(progress: number, index: number, count: number): DrumStepState {
  const position = Math.min(Math.max(count - 1, 0), clamp01(progress) * count);
  const offset = index - position;
  const activeIndex = activeStepIndex(progress, count);
  return {
    isActive: index === activeIndex,
    rotationX: Math.max(-84, Math.min(84, offset * 62)),
    yPercent: Math.max(-130, Math.min(130, offset * 94)),
    scale: Math.max(0.78, 1 - Math.abs(offset) * 0.12),
    opacity: Math.max(0, 1 - Math.abs(offset) * 1.35),
  };
}

export interface HeroFrame {
  stateIndex: number;
  fill: number[];
}

/**
 * Maps the hero section's own 0..1 scroll progress to the active copy/state
 * index (0..stateCount-1) and each step-rail item's --fill (0..1). `fill[i]`
 * reaches 1 once progress has carried past step i, so the rail fills up
 * left-to-right as the hero scrubs, matching `stateIndex` one step behind
 * the last fully-filled rail item.
 */
export function heroFrame(progress: number, stateCount: number): HeroFrame {
  const p = clamp01(progress);
  const last = Math.max(stateCount - 1, 0);
  const t = p * last;
  const stateIndex = Math.min(last, Math.round(t));
  const fill = Array.from({ length: stateCount }, (_, i) => clamp01(t - i));
  return { stateIndex, fill };
}
