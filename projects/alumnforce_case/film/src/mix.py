"""Trusted Segments — score, foley, beds and voice → out/mix.wav (+ out/stems/*.wav).
Reads out/timeline.json (tools/export.mjs) and voice/out/*.wav. Run from anywhere: python mix.py
Score: 72 BPM, D minor turning to F major; felt piano (Salamander), string sections (VSCO 2 CE), bowed vibraphone and
glockenspiel (VCSL). Foley procedural (core/audio/sfx.py)."""
import os, sys, json
import numpy as np, soundfile as sf, soxr, time
T0 = time.time()
HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.environ.get('LIB') or os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, LIB)
from core.audio import sampler as S
from core.audio import sfx as X
from core.audio.sfx import SR, add

TL = json.load(open(os.path.join(HERE, 'out', 'timeline.json')))
H, WD, DUR, BEAT = TL['hit'], TL['words'], TL['dur'], 60 / 72
N = int(DUR * SR) + SR
S.seed(72)
rng = np.random.default_rng(12)
bt = lambda n: n * BEAT

# ---------------- score ----------------
ev = []
def pn(t, p, d, v, pan=-.15): ev.append((t, 'piano', p, d, v, pan))
CH = {'Dm': ('D3', ['D4', 'F4', 'A4', 'E5']), 'Bb': ('A#2', ['D4', 'F4', 'A#4', 'C5']), 'F': ('F2', ['C4', 'F4', 'A4', 'C5']), 'C': ('C3', ['C4', 'E4', 'G4', 'D5']),
      'Gm': ('G2', ['D4', 'G4', 'A#4', 'D5'])}
PROG = ['Dm', 'Bb', 'F', 'C']
up = lambda p, k: S.name(S.midi(p) + k)

# A — the query (0 → lightOn): single felt-piano notes every two beats
for i, p in enumerate(['D4', 'A4', 'F4', 'E4', 'D4', 'C5']):
    t = 0.42 + i * bt(2) * 0.9
    if t < H['lightOn'] - 0.3: pn(t, p, bt(2.2), .30)
# B — the table (lightOn → climb): quarter-note broken chords, a low string pad
t = H['lightOn']; k = 0
while t < H['climb'] - 0.05:
    ch = PROG[k % 4]; bass, top = CH[ch]
    pn(t, bass, bt(4), .32, -.3)
    ev.append((t, 'cellos', up(bass, 12) if S.midi(bass) < 43 else bass, bt(4), .30, .25))
    for j in range(4):
        if t + bt(j) < H['climb'] - 0.05: pn(t + bt(j), top[j], bt(1.2), .27 + .03 * (j == 0))
    t += bt(4); k += 1
# C — the climb (climb → hush1): eighths, a register step at each answer, violas join
t = H['climb']; k = 0
while t < H['hush1'] - 0.05:
    ch = PROG[k % 4]; bass, top = CH[ch]
    lift = 0 if t < WD['n26'] - 0.5 else 5 if t < WD['n49'] - 0.5 else 12
    pn(t, bass, bt(4), .34, -.3)
    ev.append((t, 'cellos', up(bass, 12) if S.midi(bass) < 43 else bass, bt(4), .34, .25))
    if lift: ev.append((t, 'violas', up(top[1], 0), bt(4), .26 + .04 * (lift == 12), .35))
    pat = [0, 1, 2, 1, 3, 2, 1, 2]
    for j in range(8):
        tt = t + bt(j / 2)
        if tt < H['hush1'] - 0.05:
            p = top[pat[j]]; p = up(p, 12) if lift == 12 and j % 2 else up(p, 0)
            pn(tt, p, bt(.6), .25 + .04 * (j % 2 == 0) + .03 * (lift > 0))
    t += bt(4); k += 1
# hits on each answer
for w in ('n2', 'n26', 'n49'): ev.append((WD[w], 'glockenspiel', {'n2': 'A5', 'n26': 'D6', 'n49': 'F6'}[w], 1.2, .38, .2))
# silence 1 (hush1 → drop2): nothing
# D — the turn: bowed vibraphone and low strings, sparse piano
ev.append((H['drop2'], 'vibraphone_bowed', 'A4', 5.0, .5, -.1))
ev.append((H['front'], 'cellos', 'D3', 8.0, .36, .2)); ev.append((H['front'], 'contrabass', 'D2', 8.0, .30, 0))
ev.append((H['front'] + 0.4, 'vibraphone_bowed', 'D5', 4.5, .42, .2))
for i, p in enumerate(['E5', 'F5', 'D5', 'A4']): pn(H['front'] + bt(2) + i * bt(2), p, bt(2.5), .24, .1)
ev.append((H['pair'], 'cellos', 'A#2', 6.0, .32, .2)); ev.append((H['pair'], 'violas', 'F3', 6.0, .26, -.2))
pn(H['pair'], 'A#2', bt(4), .3, -.3); pn(H['pair'] + bt(1), 'F4', bt(2), .24); pn(H['pair'] + bt(3), 'D5', bt(2), .24)
ev.append((WD['sameSig'], 'vibraphone_bowed', 'F5', 3.5, .5, 0)); pn(WD['sameSig'], 'D3', bt(4), .3, -.3); pn(WD['sameSig'], 'A4', bt(3), .26)
q = H['quote']
ev.append((q, 'cellos', 'G2', 7.0, .3, .2)); ev.append((q, 'violas', 'D3', 7.0, .22, -.2))
for i, p in enumerate(['G3', 'D4', 'A#4', 'A4', 'G4', 'F4', 'E4']): pn(q + 0.2 + i * bt(1.5), p, bt(2), .22 + .02 * (i == 0))
# E — the split: resolve to F major, strings swell, glockenspiel on each count
ix = H['index']
for p in ('F2', 'C3', 'A3', 'F4'): pn(ix, p, bt(6), .34, -.2)
ev.append(dict(t=ix, inst='violas', pitch='A3', dur=10.0, vel=.30, pan=-.25, attack=1.6))
ev.append(dict(t=ix, inst='violins', pitch='C5', dur=10.0, vel=.24, pan=.3, attack=1.8))
ev.append(dict(t=ix, inst='cellos', pitch='F3', dur=10.0, vel=.32, pan=.15, attack=1.2))
ev.append((ix, 'contrabass', 'F2', 10.0, .26, 0))
t = ix + bt(4); k = 0
for ch in ['F', 'C', 'Dm', 'Bb', 'F']:
    if t > H['off'] - 0.1: break
    bass, top = CH[ch]
    for j in range(4):
        if t + bt(j) < H['off'] - 0.1: pn(t + bt(j), top[[0, 2, 1, 3][j]], bt(1.3), .25)
    t += bt(2)
for w, p in (('c1', 'C6'), ('c5', 'F6'), ('c43', 'A5')): ev.append((WD[w], 'glockenspiel', p, 1.4, .36, .25))
ev.append((H['six'], 'vibraphone_bowed', 'F5', 3.0, .45, 0)); pn(H['six'], 'F4', bt(3), .3); pn(H['six'], 'C5', bt(3), .28); pn(H['six'], 'A4', bt(3), .26)
# F — the close: the switch cuts the music; a cello pedal, then the title chord
ev.append(dict(t=H['off'] + 0.4, inst='cellos', pitch='F2', dur=7.5, vel=.26, pan=0, attack=1.0))
ev.append((H['glideUp'], 'vibraphone_bowed', 'C5', 4.0, .36, .1))
for k, p in ((0, 'A4'), (1, 'C5'), (2, 'F5')): pn(H['thesis'] + k * bt(2), p, bt(3), .26)        # under the thesis (F24)
ec = H['endCard']
ev.append(dict(t=ec, inst='vibraphone_bowed', pitch='F5', dur=4.0, vel=.3, pan=0, attack=.4)); ev.append(dict(t=ec, inst='cellos', pitch='F3', dur=4.0, vel=.2, pan=.1, attack=.8))
ti = H['title']
for p in ('F2', 'C3', 'F3', 'A3', 'C4', 'F4', 'A4'): pn(ti, p, 4.4, .36, -.1)
ev.append((ti, 'vibraphone_bowed', 'A5', 4.4, .42, .2)); ev.append(dict(t=ti, inst='cellos', pitch='F3', dur=4.2, vel=.28, pan=.2, attack=.6))
ev.append(dict(t=ti, inst='violins', pitch='C5', dur=4.2, vel=.2, pan=-.3, attack=.8))

music = S.render(ev, dur=N / SR, master=False)[:N]
# felt piano: soften the attack band slightly (whole score is mostly piano); gentle room
music = np.stack([X.lp(music[:, c], 7000) for c in range(2)], 1)
music = S.room(music, size=.5, mix=.22)
# the switch and the silences: hard gate before the turn, before the split, at the switch
gate = np.ones(N)
def cut(a, b, fo=.3):
    i0, i1 = int(a * SR), int(b * SR); f = int(fo * SR)
    gate[max(0, i0 - f):i0] *= np.linspace(1, 0, min(f, i0)); gate[i0:i1] = 0
cut(H['hush1'], H['drop2'] - 0.01); cut(H['hush2'], H['index'] - 0.01, .5); cut(H['off'], H['off'] + 0.38, .05)
music *= gate[:, None]

print(f'[time] score (sampler render + room): {time.time() - T0:.2f} s'); T1 = time.time()
# ---------------- voice ----------------
voice = np.zeros((N, 2)); vact = np.zeros(N)
for v in TL['voice']:
    a, sr = sf.read(os.path.join(HERE, 'voice', 'out', v['id'] + '.wav'))
    if a.ndim > 1: a = a.mean(1)
    a = soxr.resample(a, sr, SR)
    a = X.hp(a, 80); a = X.compress(a / (np.abs(a).max() + 1e-9) * .9, thr=.22, ratio=3.0)
    add(voice, a, v['t'], 1.0, 0.0); s = int(v['t'] * SR); vact[s:s + len(a)] = 1
rms = lambda x: np.sqrt(np.mean(x ** 2) + 1e-12)
v_rms = rms(voice[vact > 0])
# duck: smooth envelope of speech activity, −5 dB under the voice
from scipy.ndimage import uniform_filter1d
duck = 1 - (1 - 10 ** (-5 / 20)) * np.clip(uniform_filter1d(vact, int(.25 * SR)) * 1.5, 0, 1)
m_rms = rms(music[music.any(1)]) if music.any() else 1
music *= (v_rms * 10 ** (-11 / 20)) / m_rms
music *= duck[:, None]

# ---------------- foley ----------------
fol = np.zeros((N, 2))
def cat(*xs):
    n = max(len(x) for x in xs); o = np.zeros(n)
    for x in xs: o[:len(x)] += x
    return o
def paper(d=.25, v=1.0): n = X.noise(d); return X.norm(X.bp(n, 1500, 7000) * np.sin(np.pi * X.t_(d) / d) ** 1.5) * v
def pen(v=1.0):
    d = .38; n = X.noise(d); e = (np.abs(np.sin(2 * np.pi * 11 * X.t_(d))) ** 2) * np.sin(np.pi * X.t_(d) / d)
    return X.norm(X.bp(n, 2000, 6500) * e) * v
def ring(v=1.0, f=3520): d = 1.4; tt = X.t_(d); return X.norm(sum(a * np.sin(2 * np.pi * f * m * tt) * X.env_exp(d, tau) for m, a, tau in [(1, 1, .35), (2.76, .4, .15), (5.4, .2, .07)])) * v
def key(v=1.0): return X.norm(cat(X.click(.75 + rng.random() * .2) * .7, X.lp(X.noise(.04), 2500) * X.env_exp(.04, .006))) * v
FX = {
    'key': lambda g: key(g), 'label': lambda g: X.click(1.2, g) * .6, 'starter': lambda g: X.norm(cat(X.click(.5, 1), X.thump(.4, 120)[:3000])) * g,
    'sweep': lambda g: paper(.7, g), 'loupe': lambda g: np.concatenate([X.clack(.8, 1), np.zeros(1)]) * g * .9,
    'paper': lambda g: paper(.3, g), 'lift': lambda g: paper(.25, g) * .6, 'tick': lambda g: X.click(1.6, g) * .5,
    'land': lambda g: X.norm(cat(X.click(.9, 1), X.thump(.5, 90)[:4000] * .6)) * g, 'front': lambda g: X.whoosh(2.4, g) * .7,
    'pen': lambda g: pen(g), 'whoosh': lambda g: X.whoosh(.9, g), 'switch': lambda g: X.norm(cat(X.clack(.55, 1), X.thump(1, 60))) * g,
}
for t, typ, g in TL['ev']:
    s = FX[typ](g); pan = (rng.random() - .5) * .5
    add(fol, s, t, 1.0, pan)
    if typ == 'loupe': add(fol, ring(.35), t + .005, 1.0, pan)        # the glass ring after the clack
f_rms = rms(fol[np.abs(fol).sum(1) > 1e-4])
fol *= (v_rms * 10 ** (-9 / 20)) / f_rms

# ---------------- beds: ballast hum while the table is lit, room tone throughout ----------------
tt = np.arange(N) / SR
hum = (np.sin(2 * np.pi * 100 * tt) * .5 + np.sin(2 * np.pi * 200 * tt) * .3 + np.sin(2 * np.pi * 300 * tt) * .15 + np.sin(2 * np.pi * 500 * tt) * .06)
lit = ((tt > H['lightOn'] + .4) & (tt < H['off'])).astype(float)
lit = uniform_filter1d(lit, int(.08 * SR)) * (1 + .03 * np.sin(2 * np.pi * .7 * tt))
room = X.lp(X.brown(N / SR), 900)[:N]
beds = np.stack([hum * lit + room * .5, hum * lit * .95 + np.roll(room, 977) * .5], 1)
beds *= (v_rms * 10 ** (-24 / 20)) / rms(beds)
# in the two silences the hum is the only sound: lift it a little so the silence reads as the room
beds *= (1 + .6 * (1 - gate))[:, None]

print(f'[time] voice + foley + beds: {time.time() - T1:.2f} s'); T2 = time.time()
# ---------------- master ----------------
def hp2(x, f): return np.stack([X.hp(x[:, c], f) for c in range(2)], 1)
music, fol, beds = hp2(music, 38), hp2(fol, 38), hp2(beds, 38)
mix = voice + music + fol + beds
mix = mix[:int(DUR * SR)]
fo = int(1.2 * SR); mix[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 1.5                 # the end card fades out
peak = np.abs(mix).max(); mix = mix / peak * .95
mix = np.stack([X.limit(mix[:, c], .9) for c in range(2)], 1)
os.makedirs(os.path.join(HERE, 'out', 'stems'), exist_ok=True)
sf.write(os.path.join(HERE, 'out', 'mix.wav'), mix.astype(np.float32), SR)
for nm, x in (('voice', voice), ('music', music), ('foley', fol), ('beds', beds)):
    sf.write(os.path.join(HERE, 'out', 'stems', nm + '.wav'), (x[:int(DUR * SR)] / peak * .95).astype(np.float32), SR)
# low-end check: 20–120 Hz energy relative to the rest
spec = np.abs(np.fft.rfft(mix.mean(1))) ** 2; fr = np.fft.rfftfreq(len(mix), 1 / SR)
lo = spec[(fr >= 20) & (fr < 120)].sum(); rest = spec[(fr >= 120) & (fr < 16000)].sum()
print(f'[time] master + stems: {time.time() - T2:.2f} s')
print(f'mix.wav {len(mix) / SR:.2f} s · low band {10 * np.log10(lo / rest):.1f} dB vs rest · voice/music RMS {20 * np.log10(v_rms / max(rms(music[vact[:len(music)] > 0]), 1e-9)):.1f} dB while speaking')
