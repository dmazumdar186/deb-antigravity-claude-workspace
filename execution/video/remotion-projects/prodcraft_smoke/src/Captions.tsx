import React, { useMemo } from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import type { Word } from "./ProdCraftPhase1";

type Props = { words: Word[]; windowSize?: number };

const cleanWord = (w: string) => w.replace(/^[\s]+|[\s]+$/g, "");

export const Captions: React.FC<Props> = ({ words, windowSize = 6 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const tSec = frame / fps;

  const activeIdx = useMemo(() => {
    if (!words.length) return -1;
    let lo = 0;
    let hi = words.length - 1;
    let candidate = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      const w = words[mid];
      if (tSec < w.start) {
        hi = mid - 1;
      } else if (tSec > w.end) {
        candidate = mid;
        lo = mid + 1;
      } else {
        return mid;
      }
    }
    return candidate;
  }, [words, tSec]);

  if (activeIdx < 0) return null;

  const half = Math.floor(windowSize / 2);
  const start = Math.max(0, activeIdx - half);
  const end = Math.min(words.length, start + windowSize);
  const window = words.slice(start, end);

  return (
    <AbsoluteFill style={{ pointerEvents: "none", justifyContent: "flex-end" }}>
      {/* Thin caption strip at the very bottom edge -- low visual weight so it
          doesn't compete with on-canvas content. No pill, no border, smaller
          type. The audio carries the story; captions are accessibility, not
          decoration. */}
      <div
        style={{
          marginBottom: 32,
          display: "flex",
          justifyContent: "center",
          alignSelf: "center",
          backgroundColor: "rgba(11,18,32,0.85)",
          borderRadius: 12,
          padding: "8px 22px",
          maxWidth: 1400,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            flexWrap: "nowrap",
          }}
        >
          {window.map((w, i) => {
            const globalIdx = start + i;
            const isActive = globalIdx === activeIdx;
            return (
              <span
                key={`${globalIdx}-${w.w}`}
                style={{
                  color: isActive ? "#ffffff" : "rgba(220,228,240,0.6)",
                  fontFamily:
                    "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                  fontWeight: isActive ? 700 : 500,
                  fontSize: isActive ? 30 : 26,
                  letterSpacing: -0.2,
                  whiteSpace: "nowrap",
                }}
              >
                {cleanWord(w.w)}
              </span>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
