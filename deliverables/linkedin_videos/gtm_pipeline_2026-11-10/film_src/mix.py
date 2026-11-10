# Original score + foley for ProdCraft weekly notes wk 04.
# Usage: .venv/bin/python mix.py <lemo-opuscar root> <film dir>   -> <film dir>/out/mix.wav
# Instruments: VSCO 2 CE + VCSL only (both CC0, Versilian Studios). No piano, no voice.
import sys, json
if len(sys.argv) != 3:
    sys.exit('usage: mix.py <lemo-opuscar root> <film dir>')
sys.path.insert(0, sys.argv[1])
import numpy as np, soundfile as sf
from core.audio import sampler as S, sfx
from core.audio.sfx import SR, add

FILM = sys.argv[2]
meta = json.load(open(FILM + '/events.json', encoding='utf-8'))
DUR, EV = meta['dur'], meta['ev']
S.seed(3)
B = 60 / 90                       # 90 bpm, calm
BAR = 4 * B

# chord per section: (start, end, bass root, pad notes, pizz arpeggio)
SECT = [
    (0.0, 3.9, 'D2', ['D3', 'A3'], ['D5', 'A4', 'F#5', 'A4']),
    (3.9, 10.7, 'B1', ['B2', 'F#3'], ['B4', 'F#4', 'D5', 'F#4']),
    (10.7, 15.3, 'G1', ['G2', 'D3'], ['G4', 'D5', 'B4', 'D5']),
    (15.3, 19.95, 'A1', ['A2', 'E3'], ['A4', 'E5', 'C#5', 'E5']),
    (19.95, 23.55, 'D2', ['D3', 'A3'], ['F#5', 'A4', 'D5', 'A4']),
    (23.55, 27.7, 'G1', ['G2', 'D3'], ['G4', 'D5', 'B4', 'D5']),
    (27.7, 33.5, 'D2', ['D3', 'A3'], ['F#5', 'A4', 'D5', 'A4']),
]
ev = []
for i, (a, b, root, pad, arp) in enumerate(SECT):
    # sustained string pad, soft attack
    for j, p in enumerate(pad):
        ev.append(dict(t=a, inst='cellos' if j == 0 else 'violas', pitch=p, dur=b - a + .2, vel=.26, pan=-.25 if j == 0 else .25, attack=.9, release=1.4))
    # double-bass pizz on each bar line
    t = a
    while t < b - .3:
        ev.append((t, 'contrabass_pizz', root, 1.6, .42, 0)); t += BAR
    # light violin-pizz ostinato on the beat, every other beat dropped for air
    k, t = 0, a + B * .5
    while t < b - .2:
        if k % 4 != 3:
            ev.append((t, 'violins_pizz', arp[k % 4], .8, .30 + .06 * (k % 2 == 0), .35 if k % 2 else -.35))
        k += 1; t += B
# a high violin line over the payoff and the offer, very soft
ev.append(dict(t=20.1, inst='violins', pitch='F#5', dur=3.0, vel=.2, pan=.15, attack=1.0, release=1.5))
ev.append(dict(t=23.7, inst='violins', pitch='D5', dur=3.6, vel=.18, pan=.15, attack=.8, release=1.4))
ev.append(dict(t=27.9, inst='violins', pitch='A5', dur=4.6, vel=.17, pan=.15, attack=1.0, release=1.6))
# harp rolls on each headline
for t0, notes in [(0.05, ['D3', 'A3', 'D4', 'F#4']), (3.95, ['B2', 'F#3', 'B3', 'D4']), (10.75, ['G2', 'D3', 'G3', 'B3']),
                  (20.0, ['D3', 'A3', 'D4', 'F#4', 'A4']), (23.6, ['G2', 'D3', 'G3', 'B3']), (27.75, ['D3', 'A3', 'D4', 'F#4'])]:
    for j, p in enumerate(notes):
        ev.append((t0 + j * .07, 'harp', p, 2.5, .34, -.2 + .1 * j))
# cue-driven pitched accents
TICK = ['D5', 'E5', 'F#5', 'A5', 'B5']
for e in EV:
    if e['type'] == 'tick':
        ev.append((e['t'], 'violins_pizz', TICK[e.get('i', 0) % 5], .7, .5, .1))
    elif e['type'] == 'chime':
        ev.append((e['t'], 'hand_chimes', e['note'], 2.2, .32, .1))
    elif e['type'] == 'stamp':
        ev.append((e['t'] + .02, 'hand_chimes', 'A5', 2.4, .3, -.1))

score = S.render(ev, dur=DUR, master=False)
score = S.room(score, size=.42, mix=.2)
buf = np.zeros((int(DUR * SR), 2), np.float32)
buf[:len(score)] += score[:len(buf)] * .8

# foley
rng = np.random.default_rng(7)
def paper(v=1.0):
    d = .3; n = sfx.noise(d)
    grains = np.zeros_like(n)
    for _ in range(14):
        s = int(rng.uniform(0, .22) * SR); L = int(.012 * SR)
        grains[s:s + L] += rng.uniform(.3, 1) * np.hanning(L)[:len(grains[s:s + L])]
    x = sfx.bp(n, 1800, 7500) * (grains + .25 * sfx.env_exp(d, .08))
    return sfx.norm(x) * v
for e in EV:
    t, ty = e['t'], e['type']
    if ty == 'tick': add(buf, sfx.click(1.1, .5), t, .14, .2)
    elif ty == 'click': add(buf, sfx.click(1.0, e.get('v', .5)), t, .18, -.15)
    elif ty == 'paper': add(buf, paper(e.get('v', .5)), t, .22, .1)
    elif ty == 'whoosh': add(buf, sfx.whoosh(.4, .6), t - .05, .12, 0)
    elif ty == 'stamp':
        add(buf, sfx.thump(.9, 90), t + .3, .45, 0); add(buf, sfx.clack(.9, .8), t + .3, .25, 0)
# fade the tail so the loop point is quiet
f = int(.5 * SR); buf[-f:] *= np.linspace(1, 0, f)[:, None] ** 2
# master: bring up ~12 dB, tame transients so the -14 LUFS loudnorm can run in linear mode
buf *= 10 ** (12 / 20)
for c in range(2): buf[:, c] = sfx.limit(sfx.compress(buf[:, c], thr=.3, ratio=3, att=.003, rel=.12), ceil=.6)
sf.write(FILM + '/out/mix.wav', buf, SR)
print('instruments:', sorted({(x['inst'] if isinstance(x, dict) else x[1]) for x in ev}))
print('\n'.join(S.credits(sorted({(x['inst'] if isinstance(x, dict) else x[1]) for x in ev}))))
