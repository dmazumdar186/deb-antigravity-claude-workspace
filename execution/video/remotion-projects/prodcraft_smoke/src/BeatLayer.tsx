import React from "react";
import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { Beat } from "./ProdCraftPhase1";
import { ConceptCard } from "./ConceptCard";

type Props = { beat: Beat };

const safeStaticFile = (file: string | null | undefined): string | null => {
  if (!file) return null;
  return staticFile(file);
};

export const BeatLayer: React.FC<Props> = ({ beat }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const fadeIn = interpolate(frame, [0, 8], [0, 1], {
    extrapolateRight: "clamp",
  });

  if (beat.type === "concept_card" && beat.concept_card) {
    return (
      <div style={{ width: "100%", height: "100%", opacity: fadeIn }}>
        <ConceptCard data={beat.concept_card} />
      </div>
    );
  }

  if (beat.type === "text_card") {
    return <TextCard text={beat.card_text || beat.text} fadeIn={fadeIn} />;
  }

  const assetUrl = safeStaticFile(beat.asset_file);
  if (!assetUrl) {
    return <TextCard text={beat.card_text || beat.text} fadeIn={fadeIn} />;
  }

  // Ken Burns: gentle scale 1.00 → 1.06 over the beat.
  const t = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.quad),
  });
  const scale = interpolate(t, [0, 1], [1.0, 1.06]);
  const tx = interpolate(t, [0, 1], [-10, 10]);

  return (
    <AbsoluteFill
      style={{
        opacity: fadeIn,
        overflow: "hidden",
        backgroundColor: "#0b1220",
      }}
    >
      <Img
        src={assetUrl}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${scale}) translateX(${tx}px)`,
          transformOrigin: "center",
        }}
      />
      {/* Strong dark gradient overlay — full-frame, denser at the bottom for caption readability.
          This makes any bright/white-background image readable + ensures captions survive. */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(to bottom, rgba(11,18,32,0.42) 0%, rgba(11,18,32,0.30) 45%, rgba(11,18,32,0.78) 100%)",
          pointerEvents: "none",
        }}
      />
      {/* Soft vignette to push focus inward. */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse at center, rgba(0,0,0,0) 50%, rgba(0,0,0,0.45) 100%)",
          pointerEvents: "none",
        }}
      />
    </AbsoluteFill>
  );
};

const TextCard: React.FC<{ text: string; fadeIn: number }> = ({ text, fadeIn }) => {
  const frame = useCurrentFrame();
  const scale = interpolate(frame, [0, 16], [0.96, 1.0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  return (
    <AbsoluteFill
      style={{
        background:
          "radial-gradient(ellipse at center, #1c2030 0%, #0b1220 100%)",
        alignItems: "center",
        justifyContent: "center",
        opacity: fadeIn,
      }}
    >
      <div
        style={{
          color: "#f5f7fb",
          fontFamily:
            "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
          fontWeight: 800,
          fontSize: 88,
          letterSpacing: -1.5,
          lineHeight: 1.12,
          textAlign: "center",
          maxWidth: 1400,
          padding: 60,
          transform: `scale(${scale})`,
          textShadow: "0 4px 32px rgba(0,0,0,0.5)",
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};
