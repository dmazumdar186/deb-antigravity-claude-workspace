"""Round-3 security re-check, option B (row-level COW, signed sessions, caps). Budget <=240 requests, <=12 sandboxes.
Usage: python3 probe3.py > results3.txt"""
import re, time, sys, secrets, json, base64, threading, random, string, requests
from concurrent.futures import ThreadPoolExecutor
B = 'https://asset-voyages-demo.debanjan186.workers.dev'; H = 'asset-voyages-demo.debanjan186.workers.dev'
O = {'Origin': B}; CA = '/root/.ccr/ca-bundle.crt'
N = [0]; LOCK = threading.Lock(); SBXUSED = set()
LEAK = re.compile(r'DEMO-GME-\d{4}')
SBXC = '__Host-av_sbx'; SESC = '__Host-av_session'
def req(s, m, p, **kw):
    with LOCK:
        N[0] += 1
        if N[0] > 240: raise SystemExit('budget')
    kw.setdefault('allow_redirects', False); kw.setdefault('timeout', 30)
    if m == 'POST' and s.cookies.get(SBXC): SBXUSED.add(s.cookies.get(SBXC))
    return s.request(m, B + p, verify=CA, **kw)
def out(tag, ok, detail=''): print(('PASS ' if ok else 'FAIL ') + tag + (' | ' + str(detail)[:300] if detail else ''), flush=True)
def sess(sbx=None):
    s = requests.Session()
    if sbx: s.cookies.set(SBXC, sbx, domain=H, path='/')
    return s
def login(u, sbx):
    s = sess(sbx); r = req(s, 'GET', '/console/connexion')
    tok = re.search(r'name="_token" value="([^"]+)"', r.text).group(1)
    r = req(s, 'POST', '/console/connexion', data={'_token': tok, 'username': u, 'password': 'demo-asset'}, headers=O)
    assert r.status_code == 303, (u, r.status_code)
    s.csrf = re.search(r'name="_csrf" value="([^"]+)"', req(s, 'GET', '/console').text).group(1); return s
def sbxid(): return secrets.token_urlsafe(18)
def word(): return 'Zsec' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
def withcookie(val, sbx=None):
    z = sess(sbx); z.cookies.set(SESC, val, domain=H, path='/'); return z
def b64d(s): return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))
def b64e(b): return base64.urlsafe_b64encode(b).decode().rstrip('=')

print('== sessions')
SA, SB_, SC = sbxid(), sbxid(), sbxid()
A = login('direction', SA); E = login('equipe', SA); C = login('contributeur', SC)
tokC = C.cookies.get(SESC); pl, sig = tokC.split('.')
p = json.loads(b64d(pl)); print('  payload keys', sorted(p), 'u', p['u'])
out('payload carries no role/privilege field', set(p) == {'u', 'c', 'e', 'n'}, sorted(p))
for name, tok in [
    ('u->1 keep sig', b64e(json.dumps({**p, 'u': 1}, separators=(',', ':')).encode()) + '.' + sig),
    ('role smuggle keep sig', b64e(json.dumps({**p, 'role': 'direction'}, separators=(',', ':')).encode()) + '.' + sig),
    ('sig flipped', pl + '.' + ('A' if sig[0] != 'A' else 'B') + sig[1:]),
    ('no sig', pl + '.'), ('payload only', pl), ('extra segment', tokC + '.x'),
    ('expired-looking e=0 keep sig', b64e(json.dumps({**p, 'e': 0}).encode()) + '.' + sig),
    ('sig of other user', pl + '.' + E.cookies.get(SESC).split('.')[1]),
    ('oversize', pl + '.' + sig + 'A' * 400)]:
    r = req(withcookie(tok, SC), 'GET', '/console'); out(f'forged session [{name}] rejected', r.status_code == 303, r.status_code)
r = req(withcookie(tokC + '.x', SC), 'GET', '/console')  # note: split('.') takes first two parts
r2 = req(withcookie(tokC, SC), 'GET', '/console/gme'); out('contributeur real cookie still denied on gme', r2.status_code == 403, r2.status_code)
# logout replay
old = C.cookies.get(SESC); r = req(C, 'POST', '/console/deconnexion', data={'_csrf': C.csrf}, headers=O)
out('logout 303', r.status_code == 303, r.status_code)
r = req(withcookie(old, SC), 'GET', '/console'); out('replay after logout -> 303', r.status_code == 303, r.status_code)
r = req(withcookie(old, sbxid()), 'GET', '/console'); out('replay after logout from other sbx -> 303', r.status_code == 303, r.status_code)
r = req(withcookie(old, SC), 'POST', '/console/congres/nouveau', data={'_csrf': p['c']}, headers=O); out('replay POST after logout -> 401', r.status_code == 401, r.status_code)

print('== test-key header')
r1 = req(sess(), 'GET', '/', headers={'x-demo-test': 'A' * 64}); r2 = req(sess(), 'GET', '/', headers={'x-demo-test': '', 'x-demo-real': '1'})
out('x-demo-test gives no meter header', 'x-d1-rows-written' not in r1.headers and 'x-d1-rows-written' not in r2.headers, [k for k in r1.headers if k.lower().startswith('x-')])
out('no demo-test name in responses', 'demo-test' not in (r1.text + str(r1.headers)).lower(), '')

print('== matrix + leak crawl')
GETS = ['/console', '/console/congres', '/console/congres/nouveau', '/console/congres/101', '/console/demandes', '/console/demandes/export.csv',
        '/console/demandes/1', '/console/notifications', '/console/gme', '/console/gme/acces', '/console/gme/journal']
POSTS = ['/console/listes', '/console/congres/112/gme', '/console/demandes/1', '/console/gme/112/demande',
         '/console/gme/112/afficher', '/console/gme/acces/999', '/console/congres/101', '/console/reinitialiser']
def expect(role, m, p):
    if role == 'anon': return 303 if m == 'GET' else 401
    if p in ('/console/gme/acces', '/console/gme/journal', '/console/reinitialiser', '/console/listes', '/console/congres/112/gme') or p.startswith('/console/gme/acces/'):
        return 'ok' if role == 'direction' else 403
    if p.startswith(('/console/demandes', '/console/notifications', '/console/gme')):
        if role == 'contributeur': return 403
        if p == '/console/gme/112/demande': return 403 if role == 'direction' else 'ok'
        if p == '/console/gme/112/afficher': return 'ok' if role == 'direction' else 403
        return 'ok'
    if role == 'contributeur' and m == 'POST' and p == '/console/congres/101': return 403
    return 'ok'
C2 = login('contributeur', SC)
roles = {'anon': sess(sbxid()), 'direction': A, 'equipe': E, 'contributeur': C2}
bad = 0; tot = 0; leaks = []
for role, s in roles.items():
    for p_ in GETS:
        r = req(s, 'GET', p_); e = expect(role, 'GET', p_); tot += 1
        good = (r.status_code == e) if e != 'ok' else r.status_code == 200
        lk = LEAK.findall(r.text)
        if lk: leaks.append((role, p_, lk))
        if not good: bad += 1; out(f'M {role} GET {p_}', False, f'exp {e} got {r.status_code}')
    for p_ in POSTS:
        if role == 'direction' and p_ == '/console/reinitialiser': continue
        data = {'_csrf': getattr(s, 'csrf', 'x')}
        if p_ == '/console/gme/112/demande': data['reason'] = 'x'
        r = req(s, 'POST', p_, data=data, headers=O); e = expect(role, 'POST', p_); tot += 1
        good = (r.status_code == e) if e != 'ok' else r.status_code not in (401, 403, 500)
        lk = LEAK.findall(r.text)
        if lk: leaks.append((role, 'POST ' + p_, lk))
        if not good: bad += 1; out(f'M {role} POST {p_}', False, f'exp {e} got {r.status_code}')
out(f'authz matrix {tot - bad}/{tot}', bad == 0)
out('GME leak only where direction revealed', all(l[0] == 'direction' and 'afficher' in l[1] for l in leaks), leaks)
for pub in ['/', '/congres/journees-d-oncologie-digestive-cg-0112', '/robots.txt']:
    r = req(sess(), 'GET', pub); out(f'public {pub} no GME', not LEAK.findall(r.text) and 'code_enc' not in r.text, r.status_code)

print('== reveal statuses (direction, SA)')
for cid in ['101', '103', '105', '108', '112']:
    r = req(A, 'POST', f'/console/gme/{cid}/afficher', data={'_csrf': A.csrf}, headers=O)
    print(f'  reveal {cid} -> {r.status_code} leak={bool(LEAK.findall(r.text))} cc={r.headers.get("cache-control")}')

print('== COW isolation')
Bd = login('direction', SB_)
mk = word()
# A edits seed congress 101 title (copy-on-write) -- fetch form fields first
f = req(A, 'GET', '/console/congres/101').text
fields = dict(re.findall(r'<input[^>]*name="([a-z_]+)"[^>]*value="([^"]*)"', f))
fields.update({k: v for k, v in re.findall(r'<textarea[^>]*name="([a-z_]+)"[^>]*>([^<]*)</textarea>', f)})
for nm in re.findall(r'<select[^>]*name="([a-z_]+)"', f):
    blk = f.split(f'name="{nm}"')[1].split('</select>')[0]; sel = re.search(r'<option[^>]*value="([^"]*)"[^>]*selected', blk)
    if sel: fields[nm] = sel.group(1)
import html as _h
fields = {k: _h.unescape(v) for k, v in fields.items()}
fields['title'] = 'Congres ' + mk; fields['_csrf'] = A.csrf
r = req(A, 'POST', '/console/congres/101', data=fields, headers=O); print('  A edit 101', r.status_code, r.headers.get('location'))
out('A sees own edit', mk in req(A, 'GET', '/console/congres').text)
out('B direction does not see A edit', mk not in req(Bd, 'GET', '/console/congres').text)
out('public anon does not see A edit', mk not in req(sess(), 'GET', '/').text)
out('public in fresh-cookie sbx does not see A edit', mk not in req(sess(sbxid()), 'GET', '/').text)
# equipe in SA requests GME 112; direction A sees it in acces, B does not
r = req(E, 'POST', '/console/gme/112/demande', data={'_csrf': E.csrf, 'reason': 'Motif ' + mk}, headers=O); print('  E request', r.status_code)
out('A acces lists E request', mk in req(A, 'GET', '/console/gme/acces').text)
out('B acces does not list A request', mk not in req(Bd, 'GET', '/console/gme/acces').text)
# enquiry in SA -> notifications/history in A only
pa = sess(SA); r = req(pa, 'GET', '/congres/journees-d-oncologie-digestive-cg-0112')
tok = re.search(r'name="_token" value="([^"]+)"', r.text).group(1); cid = re.search(r'name="congress" value="(\d+)"', r.text).group(1)
time.sleep(3.3)
form = {'_token': tok, 'congress': cid, 'name': 'Probe ' + mk[4:], 'email': 'probe@example.com', 'phone': '0100000000', 'departure_city': 'Paris', 'date_out': '2027-01-27', 'date_back': '2027-01-31', 'passengers': '1', 'message': 'x', 'consent': '1'}
r = req(pa, 'POST', '/demande', data=form, headers=O); loc = r.headers.get('location', ''); print('  enquiry A', r.status_code, loc)
nm = 'Probe ' + mk[4:]
out('A notifications include enquiry', nm in req(A, 'GET', '/console/notifications').text)
out('B notifications exclude A enquiry', nm not in req(Bd, 'GET', '/console/notifications').text)
out('B CSV export excludes A enquiry', nm not in req(Bd, 'GET', '/console/demandes/export.csv').text)
ids = sorted(set(int(x) for x in re.findall(r'/console/demandes/(\d+)', req(A, 'GET', '/console/demandes').text))); top = max(ids); print('  A ids', ids)
r = req(Bd, 'GET', f'/console/demandes/{top}'); out(f'IDOR B GET A enquiry {top}', r.status_code == 404, r.status_code)
# B creates its own enquiry: same id as A's (PK (sbx,id)) -- must not collide
pb = sess(SB_); r = req(pb, 'GET', '/congres/journees-d-oncologie-digestive-cg-0112')
tokb = re.search(r'name="_token" value="([^"]+)"', r.text).group(1); time.sleep(3.3)
r = req(pb, 'POST', '/demande', data={**form, '_token': tokb, 'name': 'ProbeB ' + mk[4:]}, headers=O); locb = r.headers.get('location', ''); print('  enquiry B', r.status_code, locb)
out('B enquiry same ref number, no PK collision', r.status_code == 303 and locb.split('&')[0] == loc.split('&')[0], f'{loc[:50]} vs {locb[:50]}')
rb = req(Bd, 'GET', f'/console/demandes/{top}').text; out('B id shows B row only', 'ProbeB' in rb and nm not in rb)
ra = req(A, 'GET', f'/console/demandes/{top}').text; out('A id shows A row only', nm in ra and 'ProbeB' not in ra)
r = req(pb, 'GET', loc); out('A confirmation link in B shows B row (same ref) not A title', mk not in r.text, re.findall(r'data-ref>([^<]+)', r.text))
# history on seed enquiry 1 after A change
r = req(A, 'POST', '/console/demandes/1', data={'_csrf': A.csrf, 'action': 'note', 'note': 'Note ' + mk}, headers=O); print('  A note on 1', r.status_code)
out('A history shows note', mk in req(A, 'GET', '/console/demandes/1').text)
out('B history on 1 lacks A note', mk not in req(Bd, 'GET', '/console/demandes/1').text)
# B resets, A intact; A resets then reads seed
r = req(Bd, 'POST', '/console/reinitialiser', data={'_csrf': Bd.csrf}, headers=O); out('B reset', r.status_code == 303, r.status_code)
out('A edit survives B reset', mk in req(A, 'GET', '/console/congres').text)
print('== busy flag cosmetic')
r = req(sess(), 'GET', '/?demo=complet'); out('?demo=complet renders (banner only, no state)', r.status_code == 200 and 'set-cookie' in {k.lower() for k in r.headers}, r.status_code)
print('== cleanup')
for s in (A, C2):
    r = req(s, 'POST', '/console/reinitialiser', data={'_csrf': s.csrf}, headers=O) if s is A else None
out('A reset -> seed restored', mk not in req(A, 'GET', '/console/congres').text and nm not in req(A, 'GET', '/console/notifications').text)
print('SANDBOXES_WRITTEN', len(SBXUSED), 'REQUESTS', N[0])
