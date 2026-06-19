import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const ACCENT = "#1c8b7c";
const BG = "#0b1220";
const FONT =
  "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";

type Props = {
  totalDurationSec: number;
  channel?: string;
  handle?: string;
  tagline?: string;
};

// Intro fades out by 2.2s; Outro fades in over the final 4.5s.
const INTRO_END_SEC = 2.2;
const OUTRO_LEAD_SEC = 4.5;

export const BrandBookends: React.FC<Props> = ({
  totalDurationSec,
  channel = "ProdCraft",
  handle = "@ProdCraft",
  tagline = "Product Manager Foundations",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const introOpacity = interpolate(t, [0, 1.0, INTRO_END_SEC - 0.4, INTRO_END_SEC], [1, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.cubic),
  });
  const introScale = interpolate(t, [0, INTRO_END_SEC], [1, 1.04], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const introRailScale = interpolate(t, [0.2, 1.4], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  const outroStart = totalDurationSec - OUTRO_LEAD_SEC;
  const outroOpacity = interpolate(
    t,
    [outroStart, outroStart + 0.6, totalDurationSec - 0.3, totalDurationSec],
    [0, 1, 1, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic) },
  );
  const outroLift = interpolate(t, [outroStart, outroStart + 0.8], [24, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  return (
    <>
      {/* INTRO BOOKEND */}
      {introOpacity > 0.001 ? (
        <AbsoluteFill
          style={{
            background: BG,
            opacity: introOpacity,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexDirection: "column",
            pointerEvents: "none",
          }}
        >
          <div
            style={{
              fontFamily: FONT,
              color: "#fafbfd",
              fontSize: 132,
              fontWeight: 800,
              letterSpacing: -3.5,
              transform: `scale(${introScale})`,
            }}
          >
            {channel}
          </div>
          <div
            style={{
              width: 220,
              height: 6,
              background: ACCENT,
              borderRadius: 3,
              marginTop: 28,
              transformOrigin: "center",
              transform: `scaleX(${introRailScale})`,
            }}
          />
          <div
            style={{
              fontFamily: FONT,
              color: "rgba(250,251,253,0.65)",
              fontSize: 30,
              fontWeight: 500,
              marginTop: 26,
              letterSpacing: 0.4,
            }}
          >
            {tagline}
          </div>
          <div
            style={{
              position: "absolute",
              bottom: 80,
              fontFamily: FONT,
              color: "rgba(250,251,253,0.4)",
              fontSize: 22,
              fontWeight: 600,
              letterSpacing: 2.4,
              textTransform: "uppercase",
            }}
          >
            {handle}
          </div>
        </AbsoluteFill>
      ) : null}

      {/* OUTRO BOOKEND */}
      {outroOpacity > 0.001 ? (
        <AbsoluteFill
          style={{
            background: `rgba(11,18,32,${0.94 * outroOpacity})`,
            opacity: outroOpacity,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexDirection: "column",
            pointerEvents: "none",
          }}
        >
          <div
            style={{
              transform: `translateY(${outroLift}px)`,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
            }}
          >
            <div
              style={{
                fontFamily: FONT,
                color: "rgba(250,251,253,0.7)",
                fontSize: 28,
                fontWeight: 500,
                letterSpacing: 1.4,
                textTransform: "uppercase",
              }}
            >
              Thanks for watching
            </div>
            <div
              style={{
                fontFamily: FONT,
                color: "#fafbfd",
                fontSize: 104,
                fontWeight: 800,
                letterSpacing: -2.4,
                marginTop: 14,
              }}
            >
              {channel}
            </div>
            <div
              style={{
                width: 180,
                height: 5,
                background: ACCENT,
                borderRadius: 3,
                marginTop: 22,
              }}
            />
            <div
              style={{
                fontFamily: FONT,
                color: "rgba(250,251,253,0.85)",
                fontSize: 36,
                fontWeight: 600,
                marginTop: 30,
                letterSpacing: 0.6,
              }}
            >
              Subscribe · {handle}
            </div>
          </div>
        </AbsoluteFill>
      ) : null}
    </>
  );
};
