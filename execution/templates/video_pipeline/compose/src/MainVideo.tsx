import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { z } from "zod";

// Schema pinned via zod so props are type-safe from CLI overrides and
// from --props JSON passed to `remotion render`.
export const mainVideoSchema = z.object({
  title: z.string(),
  subtitle: z.string().optional(),
});

type MainVideoProps = z.infer<typeof mainVideoSchema>;

/**
 * Reference composition. Replace freely; the schema+defaults are the contract
 * generate.py + publish.py rely on. Uses @remotion/three when a scaffolded
 * project needs 3D — see directives/video/remotion_three.md.
 */
export const MainVideo: React.FC<MainVideoProps> = ({ title, subtitle }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const opacity = interpolate(frame, [0, fps * 0.4], [0, 1], { extrapolateRight: "clamp" });
  const scale = interpolate(frame, [0, durationInFrames], [1.0, 1.06]);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#0a0a0a",
        color: "#ffffff",
        fontFamily: "Inter, system-ui, sans-serif",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div style={{ transform: `scale(${scale})`, textAlign: "center", opacity }}>
        <div style={{ fontSize: 96, fontWeight: 800, letterSpacing: -2 }}>{title}</div>
        {subtitle ? (
          <div style={{ fontSize: 32, marginTop: 24, opacity: 0.7 }}>{subtitle}</div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
