import { describe, it, expect } from 'vitest';
import { extractJsonObject, isScorecard } from '../../functions/api/claude.ts';

describe('extractJsonObject', () => {
  it('parses a raw JSON object', () => {
    expect(extractJsonObject('{"a":1}')).toEqual({ a: 1 });
  });

  it('strips markdown fences', () => {
    const raw = '```json\n{"x":42}\n```';
    expect(extractJsonObject(raw)).toEqual({ x: 42 });
  });

  it('handles prose preamble', () => {
    const raw = 'Here is the scorecard you requested:\n{"score":88}';
    expect(extractJsonObject(raw)).toEqual({ score: 88 });
  });

  it('handles prose postamble', () => {
    const raw = '{"score":88}\n\nLet me know if you want more detail.';
    expect(extractJsonObject(raw)).toEqual({ score: 88 });
  });

  it('handles nested objects', () => {
    const raw = '```\n{"outer":{"inner":{"n":7}}}\n```';
    expect(extractJsonObject(raw)).toEqual({ outer: { inner: { n: 7 } } });
  });

  it('throws on missing braces', () => {
    expect(() => extractJsonObject('no braces here')).toThrow(/no_json_braces/);
  });

  it('throws on inverted brace order', () => {
    expect(() => extractJsonObject('} then {')).toThrow(/no_json_braces/);
  });

  it('throws on invalid JSON with recognisable diagnostic', () => {
    expect(() => extractJsonObject('{not json}')).toThrow(/invalid_json/);
  });
});

describe('isScorecard', () => {
  const good = {
    empathyScore: 80, accuracyScore: 70, resolutionScore: 60, professionalismScore: 90,
    overallScore: 75, strength: 'clear tone', improvement: 'be more specific',
  };

  it('accepts a well-formed scorecard', () => {
    expect(isScorecard(good)).toBe(true);
  });

  it('rejects null/undefined/non-objects', () => {
    expect(isScorecard(null)).toBe(false);
    expect(isScorecard(undefined)).toBe(false);
    expect(isScorecard(42)).toBe(false);
    expect(isScorecard('x')).toBe(false);
  });

  it('rejects when a numeric field is missing', () => {
    const { empathyScore, ...rest } = good;
    expect(isScorecard(rest)).toBe(false);
  });

  it('rejects when a numeric field is out of [0,100]', () => {
    expect(isScorecard({ ...good, empathyScore: 110 })).toBe(false);
    expect(isScorecard({ ...good, empathyScore: -1 })).toBe(false);
  });

  it('rejects when a text field is empty', () => {
    expect(isScorecard({ ...good, strength: '' })).toBe(false);
    expect(isScorecard({ ...good, improvement: '' })).toBe(false);
  });

  it('rejects when a numeric field is a string', () => {
    expect(isScorecard({ ...good, empathyScore: '80' })).toBe(false);
  });
});
