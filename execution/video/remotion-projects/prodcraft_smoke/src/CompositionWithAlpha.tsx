import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  spring,
  interpolate,
} from "remotion";

// ---------------------------------------------------------------------------
// CompositionWithAlpha
//
// Proof-of-concept that alpha-channel rendering works in this project.
// The root AbsoluteFill deliberately has NO backgroundColor — that is the
// whole point. When rendered with --codec=png or ProRes 4444, pixels that
// are not covered by child elements will be fully transparent (alpha = 0).
//
// At frame 15 the radial gradient has partial opacity and the square is
// mid-spring-scale, so at least one pixel will have alpha < 255.
//
// To preview in Remotion Studio: select this composition, then click the
// checkered-background button (top-right of the canvas) to toggle
// transparency view.
// ---------------------------------------------------------------------------

export const CompositionWithAlpha: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Spring-driven scale (0 → ~1 by frame 20)
  const scale = spring({ frame, fps, config: { damping: 12, stiffness: 200, mass: 1 } });

  // Rotation driven by frame count
  const rotation = interpolate(frame, [0, 60], [0, 180]);

  // Radial gradient fades in over first 30 frames (max opacity 0.4 → transparent pixels)
  const gradientOpacity = interpolate(frame, [0, 30], [0, 0.4], {
    extrapolateRight: "clamp",
  });

  return (
    // NO backgroundColor here — this is the alpha-channel proof
    <AbsoluteFill>
      {/* Translucent radial gradient — surrounding pixels stay transparent */}
      <AbsoluteFill
        style={{
          background: `radial-gradient(circle, rgba(255,107,26,${gradientOpacity}) 0%, transparent 70%)`,
        }}
      />

      {/* Animated brand-orange square in the center */}
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        <div
          style={{
            width: 200,
            height: 200,
            background: "#ff6b1a",
            transform: `scale(${scale}) rotate(${rotation}deg)`,
            borderRadius: 16,
          }}
        />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
