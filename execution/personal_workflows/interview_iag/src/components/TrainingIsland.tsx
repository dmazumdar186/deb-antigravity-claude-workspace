import { useEffect, useMemo, useRef, useState } from 'react';
import { loadState, saveState } from '../lib/storage';
import { pickDailyCases, todayUTC, updateStreak, newSessionFromCompletedCases, sessionAverage } from '../lib/session';
import { callRoleplay, callRoleplayStream, callScore, callModelAnswer, ApiError } from '../lib/api';
import { useSpeechRecognition } from '../lib/useSpeech';
import { ChunkedSpeaker } from '../lib/chunkedSpeech';
import type { Case, CompletedCase, ModelAnswer, Scorecard, Turn } from '../lib/types';

const MAX_TURNS = 5;

type Stage =
  | { kind: 'loading' }
  | { kind: 'intro'; today: Case[] }
  | { kind: 'choose-channel'; caseIdx: number; today: Case[]; completed: CompletedCase[] }
  | { kind: 'active';   caseIdx: number; today: Case[]; completed: CompletedCase[]; channel: 'Chat' | 'Call'; transcript: Turn[]; awaiting: 'agent' | 'customer'; streamingText?: string; provider?: 'anthropic' | 'gemini'; agentTurnsTaken: number }
  | { kind: 'scoring';  caseIdx: number; today: Case[]; completed: CompletedCase[]; channel: 'Chat' | 'Call'; transcript: Turn[] }
  | { kind: 'scorecard'; caseIdx: number; today: Case[]; completed: CompletedCase[]; scorecard: Scorecard }
  | { kind: 'summary';   completed: CompletedCase[]; average: number; streak: number };

// Upsert today's session into localStorage: if a session for today already
// exists, replace its cases with the current-progress list; otherwise insert.
// Streak is bumped once per new day. Called after every scorecard so partial
// sessions still appear on the dashboard even if the agent walks away.
function persistTodayProgress(completed: CompletedCase[]): void {
  if (completed.length === 0) return;
  const state = loadState();
  const dateISO = todayUTC();
  const existingIdx = state.sessions.findIndex((s) => s.date === dateISO);
  const session = newSessionFromCompletedCases(completed, dateISO);
  const nextSessions = existingIdx >= 0
    ? state.sessions.map((s, i) => (i === existingIdx ? { ...session, id: s.id } : s))
    : [session, ...state.sessions];
  const nextStreak = state.streak.lastDate === dateISO ? state.streak : updateStreak(state.streak, dateISO);
  saveState({ ...state, sessions: nextSessions, streak: nextStreak });
}

export default function TrainingIsland() {
  const [stage, setStage] = useState<Stage>({ kind: 'loading' });
  const [dpdpaPending, setDpdpaPending] = useState<null | { caseIdx: number; today: Case[]; completed: CompletedCase[]; channel: 'Chat' | 'Call' }>(null);

  useEffect(() => {
    const s = loadState();
    const today = pickDailyCases(s.cases, todayUTC());
    setStage({ kind: 'intro', today });
  }, []);

  // DPDPA consent flow — training aid: mocks the pre-call disclosure Indian
  // BPO agents are required to obtain per India's DPDP Act 2023.
  if (dpdpaPending) {
    const acceptAndProceed = () => {
      try { localStorage.setItem('agentup:dpdpa-consent', '1'); } catch { /* private mode — proceed anyway */ }
      const p = dpdpaPending;
      const c = p.today[p.caseIdx];
      setDpdpaPending(null);
      setStage({
        kind: 'active', caseIdx: p.caseIdx, today: p.today, completed: p.completed,
        channel: p.channel, transcript: [{ role: 'customer', text: c.opening }], awaiting: 'agent',
        agentTurnsTaken: 0,
      });
    };
    return <DPDPAConsent onAccept={acceptAndProceed} onCancel={() => setDpdpaPending(null)} />;
  }

  if (stage.kind === 'loading') return <SkeletonCard />;
  if (stage.kind === 'intro') return <IntroCard today={stage.today} onStart={(caseIdx) => setStage({ kind: 'choose-channel', caseIdx, today: stage.today, completed: [] })} />;

  if (stage.kind === 'choose-channel') {
    const c = stage.today[stage.caseIdx];
    if (!c) return null;
    return <ChooseChannel case={c} onPick={(channel) => {
      // On the Call channel, gate first use behind a one-time DPDPA-style
      // consent dialog (per India's Digital Personal Data Protection Act
      // 2023). Mocks the pre-call disclosure agents must obtain on real
      // customer calls; on this training app it's a training aid — the
      // consent is stored in localStorage so agents see it once.
      if (channel === 'Call') {
        const already = (() => { try { return localStorage.getItem('agentup:dpdpa-consent') === '1'; } catch { return false; } })();
        if (!already) {
          setDpdpaPending({ caseIdx: stage.caseIdx, today: stage.today, completed: stage.completed, channel });
          return;
        }
      }
      setStage({
        kind: 'active', caseIdx: stage.caseIdx, today: stage.today, completed: stage.completed,
        channel, transcript: [{ role: 'customer', text: c.opening }], awaiting: 'agent',
        agentTurnsTaken: 0,
      });
    }} />;
  }

  if (stage.kind === 'active') {
    return <ActiveCase
      key={stage.caseIdx + ':' + stage.channel}
      currentCase={stage.today[stage.caseIdx]}
      channel={stage.channel}
      transcript={stage.transcript}
      awaiting={stage.awaiting}
      streamingText={stage.streamingText}
      caseNumber={stage.caseIdx + 1}
      caseTotal={stage.today.length}
      agentTurnsTaken={stage.agentTurnsTaken}
      onSubmitAgent={async (text) => {
        const nextTranscript: Turn[] = [...stage.transcript, { role: 'agent', text }];
        // Belt-and-braces: use whichever count is LOWER — explicit counter OR
        // filter of transcript. Both should agree; if they disagree, the lower
        // one is safer (prefer under-scoring to prematurely scoring the case).
        const explicit = (typeof stage.agentTurnsTaken === 'number' ? stage.agentTurnsTaken : 0) + 1;
        const filtered = nextTranscript.filter((t) => t.role === 'agent').length;
        const agentTurnsAfter = Math.min(explicit, filtered);
        const isLastAgentTurn = agentTurnsAfter >= MAX_TURNS;

        // Every agent turn — including the 5th — is followed by the AI's
        // customer reply (PRD: "The AI responds as the customer for up to 5
        // turns"). Scoring runs after that final reply.
        setStage({ ...stage, transcript: nextTranscript, awaiting: 'customer', streamingText: '', provider: undefined, agentTurnsTaken: agentTurnsAfter });

        const difficulty = stage.today[stage.caseIdx].difficulty;
        // On the Call channel, pipe complete phrases to speech synthesis as
        // they arrive. Time-to-first-audio drops to ~200-500ms.
        const speaker = stage.channel === 'Call'
          ? new ChunkedSpeaker(
              difficulty === 'Advanced' ? { rate: 1.15, pitch: 0.95, lang: 'en-IN' } :
              difficulty === 'Beginner' ? { rate: 0.95, pitch: 1.05, lang: 'en-IN' } :
                                          { lang: 'en-IN' }
            )
          : null;

        let withCustomerReply: Turn[] | null = null;
        try {
          const { text: finalText, provider } = await callRoleplayStream({
            scenario: stage.today[stage.caseIdx].scenario,
            opening: stage.today[stage.caseIdx].opening,
            difficulty,
            history: nextTranscript.slice(1),
          }, (delta) => {
            setStage((prev) => {
              if (prev.kind !== 'active') return prev;
              return { ...prev, streamingText: (prev.streamingText ?? '') + delta, provider };
            });
            if (speaker) speaker.feed(delta);
          });
          if (speaker) speaker.finish();
          withCustomerReply = [...nextTranscript, { role: 'customer', text: finalText }];
          // Promote streamed text to a completed transcript turn.
          setStage((prev) => {
            if (prev.kind !== 'active') return prev;
            return { ...prev, transcript: withCustomerReply!, awaiting: 'agent', streamingText: undefined };
          });
        } catch (err) {
          if (speaker) speaker.cancel();
          const msg = err instanceof ApiError ? err.message : 'Customer reply failed.';
          alert('Customer reply failed: ' + msg + '\n\nPlease try again.');
          setStage((prev) => prev.kind === 'active' ? { ...prev, transcript: nextTranscript, awaiting: 'agent', streamingText: undefined } : prev);
          return;
        }

        // If that was the last agent turn AND we have the AI's reply, jump to scoring.
        if (isLastAgentTurn && withCustomerReply) {
          setStage({ kind: 'scoring', caseIdx: stage.caseIdx, today: stage.today, completed: stage.completed, channel: stage.channel, transcript: withCustomerReply });
          try {
            const scorecard = await callScore({
              scenario: stage.today[stage.caseIdx].scenario,
              difficulty: stage.today[stage.caseIdx].difficulty,
              transcript: withCustomerReply,
            });
            const done: CompletedCase = {
              caseId: stage.today[stage.caseIdx].id,
              caseTitle: stage.today[stage.caseIdx].title,
              topic: stage.today[stage.caseIdx].topic,
              channel: stage.channel,
              difficulty: stage.today[stage.caseIdx].difficulty,
              transcript: withCustomerReply,
              scorecard,
              completedAt: new Date().toISOString(),
            };
            const nextCompleted = [...stage.completed, done];
            // Persist progress AS SOON AS each case scores — don't wait for
            // "See session summary" click at the end. Dashboard reflects
            // partial sessions; users who leave mid-way still see their data.
            persistTodayProgress(nextCompleted);
            setStage({ kind: 'scorecard', caseIdx: stage.caseIdx, today: stage.today, completed: nextCompleted, scorecard });
          } catch (err) {
            const msg = err instanceof ApiError ? err.message : 'Scoring failed.';
            alert('Scoring failed: ' + msg + '\n\nYou can retry this case or move on — no data is lost.');
            setStage({ kind: 'active', caseIdx: stage.caseIdx, today: stage.today, completed: stage.completed, channel: stage.channel, transcript: withCustomerReply, awaiting: 'agent', agentTurnsTaken: agentTurnsAfter });
          }
        }
      }}
    />;
  }

  if (stage.kind === 'scoring') return <ScoringCard />;

  if (stage.kind === 'scorecard') {
    const isLast = stage.caseIdx + 1 >= stage.today.length;
    const justCompleted = stage.completed[stage.completed.length - 1];
    return <ScorecardView
      scorecard={stage.scorecard}
      completed={justCompleted}
      currentCase={stage.today[stage.caseIdx]}
      isLast={isLast}
      onNext={() => {
        if (isLast) {
          // Session was persisted incrementally at each scorecard; just navigate.
          const nextStreak = loadState().streak.count;
          setStage({ kind: 'summary', completed: stage.completed, average: sessionAverage(stage.completed), streak: nextStreak });
        } else {
          setStage({ kind: 'choose-channel', caseIdx: stage.caseIdx + 1, today: stage.today, completed: stage.completed });
        }
      }}
    />;
  }

  if (stage.kind === 'summary') return <SummaryCard {...stage} />;
  return null;
}

// ---------- Sub-views ----------

function SkeletonCard() {
  return <div className="card p-8 animate-pulse text-ink-500">Preparing today’s session…</div>;
}

function IntroCard({ today, onStart }: { today: Case[]; onStart: (caseIdx: number) => void }) {
  const [selectedIdx, setSelectedIdx] = useState<number>(0);
  if (today.length === 0) {
    return <div className="card p-8">
      <p className="text-ink-600 dark:text-ink-300">No cases available. Head over to <a href="/cases" className="text-indigo-600 underline">My Cases</a> to add one.</p>
    </div>;
  }
  return (
    <div className="card p-6 sm:p-8 animate-slide-up">
      <div className="flex items-baseline justify-between gap-4">
        <div>
          <h2 className="font-display text-2xl font-semibold">Today’s three cases</h2>
          <p className="mt-1 text-sm text-ink-600 dark:text-ink-300">Pick one to start with. You'll be walked through all three in the order you choose.</p>
        </div>
        <button type="button" onClick={() => onStart(selectedIdx)} data-testid="btn-start-session" className="btn-primary">Start session →</button>
      </div>
      <ol className="mt-6 space-y-3">
        {today.map((c, i) => (
          <li key={c.id}>
            <button
              type="button"
              onClick={() => setSelectedIdx(i)}
              data-testid={`case-tile-${i}`}
              aria-pressed={selectedIdx === i}
              className={`w-full text-left flex items-start gap-3 rounded-lg border p-3 transition ${
                selectedIdx === i
                  ? 'border-emerald-500 bg-emerald-500/5 ring-1 ring-emerald-500/30'
                  : 'border-ink-200/60 dark:border-ink-700/60 bg-white/40 dark:bg-ink-900/30 hover:border-ink-300 hover:bg-white/70 dark:hover:bg-ink-900/60'
              }`}
            >
            <span className={`mt-0.5 inline-flex h-6 w-6 flex-none items-center justify-center rounded-md text-xs font-semibold ${
              selectedIdx === i
                ? 'bg-emerald-500 text-white'
                : 'bg-ink-900 text-white dark:bg-white dark:text-ink-900'
            }`}>{i + 1}</span>
            <div className="min-w-0 flex-1">
              <div className="font-medium">{c.title}</div>
              <div className="text-xs text-ink-500 mt-0.5 flex gap-2 flex-wrap">
                <span className="chip">{c.topic}</span>
                <span className="chip">{c.channel}</span>
                <span className="chip">{c.difficulty}</span>
              </div>
            </div>
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}

function ChooseChannel({ case: c, onPick }: { case: Case; onPick: (ch: 'Chat' | 'Call') => void }) {
  const chatOnly = c.channel === 'Chat';
  const callOnly = c.channel === 'Call';
  return (
    <div className="card p-6 sm:p-8 animate-slide-up">
      <div className="flex flex-wrap items-center gap-2 text-xs text-ink-500">
        <span className="chip">{c.topic}</span>
        <span className="chip">{c.difficulty}</span>
      </div>
      <h2 className="mt-3 font-display text-2xl font-semibold">{c.title}</h2>
      <p className="mt-2 text-sm text-ink-600 dark:text-ink-300">{c.scenario}</p>
      <p className="mt-4 text-sm italic border-l-2 border-ink-300 dark:border-ink-700 pl-3 text-ink-700 dark:text-ink-200">“{c.opening}”</p>
      <div className="mt-6 flex flex-wrap gap-3">
        {!callOnly && <button type="button" data-testid="btn-channel-chat" onClick={() => onPick('Chat')} className="btn-primary">Practise via Chat</button>}
        {!chatOnly && <button type="button" data-testid="btn-channel-call" onClick={() => onPick('Call')} className="btn-ghost">Practise via Call</button>}
      </div>
    </div>
  );
}

function ActiveCase(props: {
  currentCase: Case;
  channel: 'Chat' | 'Call';
  transcript: Turn[];
  awaiting: 'agent' | 'customer';
  streamingText?: string;
  caseNumber: number;
  caseTotal: number;
  agentTurnsTaken: number;
  onSubmitAgent: (text: string) => void;
}) {
  const [draft, setDraft] = useState('');
  const [error, setError] = useState<string | null>(null);
  const speech = useSpeechRecognition({ lang: 'en-IN' });
  const scrollRef = useRef<HTMLDivElement>(null);
  const agentTurns = props.agentTurnsTaken;
  const progress = Math.min(100, Math.round((agentTurns / MAX_TURNS) * 100));

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [props.transcript]);

  function submit() {
    if (props.awaiting !== 'agent') return;
    const text = draft.trim();
    if (!text) return setError('Please type or speak a reply.');
    setError(null);
    setDraft('');
    props.onSubmitAgent(text);
  }

  return (
    <div className="space-y-4 animate-fade-in" data-testid="active-case">
      <div className="flex items-center gap-3">
        <div className="chip">Case {props.caseNumber}/{props.caseTotal}</div>
        <div className="flex-1 h-1.5 rounded-full bg-ink-200 dark:bg-ink-800 overflow-hidden">
          <div className="h-full bg-emerald-500 transition-all duration-500" style={{ width: `${progress}%` }} aria-hidden="true" />
        </div>
        <div className="text-xs font-medium text-ink-500 tabular-nums">Turn {Math.min(agentTurns + (props.awaiting === 'agent' ? 1 : 0), MAX_TURNS)} / {MAX_TURNS}</div>
      </div>

      <div className="card overflow-hidden">
        <div className="flex items-center justify-between border-b border-ink-200 dark:border-ink-700 bg-ink-100/60 dark:bg-ink-900/60 px-4 py-2">
          <div className="text-sm font-medium">{props.currentCase.title}</div>
          <div className="text-xs text-ink-500">{props.channel} channel</div>
        </div>

        <div ref={scrollRef} className="max-h-[360px] overflow-y-auto p-4 space-y-3" data-testid="transcript">
          {props.transcript.map((t, i) => <Bubble key={i} role={t.role} text={t.text} />)}
          {props.awaiting === 'customer' && (
            props.streamingText && props.streamingText.length > 0
              ? <Bubble role="customer" text={props.streamingText} streaming />
              : <Bubble role="customer" text="…" typing />
          )}
        </div>

        <div className="border-t border-ink-200 dark:border-ink-700 bg-ink-50/60 dark:bg-ink-900/40 p-3">
          {props.channel === 'Chat' ? (
            <div className="flex items-end gap-2">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); } }}
                rows={2}
                disabled={props.awaiting !== 'agent'}
                placeholder={props.awaiting === 'customer' ? 'Waiting for customer…' : 'Type your reply — Enter to send'}
                className="flex-1 rounded-md border border-ink-200 dark:border-ink-700 bg-white dark:bg-ink-900 px-3 py-2 text-sm disabled:opacity-50"
                data-testid="agent-input"
              />
              <button type="button" onClick={submit} disabled={props.awaiting !== 'agent' || !draft.trim()} data-testid="btn-send" className="btn-primary">Send</button>
            </div>
          ) : (
            <CallControls
              disabled={props.awaiting !== 'agent'}
              draft={draft}
              onDraft={setDraft}
              onSend={submit}
              speech={speech}
            />
          )}
          {error && <div className="mt-2 text-xs text-rose-600">{error}</div>}
        </div>
      </div>
    </div>
  );
}

function Bubble({ role, text, typing, streaming }: { role: 'agent' | 'customer'; text: string; typing?: boolean; streaming?: boolean }) {
  const isAgent = role === 'agent';
  return (
    <div className={`flex ${isAgent ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm leading-relaxed shadow-sm ${
        isAgent
          ? 'bg-indigo-600 text-white rounded-br-sm'
          : 'bg-white dark:bg-ink-800 text-ink-800 dark:text-ink-100 rounded-bl-sm border border-ink-200/70 dark:border-ink-700/70'
      }`}>
        <div className={`text-[10px] uppercase tracking-wider font-semibold mb-1 opacity-70 ${isAgent ? 'text-white/80' : ''} flex items-center gap-1.5`}>
          {isAgent ? 'You' : 'Customer'}
          {streaming && <span aria-hidden="true" className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse-soft" title="streaming live" />}
        </div>
        <div className={typing ? 'animate-pulse-soft' : ''}>
          {text}
          {streaming && <span className="inline-block w-1.5 h-3.5 bg-current opacity-60 ml-0.5 align-text-bottom animate-pulse-soft" aria-hidden="true" />}
        </div>
      </div>
    </div>
  );
}

function CallControls(props: {
  disabled: boolean;
  draft: string;
  onDraft: (v: string) => void;
  onSend: () => void;
  speech: ReturnType<typeof useSpeechRecognition>;
}) {
  useEffect(() => {
    if (props.speech.interim) props.onDraft(props.draft ? props.draft + ' ' + props.speech.interim : props.speech.interim);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.speech.interim]);

  if (!props.speech.supported) {
    return (
      <div className="text-xs text-ink-500">
        Voice input isn’t supported in this browser (Chrome / Edge required). You can still type your reply:
        <div className="mt-2 flex gap-2">
          <input value={props.draft} onChange={(e) => props.onDraft(e.target.value)} disabled={props.disabled}
            className="flex-1 rounded-md border border-ink-200 dark:border-ink-700 bg-white dark:bg-ink-900 px-3 py-2 text-sm"
            data-testid="agent-input"
            placeholder="Type your reply…" />
          <button type="button" onClick={props.onSend} disabled={props.disabled || !props.draft.trim()} data-testid="btn-send" className="btn-primary">Send</button>
        </div>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        onClick={() => props.speech.isListening ? props.speech.stop() : props.speech.start((finalText) => props.onDraft(props.draft ? props.draft + ' ' + finalText : finalText))}
        disabled={props.disabled}
        data-testid="btn-mic"
        className={`inline-flex h-11 w-11 items-center justify-center rounded-full text-lg shadow-sm transition ${
          props.speech.isListening
            ? 'bg-rose-600 text-white animate-pulse-soft'
            : 'bg-indigo-600 text-white hover:bg-indigo-700'
        } disabled:opacity-40`}
        aria-label={props.speech.isListening ? 'Stop recording' : 'Start recording'}
      >{props.speech.isListening ? '■' : '●'}</button>
      <div className="flex-1 rounded-md border border-ink-200 dark:border-ink-700 bg-white dark:bg-ink-900 px-3 py-2 text-sm min-h-[44px] flex items-center" data-testid="agent-input">
        {props.draft || <span className="text-ink-500 italic">Press ● and speak — release when done…</span>}
      </div>
      <button type="button" onClick={props.onSend} disabled={props.disabled || !props.draft.trim()} data-testid="btn-send" className="btn-primary">Send</button>
    </div>
  );
}

function ScoringCard() {
  return (
    <div className="card p-8 text-center animate-fade-in" data-testid="scoring">
      <div className="mx-auto h-12 w-12 rounded-full border-2 border-indigo-500/40 border-t-indigo-600 animate-spin" />
      <h3 className="mt-4 font-display text-lg font-semibold">Reviewing your responses…</h3>
      <p className="mt-1 text-sm text-ink-500">Claude Sonnet 4.6 is auditing empathy, accuracy, resolution and professionalism.</p>
    </div>
  );
}

function ScorecardView(props: {
  scorecard: Scorecard;
  completed: CompletedCase;
  currentCase: Case;
  isLast: boolean;
  onNext: () => void;
}) {
  const { scorecard, completed, currentCase, isLast, onNext } = props;
  const dims: Array<[keyof Scorecard, string]> = [
    ['empathyScore',        'Empathy & Tone'],
    ['accuracyScore',       'Accuracy'],
    ['resolutionScore',     'Resolution'],
    ['professionalismScore','Professionalism'],
  ];
  const tone = scorecard.overallScore >= 80 ? 'emerald' : scorecard.overallScore >= 60 ? 'amber' : 'rose';
  const toneMap = {
    emerald: 'from-emerald-500/20 to-emerald-500/5 text-emerald-700 dark:text-emerald-300',
    amber:   'from-amber-500/20  to-amber-500/5  text-amber-700  dark:text-amber-300',
    rose:    'from-rose-500/20   to-rose-500/5   text-rose-700   dark:text-rose-300',
  } as const;

  // Optional per-turn feedback lookup: agentTurnIndex → note.
  const notesByTurn = new Map<number, NonNullable<Scorecard['perTurnNotes']>[number]>();
  (scorecard.perTurnNotes ?? []).forEach((n) => notesByTurn.set(n.agentTurnIndex, n));

  return (
    <div className="card overflow-hidden animate-slide-up" data-testid="scorecard">
      <div className={`bg-gradient-to-br ${toneMap[tone]} px-6 py-6 flex items-center justify-between`}>
        <div>
          <div className="text-xs font-medium uppercase tracking-wider opacity-80">Overall score</div>
          <div className="mt-1 flex items-baseline gap-1 animate-score-count">
            <span className="font-display text-5xl font-black tabular-nums">{scorecard.overallScore}</span>
            <span className="text-lg opacity-70">/100</span>
          </div>
        </div>
        <div className="text-right text-xs opacity-80 max-w-[50%]">
          <div className="font-semibold uppercase tracking-wider mb-1">Strength</div>
          <div>{scorecard.strength}</div>
        </div>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4">
        {dims.map(([k, label]) => (
          <div key={k} className="rounded-lg border border-ink-200/70 dark:border-ink-700/70 bg-white/60 dark:bg-ink-900/40 p-3">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-ink-500">{label}</div>
            <div className="mt-1 font-display text-2xl font-semibold tabular-nums">{scorecard[k] as number}</div>
          </div>
        ))}
      </div>
      <div className="border-t border-ink-200 dark:border-ink-700 px-6 py-4 bg-ink-50/60 dark:bg-ink-900/30">
        <div className="text-xs font-semibold uppercase tracking-wider text-ink-500 mb-1">Where to improve</div>
        <p className="text-sm text-ink-800 dark:text-ink-100">{scorecard.improvement}</p>
      </div>

      {/* Per-turn rubric heatmap — show colour-coded transcript. */}
      {notesByTurn.size > 0 && (
        <div className="border-t border-ink-200 dark:border-ink-700 px-6 py-4" data-testid="rubric-transcript">
          <div className="text-xs font-semibold uppercase tracking-wider text-ink-500 mb-3">Turn-by-turn feedback</div>
          <RubricAnnotatedTranscript transcript={completed.transcript} notesByTurn={notesByTurn} />
        </div>
      )}

      {/* Model-answer reveal */}
      <ModelAnswerSection currentCase={currentCase} />

      <div className="flex justify-end p-4">
        <button type="button" onClick={onNext} data-testid="btn-next-case" className="btn-primary">
          {isLast ? 'See session summary →' : 'Next case →'}
        </button>
      </div>
    </div>
  );
}

function RubricAnnotatedTranscript({
  transcript,
  notesByTurn,
}: {
  transcript: Turn[];
  notesByTurn: Map<number, NonNullable<Scorecard['perTurnNotes']>[number]>;
}) {
  let agentTurnIndex = -1;
  const dimColour: Record<string, string> = {
    empathy:        'bg-rose-500/10    text-rose-700    dark:text-rose-300    border-rose-500/30',
    accuracy:       'bg-indigo-500/10  text-indigo-700  dark:text-indigo-300  border-indigo-500/30',
    resolution:     'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30',
    professionalism:'bg-amber-500/10   text-amber-700   dark:text-amber-300   border-amber-500/30',
  };
  return (
    <div className="space-y-2">
      {transcript.map((t, i) => {
        if (t.role === 'agent') agentTurnIndex++;
        const note = t.role === 'agent' ? notesByTurn.get(agentTurnIndex) : undefined;
        return (
          <div key={i} className={`rounded-lg border p-2 text-sm ${t.role === 'agent' ? 'bg-indigo-500/5 border-indigo-500/20' : 'bg-ink-100/60 dark:bg-ink-900/40 border-ink-200/60 dark:border-ink-700/60'}`}>
            <div className="flex items-baseline gap-2 mb-1">
              <span className="text-[10px] uppercase tracking-wider font-semibold text-ink-500">{t.role === 'agent' ? `You · turn ${agentTurnIndex + 1}` : 'Customer'}</span>
              {note && (
                <span className={`chip ${dimColour[note.dimension]} text-[10px]`}>
                  {note.sentiment === 'strong' ? '↑' : '↓'} {note.dimension}
                </span>
              )}
            </div>
            <div className="text-ink-800 dark:text-ink-100">{t.text}</div>
            {note && (
              <div className={`mt-1 text-xs italic ${note.sentiment === 'strong' ? 'text-emerald-700 dark:text-emerald-400' : 'text-rose-700 dark:text-rose-400'}`}>
                {note.note}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function ModelAnswerSection({ currentCase }: { currentCase: Case }) {
  const [state, setState] = useState<{ status: 'idle' | 'loading' | 'ok' | 'error'; data?: ModelAnswer; error?: string }>({ status: 'idle' });

  async function fetchIdeal() {
    setState({ status: 'loading' });
    try {
      const data = await callModelAnswer({
        scenario: currentCase.scenario,
        opening: currentCase.opening,
        difficulty: currentCase.difficulty,
      });
      setState({ status: 'ok', data });
    } catch (err) {
      setState({ status: 'error', error: err instanceof ApiError ? err.message : 'Failed to fetch model answer.' });
    }
  }

  return (
    <div className="border-t border-ink-200 dark:border-ink-700 px-6 py-4" data-testid="model-answer">
      {state.status === 'idle' && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-ink-500">Learn from an A+ reply</div>
            <p className="mt-0.5 text-sm text-ink-700 dark:text-ink-200">See how an expert agent might have handled this exact scenario.</p>
          </div>
          <button type="button" onClick={fetchIdeal} data-testid="btn-model-answer" className="btn-ghost">
            Show A+ transcript →
          </button>
        </div>
      )}
      {state.status === 'loading' && (
        <div className="flex items-center gap-3 text-sm text-ink-500">
          <div className="h-4 w-4 rounded-full border-2 border-indigo-500/40 border-t-indigo-600 animate-spin" />
          Composing an ideal transcript…
        </div>
      )}
      {state.status === 'error' && (
        <div className="text-sm text-rose-600 dark:text-rose-400">
          Couldn't fetch model answer: {state.error}
          <button type="button" onClick={fetchIdeal} className="ml-2 underline">retry</button>
        </div>
      )}
      {state.status === 'ok' && state.data && (
        <div className="space-y-2 animate-fade-in">
          <div className="text-xs font-semibold uppercase tracking-wider text-ink-500">A+ transcript · why this works</div>
          <p className="text-sm italic text-ink-700 dark:text-ink-200">{state.data.commentary}</p>
          <div className="space-y-1.5 pt-1">
            {state.data.transcript.map((t, i) => (
              <div key={i} className={`rounded-lg border p-2 text-sm ${t.role === 'agent' ? 'bg-emerald-500/5 border-emerald-500/20' : 'bg-ink-100/60 dark:bg-ink-900/40 border-ink-200/60 dark:border-ink-700/60'}`}>
                <div className="text-[10px] uppercase tracking-wider font-semibold text-ink-500 mb-0.5">
                  {t.role === 'agent' ? 'Model agent' : 'Customer'}
                </div>
                <div className="text-ink-800 dark:text-ink-100">{t.text}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function DPDPAConsent(props: { onAccept: () => void; onCancel: () => void }) {
  return (
    <div className="card p-6 sm:p-8 animate-slide-up border-amber-500/40" data-testid="dpdpa-consent">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 inline-flex h-8 w-8 flex-none items-center justify-center rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400 text-lg">🔒</div>
        <div className="min-w-0 flex-1">
          <div className="text-xs font-semibold uppercase tracking-wider text-amber-700 dark:text-amber-400">Compliance training aid</div>
          <h2 className="mt-0.5 font-display text-xl font-semibold">Pre-call disclosure &amp; consent</h2>
          <p className="mt-2 text-sm text-ink-700 dark:text-ink-200">
            On a real customer call, India's <strong>Digital Personal Data Protection Act (2023)</strong>
            requires you to disclose the purpose of the call and obtain explicit consent
            <em> before</em> recording. Practise the script below with your simulated customer.
          </p>
          <blockquote className="mt-4 border-l-2 border-amber-500/60 pl-3 text-sm italic text-ink-700 dark:text-ink-200">
            "Hello, this is [name] from [company]. This call is being recorded for quality
            and training purposes. May I have your consent to proceed?"
          </blockquote>
          <div className="mt-4 rounded-lg border border-ink-200 dark:border-ink-700 bg-ink-100/60 dark:bg-ink-900/40 p-3 text-xs text-ink-600 dark:text-ink-300">
            <div className="font-semibold uppercase tracking-wider text-ink-500 mb-1">Client-side data safety</div>
            Any PII you speak or type (Aadhaar, PAN, mobile number, card number, UPI ID, email)
            is <strong>automatically redacted before leaving your browser</strong>. The upstream
            LLM never sees the raw values — only <code>[AADHAAR_REDACTED]</code> etc.
          </div>
          <div className="mt-6 flex flex-wrap justify-end gap-2">
            <button type="button" onClick={props.onCancel} data-testid="btn-dpdpa-cancel" className="btn-ghost">Cancel</button>
            <button type="button" onClick={props.onAccept} data-testid="btn-dpdpa-accept" className="btn-primary">I've read this &mdash; start Call practice</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function SummaryCard(props: { completed: CompletedCase[]; average: number; streak: number }) {
  return (
    <div className="card p-6 sm:p-8 animate-slide-up text-center" data-testid="summary">
      <div className="inline-flex items-center gap-2 chip">🔥 Streak · {props.streak} day{props.streak === 1 ? '' : 's'}</div>
      <div className="mt-4 font-display text-4xl sm:text-5xl font-black tabular-nums">{props.average}<span className="text-2xl opacity-60">/100</span></div>
      <p className="mt-2 text-sm text-ink-600 dark:text-ink-300">Session average across {props.completed.length} cases.</p>
      <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-3 text-left">
        {props.completed.map((c) => (
          <div key={c.caseId + c.completedAt} className="rounded-lg border border-ink-200/70 dark:border-ink-700/70 bg-white/60 dark:bg-ink-900/40 p-3">
            <div className="text-xs text-ink-500 truncate">{c.caseTitle}</div>
            <div className="mt-1 font-display text-2xl font-semibold tabular-nums">{c.scorecard.overallScore}</div>
          </div>
        ))}
      </div>
      <div className="mt-6 flex justify-center gap-3">
        <a href="/dashboard" className="btn-primary">View dashboard →</a>
        <a href="/" className="btn-ghost">Back to home</a>
      </div>
    </div>
  );
}
