import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { DocSection } from "./DocSection";
import { computeDocSnapshot } from "./use-doc-state";
import type { LivingPRDPlan } from "./types";

// Full-bleed, no browser-window chrome. The whole 1920x1080 IS the document.
const PAGE_BG_TOP = "#fafbfd";
const PAGE_BG_BOTTOM = "#eef1f7";
const ACCENT = "#1c8b7c"; // deeper teal vs the demo neon
const TITLE_COLOR = "#0b1220";
const SUBTITLE_COLOR = "rgba(11,18,32,0.55)";

const FONT =
  "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";

type Props = {
  plan: LivingPRDPlan;
};

const HEADER_PAD_TOP = 56;
const HEADER_BLOCK_H = 220; // title + subtitle + spacing
const TITLE_BLOCK_PAD_TOP = 40; // matches paddingTop inside title block JSX
const SECTION_COLUMN_MARGIN_TOP = 40; // matches "40px auto 0" margin on sections column
const SECTION_GAP = 40;
const CONTENT_MAX_W = 1560;
const SECTION_CHROME_PX = 128; // title row + vertical padding (32+32) + borders
const PARAGRAPH_LINE_PX = 50; // font-size 34 × line-height 1.45
const LIST_ITEM_PX = 59; // font-size 32 × line-height 1.4 + 14 gap
const PARAGRAPH_CHARS_PER_LINE = 60; // empirical wrap at 1560-1480 max-width, font-size 34

// Estimate a section's rendered height from its content. Replaces the prior
// fixed 230px assumption which over-scrolled tall sections off the viewport
// (CTA section landed ~400px below the 1080 cutoff in v3).
const estimateSectionHeight = (
  bodyLines: string[],
  bodyStyle: "paragraph" | "list" | "checklist",
): number => {
  if (bodyLines.length === 0) return SECTION_CHROME_PX + 40;
  if (bodyStyle === "paragraph") {
    const text = bodyLines.join(" ");
    const lines = Math.max(1, Math.ceil(text.length / PARAGRAPH_CHARS_PER_LINE));
    return SECTION_CHROME_PX + lines * PARAGRAPH_LINE_PX;
  }
  // list / checklist: gap between items is included in LIST_ITEM_PX
  return SECTION_CHROME_PX + bodyLines.length * LIST_ITEM_PX - 14;
};

export const DocCanvas: React.FC<Props> = ({ plan }) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const t = frame / fps;

  const snap = computeDocSnapshot(plan, t);

  // Auto-scroll: when sections accumulate beyond viewport, the doc translates
  // upward to keep the NEWEST section near visual center.
  // Real per-section heights vary 226-350px; prior fixed-230 assumption left
  // tall sections 200-400px below the viewport at the outro.
  const titleBlockH =
    HEADER_PAD_TOP + TITLE_BLOCK_PAD_TOP + HEADER_BLOCK_H + SECTION_COLUMN_MARGIN_TOP;
  let contentHeightBeforeNewest = titleBlockH;
  for (let i = 0; i < snap.sections.length - 1; i++) {
    const s = snap.sections[i];
    contentHeightBeforeNewest += estimateSectionHeight(s.body_lines, s.body_style);
    contentHeightBeforeNewest += SECTION_GAP;
  }
  const desiredNewestSectionTop = height * 0.55;
  const naiveOffset = desiredNewestSectionTop - contentHeightBeforeNewest;
  const targetOffset = Math.min(0, naiveOffset);

  // Smooth the offset over time to avoid sudden jumps when a section is added.
  // We approximate this by easing toward target over ~30 frames per add.
  // For the POC we apply easing per-frame on absolute time since the last section add;
  // good enough without writing a real spring.
  const smoothedOffset = targetOffset; // jumps allowed for POC; sections appear with their own animation

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(180deg, ${PAGE_BG_TOP} 0%, ${PAGE_BG_BOTTOM} 100%)`,
      }}
    >
      {/* Subtle paper grain via two faint gradient layers */}
      <AbsoluteFill
        style={{
          opacity: 0.5,
          background:
            "radial-gradient(ellipse at top, rgba(28,139,124,0.04) 0%, transparent 60%)",
          pointerEvents: "none",
        }}
      />

      {/* Left accent rail */}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          bottom: 0,
          width: 6,
          background: `linear-gradient(180deg, ${ACCENT} 0%, rgba(28,139,124,0.0) 80%)`,
        }}
      />

      {/* Top breadcrumb / channel label — gives the video an identity */}
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
          opacity: 0.65,
        }}
      >
        ProdCraft · Product Manager Foundations
      </div>

      {/* Document body, translated to auto-scroll */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 0,
          transform: `translateY(${smoothedOffset}px)`,
        }}
      >
        {/* Title block */}
        <div
          style={{
            paddingTop: HEADER_PAD_TOP + 40,
            paddingLeft: 120,
            paddingRight: 120,
            maxWidth: CONTENT_MAX_W + 240,
            margin: "0 auto",
          }}
        >
          {snap.title ? (
            <div
              style={{
                color: TITLE_COLOR,
                fontFamily: FONT,
                fontSize: 76,
                fontWeight: 800,
                letterSpacing: -1.8,
                lineHeight: 1.05,
                opacity: snap.title_progress,
                transform: `translateY(${(1 - snap.title_progress) * 16}px)`,
              }}
            >
              {snap.title}
            </div>
          ) : (
            <div style={{ height: 88 }} />
          )}
          {snap.subtitle ? (
            <div
              style={{
                color: SUBTITLE_COLOR,
                fontFamily: FONT,
                fontSize: 30,
                fontWeight: 500,
                marginTop: 14,
                opacity: snap.title_progress * 0.9,
              }}
            >
              {snap.subtitle}
            </div>
          ) : null}

          {/* Accent line under title */}
          <div
            style={{
              width: 140,
              height: 5,
              background: ACCENT,
              borderRadius: 3,
              marginTop: 28,
              opacity: snap.title_progress,
              transformOrigin: "left",
              transform: `scaleX(${snap.title_progress})`,
            }}
          />
        </div>

        {/* Sections column */}
        <div
          style={{
            margin: "40px auto 0",
            padding: "0 120px",
            maxWidth: CONTENT_MAX_W + 240,
            display: "flex",
            flexDirection: "column",
            gap: SECTION_GAP,
          }}
        >
          {snap.sections.map((s, idx) => (
            <DocSection
              key={s.id}
              section={s}
              accent={ACCENT}
              maxWidth={CONTENT_MAX_W}
              appearProgress={interpolate(
                (t - (snap.section_added_at?.[s.id] ?? t)) * fps,
                [0, 14],
                [0, 1],
                { extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) },
              )}
            />
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};
