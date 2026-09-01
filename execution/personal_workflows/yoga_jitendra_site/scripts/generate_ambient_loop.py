"""Generate the site's ambient audio loop: soft felt-piano notes over a warm,
quiet pad. Einaudi-direction calm (sparse, minimal, gentle) — NOT chant, NOT
bowls, NOT birds.

History of this asset (client-driven):
  procedural raga engine -> birds-dawn.mp3 (client: bird sounds not soothing)
  -> himalayan-chant.mp3 v1 (chant drone + singing bowls; client 2026-09-01:
  "very wild; think Metallica, I want Ludovico Einaudi")
  -> serene-dawn.mp3 (this file): slow Am-F-C-G pad + sparse pentatonic
  felt-piano tones, everything soft and low-level.

Fully synthesized (numpy) so the asset is rights-free and regenerable.
~92 s seamless loop, encoded to MP3 via lameenc (pip install --user lameenc).

Usage (NOTE: run with the default interpreter, not `py script.py` — the py
launcher would dispatch a shebang to a different Python; see
.claude/rules/python-hardening.md rule 7):
    py -3.14 scripts/generate_ambient_loop.py            # writes public/assets/audio/serene-dawn.mp3
    py -3.14 scripts/generate_ambient_loop.py --wav-out  # also writes a WAV for listening checks

Loop seamlessness: note tails wrap circularly (index modulo N); the final mix
gets a 4 s equal-power crossfade of tail into head, then the tail is
truncated, and the result is re-normalized (the fold can push peaks past 1.0).
"""

import sys
from pathlib import Path

import numpy as np

SR = 44100
DUR = 96.0                      # seconds before crossfade-truncate
XFADE = 4.0                     # seconds of tail folded into head
N = int(SR * DUR)
T = np.arange(N) / SR

OUT_DIR = Path(__file__).resolve().parent.parent / "public" / "assets" / "audio"
OUT_MP3 = OUT_DIR / "serene-dawn.mp3"

rng = np.random.default_rng(20260901)   # deterministic — same file every run


def fail(msg: str) -> None:
    # sys.exit, not assert: gates must survive `py -O` (output-acceptance-gate
    # discipline — an optimized run must not silently skip the checks).
    sys.exit(f"[ambient] GATE FAILED: {msg}")


# ── Harmony: Am - F - C - G, 12 s per chord, cycle twice per loop ───────────
# Root frequencies (Hz) and chord-tone semitone offsets from the root.

CHORDS = [
    (110.00, [0, 7, 12, 15]),   # A minor  (A2)
    (87.31,  [0, 7, 12, 16]),   # F major  (F2)
    (130.81, [0, 7, 12, 16]),   # C major  (C3)
    (98.00,  [0, 7, 12, 16]),   # G major  (G2)
]
CHORD_LEN = 12.0
PROGRESSION = CHORDS + CHORDS   # 8 slots x 12 s = 96 s

# Note pool for the sparse melody: chord tones two octaves up, plus the 9th
# as a soft color tone. Kept inside A-minor-pentatonic-friendly territory.
MELODY_OFFSETS = [24, 31, 36, 38, 43]

semitone = lambda f, s: f * (2.0 ** (s / 12.0))


# ── Layer 1: warm pad ───────────────────────────────────────────────────────
# Near-sine tones (tiny 2nd/3rd harmonic) per chord tone, slow raised-cosine
# attack/release so consecutive chords melt into each other. Two detuned
# layers for warmth. No formants, no beating — nothing growls.

def pad() -> np.ndarray:
    left = np.zeros(N)
    right = np.zeros(N)
    atk, rel = 3.0, 4.0
    for k, (root, offsets) in enumerate(PROGRESSION):
        t0, t1 = k * CHORD_LEN, (k + 1) * CHORD_LEN
        # trapezoid envelope with raised-cosine edges, wrapped modulo loop
        env = np.zeros(N)
        tt = (T - t0) % DUR
        rise = np.clip(tt / atk, 0, 1)
        span = CHORD_LEN + rel
        fall = np.clip((span - tt) / rel, 0, 1)
        inside = tt < span
        env[inside] = (0.5 - 0.5 * np.cos(np.pi * rise[inside])) * \
                      (0.5 - 0.5 * np.cos(np.pi * fall[inside]))
        for i, off in enumerate(offsets):
            f = semitone(root, off)
            amp = [1.0, 0.75, 0.6, 0.4][i]
            pan = [-0.2, 0.15, -0.1, 0.25][i]
            for det, dgain in ((1.0, 1.0), (1.0015, 0.5)):
                fd = f * det
                tone = (np.sin(2 * np.pi * fd * T)
                        + 0.18 * np.sin(2 * np.pi * 2 * fd * T)
                        + 0.05 * np.sin(2 * np.pi * 3 * fd * T))
                sig = amp * dgain * env * tone
                left += np.sqrt(0.5 * (1 - pan)) * sig
                right += np.sqrt(0.5 * (1 + pan)) * sig
    # slow breathing, integer cycles per loop so the seam stays clean
    breath = 0.92 + 0.08 * np.sin(2 * np.pi * 2 * T / DUR)
    out = np.stack([left * breath, right * breath])
    return out / np.max(np.abs(out))


# ── Layer 2: sparse felt-piano notes ────────────────────────────────────────
# Soft attack, fast-decaying upper harmonics, long sustain on the fundamental.
# One note every ~3.5-7 s, chord tones only, gentle velocities.

def felt_piano() -> np.ndarray:
    left = np.zeros(N)
    right = np.zeros(N)
    tail = int(SR * 9)
    tt = np.arange(tail) / SR
    attack = 0.5 * (1 - np.cos(np.pi * np.minimum(tt / 0.02, 1.0)))
    harm_amps = [1.0, 0.30, 0.12, 0.05, 0.025]
    harm_taus = [3.2, 1.6, 0.9, 0.55, 0.35]

    t = 1.2
    while t < DUR - 0.5:
        k = int(t // CHORD_LEN) % len(PROGRESSION)
        root, _ = PROGRESSION[k]
        off = MELODY_OFFSETS[rng.integers(0, len(MELODY_OFFSETS))]
        f = semitone(root, off)
        vel = 0.24 + 0.24 * rng.random()
        pan = float(rng.uniform(-0.35, 0.35))
        note = np.zeros(tail)
        for a, tau, h in zip(harm_amps, harm_taus, range(1, 6)):
            note += a * np.exp(-tt / tau) * np.sin(2 * np.pi * f * h * tt)
        note *= attack * vel
        idx = (int(t * SR) + np.arange(tail)) % N
        np.add.at(left, idx, np.sqrt(0.5 * (1 - pan)) * note)
        np.add.at(right, idx, np.sqrt(0.5 * (1 + pan)) * note)
        t += 4.5 + 3.5 * rng.random()
    out = np.stack([left, right])
    return out / np.max(np.abs(out))


# ── Layer 3: very soft air wash ─────────────────────────────────────────────

def air_wash() -> np.ndarray:
    noise = rng.standard_normal((2, N))
    spec = np.fft.rfft(noise, axis=1)
    freqs = np.fft.rfftfreq(N, 1 / SR)
    shape = 1.0 / np.sqrt(np.maximum(freqs, 20.0))
    shape *= 1.0 / (1.0 + (freqs / 380.0) ** 4)
    spec *= shape
    wash = np.fft.irfft(spec, n=N, axis=1)
    swell = 0.8 + 0.2 * np.sin(2 * np.pi * 2 * T / DUR + 1.0)
    wash *= swell
    return wash / np.max(np.abs(wash))


# ── Mix, loop-fold, master ──────────────────────────────────────────────────

def build() -> np.ndarray:
    # piano-forward, pad as a quiet cushion underneath (Einaudi direction:
    # sparse notes with space around them, not a wall of sustained tone)
    mix = 0.26 * pad() + 0.46 * felt_piano() + 0.018 * air_wash()
    mix /= np.max(np.abs(mix))
    mix *= 0.72   # deliberate headroom — this bed should sit low

    # equal-power crossfade: fold the last XFADE s into the first XFADE s
    xn = int(SR * XFADE)
    fade_in = np.sin(0.5 * np.pi * np.arange(xn) / xn)
    fade_out = np.cos(0.5 * np.pi * np.arange(xn) / xn)
    head = mix[:, :xn] * fade_in + mix[:, -xn:] * fade_out
    out = np.concatenate([head, mix[:, xn:-xn]], axis=1)
    # the fold sums two signals — re-normalize if it pushed past full scale
    peak = np.max(np.abs(out))
    if peak > 0.95:
        out *= 0.95 / peak
    return out


def encode_mp3(audio: np.ndarray, path: Path) -> None:
    import lameenc
    pcm = np.clip(audio, -1, 1)
    interleaved = (pcm.T.reshape(-1) * 32767).astype(np.int16)
    enc = lameenc.Encoder()
    enc.set_bit_rate(112)
    enc.set_in_sample_rate(SR)
    enc.set_channels(2)
    enc.set_quality(2)
    data = enc.encode(interleaved.tobytes())
    data += enc.flush()
    if len(data) > 2 * 1024 * 1024:
        fail(f"encoded asset too large ({len(data)/1024:.0f} KB) — not writing")
    path.write_bytes(bytes(data))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    audio = build()
    dur = audio.shape[1] / SR
    peak = float(np.max(np.abs(audio)))
    rms_db = float(20 * np.log10(np.sqrt(np.mean(audio ** 2))))
    seam = float(np.max(np.abs(audio[:, 0] - audio[:, -1])))
    print(f"[ambient] duration {dur:.1f}s  peak {peak:.3f}  rms {rms_db:.1f} dBFS  seam {seam:.4f}")
    if not (85 < dur < 95):
        fail(f"unexpected loop duration {dur:.1f}s")
    if not (-32 < rms_db < -14):
        fail(f"level off target ({rms_db:.1f} dBFS) — inspect before shipping")
    if peak > 1.0:
        fail(f"peak {peak:.3f} > 1.0 — would clip at encode")
    if seam > 0.05:
        fail(f"loop seam delta {seam:.4f} too large — crossfade broken")
    encode_mp3(audio, OUT_MP3)
    print(f"[ambient] wrote {OUT_MP3} ({OUT_MP3.stat().st_size/1024:.0f} KB)")
    if "--wav-out" in sys.argv:
        import wave
        wav_path = OUT_MP3.with_suffix(".wav")
        pcm = (np.clip(audio, -1, 1).T.reshape(-1) * 32767).astype(np.int16)
        with wave.open(str(wav_path), "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(pcm.tobytes())
        print(f"[ambient] wrote {wav_path} for listening check")


if __name__ == "__main__":
    main()
