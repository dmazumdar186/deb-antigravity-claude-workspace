"""Generate the ProdCraft LinkedIn banner (1584x396, LinkedIn personal spec).

Matches the website brand (bone / ink / brass, Cambria serif headline, Consolas mono
metrics). Keeps the bottom-left clear for the profile-photo overlap. Renders at 2x
supersample then downscales for crisp text.

Output: public/linkedin-banner.png (+ a copy to Downloads for easy upload).
Run: py execution/personal_workflows/portfolio_site/scripts/make_linkedin_banner.py
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PUB = Path(__file__).resolve().parents[1] / "public"
DOWNLOADS = Path.home() / "Downloads"

S = 2  # supersample factor
W, H = 1584 * S, 396 * S
BONE = (247, 243, 236); INK = (22, 24, 28); INK7 = (61, 65, 72)
BRASS = (200, 163, 92); BRASSL = (222, 196, 135)

def f(path, sz):
    return ImageFont.truetype(path, sz * S)
serif = lambda s: f("C:/Windows/Fonts/cambriab.ttf", s)
sans  = lambda s: f("C:/Windows/Fonts/arial.ttf", s)
mono  = lambda s: f("C:/Windows/Fonts/consolab.ttf", s)

img = Image.new("RGB", (W, H), BONE)
d = ImageDraw.Draw(img)
logo = Image.open(PUB / "logo.png").convert("RGBA")

# faint oversized logo watermark, right side
wm = logo.resize((360 * S, 360 * S), Image.LANCZOS)
wm.putalpha(wm.split()[3].point(lambda p: int(p * 0.10)))
img.paste(wm, (W - 330 * S, (H - 360 * S) // 2), wm)

# top-left lockup: logo + wordmark + tagline (above the avatar overlap)
sl = logo.resize((68 * S, 68 * S), Image.LANCZOS)
img.paste(sl, (60 * S, 40 * S), sl)
d.text((138 * S, 46 * S), "ProdCraft", font=serif(34), fill=INK)
d.text((140 * S, 86 * S), "AI builds, shipped.", font=sans(17), fill=BRASS)

# domain, top-right
dom = "prodcraft.fyi"
d.text((W - d.textlength(dom, font=mono(20)) - 60 * S, 52 * S), dom, font=mono(20), fill=INK7)

# headline (2 lines) — x>=360 keeps it clear of the bottom-left avatar
hx = 360 * S
d.text((hx, 120 * S), "The senior AI engineer", font=serif(62), fill=INK)
d.text((hx, 196 * S), "your roadmap is missing.", font=serif(62), fill=INK)
d.rectangle([hx, 278 * S, hx + 150 * S, 281 * S], fill=BRASS)

# metrics row (mono)
my = 300 * S
parts = [("$1M+ ", BRASS), ("pipeline     ", INK7),
         ("<30-day ", BRASS), ("ship     ", INK7),
         ("+45% ", BRASS), ("adoption", INK7)]
x = hx
for t, c in parts:
    d.text((x, my), t, font=mono(22), fill=c)
    x += d.textlength(t, font=mono(22))

out = img.resize((1584, 396), Image.LANCZOS)
out.save(PUB / "linkedin-banner.png")
out.save(DOWNLOADS / "prodcraft-linkedin-banner.png")
print(f"banner saved -> {PUB / 'linkedin-banner.png'} and {DOWNLOADS / 'prodcraft-linkedin-banner.png'}")
