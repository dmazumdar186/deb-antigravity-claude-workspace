import { useEffect, useMemo, useState } from 'react';
import { loadState, saveState } from '../lib/storage';
import type { Case, Channel, Difficulty } from '../lib/types';

const CHANNELS: Channel[] = ['Chat', 'Call', 'Both'];
const DIFFICULTIES: Difficulty[] = ['Beginner', 'Intermediate', 'Advanced'];
const KNOWN_TOPICS = ['Billing', 'De-escalation', 'Technical', 'Retention', 'Policy Exception', 'Onboarding', 'Other'];

const difficultyChip: Record<Difficulty, string> = {
  Beginner:     'bg-emerald-500/10 text-emerald-600 border-emerald-500/30 dark:text-emerald-400',
  Intermediate: 'bg-amber-500/10  text-amber-600  border-amber-500/30  dark:text-amber-400',
  Advanced:     'bg-rose-500/10   text-rose-600   border-rose-500/30   dark:text-rose-400',
};

const channelChip: Record<Channel, string> = {
  Chat: 'bg-indigo-500/10 text-indigo-600 border-indigo-500/30 dark:text-indigo-400',
  Call: 'bg-ink-500/10 text-ink-700 border-ink-500/30 dark:text-ink-300',
  Both: 'bg-ink-500/10 text-ink-700 border-ink-500/30 dark:text-ink-300',
};

export default function CasesIsland() {
  const [cases, setCases] = useState<Case[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [topicFilter, setTopicFilter] = useState('');
  const [channelFilter, setChannelFilter] = useState('');
  const [difficultyFilter, setDifficultyFilter] = useState('');

  useEffect(() => { setCases(loadState().cases); }, []);

  const filtered = useMemo(() => cases.filter((c) =>
    (!topicFilter || c.topic === topicFilter) &&
    (!channelFilter || c.channel === channelFilter) &&
    (!difficultyFilter || c.difficulty === difficultyFilter)
  ), [cases, topicFilter, channelFilter, difficultyFilter]);

  const topics = useMemo(() => Array.from(new Set(cases.map((c) => c.topic))).sort(), [cases]);

  function saveCase(newCase: Case) {
    const state = loadState();
    const updated = { ...state, cases: [newCase, ...state.cases] };
    saveState(updated);
    setCases(updated.cases);
    setShowForm(false);
  }

  function deleteCustom(id: string) {
    if (!confirm('Delete this case? Default cases cannot be deleted.')) return;
    const state = loadState();
    const updated = { ...state, cases: state.cases.filter((c) => c.id !== id || c.isDefault) };
    saveState(updated);
    setCases(updated.cases);
  }

  return (
    <div className="space-y-6">
      {/* Filter bar + Add button */}
      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-ink-200 dark:border-ink-700 bg-white/60 dark:bg-ink-900/40 p-4">
        <FilterSelect label="Topic"      value={topicFilter}      onChange={setTopicFilter}      options={topics} />
        <FilterSelect label="Channel"    value={channelFilter}    onChange={setChannelFilter}    options={CHANNELS} />
        <FilterSelect label="Difficulty" value={difficultyFilter} onChange={setDifficultyFilter} options={DIFFICULTIES} />
        <div className="flex-1" />
        <button type="button" onClick={() => setShowForm(true)} data-testid="btn-new-case" className="btn-primary">
          + New case
        </button>
      </div>

      {/* Cases table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-ink-100 dark:bg-ink-900 text-ink-600 dark:text-ink-300 text-xs uppercase tracking-wide">
              <tr>
                <th className="px-4 py-3">Title</th>
                <th className="px-4 py-3">Topic</th>
                <th className="px-4 py-3">Channel</th>
                <th className="px-4 py-3">Difficulty</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody data-testid="cases-list">
              {filtered.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-10 text-center text-ink-500">
                  No cases match these filters.
                </td></tr>
              )}
              {filtered.map((c) => (
                <tr key={c.id} className="border-t border-ink-200/60 dark:border-ink-700/60 hover:bg-ink-100/40 dark:hover:bg-ink-900/40 transition-colors">
                  <td className="px-4 py-3 font-medium">
                    <div className="flex items-center gap-2">
                      <span>{c.title}</span>
                      {c.isDefault && <span className="chip text-[10px] uppercase tracking-wider">default</span>}
                    </div>
                    <div className="text-xs text-ink-500 mt-0.5 max-w-xl line-clamp-1">{c.scenario}</div>
                  </td>
                  <td className="px-4 py-3 text-ink-700 dark:text-ink-200">{c.topic}</td>
                  <td className="px-4 py-3"><span className={`chip ${channelChip[c.channel]}`}>{c.channel}</span></td>
                  <td className="px-4 py-3"><span className={`chip ${difficultyChip[c.difficulty]}`}>{c.difficulty}</span></td>
                  <td className="px-4 py-3 text-right">
                    {!c.isDefault && (
                      <button type="button" onClick={() => deleteCustom(c.id)} className="text-xs text-rose-600 hover:underline">
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {showForm && <NewCaseModal onSave={saveCase} onClose={() => setShowForm(false)} />}
    </div>
  );
}

function FilterSelect(props: { label: string; value: string; onChange: (v: string) => void; options: string[] }) {
  return (
    <label className="flex flex-col gap-1 text-xs font-medium text-ink-600 dark:text-ink-300">
      <span>{props.label}</span>
      <select
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
        className="rounded-md border border-ink-200 dark:border-ink-700 bg-white dark:bg-ink-900 px-2 py-1.5 text-sm text-ink-800 dark:text-ink-100"
        data-testid={`filter-${props.label.toLowerCase()}`}
      >
        <option value="">All</option>
        {props.options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
}

function NewCaseModal(props: { onSave: (c: Case) => void; onClose: () => void }) {
  const [title, setTitle]           = useState('');
  const [scenario, setScenario]     = useState('');
  const [opening, setOpening]       = useState('');
  const [channel, setChannel]       = useState<Channel>('Chat');
  const [topic, setTopic]           = useState('Billing');
  const [customTopic, setCustomTopic] = useState('');
  const [difficulty, setDifficulty] = useState<Difficulty>('Intermediate');
  const [err, setErr] = useState<string | null>(null);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const finalTopic = topic === 'Other' ? customTopic.trim() : topic;
    if (title.trim().length < 5 || title.trim().length > 50) return setErr('Title must be 5–50 characters.');
    if (scenario.trim().length < 50) return setErr('Scenario must be at least 50 characters.');
    if (opening.trim().length < 1) return setErr('Opening message is required.');
    if (!finalTopic) return setErr('Please pick or type a topic.');
    props.onSave({
      id: 'cust-' + Math.random().toString(36).slice(2, 10),
      title: title.trim(),
      scenario: scenario.trim(),
      opening: opening.trim(),
      channel, topic: finalTopic, difficulty,
      createdAt: new Date().toISOString(),
    });
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-ink-950/60 backdrop-blur-sm animate-fade-in" role="dialog" aria-modal="true">
      <div className="card w-full max-w-xl m-4 p-6 animate-slide-up">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display text-xl font-semibold">New case</h2>
          <button type="button" onClick={props.onClose} className="text-ink-500 hover:text-ink-800 dark:hover:text-white" aria-label="Close">✕</button>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <Field label="Title">
            <input value={title} onChange={(e) => setTitle(e.target.value)} data-testid="in-title"
              className="w-full rounded-md border border-ink-200 dark:border-ink-700 bg-white dark:bg-ink-900 px-3 py-2 text-sm" />
          </Field>
          <Field label="Customer scenario">
            <textarea value={scenario} onChange={(e) => setScenario(e.target.value)} rows={4} data-testid="in-scenario"
              className="w-full rounded-md border border-ink-200 dark:border-ink-700 bg-white dark:bg-ink-900 px-3 py-2 text-sm" />
          </Field>
          <Field label="Customer opening message">
            <textarea value={opening} onChange={(e) => setOpening(e.target.value)} rows={2} data-testid="in-opening"
              className="w-full rounded-md border border-ink-200 dark:border-ink-700 bg-white dark:bg-ink-900 px-3 py-2 text-sm" />
          </Field>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Field label="Channel">
              <select value={channel} onChange={(e) => setChannel(e.target.value as Channel)} className="w-full rounded-md border border-ink-200 dark:border-ink-700 bg-white dark:bg-ink-900 px-3 py-2 text-sm">
                {CHANNELS.map((c) => <option key={c}>{c}</option>)}
              </select>
            </Field>
            <Field label="Topic">
              <select value={topic} onChange={(e) => setTopic(e.target.value)} data-testid="in-topic" className="w-full rounded-md border border-ink-200 dark:border-ink-700 bg-white dark:bg-ink-900 px-3 py-2 text-sm">
                {KNOWN_TOPICS.map((t) => <option key={t}>{t}</option>)}
              </select>
            </Field>
            <Field label="Difficulty">
              <select value={difficulty} onChange={(e) => setDifficulty(e.target.value as Difficulty)} className="w-full rounded-md border border-ink-200 dark:border-ink-700 bg-white dark:bg-ink-900 px-3 py-2 text-sm">
                {DIFFICULTIES.map((d) => <option key={d}>{d}</option>)}
              </select>
            </Field>
          </div>
          {topic === 'Other' && (
            <Field label="Custom topic">
              <input value={customTopic} onChange={(e) => setCustomTopic(e.target.value)} className="w-full rounded-md border border-ink-200 dark:border-ink-700 bg-white dark:bg-ink-900 px-3 py-2 text-sm" />
            </Field>
          )}
          {err && <div className="rounded-md bg-rose-500/10 px-3 py-2 text-sm text-rose-600 dark:text-rose-400">{err}</div>}
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={props.onClose} className="btn-ghost">Cancel</button>
            <button type="submit" data-testid="btn-save-case" className="btn-primary">Save case</button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Field(props: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-ink-500">{props.label}</span>
      {props.children}
    </label>
  );
}
