"""F21: the code on screen, byte-identical to the source. Reads reply_classifier.py lines 99-107 (the OOO block the
wk 02 card shows; line 98 is the comment with the unmeasured "~95%", which FACTS forbids on screen), removes exactly the
4-space function indent (re-indentation is allowed by FACTS) and writes out/code.json. Fails if any line does not start
with those 4 spaces or if re-adding them does not reproduce the file bytes.
usage: python -I tools/code.py <reply_classifier.py> <film_dir>"""
import sys, json, hashlib, os
src, film = sys.argv[1], sys.argv[2]
raw = open(src, 'rb').read().split(b'\n')
block = raw[98:107]                                   # 1-based lines 99..107
assert block[0].strip().startswith(b'ooo_hits = _matches_any'), block[0]
assert all(l.startswith(b'    ') for l in block), 'unexpected indent'
lines = [l[4:].decode('utf-8') for l in block]
assert b'\n'.join(b'    ' + l.encode('utf-8') for l in lines) == b'\n'.join(block)
assert not any('95' in l or '%' in l for l in lines)
sha = hashlib.sha256(b'\n'.join(block)).hexdigest()
os.makedirs(os.path.join(film, 'out'), exist_ok=True)
json.dump({'source': 'execution/personal_workflows/self_outbound_system/reply_classifier.py', 'lines_1based': [99, 107],
           'dedent': 4, 'sha256_of_source_lines': sha, 'lines': lines}, open(os.path.join(film, 'out', 'code.json'), 'w'), indent=1)
print(f'code.py: 9 lines verbatim (dedent 4), sha256 {sha[:16]}')
