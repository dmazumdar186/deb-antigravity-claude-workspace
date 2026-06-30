import React from "react";
import { Composition, staticFile } from "remotion";
import { Scene, myCompSchema } from "./Scene";
import { getMediaMetadata } from "./helpers/get-media-metadata";
import { CompositionWithAlpha } from "./CompositionWithAlpha";
import {
  ProdCraftPhase1,
  type Beat,
  type Word,
} from "./ProdCraftPhase1";
import { ProdCraftLivingPRD } from "./living-prd/ProdCraftLivingPRD";
import type { LivingPRDPlan, Word as LPWord } from "./living-prd/types";
import { ProdCraftCreative } from "./creative/ProdCraftCreative";
import type { CreativePlan, Word as CreativeWord } from "./creative/types";

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

      {/* ------------------------------------------------------------------ */}
      {/* ProdCraftPhase1 — Phase 1 end-to-end PRD video                     */}
      {/* Loads beats.json + words.json + audio.wav from public/ at runtime  */}
      {/* durationInFrames derived from beats.json's audio_duration_sec       */}
      {/* ------------------------------------------------------------------ */}
      {/* ------------------------------------------------------------------ */}
      {/* ProdCraftLivingPRD — Living PRD POC                                 */}
      {/* Loads living_prd_plan.json + words.json + audio.wav from public/    */}
      {/* ------------------------------------------------------------------ */}
      <Composition
        id="ProdCraftLivingPRD"
        component={ProdCraftLivingPRD}
        fps={30}
        width={1920}
        height={1080}
        durationInFrames={1500}
        defaultProps={{
          audioSrc: staticFile("audio.wav"),
          plan: {
            doc_title: "Loading…",
            audio_duration_sec: 50,
            ops: [],
          } as LivingPRDPlan,
          words: [] as LPWord[],
        }}
        calculateMetadata={async () => {
          const planRes = await fetch(staticFile("living_prd_plan.json"));
          const plan = (await planRes.json()) as LivingPRDPlan;
          const wordsRes = await fetch(staticFile("words.json"));
          const words = (await wordsRes.json()) as LPWord[];
          const fps = 30;
          const durationInFrames = Math.max(
            1,
            Math.ceil(plan.audio_duration_sec * fps),
          );
          return {
            durationInFrames,
            props: {
              audioSrc: staticFile("audio.wav"),
              plan,
              words,
              enableBookends: true,
            },
          };
        }}
      />

      {/* ------------------------------------------------------------------ */}
      {/* ProdCraftCreative — GLM-authored per-section bespoke SVG scenes     */}
      {/* Loads creative_plan.json + words.json + audio.wav from public/       */}
      {/* ------------------------------------------------------------------ */}
      <Composition
        id="ProdCraftCreative"
        component={ProdCraftCreative}
        fps={30}
        width={1920}
        height={1080}
        durationInFrames={1500}
        defaultProps={{
          audioSrc: staticFile("audio.wav"),
          plan: {
            doc_title: "Loading...",
            audio_duration_sec: 50,
            scenes: [],
          } as CreativePlan,
          words: [] as CreativeWord[],
        }}
        calculateMetadata={async () => {
          const planRes = await fetch(staticFile("creative_plan.json"));
          const plan = (await planRes.json()) as CreativePlan;
          const wordsRes = await fetch(staticFile("words.json"));
          const words = (await wordsRes.json()) as CreativeWord[];
          const fps = 30;
          const durationInFrames = Math.max(
            1,
            Math.ceil(plan.audio_duration_sec * fps),
          );
          return {
            durationInFrames,
            props: {
              audioSrc: staticFile("audio.wav"),
              plan,
              words,
              enableBookends: true,
            },
          };
        }}
      />

      <Composition
        id="ProdCraftPhase1"
        component={ProdCraftPhase1}
        fps={30}
        width={1920}
        height={1080}
        durationInFrames={4440}
        defaultProps={{
          audioSrc: staticFile("audio.wav"),
          beats: [] as Beat[],
          words: [] as Word[],
        }}
        calculateMetadata={async () => {
          const beatsRes = await fetch(staticFile("beats.json"));
          const beatsData = (await beatsRes.json()) as {
            audio_duration_sec: number;
            beats: Beat[];
          };
          const wordsRes = await fetch(staticFile("words.json"));
          const wordsData = (await wordsRes.json()) as Word[];

          const fps = 30;
          const durationInFrames = Math.max(
            1,
            Math.ceil(beatsData.audio_duration_sec * fps),
          );

          return {
            durationInFrames,
            props: {
              audioSrc: staticFile("audio.wav"),
              beats: beatsData.beats,
              words: wordsData,
            },
          };
        }}
      />
    </>
  );
};
