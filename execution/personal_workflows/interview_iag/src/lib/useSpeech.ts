// React hooks for the browser's native Web Speech API. Cribbed from
// the case study's Section 4 pattern, hardened for missing-support gracefully.

import { useEffect, useRef, useState, useCallback } from 'react';

// Chrome/Edge expose webkitSpeechRecognition; Firefox has no SpeechRecognition
// at all (Nightly gated). We surface `supported: false` so the UI can fall
// back to a "type instead" message rather than silently breaking.

interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: {
    length: number;
    [i: number]: { isFinal: boolean; [j: number]: { transcript: string } };
  };
}

export function useSpeechRecognition(opts?: { lang?: string }): {
  supported: boolean;
  isListening: boolean;
  interim: string;
  start: (onFinal: (text: string) => void) => void;
  stop: () => void;
} {
  const lang = opts?.lang ?? 'en-IN';
  const [supported, setSupported] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [interim, setInterim] = useState('');
  const recRef = useRef<any>(null);
  const finalCbRef = useRef<((text: string) => void) | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) { setSupported(false); return; }
    setSupported(true);
    const rec = new SR();
    rec.continuous = false;
    rec.interimResults = true;
    rec.lang = lang;

    rec.onstart = () => setIsListening(true);
    rec.onend   = () => { setIsListening(false); setInterim(''); };
    rec.onerror = () => { setIsListening(false); setInterim(''); };

    rec.onresult = (event: SpeechRecognitionEventLike) => {
      let interimText = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const r = event.results[i];
        const chunk = r[0]?.transcript ?? '';
        if (r.isFinal) { finalCbRef.current?.(chunk); }
        else { interimText += chunk; }
      }
      setInterim(interimText);
    };
    recRef.current = rec;
    return () => { try { rec.stop(); } catch { /* ignore */ } };
  }, [lang]);

  const start = useCallback((onFinal: (text: string) => void) => {
    finalCbRef.current = onFinal;
    try { recRef.current?.start(); } catch { /* already started */ }
  }, []);
  const stop = useCallback(() => { try { recRef.current?.stop(); } catch { /* ignore */ } }, []);

  return { supported, isListening, interim, start, stop };
}

export function speak(text: string, opts?: { rate?: number; pitch?: number; lang?: string }): void {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.rate  = opts?.rate  ?? 1.0;
  u.pitch = opts?.pitch ?? 1.0;
  u.lang  = opts?.lang  ?? 'en-IN';
  const voices = window.speechSynthesis.getVoices();
  const pick = voices.find((v) => v.lang === u.lang) ||
               voices.find((v) => v.lang.startsWith('en-')) ||
               voices[0];
  if (pick) u.voice = pick;
  window.speechSynthesis.speak(u);
}

export function speakByDifficulty(text: string, difficulty: 'Beginner' | 'Intermediate' | 'Advanced'): void {
  const map = {
    Beginner:     { rate: 0.95, pitch: 1.05 },
    Intermediate: { rate: 1.00, pitch: 1.00 },
    Advanced:     { rate: 1.15, pitch: 0.95 },
  } as const;
  speak(text, map[difficulty]);
}
