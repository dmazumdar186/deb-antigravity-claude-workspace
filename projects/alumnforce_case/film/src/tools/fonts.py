"""Fonts the page uses, from Google Fonts (SIL OFL 1.1), Latin subset, into fonts/; licence texts from github.com/google/fonts.
usage: python -I tools/fonts.py <film_dir>"""
import sys, os, re, urllib.request, urllib.parse
D = sys.argv[1]
latin = ''.join(chr(c) for c in range(32, 127)) + '·×→−—’‘“”⇄≠=…▏█'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'
get = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': UA}), timeout=60).read()
for fam, axis, out in (('IBM Plex Mono', 'wght@400', 'IBMPlexMono-400.woff2'), ('IBM Plex Mono', 'wght@500', 'IBMPlexMono-500.woff2'),
                       ('IBM Plex Sans', 'wght@400', 'IBMPlexSans-400.woff2'), ('IBM Plex Sans', 'wght@500', 'IBMPlexSans-500.woff2'),
                       ('IBM Plex Sans', 'wght@600', 'IBMPlexSans-600.woff2'),
                       ('IBM Plex Serif', 'wght@500', 'IBMPlexSerif-500.woff2'), ('IBM Plex Serif', 'ital,wght@1,400', 'IBMPlexSerif-400i.woff2')):
    css = get('https://fonts.googleapis.com/css2?family=' + urllib.parse.quote(fam) + ':' + axis + '&text=' + urllib.parse.quote(latin)).decode()
    urls = re.findall(r'url\((https://[^)]+)\)', css)
    assert len(urls) == 1, css[:400]
    data = get(urls[0]); open(os.path.join(D, 'fonts', out), 'wb').write(data); print(out, len(data), 'bytes')
for fam in ('ibmplexmono', 'ibmplexsans', 'ibmplexserif'):
    open(os.path.join(D, 'fonts', f'OFL-{fam}.txt'), 'wb').write(get(f'https://raw.githubusercontent.com/google/fonts/main/ofl/{fam}/OFL.txt'))
print('licence texts written')
