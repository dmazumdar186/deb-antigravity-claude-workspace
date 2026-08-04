// Shared type contracts across the client + the Pages Function.
// Kept in one file so vitest can import them from either side.

export type Difficulty = 'Beginner' | 'Intermediate' | 'Advanced';
export type Channel    = 'Chat' | 'Call' | 'Both';

export interface Case {
  id: string;
  title: string;
  scenario: string;
  opening: string;
  channel: Channel;
  topic: string;
  difficulty: Difficulty;
  isDefault?: boolean;
  createdAt?: string;
}

export interface Turn { role: 'agent' | 'customer'; text: string }

export interface PerTurnNote {
  agentTurnIndex: number;
  dimension: 'empathy' | 'accuracy' | 'resolution' | 'professionalism';
  sentiment: 'strong' | 'weak';
  note: string;
}

export interface Scorecard {
  empathyScore: number;
  accuracyScore: number;
  resolutionScore: number;
  professionalismScore: number;
  overallScore: number;
  strength: string;
  improvement: string;
  perTurnNotes?: PerTurnNote[];
}

export interface ModelAnswer {
  transcript: Array<{ role: 'agent' | 'customer'; text: string }>;
  commentary: string;
}

export interface CompletedCase {
  caseId: string;
  caseTitle: string;
  topic: string;
  channel: 'Chat' | 'Call'; // resolved at session start (Both → user chose)
  difficulty: Difficulty;
  transcript: Turn[];
  scorecard: Scorecard;
  completedAt: string; // ISO
}

export interface Session {
  id: string;
  date: string; // YYYY-MM-DD (UTC)
  cases: CompletedCase[];
  averageScore: number;
}

export interface AppState {
  cases: Case[];
  sessions: Session[];
  streak: { count: number; lastDate: string | null };
}
