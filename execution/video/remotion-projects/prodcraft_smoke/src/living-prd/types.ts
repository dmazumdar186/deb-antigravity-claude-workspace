// Shared types for the Living PRD composition.

export type BodyStyle = "paragraph" | "list" | "checklist";

export type DocSectionState =
  | "empty"
  | "appearing"
  | "building"
  | "complete"
  | "highlighted";

export type DocSectionData = {
  id: string;
  title: string;
  body_lines: string[]; // each entry is either a list item OR a full paragraph (depending on body_style)
  body_style: BodyStyle;
  icon?: string | null;
};

export type DocOp =
  | { t: number; op: "title_in"; title: string }
  | { t: number; op: "add_section"; id: string; title: string; icon?: string | null }
  | {
      t: number;
      op: "typewriter_lines";
      id: string;
      lines: string[];
      // EITHER end_t (preferred, audio-aligned) OR duration_sec (fallback).
      end_t?: number;
      duration_sec?: number;
      body_style?: BodyStyle; // default "paragraph"
    }
  | { t: number; op: "highlight_section"; id: string }
  | { t: number; op: "checklist"; id: string; items: string[]; end_t?: number };

export type LivingPRDPlan = {
  doc_title: string;
  doc_subtitle?: string;
  audio_duration_sec: number;
  ops: DocOp[];
};

export type Word = { w: string; start: number; end: number };
