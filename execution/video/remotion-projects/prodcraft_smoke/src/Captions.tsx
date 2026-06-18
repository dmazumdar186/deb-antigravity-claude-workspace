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
      {/* Dark rounded pill that survives any background — even pure white frames. */}
      <div
        style={{
          marginBottom: 110,
          display: "flex",
          justifyContent: "center",
          alignSelf: "center",
          // Pill container
          backgroundColor: "rgba(8,12,22,0.78)",
          backdropFilter: "blur(2px)",
          border: "1.5px solid rgba(93,214,199,0.28)",
          borderRadius: 999,
          padding: "18px 36px",
          maxWidth: 1500,
          boxShadow:
            "0 6px 30px rgba(0,0,0,0.45), 0 0 0 1px rgba(255,255,255,0.05) inset",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 14,
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
                  color: isActive ? "#ffffff" : "rgba(220,228,240,0.55)",
                  fontFamily:
                    "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                  fontWeight: isActive ? 800 : 600,
                  fontSize: isActive ? 50 : 42,
                  letterSpacing: -0.4,
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
