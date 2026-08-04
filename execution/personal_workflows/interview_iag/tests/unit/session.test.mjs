import { describe, it, expect } from 'vitest';
import {
  pickDailyCases, updateStreak, averageOfScores, sessionAverage,
  daily30, groupByKey, summaryStats, daysBetween, newSessionFromCompletedCases,
} from '../../src/lib/session.ts';

const cases = [
  { id: 'a', title: 'A', scenario: 's', opening: 'o', channel: 'Chat', topic: 'Billing', difficulty: 'Beginner' },
  { id: 'b', title: 'B', scenario: 's', opening: 'o', channel: 'Call', topic: 'Tech', difficulty: 'Advanced' },
  { id: 'c', title: 'C', scenario: 's', opening: 'o', channel: 'Chat', topic: 'Billing', difficulty: 'Intermediate' },
  { id: 'd', title: 'D', scenario: 's', opening: 'o', channel: 'Chat', topic: 'Retention', difficulty: 'Beginner' },
  { id: 'e', title: 'E', scenario: 's', opening: 'o', channel: 'Both', topic: 'Tech', difficulty: 'Advanced' },
];

const scorecard = (n) => ({
  empathyScore: n, accuracyScore: n, resolutionScore: n, professionalismScore: n,
  overallScore: n, strength: 'x', improvement: 'x',
});

const completed = (id, topic, channel, n, difficulty = 'Beginner') => ({
  caseId: id, caseTitle: id.toUpperCase(), topic, channel, difficulty,
  transcript: [], scorecard: scorecard(n), completedAt: '2026-07-27T10:00:00Z',
});

describe('pickDailyCases', () => {
  it('is deterministic for the same date', () => {
    const a = pickDailyCases(cases, '2026-07-27');
    const b = pickDailyCases(cases, '2026-07-27');
    expect(a.map((c) => c.id)).toEqual(b.map((c) => c.id));
  });

  it('picks different cases on different dates (on average)', () => {
    const days = ['2026-07-27', '2026-07-28', '2026-07-29', '2026-07-30', '2026-07-31'];
    const picks = new Set(days.map((d) => pickDailyCases(cases, d).map((c) => c.id).join(',')));
    expect(picks.size).toBeGreaterThan(1);
  });

  it('never picks duplicates within a day', () => {
    const picked = pickDailyCases(cases, '2026-07-27', 3);
    expect(new Set(picked.map((c) => c.id)).size).toBe(picked.length);
  });

  it('picks min(pool, n) when pool is small', () => {
    const picked = pickDailyCases(cases.slice(0, 2), '2026-07-27', 3);
    expect(picked.length).toBe(2);
  });

  it('returns empty on empty pool', () => {
    expect(pickDailyCases([], '2026-07-27')).toEqual([]);
  });
});

describe('daysBetween + updateStreak', () => {
  it('daysBetween basics', () => {
    expect(daysBetween('2026-07-27', '2026-07-27')).toBe(0);
    expect(daysBetween('2026-07-27', '2026-07-28')).toBe(1);
    expect(daysBetween('2026-07-27', '2026-08-03')).toBe(7);
  });

  it('first run initializes streak to 1', () => {
    expect(updateStreak({ count: 0, lastDate: null }, '2026-07-27'))
      .toEqual({ count: 1, lastDate: '2026-07-27' });
  });

  it('same-day repeat does not double-count', () => {
    expect(updateStreak({ count: 3, lastDate: '2026-07-27' }, '2026-07-27'))
      .toEqual({ count: 3, lastDate: '2026-07-27' });
  });

  it('consecutive day increments', () => {
    expect(updateStreak({ count: 5, lastDate: '2026-07-27' }, '2026-07-28'))
      .toEqual({ count: 6, lastDate: '2026-07-28' });
  });

  it('gap > 1 day resets to 1', () => {
    expect(updateStreak({ count: 12, lastDate: '2026-07-20' }, '2026-07-27'))
      .toEqual({ count: 1, lastDate: '2026-07-27' });
  });
});

describe('averageOfScores + sessionAverage', () => {
  it('rounds to nearest integer', () => {
    expect(averageOfScores([80, 81, 82])).toBe(81);
    expect(averageOfScores([80, 81])).toBe(81); // rounded up (80.5→81)
  });
  it('empty → 0', () => expect(averageOfScores([])).toBe(0));
  it('sessionAverage uses overall', () => {
    const cs = [completed('a', 'Billing', 'Chat', 80), completed('b', 'Tech', 'Call', 90)];
    expect(sessionAverage(cs)).toBe(85);
  });
});

describe('daily30', () => {
  it('produces exactly 30 points ending on today', () => {
    const points = daily30([], '2026-07-27');
    expect(points.length).toBe(30);
    expect(points[29].date).toBe('2026-07-27');
    expect(points[0].date).toBe('2026-06-28');
  });

  it('averages multiple sessions on the same day', () => {
    const sessions = [
      { id: 's1', date: '2026-07-27', cases: [], averageScore: 80 },
      { id: 's2', date: '2026-07-27', cases: [], averageScore: 90 },
    ];
    const pts = daily30(sessions, '2026-07-27');
    expect(pts[29].score).toBe(85);
    expect(pts[29].sessions).toBe(2);
  });

  it('zeroes out days with no sessions', () => {
    const pts = daily30([], '2026-07-27');
    expect(pts.every((p) => p.score === 0 && p.sessions === 0)).toBe(true);
  });
});

describe('groupByKey', () => {
  const sessions = [
    { id: 's1', date: '2026-07-27', cases: [
      completed('a', 'Billing', 'Chat', 80),
      completed('b', 'Billing', 'Call', 60),
      completed('c', 'Tech',    'Chat', 90),
    ], averageScore: 77 },
  ];

  it('groups by topic and averages correctly', () => {
    const pts = groupByKey(sessions, (c) => c.topic);
    const map = Object.fromEntries(pts.map((p) => [p.key, p.score]));
    expect(map.Billing).toBe(70);
    expect(map.Tech).toBe(90);
    expect(pts[0].key).toBe('Tech'); // sorted desc
  });

  it('groups by channel', () => {
    const pts = groupByKey(sessions, (c) => c.channel);
    const map = Object.fromEntries(pts.map((p) => [p.key, p.score]));
    expect(map.Chat).toBe(85);
    expect(map.Call).toBe(60);
  });
});

describe('summaryStats', () => {
  it('empty state → no top/weak skill', () => {
    const s = summaryStats({ cases: [], sessions: [], streak: { count: 0, lastDate: null } });
    expect(s.streak).toBe(0);
    expect(s.sessionsThisWeek).toBe(0);
    expect(s.topSkill).toBeNull();
    expect(s.weakSkill).toBeNull();
  });

  it('surfaces top and weak dimensions distinctly', () => {
    const c1 = {
      caseId: 'a', caseTitle: 'A', topic: 'Billing', channel: 'Chat', difficulty: 'Beginner',
      transcript: [], completedAt: '2026-07-27T10:00:00Z',
      scorecard: { empathyScore: 95, accuracyScore: 60, resolutionScore: 70, professionalismScore: 85,
                   overallScore: 78, strength: 'x', improvement: 'x' },
    };
    const s = summaryStats({
      cases: [], sessions: [{ id: 's1', date: '2026-07-27', cases: [c1], averageScore: 78 }],
      streak: { count: 1, lastDate: '2026-07-27' },
    });
    expect(s.topSkill?.label).toBe('Empathy & Tone');
    expect(s.weakSkill?.label).toBe('Accuracy');
  });
});

describe('newSessionFromCompletedCases', () => {
  it('computes averageScore and assigns date', () => {
    const cs = [completed('a', 'X', 'Chat', 70), completed('b', 'Y', 'Chat', 90)];
    const s = newSessionFromCompletedCases(cs, '2026-07-27');
    expect(s.date).toBe('2026-07-27');
    expect(s.averageScore).toBe(80);
    expect(s.cases.length).toBe(2);
    expect(s.id).toMatch(/^sess-2026-07-27-/);
  });
});
