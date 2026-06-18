import React from "react";
import { useCurrentFrame } from "remotion";
import type { SectionSnapshot } from "./use-doc-state";

const FONT =
  "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";

const COLOR = {
  title: "#0b1220",
  body: "rgba(11,18,32,0.82)",
  bodyMuted: "rgba(11,18,32,0.55)",
  border: "rgba(11,18,32,0.08)",
  highlightBg: "rgba(28,139,124,0.10)",
  highlightBorder: "rgba(28,139,124,0.55)",
};

type Props = {
  section: SectionSnapshot;
  accent: string;
  maxWidth: number;
  appearProgress: number; // 0..1, governs fade+slide-in
};

export const DocSection: React.FC<Props> = ({
  section,
  accent,
  maxWidth,
  appearProgress,
}) => {
  const isHighlighted = section.state === "highlighted";

  // Body: handled differently per style.
  const body = renderBody(section, accent);

  return (
    <div
      style={{
        opacity: appearProgress,
        transform: `translateY(${(1 - appearProgress) * 16}px)`,
        background: isHighlighted ? COLOR.highlightBg : "transparent",
        border: `1.5px solid ${isHighlighted ? COLOR.highlightBorder : COLOR.border}`,
        borderRadius: 18,
        padding: "32px 40px",
        maxWidth,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          marginBottom: 18,
        }}
      >
        <div
          style={{
            width: 14,
            height: 14,
            borderRadius: 4,
            background: accent,
            transform: "rotate(45deg)",
          }}
        />
        <div
          style={{
            color: COLOR.title,
            fontFamily: FONT,
            fontSize: 42,
            fontWeight: 700,
            letterSpacing: -0.8,
            lineHeight: 1.1,
          }}
        >
          {section.title}
        </div>
      </div>
      {body}
    </div>
  );
};

const renderBody = (section: SectionSnapshot, accent: string) => {
  if (section.body_lines.length === 0) return null;
  const style = section.body_style;

  if (style === "paragraph") {
    // Concatenate lines with a single space; typewriter reveals chars across the whole text.
    const fullText = section.body_lines.join(" ");
    const charsRevealed = computeCharsRevealed(section);
    const revealed = fullText.slice(0, charsRevealed);
    const inProgress = charsRevealed < fullText.length;
    return (
      <div
        style={{
          color: COLOR.body,
          fontFamily: FONT,
          fontSize: 34,
          fontWeight: 500,
          lineHeight: 1.45,
          letterSpacing: -0.2,
        }}
      >
        {revealed}
        {inProgress ? <Cursor accent={accent} /> : null}
      </div>
    );
  }

  if (style === "list" || style === "checklist") {
    const visible = section.body_lines.slice(0, section.visible_lines);
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {visible.map((line, i) => (
          <div
            key={`${i}-${line}`}
            style={{
              display: "flex",
              gap: 18,
              alignItems: "flex-start",
              color: COLOR.body,
              fontFamily: FONT,
              fontSize: 32,
              fontWeight: 500,
              lineHeight: 1.4,
            }}
          >
            <span
              style={{
                color: accent,
                fontSize: 30,
                minWidth: 28,
                marginTop: 2,
              }}
            >
              {style === "checklist" ? "✓" : "▸"}
            </span>
            <span>{line}</span>
          </div>
        ))}
      </div>
    );
  }

  return null;
};

const computeCharsRevealed = (section: SectionSnapshot): number => {
  // For paragraph style: total chars = visible_lines worth of completed text + current chars
  let completed = 0;
  for (let i = 0; i < section.visible_lines && i < section.body_lines.length; i++) {
    completed += section.body_lines[i].length;
  }
  // Account for the joiner space we added during render (each completed line adds 1 space).
  const joinerSpaces = Math.max(0, section.visible_lines);
  return completed + joinerSpaces + section.visible_chars_for_line;
};

const Cursor: React.FC<{ accent: string }> = ({ accent }) => {
  const frame = useCurrentFrame();
  // Blink ~2Hz.
  const visible = Math.floor(frame / 9) % 2 === 0;
  return (
    <span
      style={{
        display: "inline-block",
        width: 3,
        height: "1.1em",
        background: accent,
        marginLeft: 4,
        verticalAlign: "text-bottom",
        opacity: visible ? 1 : 0,
      }}
    />
  );
};
