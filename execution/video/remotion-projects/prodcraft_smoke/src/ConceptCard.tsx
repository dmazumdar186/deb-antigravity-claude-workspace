import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  useCurrentFrame,
} from "remotion";
import type { ConceptCardData } from "./ProdCraftPhase1";

type Props = { data: ConceptCardData };

const FONT =
  "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";

// Color palette — dark navy with teal/cream accents. Matches FLUX style.
const COLORS = {
  bg1: "#0b1220",
  bg2: "#131c2e",
  title: "#f3f4f6",
  accent: "#5dd6c7",
  cardBg: "rgba(255,255,255,0.04)",
  cardBorder: "rgba(93,214,199,0.35)",
  itemLabel: "#fbfbfd",
  itemSub: "rgba(220,228,240,0.78)",
};

const containerStyle: React.CSSProperties = {
  background: `linear-gradient(135deg, ${COLORS.bg1} 0%, ${COLORS.bg2} 100%)`,
  alignItems: "center",
  justifyContent: "center",
  padding: 80,
};

export const ConceptCard: React.FC<Props> = ({ data }) => {
  const frame = useCurrentFrame();
  const titleOpacity = interpolate(frame, [0, 14], [0, 1], {
    extrapolateRight: "clamp",
  });
  const titleY = interpolate(frame, [0, 16], [18, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  const items = data.items || [];
  const cols = items.length <= 2 ? items.length : items.length <= 4 ? 2 : 3;
  // For 3 items, prefer a single row of 3.
  const oneRowOf3 = items.length === 3;
  const gridCols = oneRowOf3 ? 3 : cols;

  return (
    <AbsoluteFill style={containerStyle}>
      {/* Accent line under title */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          maxWidth: 1600,
          width: "100%",
          opacity: titleOpacity,
          transform: `translateY(${titleY}px)`,
        }}
      >
        <div
          style={{
            color: COLORS.title,
            fontFamily: FONT,
            fontSize: 66,
            fontWeight: 800,
            letterSpacing: -1.2,
            lineHeight: 1.1,
            textAlign: "center",
            marginBottom: 18,
          }}
        >
          {data.title}
        </div>
        <div
          style={{
            width: 120,
            height: 4,
            background: COLORS.accent,
            borderRadius: 2,
            marginBottom: 56,
          }}
        />
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${gridCols}, 1fr)`,
          gap: 28,
          width: "100%",
          maxWidth: 1600,
        }}
      >
        {items.map((it, i) => {
          // Stagger entrance.
          const start = 8 + i * 5;
          const itemOpacity = interpolate(frame, [start, start + 16], [0, 1], {
            extrapolateRight: "clamp",
          });
          const itemY = interpolate(frame, [start, start + 18], [22, 0], {
            extrapolateRight: "clamp",
            easing: Easing.out(Easing.cubic),
          });
          return (
            <div
              key={`${i}-${it.label}`}
              style={{
                background: COLORS.cardBg,
                border: `1.5px solid ${COLORS.cardBorder}`,
                borderRadius: 22,
                padding: "28px 32px",
                minHeight: 140,
                display: "flex",
                flexDirection: "column",
                gap: 10,
                opacity: itemOpacity,
                transform: `translateY(${itemY}px)`,
              }}
            >
              <div
                style={{
                  color: COLORS.accent,
                  fontFamily: FONT,
                  fontSize: 26,
                  fontWeight: 700,
                  letterSpacing: 0.5,
                  textTransform: "uppercase",
                  opacity: 0.85,
                }}
              >
                {String(i + 1).padStart(2, "0")}
              </div>
              <div
                style={{
                  color: COLORS.itemLabel,
                  fontFamily: FONT,
                  fontSize: 36,
                  fontWeight: 700,
                  letterSpacing: -0.4,
                  lineHeight: 1.15,
                }}
              >
                {it.label}
              </div>
              {it.sub ? (
                <div
                  style={{
                    color: COLORS.itemSub,
                    fontFamily: FONT,
                    fontSize: 22,
                    fontWeight: 400,
                    lineHeight: 1.35,
                  }}
                >
                  {it.sub}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
