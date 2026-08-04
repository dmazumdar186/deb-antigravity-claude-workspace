// Streaming text → sentence-chunked speech synthesis.
//
// Idea: as text tokens arrive from the LLM, buffer them until we see a
// natural break (`.`, `?`, `!`, `,` — in that priority) or exceed a soft
// max. Then hand the chunk to `SpeechSynthesisUtterance` and continue
// buffering the rest. This gives time-to-first-audio of ~200-500ms
// instead of ~2s (wait-for-full-response).
//
// The chunker is a stateful class so multiple stream consumers don't fight
// over the shared window.speechSynthesis queue.

export interface ChunkedSpeakerOptions {
  rate?: number;
  pitch?: number;
  lang?: string;
  minChunkChars?: number;    // don't speak chunks shorter than this
  softMaxChunkChars?: number; // force-flush around this length
}

const PHRASE_REGEX = /^[^.!?,]+[.!?,]/;

export class ChunkedSpeaker {
  private buffer = '';
  private queued = 0;
  private opts: Required<ChunkedSpeakerOptions>;
  private cancelled = false;

  constructor(opts: ChunkedSpeakerOptions = {}) {
    this.opts = {
      rate:  opts.rate  ?? 1.0,
      pitch: opts.pitch ?? 1.0,
      lang:  opts.lang  ?? 'en-IN',
      minChunkChars:     opts.minChunkChars     ?? 8,
      softMaxChunkChars: opts.softMaxChunkChars ?? 140,
    };
  }

  /** Feed a text delta. Speaks complete phrases as they emerge. */
  feed(delta: string): void {
    if (this.cancelled) return;
    this.buffer += delta;
    // Emit as many complete phrases as we can find.
    while (true) {
      const m = this.buffer.match(PHRASE_REGEX);
      if (m && m[0].length >= this.opts.minChunkChars) {
        this.speak(m[0].trim());
        this.buffer = this.buffer.slice(m[0].length);
        continue;
      }
      // If buffer's grown past soft max without hitting punctuation, split
      // on the last whitespace to avoid mid-word cuts.
      if (this.buffer.length >= this.opts.softMaxChunkChars) {
        const cut = this.buffer.lastIndexOf(' ', this.opts.softMaxChunkChars);
        if (cut > this.opts.minChunkChars) {
          this.speak(this.buffer.slice(0, cut).trim());
          this.buffer = this.buffer.slice(cut).trimStart();
          continue;
        }
      }
      break;
    }
  }

  /** Flush any remaining buffered text as one final chunk. */
  finish(): void {
    if (this.cancelled) return;
    const rest = this.buffer.trim();
    if (rest.length > 0) this.speak(rest);
    this.buffer = '';
  }

  /** Stop all queued + current speech. */
  cancel(): void {
    this.cancelled = true;
    this.buffer = '';
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
  }

  private speak(text: string): void {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    const u = new SpeechSynthesisUtterance(text);
    u.rate  = this.opts.rate;
    u.pitch = this.opts.pitch;
    u.lang  = this.opts.lang;
    const voices = window.speechSynthesis.getVoices();
    const pick = voices.find((v) => v.lang === this.opts.lang) ||
                 voices.find((v) => v.lang.startsWith('en-')) ||
                 voices[0];
    if (pick) u.voice = pick;
    window.speechSynthesis.speak(u);
    this.queued++;
  }
}
