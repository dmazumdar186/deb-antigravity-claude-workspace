import React from "react";
import { Composition, staticFile } from "remotion";
import { Scene, myCompSchema } from "./Scene";
import { getMediaMetadata } from "./helpers/get-media-metadata";
import { CompositionWithAlpha } from "./CompositionWithAlpha";

// ---------------------------------------------------------------------------
// RemotionRoot — OVERLAY (overwriting upstream)
//
// Registers the upstream Scene composition (unchanged props contract) plus
// our CompositionWithAlpha proof composition. Both appear in Remotion Studio.
//
// IMPORTANT: The Scene defaultProps and calculateMetadata below are copied
// verbatim from the upstream template-three Root.tsx (SHA pinned in
// .template-version). If upstream renames props, remotion_bootstrap.py will
// warn and bail before copying this file.
// ---------------------------------------------------------------------------

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* ------------------------------------------------------------------ */}
      {/* Upstream Scene — 3D phone/tablet mockup composition                */}
      {/* defaultProps + calculateMetadata kept in sync with upstream contract */}
      {/* ------------------------------------------------------------------ */}
      <Composition
        id="Scene"
        component={Scene}
        fps={30}
        durationInFrames={300}
        width={1280}
        height={720}
        schema={myCompSchema}
        defaultProps={{
          deviceType: "phone" as const,
          phoneColor: "rgba(110, 152, 191, 0.00)" as const,
          baseScale: 1,
          mediaMetadata: null,
          videoSrc: null,
        }}
        calculateMetadata={async ({ props }) => {
          const videoSrc =
            props.deviceType === "phone"
              ? staticFile("phone.mp4")
              : staticFile("tablet.mp4");

          const mediaMetadata = await getMediaMetadata(videoSrc);

          return {
            props: {
              ...props,
              mediaMetadata,
              videoSrc,
            },
          };
        }}
      />

      {/* ------------------------------------------------------------------ */}
      {/* CompositionWithAlpha — alpha-channel proof composition              */}
      {/* Run this to verify transparency before rendering ProRes 4444/WebM   */}
      {/* Toggle checkered background in Studio (top-right) to preview alpha  */}
      {/* ------------------------------------------------------------------ */}
      <Composition
        id="CompositionWithAlpha"
        component={CompositionWithAlpha}
        durationInFrames={90}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
