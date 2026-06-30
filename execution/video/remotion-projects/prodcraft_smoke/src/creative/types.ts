// Creative-scene schema for GLM-authored ProdCraft visuals.
//
// Each `CreativeScene` is a single section of the video. GLM 5.2 authors the
// raw inline SVG (the visual art) and a small JSON `timeline` of keyframes that
// the renderer interprets to animate the SVG over time.
//
// The SVG is rendered via `dangerouslySetInnerHTML`. A separate validator in
// the Python pipeline sanitizes the SVG before it ships into this Remotion
// project — strips <script>, on*= event handlers, <foreignObject>, <iframe>,
// <link>, <use href> with http(s) targets. The renderer treats whatever
// survives validation as trusted; the trust boundary lives in the validator.

export type AnimatableProperty =
  | "opacity"
  | "translateX"
  | "translateY"
  | "scale"
  | "rotate"
  | "stroke-dashoffset"
  | "stroke-dasharray"
  | "fill-opacity"
  | "stroke-opacity";

export type Easing = "linear" | "ease-in" | "ease-out" | "ease-in-out";

export type TimelineKeyframe = {
  // Absolute seconds within the scene (0-based — scene-relative, NOT video-absolute).
  t: number;
  // SVG element id to animate (must match an id="el-..." in the scene's svg).
  // Multiple keyframes can target the same id at different t.
  target: string;
  // Which CSS / SVG presentation property to interpolate.
  property: AnimatableProperty;
  // The target value at this keyframe. Strings allowed for stroke-dasharray
  // (e.g. "100 1000"); numbers for everything else. The renderer interpolates
  // from the PREVIOUS keyframe's value for the same (target, property), or
  // from a sensible initial (opacity:0, translate:0, scale:1, rotate:0) if
  // none.
  value: number | string;
  // Interp duration in seconds. The animation reaches `value` at t + duration_sec.
  // Default 0.4 if omitted.
  duration_sec?: number;
  // Easing curve. Default "ease-out".
  easing?: Easing;
};

export type CreativeScene = {
  // Kebab-case, unique across the plan.
  id: string;
  // Section title displayed in the chrome strip.
  title: string;
  // Scene start time (seconds, absolute within the audio).
  start_t: number;
  // Scene end time (seconds, absolute within the audio).
  end_t: number;
  // Raw inline SVG markup. Author-time freedom is unconstrained; load-time
  // sanitizer (Python side) strips scripts/handlers/foreignObject before this
  // ever reaches the renderer. Elements meant to be animated must carry
  // id="el-<slug>" so the timeline can target them.
  svg: string;
  // Optional 1-line on-screen hook for this scene (rendered as supporting
  // typography above or below the SVG). Empty string = no hook strip.
  hook?: string;
  // Ordered keyframes (renderer sorts by t but well-formed plans are already
  // sorted). Empty array = static SVG with no animation (rare; usually each
  // scene has at least an opacity:0->1 entry on its root group).
  timeline: TimelineKeyframe[];
};

export type CreativePlan = {
  doc_title: string;
  audio_duration_sec: number;
  scenes: CreativeScene[];
};

export type Word = { word: string; start: number; end: number };
