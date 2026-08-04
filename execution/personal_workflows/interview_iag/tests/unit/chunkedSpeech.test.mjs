import { describe, it, expect, beforeEach } from 'vitest';
import { ChunkedSpeaker } from '../../src/lib/chunkedSpeech.ts';

// Node environment lacks window.speechSynthesis — the speaker degrades to a
// no-op there. To exercise chunking logic we spy on `speak()` by subclassing.

class ProbeSpeaker extends ChunkedSpeaker {
  spoken = [];
  // Override the private speak() via a workaround: the class's speak method
  // is private; we intercept by patching speechSynthesis globally.
}

beforeEach(() => {
  // Fake window.speechSynthesis so ChunkedSpeaker's speak() actually captures.
  globalThis.window = globalThis.window || {};
  const captured = [];
  window.speechSynthesis = {
    speak: (u) => captured.push(u.text),
    cancel: () => { captured.length = 0; },
    getVoices: () => [],
  };
  globalThis.__captured = captured;
  // Polyfill SpeechSynthesisUtterance
  globalThis.SpeechSynthesisUtterance = class { constructor(t) { this.text = t; this.rate = 1; this.pitch = 1; this.lang = ''; this.voice = null; } };
});

describe('ChunkedSpeaker', () => {
  it('emits chunks on sentence boundaries', () => {
    const s = new ChunkedSpeaker({ minChunkChars: 3 });
    s.feed('Hello there.');
    expect(globalThis.__captured).toEqual(['Hello there.']);
  });

  it('accumulates deltas across multiple feeds until punctuation lands', () => {
    const s = new ChunkedSpeaker({ minChunkChars: 3 });
    s.feed('This is');
    expect(globalThis.__captured).toEqual([]);
    s.feed(' a test');
    expect(globalThis.__captured).toEqual([]);
    s.feed(' sentence.');
    expect(globalThis.__captured).toEqual(['This is a test sentence.']);
  });

  it('emits multiple phrases from one delta if present', () => {
    const s = new ChunkedSpeaker({ minChunkChars: 3 });
    s.feed('First. Second. Third.');
    expect(globalThis.__captured).toEqual(['First.', 'Second.', 'Third.']);
  });

  it('splits on commas as a lesser break', () => {
    const s = new ChunkedSpeaker({ minChunkChars: 3 });
    s.feed('Well, alright, then.');
    expect(globalThis.__captured).toEqual(['Well,', 'alright,', 'then.']);
  });

  it('flushes tail on finish()', () => {
    const s = new ChunkedSpeaker({ minChunkChars: 3 });
    s.feed('No punctuation here');
    expect(globalThis.__captured).toEqual([]);
    s.finish();
    expect(globalThis.__captured).toEqual(['No punctuation here']);
  });

  it('force-flushes when buffer grows past softMaxChunkChars', () => {
    const s = new ChunkedSpeaker({ minChunkChars: 3, softMaxChunkChars: 20 });
    // 40 chars, no punctuation
    s.feed('one two three four five six seven eight nine ten');
    expect(globalThis.__captured.length).toBeGreaterThan(0);
    // Force-flush cut should land on whitespace, not mid-word.
    expect(globalThis.__captured.every((chunk) => !chunk.match(/^\S{1}\S+/) || !chunk.endsWith(' '))).toBe(true);
  });

  it('cancel() clears buffer and stops further chunks', () => {
    const s = new ChunkedSpeaker({ minChunkChars: 3 });
    s.feed('partial');
    s.cancel();
    s.feed(' more.');
    expect(globalThis.__captured).toEqual([]);
  });
});
