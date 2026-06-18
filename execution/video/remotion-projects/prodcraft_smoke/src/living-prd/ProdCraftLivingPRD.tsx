import React from "react";
import { AbsoluteFill, Audio, useVideoConfig } from "remotion";
import { DocCanvas } from "./DocCanvas";
import { Captions } from "../Captions";
import type { LivingPRDPlan, Word } from "./types";

export type ProdCraftLivingPRDProps = {
  audioSrc: string;
  plan: LivingPRDPlan;
  words: Word[];
};

export const ProdCraftLivingPRD: React.FC<ProdCraftLivingPRDProps> = ({
  audioSrc,
  plan,
  words,
}) => {
  return (
    <AbsoluteFill style={{ background: "#0b1220" }}>
      <Audio src={audioSrc} />
      <DocCanvas plan={plan} />
      <Captions words={words} />
    </AbsoluteFill>
  );
};
