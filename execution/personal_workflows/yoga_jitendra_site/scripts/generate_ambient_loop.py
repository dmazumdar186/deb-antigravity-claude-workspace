"""Generate the site's ambient audio loop: soft bansuri flute phrases over a
gentle Sa-Pa drone. Reference the client pointed at (2026-09-01): Nu
Meditation Music's "Hatha Yoga Music" (bansuri flute, soft Indian
instrumental) — we synthesize in that STYLE; the actual track is copyrighted
and cannot be embedded.

History of this asset (client-driven):
  procedural raga engine (short random flute chirps -> read as "bird sounds")
  -> birds-dawn.mp3 (actual birds; client: not soothing)
  -> himalayan-chant.mp3 (chant + bowls; client: "very wild, Metallica")
  -> serene-dawn.mp3 (piano + pad, Einaudi direction)
  -> bansuri-dawn.mp3 (this file): long breathy bansuri phrases with meend
  glides, D-major-pentatonic, over a quiet D drone. The fix for the original
  "bird chirp" failure is PHRASING: long low notes, slow glides, real rests.

Fully synthesized (numpy) so the asset is rights-free and regenerable.
~92 s seamless loop, encoded to MP3 via lameenc (pip install --user lameenc).

Usage (NOTE: run with the default interpreter, not `py script.py` — the py
launcher would dispatch a shebang to a different Python; see
.claude/rules/python-hardening.md rule 7):
    py -3.14 scripts/generate_ambient_loop.py            # writes public/assets/audio/bansuri-dawn.mp3
    py -3.14 scripts/generate_ambient_loop.py --wav-out  # also writes a WAV for listening checks

Loop seamlessness: phrase tails wrap circularly (index modulo N); the final
mix gets a 4 s equal-power crossfade of tail into head, then the tail is
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
OUT_MP3 = OUT_DIR / "bansuri-dawn.mp3"

rng = np.random.default_rng(20260901)   # deterministic — same file every run


def fail(msg: str) -> None:
    # sys.exit, not assert: gates must survive `py -O` (output-acceptance-gate
    # discipline — an optimized run must not silently skip the checks).
    sys.exit(f"[ambient] GATE FAILED: {msg}")


# ── Musical material ────────────────────────────────────────────────────────
# D major pentatonic in the bansuri's warm middle register (D4-D5). The drone
# holds Sa (D) and Pa (A) underneath — Indian-style static harmony, no western
# chord changes to fight the flute.

SCALE = [293.66, 329.63, 369.99, 440.00, 493.88, 587.33]   # D4 E4 F#4 A4 B4 D5
DRONE_TONES = [
    (73.42, 1.00, -0.10),   # D2
    (110.00, 0.55, 0.15),   # A2
    (146.83, 0.45, -0.20),  # D3
    (220.00, 0.22, 0.20),   # A3
]


# ── Layer 1: Sa-Pa drone ────────────────────────────────────────────────────
# Near-sine tones with a faint slow shimmer on the upper harmonics — evokes a
# tanpura's glow without the buzz (buzz is what read "wild" in the chant mix).

def drone() -> np.ndarray:
    left = np.zeros(N)
    right = np.zeros(N)
    breath = 0.90 + 0.10 * np.sin(2 * np.pi * 2 * T / DUR)          # 2 cycles/loop
    shimmer = 0.5 + 0.5 * np.sin(2 * np.pi * 5 * T / DUR + 1.3)     # 5 cycles/loop
    for f, amp, pan in DRONE_TONES:
        for det, dgain in ((1.0, 1.0), (1.0012, 0.45)):
            fd = f * det
            tone = (np.sin(2 * np.pi * fd * T)
                    + 0.16 * np.sin(2 * np.pi * 2 * fd * T)
                    + (0.05 + 0.03 * shimmer) * np.sin(2 * np.pi * 3 * fd * T)
                    + 0.02 * shimmer * np.sin(2 * np.pi * 4 * fd * T))
            sig = amp * dgain * tone
            left += np.sqrt(0.5 * (1 - pan)) * sig
            right += np.sqrt(0.5 * (1 + pan)) * sig
    out = np.stack([left * breath, right * breath])
    return out / np.max(np.abs(out))


# ── Layer 2: bansuri phrases ────────────────────────────────────────────────
# Each phrase: 3-5 long notes (1.8-3.8 s) connected by meend glides, vibrato
# that blooms mid-note, a breathy noise component that follows the envelope,
# soft attack/release, then a real rest before the next phrase.

def _phrase_freq_track(notes, durs, glide=0.15):
    """Piecewise frequency track with linear glides between notes."""
    segs = []
    for i, (f, d) in enumerate(zip(notes, durs)):
        n_hold = int(SR * max(d - glide, 0.2))
        segs.append(np.full(n_hold, f))
        if i < len(notes) - 1:
            n_gl = int(SR * glide)
            segs.append(np.linspace(f, notes[i + 1], n_gl, endpoint=False))
    return np.concatenate(segs)


def _phrase_env(notes, durs, total_n):
    """Per-note swells inside one overall phrase arc."""
    env = np.zeros(total_n)
    pos = 0
    for f, d in zip(notes, durs):
        n = int(SR * d)
        n = min(n, total_n - pos)
        if n <= 0:
            break
        tt = np.arange(n) / SR
        a = np.clip(tt / 0.25, 0, 1)                    # soft 250 ms attack
        r = np.clip((d - tt) / 0.40, 0, 1)              # 400 ms release
        swell = 0.85 + 0.15 * np.sin(np.pi * np.clip(tt / d, 0, 1))
        env[pos:pos + n] = np.maximum(env[pos:pos + n],
                                      (0.5 - 0.5 * np.cos(np.pi * a)) *
                                      (0.5 - 0.5 * np.cos(np.pi * r)) * swell)
        pos += n
    # overall phrase arc so no phrase barks in or cuts off
    arc = np.sin(np.pi * np.clip(np.arange(total_n) / total_n, 0, 1)) ** 0.35
    return env * arc


def bansuri() -> np.ndarray:
    left = np.zeros(N)
    right = np.zeros(N)
    t = 3.0
    while t < DUR - 6.0:
        n_notes = int(rng.integers(3, 6))
        idx = int(rng.integers(1, len(SCALE) - 1))
        notes = []
        for _ in range(n_notes):
            notes.append(SCALE[idx])
            step = int(rng.integers(-2, 3))
            idx = int(np.clip(idx + step, 0, len(SCALE) - 1))
        durs = [1.8 + 2.0 * rng.random() for _ in notes]
        freq = _phrase_freq_track(notes, durs)
        L = len(freq)
        tt = np.arange(L) / SR
        # vibrato blooms after the first second of each phrase
        vib_depth = 0.004 * np.clip((tt - 1.0) / 1.5, 0, 1)
        freq = freq * (1.0 + vib_depth * np.sin(2 * np.pi * 5.1 * tt))
        phase = 2 * np.pi * np.cumsum(freq) / SR
        tone = (np.sin(phase)
                + 0.34 * np.sin(2 * phase)
                + 0.10 * np.sin(3 * phase)
                + 0.03 * np.sin(4 * phase))
        env = _phrase_env(notes, durs, L)
        # breathiness: band-tilted noise riding the same envelope
        noise = rng.standard_normal(L)
        spec = np.fft.rfft(noise)
        fr = np.fft.rfftfreq(L, 1 / SR)
        band = np.exp(-0.5 * ((fr - 900.0) / 700.0) ** 2)
        breathn = np.fft.irfft(spec * band, n=L)
        breathn /= max(np.max(np.abs(breathn)), 1e-9)
        vel = 0.55 + 0.15 * rng.random()
        sig = vel * env * (tone + 0.09 * breathn)
        pan = float(rng.uniform(-0.2, 0.2))
        pos = (int(t * SR) + np.arange(L)) % N
        np.add.at(left, pos, np.sqrt(0.5 * (1 - pan)) * sig)
        np.add.at(right, pos, np.sqrt(0.5 * (1 + pan)) * sig)
        t += L / SR + 5.5 + 4.5 * rng.random()          # real rest between phrases
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
    # flute-forward; drone is a cushion, not a wall
    mix = 0.22 * drone() + 0.50 * bansuri() + 0.016 * air_wash()
    mix /= np.max(np.abs(mix))
    mix *= 0.62   # deliberate headroom — this bed should sit low

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
    if not (-34 < rms_db < -14):
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
