"""Contact sheet of the final file: one frame per beat of the story, labelled with its time.
usage: python -I tools/contact_sheet.py <film.mp4> <out.jpg>"""
import sys, subprocess, tempfile, os
from PIL import Image, ImageDraw
mp4, out = sys.argv[1], sys.argv[2]
SHOTS = [(0.0, 'poster / frame 0'), (3.3, 'replies pour in'), (6.0, 'the bottleneck (F05)'), (9.6, 'rules first: OOO fires'),
         (13.3, 'stop + hot sorted'), (15.5, 'the rest: to a person, CRM'), (20.5, 'the reframe (F19, F18)'), (26.5, 'end card')]
W, H, cols = 360, 450, 4
rows = (len(SHOTS) + cols - 1) // cols
S = Image.new('RGB', (cols * W, rows * (H + 28)), (22, 24, 28)); d = ImageDraw.Draw(S)
with tempfile.TemporaryDirectory() as tmp:
    for k, (t, cap) in enumerate(SHOTS):
        f = os.path.join(tmp, f'{k}.png')
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-ss', str(t), '-i', mp4, '-frames:v', '1', f], check=True)
        x, y = (k % cols) * W, (k // cols) * (H + 28)
        S.paste(Image.open(f).convert('RGB').resize((W, H), Image.LANCZOS), (x, y + 28))
        d.text((x + 8, y + 8), f'{t:5.1f}s  {cap}', fill=(235, 235, 235))
S.save(out, 'JPEG', quality=88); print('contact sheet:', out, S.size)
