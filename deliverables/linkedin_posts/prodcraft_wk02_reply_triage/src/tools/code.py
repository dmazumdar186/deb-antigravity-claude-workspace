"""The code on screen, byte-identical to the source (FACTS: verbatim; re-indentation only to fit the frame).
Reads content.json "code": file, from, to (1-based, inclusive), dedent, reindent. Writes out/code.json with
  lines: the source lines minus the common `dedent` spaces (proved to re-expand to the exact source bytes), and
  shown: the same lines re-indented to `reindent` spaces per 4-space level (proved to re-expand to `lines`).
Fails on any forbidden substring (content.json code.forbid) or if a line does not carry the dedent.
usage: python -I tools/code.py <workspace_root> <film_dir>"""
import sys, json, hashlib, os, re
ws, film = sys.argv[1], sys.argv[2]
cfg = json.load(open(os.path.join(film, 'content.json'), encoding='utf-8'))['code']
raw = open(os.path.join(ws, cfg['file']), 'rb').read().split(b'\n')
block = raw[cfg['from'] - 1:cfg['to']]
d = cfg['dedent']
assert all(l.startswith(b' ' * d) for l in block), 'a line lacks the common indent'
lines = [l[d:].decode('utf-8') for l in block]
assert b'\n'.join(b' ' * d + l.encode('utf-8') for l in lines) == b'\n'.join(block)
for bad in cfg.get('forbid', []):
    assert not any(bad in l for l in lines), f'forbidden substring {bad!r} in the code block'
def reind(l, n):
    m = re.match(r'^( *)', l); k = len(m.group(1)); assert k % 4 == 0, l
    return ' ' * (k // 4 * n) + l[k:]
shown = [reind(l, cfg['reindent']) for l in lines]
def expand(s, n):
    k = len(s) - len(s.lstrip(' ')); assert k % n == 0, s
    return ' ' * (k // n * 4) + s[k:]
assert [expand(s, cfg['reindent']) for s in shown] == lines       # re-indent is reversible: nothing else changed
assert [s.lstrip(' ') for s in shown] == [l.lstrip(' ') for l in lines]       # same tokens, same order
sha = hashlib.sha256(b'\n'.join(block)).hexdigest()
os.makedirs(os.path.join(film, 'out'), exist_ok=True)
json.dump({'source': cfg['file'], 'lines_1based': [cfg['from'], cfg['to']], 'dedent': d, 'reindent_per_level': cfg['reindent'],
           'sha256_of_source_lines': sha, 'lines': lines, 'shown': shown},
          open(os.path.join(film, 'out', 'code.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
print(f'code.py: {len(lines)} lines verbatim ({cfg["file"]} {cfg["from"]}-{cfg["to"]}, dedent {d}, re-indent {cfg["reindent"]}/level), sha256 {sha[:16]}')
