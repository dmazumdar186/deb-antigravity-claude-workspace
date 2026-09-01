"""Generate the site's ambient audio loop: deep monk-chant drone + Tibetan
singing bowls. Replaces birds-dawn.mp3 (client feedback 2026-09-01: bird
sounds not soothing enough; asked for something like Tibetan chanting).

Fully synthesized (numpy) so the asset is rights-free — no CC0 hunting, no
attribution, regenerable at will. ~96 s seamless loop, encoded to MP3 via
lameenc (pip install --user lameenc).

Usage:
    py scripts/generate_ambient_loop.py            # writes public/assets/audio/himalayan-chant.mp3
    py scripts/generate_ambient_loop.py --wav-out  # also keeps a WAV next to it for listening checks

Loop seamlessness: bowl-strike decay tails wrap circularly (index modulo N);
the final mix gets a 4 s equal-power crossfade of tail into head, then the
tail is truncated. <audio loop> plays it gaplessly enough for ambience
(browser MP3 loop gaps are masked by the drone's slow breathing).
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
OUT_MP3 = OUT_DIR / "himalayan-chant.mp3"

rng = np.random.default_rng(20260901)   # deterministic — same file every run


# ── Layer 1: monk chant drone ────────────────────────────────────────────────
# Three detuned voices on C2 (65.41 Hz), additive harmonics shaped by two
# vowel formants that slowly morph O → M (hum) and back, 3 cycles per loop.

def chant_drone() -> np.ndarray:
    f0 = 65.41
    n_harm = 14
    # formant morph 0..1, integer cycles per loop so it self-loops
    morph = 0.5 + 0.5 * np.sin(2 * np.pi * 3 * T / DUR - np.pi / 2)
    # formant centers (Hz): "O" -> "M"
    f1 = 420 - 170 * morph          # 420 -> 250
    f2 = 850 - 250 * morph          # 850 -> 600
    f2_gain = 0.7 - 0.45 * morph    # F2 fades as lips close on the M

    # slow breath: 4 cycles per loop, gentle 20 % swell
    breath = 0.9 + 0.1 * np.sin(2 * np.pi * 4 * T / DUR)

    voices = [
        (1.0000, -0.25, 0.0),
        (1.0040,  0.25, 2.1),
        (0.9965,  0.00, 4.2),
    ]
    left = np.zeros(N)
    right = np.zeros(N)
    for detune, pan, phase0 in voices:
        v = np.zeros(N)
        for h in range(1, n_harm + 1):
            fh = f0 * detune * h
            # base 1/h rolloff plus time-varying formant emphasis
            g1 = np.exp(-0.5 * ((fh - f1) / 110.0) ** 2)
            g2 = f2_gain * np.exp(-0.5 * ((fh - f2) / 140.0) ** 2)
            gain = (1.0 / h) * (0.25 + g1 + g2)
            # tiny per-harmonic vibrato (integer cycles/loop keeps the seam clean)
            vib = 1.0 + 0.0012 * np.sin(2 * np.pi * (432 + 7 * h) * T / DUR + h)
            v += gain * np.sin(2 * np.pi * fh * np.cumsum(vib) / SR + phase0)
        v *= breath
        v /= np.max(np.abs(v))
        gl = np.sqrt(0.5 * (1 - pan))
        gr = np.sqrt(0.5 * (1 + pan))
        left += gl * v
        right += gr * v
    out = np.stack([left, right])
    return out / np.max(np.abs(out))


# ── Layer 2: Tibetan singing bowls ───────────────────────────────────────────
# Inharmonic partials (measured-bowl ratios), long decays, twin detuned
# partials for the characteristic slow "wah" beating. Tails wrap modulo N.

BOWL_RATIOS = [1.0, 2.71, 5.18, 8.16, 11.66]
BOWL_GAINS = [1.0, 0.55, 0.30, 0.16, 0.08]
BOWL_TAUS = [15.0, 8.0, 5.0, 3.2, 2.2]     # decay time constants (s)

STRIKES = [  # (time s, fundamental Hz, pan, level)
    (8.0, 196.00, -0.4, 0.9),    # G3
    (26.0, 146.83, 0.35, 0.8),   # D3
    (47.0, 174.61, -0.2, 0.85),  # F3
    (66.0, 130.81, 0.4, 0.9),    # C3
    (84.0, 164.81, -0.35, 0.75), # E3
]


def bowls() -> np.ndarray:
    left = np.zeros(N)
    right = np.zeros(N)
    tail = int(SR * 30)  # render 30 s of decay per strike, wrapped
    tt = np.arange(tail) / SR
    attack = 0.5 * (1 - np.cos(np.pi * np.minimum(tt / 0.008, 1.0)))
    for t0, f0, pan, lvl in STRIKES:
        s = np.zeros(tail)
        for ratio, g, tau in zip(BOWL_RATIOS, BOWL_GAINS, BOWL_TAUS):
            f = f0 * ratio
            beat = 0.6 + 1.3 * ratio / 5.0   # Hz offset between the twin partials
            env = g * np.exp(-tt / tau)
            s += env * (np.sin(2 * np.pi * f * tt)
                        + 0.85 * np.sin(2 * np.pi * (f + beat) * tt + 0.7))
        s *= attack * lvl
        idx = (int(t0 * SR) + np.arange(tail)) % N
        gl = np.sqrt(0.5 * (1 - pan))
        gr = np.sqrt(0.5 * (1 + pan))
        np.add.at(left, idx, gl * s)
        np.add.at(right, idx, gr * s)
    out = np.stack([left, right])
    return out / np.max(np.abs(out))


# ── Layer 3: soft mountain-air wash ─────────────────────────────────────────

def air_wash() -> np.ndarray:
    noise = rng.standard_normal((2, N))
    spec = np.fft.rfft(noise, axis=1)
    freqs = np.fft.rfftfreq(N, 1 / SR)
    # pink-ish tilt + lowpass at ~450 Hz
    shape = 1.0 / np.sqrt(np.maximum(freqs, 20.0))
    shape *= 1.0 / (1.0 + (freqs / 450.0) ** 4)
    spec *= shape
    wash = np.fft.irfft(spec, n=N, axis=1)
    swell = 0.75 + 0.25 * np.sin(2 * np.pi * 2 * T / DUR + 1.0)
    wash *= swell
    return wash / np.max(np.abs(wash))


# ── Mix, loop-fold, master ──────────────────────────────────────────────────

def build() -> np.ndarray:
    mix = 0.34 * chant_drone() + 0.44 * bowls() + 0.035 * air_wash()
    # gentle soft-knee saturation, then normalize with headroom
    mix = np.tanh(1.3 * mix) / np.tanh(1.3)
    mix /= np.max(np.abs(mix))
    mix *= 0.89

    # equal-power crossfade: fold the last XFADE s into the first XFADE s
    xn = int(SR * XFADE)
    fade_in = np.sin(0.5 * np.pi * np.arange(xn) / xn)
    fade_out = np.cos(0.5 * np.pi * np.arange(xn) / xn)
    head = mix[:, :xn] * fade_in + mix[:, -xn:] * fade_out
    out = np.concatenate([head, mix[:, xn:-xn]], axis=1)
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
    path.write_bytes(bytes(data))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    audio = build()
    dur = audio.shape[1] / SR
    rms_db = 20 * np.log10(np.sqrt(np.mean(audio ** 2)))
    print(f"[ambient] duration {dur:.1f}s  peak {np.max(np.abs(audio)):.3f}  rms {rms_db:.1f} dBFS")
    # sanity gates — hard-fail rather than ship a broken asset
    assert 85 < dur < 95, "unexpected loop duration"
    assert -30 < rms_db < -8, "level way off — inspect before shipping"
    seam = np.max(np.abs(audio[:, 0] - audio[:, -1]))
    print(f"[ambient] loop-seam sample delta {seam:.4f}")
    encode_mp3(audio, OUT_MP3)
    size_kb = OUT_MP3.stat().st_size / 1024
    print(f"[ambient] wrote {OUT_MP3} ({size_kb:.0f} KB)")
    assert size_kb < 2048, "asset too large for a page-weight budget"
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
