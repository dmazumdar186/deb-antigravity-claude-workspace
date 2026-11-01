"""Contact sheet of the final file: one frame per beat, times and captions from content.json "contact_sheet".
usage: python -I tools/contact_sheet.py <film.mp4> <content.json> <out.jpg>"""
import sys, subprocess, tempfile, os, json
from PIL import Image, ImageDraw
mp4, cj, out = sys.argv[1], sys.argv[2], sys.argv[3]
SHOTS = json.load(open(cj, encoding='utf-8'))['contact_sheet']
W, H, cols = 360, 450, 3
rows = (len(SHOTS) + cols - 1) // cols
S = Image.new('RGB', (cols * W, rows * (H + 28)), (22, 24, 28)); d = ImageDraw.Draw(S)
with tempfile.TemporaryDirectory() as tmp:
    for k, (t, cap) in enumerate(SHOTS):
        f = os.path.join(tmp, f'{k}.png')
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-ss', str(t), '-i', mp4, '-frames:v', '1',
                        '-vf', 'scale=in_color_matrix=bt709:in_range=tv:out_range=pc,format=rgb24', f], check=True)
        x, y = (k % cols) * W, (k // cols) * (H + 28)
        S.paste(Image.open(f).convert('RGB').resize((W, H), Image.LANCZOS), (x, y + 28))
        d.text((x + 8, y + 8), f'{t:5.1f}s  {cap}', fill=(235, 235, 235))
S.save(out, 'JPEG', quality=88); print('contact sheet:', out, S.size)
