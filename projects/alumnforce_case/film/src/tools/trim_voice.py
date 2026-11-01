"""Cut a voice line right after a given word (Kokoro adds a vowel tail after a sentence-final "Segments").
Lines with "cut_after" are spoken with a tail ("..., the product."), transcribed once to find the word end, then cut there
with a 40 ms fade; dur.json is updated. usage: python tools/trim_voice.py lines.json voices_dir"""
import sys, json, os, numpy as np, soundfile as sf
from faster_whisper import WhisperModel
lines, d = json.load(open(sys.argv[1])), sys.argv[2]
todo = [L for L in lines if L.get('cut_after')]
if not todo: sys.exit(0)
m = WhisperModel(os.environ.get('WHISPER_MODEL', 'small.en'), device='cpu', compute_type='int8')
dur = json.load(open(os.path.join(d, 'dur.json')))
for L in todo:
    p = os.path.join(d, L['id'] + '.wav'); a, sr = sf.read(p)
    segs, _ = m.transcribe(p, language='en', word_timestamps=True)
    ws = [w for s in segs for w in s.words]
    w = next(w for w in ws if w.word.strip(' ,.!?').lower() == L['cut_after'])
    # Whisper's word end falls before the final /ts/; find the sibilant burst (energy above 4 kHz) within 0.2 s
    # after it, then cut at the first quiet 10 ms window once the burst is over
    from scipy.signal import butter, sosfilt
    hf = sosfilt(butter(4, 4000, 'high', fs=sr, output='sos'), a); win = int(.01 * sr); e = int(w.end * sr)
    r = lambda x, i: float(np.sqrt(np.mean(x[i:i + win] ** 2)))
    idx = list(range(e, min(len(a) - win, e + int(.2 * sr)), win))
    pk = max(idx, key=lambda i: r(hf, i))
    c = next((i for i in range(pk, len(a) - win, win // 2) if r(a, i) < .1 * r(a, pk)), pk + int(.08 * sr))
    f = int(.03 * sr); a = a[:c + f].copy(); a[-f:] *= np.linspace(1, 0, f)
    sf.write(p, a, sr); dur[L['id']] = round(len(a) / sr, 3)
    print(L['id'], 'cut after', repr(w.word), 'at', round((c + f) / sr, 3), 's')
json.dump(dur, open(os.path.join(d, 'dur.json'), 'w'), indent=1)
