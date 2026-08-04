import { Composition } from "remotion";
import { MainVideo, mainVideoSchema } from "./MainVideo";

// Read pipeline defaults at bundle time.
// eslint-disable-next-line @typescript-eslint/no-var-requires
const pipelineConfig = require("../../config/pipeline.json");

const [aspectW, aspectH] = String(pipelineConfig.aspect_ratio ?? "9:16")
  .split(":")
  .map((n: string) => Number(n));

// 9:16 → 1080x1920; 16:9 → 1920x1080; 1:1 → 1080x1080.
const shortEdge = 1080;
const width = aspectW >= aspectH ? Math.round(shortEdge * aspectW / aspectH) : shortEdge;
const height = aspectW >= aspectH ? shortEdge : Math.round(shortEdge * aspectH / aspectW);

const fps = Number(pipelineConfig.fps ?? 30);
const durationInFrames = Math.max(
  1,
  Math.round(Number(pipelineConfig.duration_seconds ?? 30) * fps),
);

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="MainVideo"
        component={MainVideo}
        durationInFrames={durationInFrames}
        fps={fps}
        width={width}
        height={height}
        schema={mainVideoSchema}
        defaultProps={{
          title: pipelineConfig.slug ?? "video",
          subtitle: "scaffolded by the video pipeline template",
        }}
      />
    </>
  );
};
