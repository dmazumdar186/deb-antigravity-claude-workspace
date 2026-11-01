"""Speech check on the final film: transcribe the mixed soundtrack (music, foley and all) with faster-whisper and compare it,
word for word, with the narration script (numbers normalised the way asr_check.py does). usage: python tools/final_asr.py film.mp4 lines.json"""
import sys, json, os, subprocess, tempfile, difflib
sys.path.insert(0, os.path.join(os.environ.get('LIB', '.'), 'core', 'tts'))
from asr_check import norm_en
from faster_whisper import WhisperModel
mp4, lines = sys.argv[1], json.load(open(sys.argv[2]))
wav = os.path.join(tempfile.mkdtemp(), 'a.wav')
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', mp4, '-ac', '1', '-ar', '16000', wav], check=True)
m = WhisperModel(os.environ.get('WHISPER_MODEL', 'small.en'), device='cpu', compute_type='int8')
segs, _ = m.transcribe(wav, language='en', vad_filter=False)
got = ' '.join(s.text.strip() for s in segs)
want = ' '.join(L.get('asr', L['text']) for L in lines)
a, b = norm_en(want), norm_en(got)
sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
diffs = [(op, ' '.join(a[i1:i2]), ' '.join(b[j1:j2])) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != 'equal']
print('heard:', got)
print(f'words expected {len(a)}, heard {len(b)}, word match ratio {sm.ratio():.4f}, differences {len(diffs)}')
for d in diffs: print('  ', d)
