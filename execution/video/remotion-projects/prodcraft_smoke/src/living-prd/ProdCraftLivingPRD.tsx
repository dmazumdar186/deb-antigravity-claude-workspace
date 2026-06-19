import React from "react";
import { AbsoluteFill, Audio } from "remotion";
import { DocCanvas } from "./DocCanvas";
import { Captions } from "../Captions";
import { BrandBookends } from "./BrandBookends";
import type { LivingPRDPlan, Word } from "./types";

export type ProdCraftLivingPRDProps = {
  audioSrc: string;
  plan: LivingPRDPlan;
  words: Word[];
  enableBookends?: boolean;
};

export const ProdCraftLivingPRD: React.FC<ProdCraftLivingPRDProps> = ({
  audioSrc,
  plan,
  words,
  enableBookends = true,
}) => {
  return (
    <AbsoluteFill style={{ background: "#0b1220" }}>
      <Audio src={audioSrc} />
      <DocCanvas plan={plan} />
      <Captions words={words} />
      {enableBookends ? (
        <BrandBookends totalDurationSec={plan.audio_duration_sec} />
      ) : null}
    </AbsoluteFill>
  );
};
