import React from "react";
import { AbsoluteFill, Audio, Sequence, useVideoConfig } from "remotion";
import { SceneCanvas } from "./SceneCanvas";
import { Captions } from "../Captions";
import { BrandBookends } from "../living-prd/BrandBookends";
import type { CreativePlan, Word } from "./types";

const ACCENT = "#1c8b7c";
const BG_TOP = "#fafbfd";
const BG_BOTTOM = "#eef1f7";
const FONT = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
const SUBTITLE_COLOR = "rgba(11,18,32,0.55)";
const TITLE_COLOR = "#0b1220";

export type ProdCraftCreativeProps = {
  audioSrc: string;
  plan: CreativePlan;
  words: Word[];
  enableBookends?: boolean;
};

export const ProdCraftCreative: React.FC<ProdCraftCreativeProps> = ({
  audioSrc,
  plan,
  words,
  enableBookends = true,
}) => {
  const { fps, width, height } = useVideoConfig();

  // Reserve top strip for watermark + section title (kept above all scenes so
  // the channel chrome stays consistent across cuts).
  const TOP_STRIP_H = 170;
  // Reserve bottom strip for the (now slim) captions. Was 220 with the big
  // pill; the new low-weight strip needs only ~90px clearance.
  const BOTTOM_STRIP_H = 100;
  const sceneAreaH = height - TOP_STRIP_H - BOTTOM_STRIP_H;

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(180deg, ${BG_TOP} 0%, ${BG_BOTTOM} 100%)`,
      }}
    >
      <Audio src={audioSrc} />

      {/* Left accent rail — keeps the ProdCraft visual identity across the new format */}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          bottom: 0,
          width: 6,
          background: `linear-gradient(180deg, ${ACCENT} 0%, rgba(28,139,124,0) 80%)`,
          zIndex: 4,
        }}
      />

      {/* Section sequence — each scene plays during its [start_t, end_t] window. */}
      {plan.scenes.map((scene) => {
        const startFrame = Math.max(0, Math.round(scene.start_t * fps));
        const durationFrames = Math.max(
          1,
          Math.round((scene.end_t - scene.start_t) * fps),
        );
        return (
          <Sequence
            key={scene.id}
            from={startFrame}
            durationInFrames={durationFrames}
            layout="none"
          >
            <AbsoluteFill style={{ zIndex: 1 }}>
              {/* Section title strip at top */}
              <div
                style={{
                  position: "absolute",
                  top: 76,
                  left: 0,
                  right: 0,
                  textAlign: "center",
                  color: TITLE_COLOR,
                  fontFamily: FONT,
                  fontSize: 38,
                  fontWeight: 700,
                  letterSpacing: -0.5,
                  zIndex: 3,
                }}
              >
                {scene.title}
              </div>
              {/* Scene SVG canvas */}
              <div
                style={{
                  position: "absolute",
                  top: TOP_STRIP_H,
                  left: 0,
                  width,
                  height: sceneAreaH,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  zIndex: 1,
                }}
              >
                <SceneCanvas scene={scene} width={width - 80} height={sceneAreaH} />
              </div>
              {/* Hook chip — pinned in the top strip directly under the section
                  title, out of the bottom caption-capsule overlap zone. Smaller,
                  italic, supporting role. */}
              {scene.hook ? (
                <div
                  style={{
                    position: "absolute",
                    top: 126,
                    left: 0,
                    right: 0,
                    textAlign: "center",
                    color: SUBTITLE_COLOR,
                    fontFamily: FONT,
                    fontSize: 24,
                    fontWeight: 500,
                    fontStyle: "italic",
                    letterSpacing: 0.2,
                    zIndex: 3,
                  }}
                >
                  {scene.hook}
                </div>
              ) : null}
            </AbsoluteFill>
          </Sequence>
        );
      })}

      {/* Live captions stay anchored at bottom; existing Captions component
          already handles word-timing reveal. */}
      <Captions words={words} />

      {/* Watermark backdrop fade + channel label — pinned above all scenes.
          Matches the post-fix DocCanvas pattern: backdrop strip dims scrolling
          content underneath, label sits on top at zIndex 6. */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 0,
          height: 110,
          background: `linear-gradient(180deg, ${BG_TOP} 0%, ${BG_TOP} 55%, rgba(250,251,253,0) 100%)`,
          pointerEvents: "none",
          zIndex: 5,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 56,
          top: 40,
          color: SUBTITLE_COLOR,
          fontFamily: FONT,
          fontSize: 22,
          fontWeight: 600,
          letterSpacing: 1.2,
          textTransform: "uppercase",
          opacity: 0.85,
          zIndex: 6,
        }}
      >
        ProdCraft · Product Manager Foundations
      </div>

      {enableBookends ? (
        <BrandBookends totalDurationSec={plan.audio_duration_sec} />
      ) : null}
    </AbsoluteFill>
  );
};
