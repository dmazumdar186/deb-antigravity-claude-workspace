import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile, useVideoConfig } from "remotion";
import { BeatLayer } from "./BeatLayer";
import { Captions } from "./Captions";

export type ConceptCardItem = { label: string; sub?: string | null };
export type ConceptCardData = { title: string; items: ConceptCardItem[] };

export type Beat = {
  id: string;
  start_sec: number;
  end_sec: number;
  duration_sec: number;
  text: string;
  type: "stock" | "diagram" | "text_card" | "concept_card";
  stock_query: string | null;
  diagram_prompt: string | null;
  card_text: string | null;
  concept_card: ConceptCardData | null;
  asset_path?: string | null;
  asset_file?: string | null;
};

export type Word = { w: string; start: number; end: number };

export type ProdCraftProps = {
  audioSrc: string;
  beats: Beat[];
  words: Word[];
};

const containerStyle: React.CSSProperties = {
  backgroundColor: "#0f1115",
};

export const ProdCraftPhase1: React.FC<ProdCraftProps> = ({ audioSrc, beats, words }) => {
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill style={containerStyle}>
      <Audio src={audioSrc} />

      {beats.map((beat) => {
        const fromFrame = Math.round(beat.start_sec * fps);
        const durFrames = Math.max(1, Math.round(beat.duration_sec * fps));
        return (
          <Sequence
            key={beat.id}
            from={fromFrame}
            durationInFrames={durFrames}
            layout="none"
          >
            <BeatLayer beat={beat} />
          </Sequence>
        );
      })}

      <Captions words={words} />
    </AbsoluteFill>
  );
};
