// Replays the doc_ops up to the current time and produces a snapshot of doc state.
// Pure function of (ops, t_sec); deterministic, called every frame.

import type {
  BodyStyle,
  DocSectionData,
  DocSectionState,
  LivingPRDPlan,
} from "./types";

export type SectionSnapshot = DocSectionData & {
  state: DocSectionState;
  visible_lines: number;
  typing_progress: number; // 0..1 of the actively-typing line
  visible_chars_for_line: number; // chars revealed on the in-progress paragraph
};

export type DocSnapshot = {
  title: string | null;
  title_progress: number;
  subtitle?: string;
  sections: SectionSnapshot[];
  section_added_at: Record<string, number>; // section_id -> t when added (for entrance animation)
  focus_section_id: string | null;
};

const easeOut = (t: number): number => 1 - Math.pow(1 - t, 3);

export const computeDocSnapshot = (
  plan: LivingPRDPlan,
  t: number,
): DocSnapshot => {
  const ops = [...plan.ops].sort((a, b) => a.t - b.t);

  const snapshot: DocSnapshot = {
    title: null,
    title_progress: 0,
    subtitle: plan.doc_subtitle,
    sections: [],
    section_added_at: {},
    focus_section_id: null,
  };

  const sectionMap = new Map<string, SectionSnapshot>();

  type TyperState = {
    section_id: string;
    start_t: number;
    end_t: number;
    lines: string[];
    body_style: BodyStyle;
  };
  const typers: TyperState[] = [];

  type ChecklistState = {
    section_id: string;
    start_t: number;
    end_t: number;
    items: string[];
  };
  const checklists: ChecklistState[] = [];

  for (const op of ops) {
    if (op.t > t) break;
    switch (op.op) {
      case "title_in":
        snapshot.title = op.title;
        snapshot.title_progress = Math.min(1, (t - op.t) / 0.8);
        break;
      case "add_section": {
        const s: SectionSnapshot = {
          id: op.id,
          title: op.title,
          icon: op.icon ?? null,
          body_lines: [],
          body_style: "paragraph",
          state: "appearing",
          visible_lines: 0,
          typing_progress: 0,
          visible_chars_for_line: 0,
        };
        sectionMap.set(op.id, s);
        snapshot.sections.push(s);
        snapshot.section_added_at[op.id] = op.t;
        break;
      }
      case "typewriter_lines": {
        const sec = sectionMap.get(op.id);
        if (sec) {
          sec.body_lines = op.lines;
          sec.body_style = op.body_style ?? "paragraph";
          sec.state = "building";
          const end_t = op.end_t ?? op.t + (op.duration_sec ?? Math.max(0.8, op.lines.join(" ").length / 18));
          typers.push({
            section_id: op.id,
            start_t: op.t,
            end_t,
            lines: op.lines,
            body_style: sec.body_style,
          });
        }
        break;
      }
      case "highlight_section": {
        for (const s of snapshot.sections) {
          if (s.state === "highlighted") s.state = "complete";
        }
        const sec = sectionMap.get(op.id);
        if (sec) {
          sec.state = "highlighted";
          snapshot.focus_section_id = op.id;
        }
        break;
      }
      case "checklist": {
        const sec = sectionMap.get(op.id);
        if (sec) {
          sec.body_lines = op.items;
          sec.body_style = "checklist";
          sec.state = "building";
          const end_t = op.end_t ?? op.t + Math.max(0.8, op.items.length * 0.5);
          checklists.push({
            section_id: op.id,
            start_t: op.t,
            end_t,
            items: op.items,
          });
        }
        break;
      }
    }
  }

  // Resolve typewriters.
  for (const typer of typers) {
    const sec = sectionMap.get(typer.section_id);
    if (!sec) continue;
    const totalChars = typer.lines.reduce((a, l) => a + l.length, 0);
    if (totalChars === 0) continue;
    const dur = Math.max(0.05, typer.end_t - typer.start_t);
    const dt = t - typer.start_t;
    if (dt >= dur) {
      sec.visible_lines = typer.lines.length;
      sec.typing_progress = 1;
      sec.visible_chars_for_line =
        typer.lines.length > 0 ? typer.lines[typer.lines.length - 1].length : 0;
      if (sec.state === "building") sec.state = "complete";
    } else if (dt <= 0) {
      sec.visible_lines = 0;
      sec.typing_progress = 0;
      sec.visible_chars_for_line = 0;
    } else {
      // Linear reveal in audio time. Easing makes typewriter feel unnatural
      // against a steady-paced narrator, so use raw ratio.
      const ratio = dt / dur;
      const charsRevealed = totalChars * ratio;
      let used = 0;
      let visible = 0;
      let activeChars = 0;
      for (const line of typer.lines) {
        if (used + line.length <= charsRevealed) {
          visible++;
          used += line.length;
        } else {
          activeChars = Math.max(0, Math.floor(charsRevealed - used));
          break;
        }
      }
      sec.visible_lines = visible;
      sec.visible_chars_for_line = activeChars;
      const activeLine = typer.lines[visible];
      sec.typing_progress = activeLine && activeLine.length > 0
        ? activeChars / activeLine.length
        : 0;
    }
  }

  // Resolve checklists (no per-char typewriter; reveal item by item).
  for (const cl of checklists) {
    const sec = sectionMap.get(cl.section_id);
    if (!sec) continue;
    const dur = Math.max(0.05, cl.end_t - cl.start_t);
    const dt = t - cl.start_t;
    if (dt <= 0) {
      sec.visible_lines = 0;
    } else if (dt >= dur) {
      sec.visible_lines = cl.items.length;
      if (sec.state === "building") sec.state = "complete";
    } else {
      sec.visible_lines = Math.floor((dt / dur) * cl.items.length + 1e-6);
    }
    sec.visible_chars_for_line = 0;
    sec.typing_progress = 0;
  }

  return snapshot;
};
