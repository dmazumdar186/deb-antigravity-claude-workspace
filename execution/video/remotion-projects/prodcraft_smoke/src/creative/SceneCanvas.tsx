import React, { useLayoutEffect, useMemo, useRef } from "react";
import { Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import type { AnimatableProperty, CreativeScene, Easing as EasingName, TimelineKeyframe } from "./types";

// Initial values used when a property has no prior keyframe at a given target.
// These match the "neutral identity" of each property so missing-keyframe paths
// don't snap the element into an unexpected pose.
const INITIAL: Record<AnimatableProperty, number | string> = {
  opacity: 1,
  translateX: 0,
  translateY: 0,
  scale: 1,
  rotate: 0,
  "stroke-dashoffset": 0,
  "stroke-dasharray": "none",
  "fill-opacity": 1,
  "stroke-opacity": 1,
};

const EASING_FN: Record<EasingName, (n: number) => number> = {
  linear: Easing.linear,
  "ease-in": Easing.in(Easing.cubic),
  "ease-out": Easing.out(Easing.cubic),
  "ease-in-out": Easing.inOut(Easing.cubic),
};

// Group keyframes by (target, property) and ensure each list is t-sorted.
const indexTimeline = (timeline: TimelineKeyframe[]) => {
  const buckets = new Map<string, TimelineKeyframe[]>();
  for (const kf of timeline) {
    const key = `${kf.target}::${kf.property}`;
    const list = buckets.get(key) ?? [];
    list.push(kf);
    buckets.set(key, list);
  }
  for (const list of buckets.values()) {
    list.sort((a, b) => a.t - b.t);
  }
  return buckets;
};

// Resolve a single (target, property) to its current numeric/string value at
// scene-relative time `t`. Strings only interpolate as raw strings (we step,
// not interpolate) — used for stroke-dasharray where component arithmetic is
// ambiguous.
const resolveProperty = (
  list: TimelineKeyframe[],
  property: AnimatableProperty,
  t: number,
): number | string => {
  if (list.length === 0) return INITIAL[property];

  // Before the first keyframe: hold initial value.
  if (t < list[0].t) return INITIAL[property];

  // Find the active segment.
  for (let i = 0; i < list.length; i++) {
    const cur = list[i];
    const duration = cur.duration_sec ?? 0.4;
    const segmentEnd = cur.t + duration;
    const from =
      i === 0
        ? INITIAL[property]
        : list[i - 1].value;

    if (t < cur.t) {
      // Between previous keyframe's end and this keyframe's start — hold prev value.
      return from;
    }

    if (t <= segmentEnd) {
      // Interpolating this keyframe.
      const easing = EASING_FN[cur.easing ?? "ease-out"];
      const progress = (t - cur.t) / Math.max(duration, 1e-6);
      const eased = easing(Math.min(1, Math.max(0, progress)));
      if (typeof from === "number" && typeof cur.value === "number") {
        return interpolate(eased, [0, 1], [from, cur.value]);
      }
      // String values: step to target at segment end, otherwise stay at from.
      return eased >= 1 ? cur.value : from;
    }
  }

  // Past the last keyframe: hold final value.
  return list[list.length - 1].value;
};

const applyToElement = (
  el: SVGElement,
  property: AnimatableProperty,
  value: number | string,
  transformAccum: Record<string, number>,
) => {
  switch (property) {
    case "opacity":
      el.style.opacity = String(value);
      break;
    case "fill-opacity":
      el.setAttribute("fill-opacity", String(value));
      break;
    case "stroke-opacity":
      el.setAttribute("stroke-opacity", String(value));
      break;
    case "stroke-dashoffset":
      el.setAttribute("stroke-dashoffset", String(value));
      break;
    case "stroke-dasharray":
      el.setAttribute("stroke-dasharray", String(value));
      break;
    case "translateX":
      transformAccum.tx = Number(value) || 0;
      break;
    case "translateY":
      transformAccum.ty = Number(value) || 0;
      break;
    case "scale":
      transformAccum.s = Number(value) || 1;
      break;
    case "rotate":
      transformAccum.r = Number(value) || 0;
      break;
  }
};

type Props = {
  scene: CreativeScene;
  width: number;
  height: number;
};

// Renders ONE creative scene: dangerouslySetInnerHTML the (already-sanitized)
// SVG, then on every frame walk the timeline and apply transforms/opacity to
// the elements by id. We do this imperatively (refs + DOM mutation) rather
// than re-rendering React on every frame, because Remotion already runs us
// per-frame and rebuilding the SVG tree each tick would tank render perf.
export const SceneCanvas: React.FC<Props> = ({ scene, width, height }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const buckets = useMemo(() => indexTimeline(scene.timeline), [scene.timeline]);

  // Scene-relative time. The composition sequences scenes so each instance
  // sees frame 0 at its own start_t — but we still subtract defensively in
  // case the parent renders all scenes at once.
  const t = frame / fps;

  useLayoutEffect(() => {
    const root = containerRef.current;
    if (!root) return;

    // Gather every animated element id mentioned in the timeline.
    const ids = new Set<string>();
    for (const kf of scene.timeline) ids.add(kf.target);

    // Per-element transform accumulator: tx, ty, s, r combine into one transform attribute.
    for (const id of ids) {
      const el = root.querySelector<SVGElement>(`#${CSS.escape(id)}`);
      if (!el) continue;

      const accum: Record<string, number> = { tx: 0, ty: 0, s: 1, r: 0 };

      const props: AnimatableProperty[] = [
        "opacity",
        "fill-opacity",
        "stroke-opacity",
        "stroke-dashoffset",
        "stroke-dasharray",
        "translateX",
        "translateY",
        "scale",
        "rotate",
      ];
      for (const property of props) {
        const list = buckets.get(`${id}::${property}`);
        if (!list) continue;
        const value = resolveProperty(list, property, t);
        applyToElement(el, property, value, accum);
      }

      const transformParts: string[] = [];
      if (accum.tx !== 0 || accum.ty !== 0) {
        transformParts.push(`translate(${accum.tx}, ${accum.ty})`);
      }
      if (accum.r !== 0) {
        transformParts.push(`rotate(${accum.r})`);
      }
      if (accum.s !== 1) {
        transformParts.push(`scale(${accum.s})`);
      }
      const xform = transformParts.join(" ");

      // Use the `transform` attribute (SVG, not CSS) because some SVG attrs
      // (e.g. stroke-dasharray) don't combine with CSS transforms cleanly
      // across rendering backends.
      if (xform) {
        el.setAttribute("transform", xform);
      } else {
        el.removeAttribute("transform");
      }
    }
  }, [t, scene.timeline, buckets]);

  return (
    <div
      ref={containerRef}
      style={{
        width,
        height,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
      dangerouslySetInnerHTML={{ __html: scene.svg }}
    />
  );
};
