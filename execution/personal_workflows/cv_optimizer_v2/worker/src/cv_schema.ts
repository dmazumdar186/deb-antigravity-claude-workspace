// CVSpec — output shape returned by Gemini Flash with responseSchema.
// Field names + types MUST match prompts/cv_response_schema.json exactly.

export type Language = "en" | "fr" | "es" | "de";

export interface CVContact {
  email: string;
  phone: string;
  location: string;
  linkedin?: string;
  github?: string;
}

export interface CVExperience {
  role: string;
  company_line: string;
  bullets: string[];
  is_oneliner: boolean;
}

export interface CVSkill {
  category: string;
  value: string;
}

export interface CVEducation {
  degree: string;
  institution_line: string;
}

export interface CVSpec {
  language_detected: Language;
  ats_score: number;
  name: string;
  title: string;
  contact: CVContact;
  summary: string;
  summary_kpis: string;
  experience: CVExperience[];
  skills: CVSkill[];
  education: CVEducation[];
  languages: string[];
  certifications?: string[];
  projects?: string[];
  recommendations: string[];
}

// Type guard for runtime validation of Gemini's response shape.
export function isCVSpec(x: unknown): x is CVSpec {
  if (typeof x !== "object" || x === null) return false;
  const o = x as Record<string, unknown>;
  return (
    typeof o.language_detected === "string" &&
    typeof o.ats_score === "number" &&
    typeof o.name === "string" &&
    typeof o.title === "string" &&
    typeof o.contact === "object" && o.contact !== null &&
    typeof o.summary === "string" &&
    Array.isArray(o.experience) &&
    Array.isArray(o.skills) &&
    Array.isArray(o.education) &&
    Array.isArray(o.recommendations)
  );
}
