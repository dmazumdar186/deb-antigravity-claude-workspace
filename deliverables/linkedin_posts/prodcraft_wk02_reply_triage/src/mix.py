"""Score + sound design for ProdCraft wk 02, from events.json (window.EV, written by core/render/events.mjs).
Original score, 112.5 BPM, 13 bars of 4/4 = 27.733 s, D major, CC0 samples only (VCSL / VSCO 2 CE via sampler.py):
marimba ostinato (the grid's pulse), bowed/soft vibraphone chords, contrabass pizzicato, glockenspiel on every rule
that fires (the signal sings), woodblock / claves sorting ticks, shaker sixteenths while replies pour in.
No piano, no drum kit (so no CC BY credit is needed). Foley is procedural (core/audio/sfx.py), dry and close.
Two silences: a half-beat break before the code panel lands (beats 15-16) and a near-silence before the reframe
(beats 31-32.5). The last bar is the first bar again, so the loop is seamless.
Week-specific inputs come from content.json (dur, fire notes); timing from out/events.json (window.EV).
Writes out/mix.wav (48 kHz float, peak -3 dBFS; tools/master.sh does loudness) and out/stems/*.wav.
usage: python mix.py   (LEMO_OPUSCAR_HOME or LIB = the toolkit clone, for core.audio)"""
import json, os, sys
import numpy as np, soundfile as sf
HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.environ.get('LEMO_OPUSCAR_HOME') or os.environ.get('LIB') or os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, LIB)
from core.audio import sampler as S
from core.audio import sfx as X
from core.audio.sfx import SR, add

S.seed(2026)
E = json.load(open(os.path.join(HERE, 'out', 'events.json')))
CONTENT = json.load(open(os.path.join(HERE, 'content.json'), encoding='utf-8'))
DUR, EV = E['dur'], E['ev']
BEAT = 60 / 112.5
bt = lambda beats: beats * BEAT
N = int(round(DUR * SR))
def buf(): return np.zeros((N, 2), np.float32)

# ---------------- harmony: one chord per two beats, 13 bars ----------------
# (bar index -> two chords). Loop: bar 13 == bar 1.
CH = {
    'Dmaj7': ['D3', 'F#3', 'A3', 'C#4'], 'Bm7': ['B2', 'D3', 'F#3', 'A3'], 'Gmaj7': ['G2', 'B2', 'D3', 'F#3'],
    'A6': ['A2', 'C#3', 'E3', 'F#3'], 'Em7': ['E2', 'G2', 'B2', 'D3'], 'Asus': ['A2', 'D3', 'E3', 'G3'],
    'D/F#': ['F#2', 'A2', 'D3', 'F#3'], 'G6': ['G2', 'B2', 'E3', 'G3'],
}
BARS = [('Dmaj7', 'Bm7'), ('Dmaj7', 'Bm7'), ('Gmaj7', 'A6'), ('Gmaj7', 'A6'),     # poster, pour, F05
        ('Dmaj7', 'Bm7'), ('Gmaj7', 'A6'),                                        # rules
        ('Gmaj7', 'Em7'), ('Em7', 'Asus'),                                        # judgement, CRM; near-silence at 31
        ('G6', 'D/F#'), ('Em7', 'A6'), ('G6', 'D/F#'), ('Em7', 'Asus'),          # the reframe
        ('Dmaj7', 'Bm7')]                                                          # end card == bar 1
ROOT = {'Dmaj7': 'D2', 'Bm7': 'B1', 'Gmaj7': 'G1', 'A6': 'A1', 'Em7': 'E2', 'Asus': 'A1', 'D/F#': 'F#1', 'G6': 'G1'}
def chord_at(beat):
    bar, half = int(beat // 4), int((beat % 4) // 2)
    return BARS[min(bar, 12)][half]
def silent(beat):          # the two silences: a break before the panel lands, a near-silence before the reframe
    return 14.75 <= beat < 15.75 or 31.5 <= beat < 33.0

ev = []   # sampler score: (t, inst, pitch, dur, vel, pan[, gain])
# marimba ostinato in eighths: root-fifth-third-fifth, octave up in the second half of each chord (the grid's pulse)
for k in range(0, 52 * 2):
    beat = k / 2
    if silent(beat) or 47.0 <= beat < 48.0: continue
    notes = CH[chord_at(beat)]
    up = [S.midi(p) + 12 for p in notes]
    pat = [up[0], up[2], up[1], up[2]]
    m = pat[k % 4] + (12 if (k % 8) >= 4 and beat < 47 else 0)
    if m > S.midi('A5'): m -= 12
    vel = 0.42 if k % 2 == 0 else 0.30
    if 15.5 <= beat < 31: vel += 0.05               # a little brighter while the rules sort
    ev.append((bt(beat), 'marimba', m, BEAT / 2, vel, -0.25 + 0.5 * ((k % 4) / 3)))
# vibraphone chord pads on each chord change, soft (the 'air' of the paper)
for k in range(26):
    beat = k * 2
    if silent(beat): continue
    name = chord_at(beat)
    for j, p in enumerate(CH[name]):
        ev.append((bt(beat) + j * 0.012, 'vibraphone', S.midi(p) + 12, BEAT * 2.1, 0.28, -0.3 + 0.2 * j, 0.8))
# contrabass pizzicato: root on beats 1 and 3, plus the eighth before beat 3 in the reframe
for k in range(26):
    beat = k * 2
    if silent(beat) or beat < 4: continue
    r = ROOT[chord_at(beat)]
    ev.append((bt(beat), 'contrabass_pizz', S.midi(r) + 12, BEAT * 1.5, 0.62, 0.0, 0.5))
    if 33 <= beat < 47:
        ev.append((bt(beat + 1.5), 'contrabass_pizz', S.midi(r) + 19, BEAT * 0.5, 0.45, 0.0, 0.5))
# shaker sixteenths while the replies pour in (beats 6-14), very soft
for k in range(int(6 * 4), int(14 * 4)):
    beat = k / 4
    ev.append((bt(beat), 'shaker', 'down' if k % 2 == 0 else 'up', None, 0.18 if k % 4 else 0.26, 0.35))

# ---------------- events from the picture ----------------
GLOCK = CONTENT['sound']['fire_notes']
fol = buf()
for e in EV:
    t, ty = e['t'], e['type']
    if ty == 'card':      # a reply lands: a woodblock tick, pitched by arrival order
        ev.append((t, 'woodblock', ['a', 'b', 'c'][e['i'] % 3], None, 0.42, -0.2 + 0.07 * e['i']))
    elif ty == 'light':   # an inbox lights: a soft click (the poster's first lights also get a marimba tick)
        add(fol, X.click(pitch=1.6 + 0.02 * (e['k'] % 5), v=0.25), t, 0.10, -0.6 + 0.04 * e['k'])
        if e.get('v'):
            ev.append((t, 'woodblock', 'a', None, 0.30, -0.3 + 0.08 * e['k']))
    elif ty == 'slide':   # paper slide (re-flow, wipes)
        add(fol, X.whoosh(d=0.32, v=1.0), t, 0.10 * e.get('v', 0.4) / 0.4, 0.0)
    elif ty == 'rule':
        add(fol, X.whoosh(d=0.18, v=1.0), t, 0.06, -0.2)
    elif ty == 'knife':   # ruling pen 'tss' + snick
        add(fol, X.whoosh(d=0.14, v=1.0), t, 0.09, 0.3); add(fol, X.click(pitch=2.2, v=0.5), t + bt(0.25), 0.18, 0.2)
    elif ty == 'panel':
        add(fol, X.whoosh(d=0.5, v=1.0), t, 0.14, 0.5)
    elif ty == 'land':    # the panel / the reframe lands on the downbeat
        add(fol, X.thump(v=0.6, f=110), t, 0.16, 0.0)
    elif ty == 'fire':    # a rule fires: the signal sings (glockenspiel) + claves
        ev.append((t, 'glockenspiel', GLOCK[e['kind']], BEAT * 2, 0.50, 0.15))
        ev.append((t, 'claves', None, None, 0.40, 0.25))
    elif ty == 'stamp':   # result stamped: woodblock clack (two for the two OOO cards)
        for j in range(e['n']):
            ev.append((t + j * bt(0.25), 'woodblock', 'c', None, 0.55, 0.1))
    elif ty == 'crm':     # CRM updated: one rising vibraphone figure
        for j, p in enumerate(['E5', 'G5', 'B5']):
            ev.append((t + j * bt(0.25), 'vibraphone', p, BEAT, 0.45, 0.2 + 0.1 * j))
    elif ty == 'thunk':   # the giant 30-60: numeral thunk + glock
        add(fol, X.thump(v=0.7, f=100), t, 0.16, 0.0)
        ev.append((t, 'glockenspiel', 'A6', BEAT * 3, 0.45, 0.1))

music = S.render([x for x in ev if x[1] not in ('woodblock', 'claves', 'shaker')], dur=DUR + 3)
ticks = S.render([x for x in ev if x[1] in ('woodblock', 'claves', 'shaker')], dur=DUR + 3)
music = S.room(music, size=0.35, mix=0.14)

def fit(x):
    y = np.zeros((N + int(3 * SR), 2), np.float32); n = min(len(x), len(y)); y[:n] = x[:n]; return y
music, ticks = fit(music), fit(ticks)
# seamless loop: whatever rings past the end folds back onto the start (the film loops on the bar line)
tail = int(3 * SR)
for x in (music, ticks):
    x[:tail] += x[N:N + tail]
music, ticks = music[:N], ticks[:N]
# the near-silence before the reframe: duck everything that still rings (beats 31.5-33) to -24 dB
g = np.ones(N, np.float32)
a0, a1, a2 = int(bt(31.5) * SR), int(bt(31.75) * SR), int(bt(33.0) * SR)
g[a0:a1] = np.linspace(1, 0.063, a1 - a0); g[a1:a2] = 0.063
music *= g[:, None]
ticks *= g[:, None]
fol = fol[:N]

mix = music * 1.0 + ticks * 0.75 + fol * 1.0
# peak-normalise to -3 dBFS; loudness and true peak are set in mastering (tools/master.sh)
peak = np.abs(mix).max()
mix = mix / max(peak, 1e-6) * 0.7
os.makedirs(os.path.join(HERE, 'out', 'stems'), exist_ok=True)
sf.write(os.path.join(HERE, 'out', 'mix.wav'), mix.astype(np.float32), SR, subtype='FLOAT')
for name, x in (('music', music), ('ticks', ticks), ('foley', fol)):
    sf.write(os.path.join(HERE, 'out', 'stems', name + '.wav'), (x / max(peak, 1e-6) * 0.7).astype(np.float32), SR, subtype='FLOAT')
# band balance check (TECHNIQUE §5): 20-120 Hz vs the rest
spec = np.abs(np.fft.rfft(mix.mean(axis=1))) ** 2; f = np.fft.rfftfreq(N, 1 / SR)
low, rest = spec[(f >= 20) & (f < 120)].sum(), spec[(f >= 120) & (f < 16000)].sum()
print(f'mix.py: {DUR:.3f}s, {len(ev)} sampler events, {len(EV)} picture events, low band {10*np.log10(low/rest):+.1f} dB vs rest')
