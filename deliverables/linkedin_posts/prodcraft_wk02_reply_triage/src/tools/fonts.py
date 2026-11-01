"""ProdCraft Notes fonts from Google Fonts (SIL OFL 1.1), Latin + the punctuation the series uses, into <dir>/fonts/,
with the licence texts from github.com/google/fonts.  Run by hand when fonts/ is missing (build.sh never writes into src/ outside out/).
usage: python -I tools/fonts.py <film_or_style_dir>"""
import sys, os, re, urllib.request, urllib.parse
D = os.path.join(sys.argv[1], 'fonts'); os.makedirs(D, exist_ok=True)
CHARS = ''.join(chr(c) for c in range(32, 127)) + '·–—€’‘“”→←↳×…•'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'
get = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': UA}), timeout=60).read()
FACES = [  # (family, axis spec, file)
    ('Newsreader', 'ital,opsz,wght@0,72,500', 'Newsreader-D500.woff2'),     # headlines (display optical size)
    ('Newsreader', 'ital,opsz,wght@0,72,600', 'Newsreader-D600.woff2'),
    ('Newsreader', 'ital,opsz,wght@0,24,400', 'Newsreader-T400.woff2'),     # text size (subheads, wordmark)
    ('Newsreader', 'ital,opsz,wght@0,24,500', 'Newsreader-T500.woff2'),
    ('Newsreader', 'ital,opsz,wght@1,36,400', 'Newsreader-I400.woff2'),     # gold italic accent line
    ('JetBrains Mono', 'wght@400', 'JetBrainsMono-400.woff2'),
    ('JetBrains Mono', 'wght@700', 'JetBrainsMono-700.woff2'),
]
for fam, axis, out in FACES:
    css = get('https://fonts.googleapis.com/css2?family=' + urllib.parse.quote(fam) + ':' + axis + '&text=' + urllib.parse.quote(CHARS)).decode()
    urls = re.findall(r'url\((https://[^)]+)\)', css)
    assert len(urls) == 1, css[:400]
    data = get(urls[0]); open(os.path.join(D, out), 'wb').write(data); print(out, len(data), 'bytes')
for fam in ('newsreader', 'jetbrainsmono'):
    open(os.path.join(D, f'OFL-{fam}.txt'), 'wb').write(get(f'https://raw.githubusercontent.com/google/fonts/main/ofl/{fam}/OFL.txt'))
print('licence texts written')
