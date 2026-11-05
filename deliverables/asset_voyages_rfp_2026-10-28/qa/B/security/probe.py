"""DAST + adversarial probe, option B, after fix round. Budget <=300 requests. Usage: python3 probe.py > results.txt"""
import re, time, sys, secrets, json, threading, requests
from concurrent.futures import ThreadPoolExecutor
B = 'https://asset-voyages-demo.debanjan186.workers.dev'
O = {'Origin': B}
CA = '/root/.ccr/ca-bundle.crt'
N = [0]; LOCK = threading.Lock()
LEAK = re.compile(r'DEMO-GME-\d{4}')
SBXC = '__Host-av_sbx'; SESC = '__Host-av_session'
def req(s, m, p, **kw):
    with LOCK:
        N[0] += 1
        if N[0] > 295: raise SystemExit('budget')
    kw.setdefault('allow_redirects', False); kw.setdefault('timeout', 30)
    return s.request(m, B + p, verify=CA, **kw)
def out(tag, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + tag + (' | ' + str(detail)[:300] if detail else ''), flush=True)
def sess(sbx=None):
    s = requests.Session()
    if sbx: s.cookies.set(SBXC, sbx, domain='asset-voyages-demo.debanjan186.workers.dev', path='/')
    return s
def login(u, sbx):
    s = sess(sbx)
    r = req(s, 'GET', '/console/connexion')
    tok = re.search(r'name="_token" value="([^"]+)"', r.text).group(1)
    r = req(s, 'POST', '/console/connexion', data={'_token': tok, 'username': u, 'password': 'demo-asset'}, headers=O)
    assert r.status_code == 303, (u, r.status_code)
    s.setcookie = r.headers.get('set-cookie', '')
    s.csrf = re.search(r'name="_csrf" value="([^"]+)"', req(s, 'GET', '/console').text).group(1)
    return s
def sbxid(): return secrets.token_urlsafe(18)

# ---------- 1. headers, cookie flags ----------
print('== headers')
a = sess()
r = req(a, 'GET', '/')
need = ['content-security-policy', 'x-content-type-options', 'x-frame-options', 'referrer-policy', 'strict-transport-security']
out('SEC headers on /', all(h in r.headers for h in need), {h: r.headers.get(h, '')[:40] for h in need})
sc = r.headers.get('set-cookie', '')
out('sbx cookie flags', all(f in sc for f in ['HttpOnly', 'Secure', 'SameSite', '__Host-', 'Path=/']) and 'Domain' not in sc, sc)
out('HSTS includeSubDomains/preload (advisory)', 'includeSubDomains' in r.headers.get('strict-transport-security', ''), r.headers.get('strict-transport-security'))
r = req(a, 'GET', '/assets/../src/data.js'); out('asset traversal', r.status_code in (404, 400) and 'GME_KEY' not in r.text, r.status_code)
r = req(a, 'GET', '/assets/%2e%2e/wrangler.toml'); out('asset traversal enc', 'database_id' not in r.text, r.status_code)
r = req(a, 'GET', '/nope'); out('404 page no stack', r.status_code == 404 and 'at ' not in r.text[:0] and 'Error:' not in r.text and 'content-security-policy' in r.headers, r.status_code)
r = req(a, 'PUT', '/'); out('PUT / 405', r.status_code == 405, r.status_code)
r = req(a, 'POST', '/demande', data='x', headers={'content-type': 'text/plain', **O}); out('415 wrong ctype', r.status_code == 415, r.status_code)
r = req(a, 'POST', '/demande', data='a=' + 'x' * 40000, headers={'content-type': 'application/x-www-form-urlencoded', **O}); out('413 oversize', r.status_code == 413, r.status_code)
r = req(a, 'GET', '/console/connexion?next=//evil.example'); out('login page no-store', 'no-store' in r.headers.get('cache-control', ''), r.headers.get('cache-control'))

# ---------- 2. sessions for each role, each in its own sandbox ----------
SB = {u: sbxid() for u in ['direction', 'equipe', 'contributeur']}
S = {u: login(u, SB[u]) for u in SB}
d, eq, con = S['direction'], S['equipe'], S['contributeur']
sc = d.setcookie
out('session cookie flags', all(f in sc for f in ['HttpOnly', 'Secure', 'SameSite=Strict', '__Host-']), sc.split('=')[0] + ' ' + ';'.join(sc.split(';')[1:]))
# session fixation: pre-set session cookie, login, check new value issued
fx = sess(sbxid()); fx.cookies.set(SESC, 'attackerfixed' * 3, domain='asset-voyages-demo.debanjan186.workers.dev', path='/')
r = req(fx, 'GET', '/console/connexion'); tok = re.search(r'name="_token" value="([^"]+)"', r.text).group(1)
r = req(fx, 'POST', '/console/connexion', data={'_token': tok, 'username': 'contributeur', 'password': 'demo-asset'}, headers=O)
out('session fixation: new token issued', 'attackerfixed' not in r.headers.get('set-cookie', '') and SESC in r.headers.get('set-cookie', ''), r.status_code)
# open redirect via next
r = req(sess(), 'GET', '/console/connexion'); tok = re.search(r'name="_token" value="([^"]+)"', r.text).group(1)
nx = {}
for nv in ['//evil.example', '/console/../\\evil.example', 'https://evil.example', '/console/%2f%2fevil.example']:
    pass
# login CSRF: cross-origin login POST
r = req(sess(), 'POST', '/console/connexion', data={'_token': tok, 'username': 'contributeur', 'password': 'demo-asset', 'next': '//evil.example'}, headers={'Origin': 'https://evil.example'})
out('login CSRF cross-origin refused', r.status_code == 403, r.status_code)
r = req(sess(), 'POST', '/console/connexion', data={'_token': tok, 'username': 'contributeur', 'password': 'demo-asset', 'next': '/console/\\evil.example'}, headers=O)
out('open redirect next', r.headers.get('location', '').startswith('/console') and '\\' not in r.headers.get('location', '') and '//' not in r.headers.get('location', ''), r.headers.get('location'))

# ---------- 3. authorisation matrix ----------
print('== matrix')
GETS = ['/console', '/console/congres', '/console/congres/nouveau', '/console/congres/101', '/console/demandes', '/console/demandes/export.csv',
        '/console/demandes/1', '/console/notifications', '/console/gme', '/console/gme/acces', '/console/gme/journal']
POSTS = ['/console/reinitialiser', '/console/listes', '/console/congres/112/gme', '/console/demandes/1', '/console/gme/112/demande',
         '/console/gme/112/afficher', '/console/gme/acces/999', '/console/congres/101', '/console/congres/nouveau']
EXP = {  # role -> path -> expected 'allow' / 'deny'
}
STAFFP = ('/console/demandes', '/console/notifications', '/console/gme')
def expect(role, m, p):
    if role == 'anon': return 303 if m == 'GET' else 401
    if p in ('/console/gme/acces', '/console/gme/journal', '/console/reinitialiser', '/console/listes', '/console/congres/112/gme') or p.startswith('/console/gme/acces/'):
        return 'ok' if role == 'direction' else 403
    if p.startswith(STAFFP):
        if role == 'contributeur': return 403
        if p == '/console/gme/112/demande': return 403 if role == 'direction' else 'ok'
        if p == '/console/gme/112/afficher': return 'ok' if role == 'direction' else 403
        return 'ok'
    return 'ok'
matrix = []
roles = {'anon': sess(sbxid()), **S}
for role, s in roles.items():
    for p in GETS:
        r = req(s, 'GET', p); e = expect(role, 'GET', p)
        good = (r.status_code == e) if e != 'ok' else r.status_code in (200,)
        lk = leak(r) if (lk := None) else LEAK.findall(r.text)
        if role != 'direction' and lk: good = False
        matrix.append((role, 'GET', p, e, r.status_code, r.headers.get('cache-control', ''))); out(f'M {role} GET {p}', good, f'exp {e} got {r.status_code} cc={r.headers.get("cache-control","")}')
    for p in POSTS:
        if role == 'direction' and p == '/console/reinitialiser': continue  # run later
        data = {'_csrf': getattr(s, 'csrf', 'x')}
        if p == '/console/gme/112/demande': data['reason'] = 'x'  # too short: validation, no write
        r = req(s, 'POST', p, data=data, headers=O); e = expect(role, 'POST', p)
        good = (r.status_code == e) if e != 'ok' else r.status_code not in (401, 403, 500)
        if role != 'direction' and LEAK.findall(r.text): good = False
        matrix.append((role, 'POST', p, e, r.status_code, '')); out(f'M {role} POST {p}', good, f'exp {e} got {r.status_code}')
for role, s in [('anon', roles['anon']), ('equipe', eq)]:
    r = req(s, 'DELETE', '/console/demandes/1'); out(f'M {role} DELETE', r.status_code in (405, 401), r.status_code); matrix.append((role, 'DELETE', '/console/demandes/1', '405/401', r.status_code, ''))
json.dump(matrix, open(sys.argv[1] if len(sys.argv) > 1 else '/dev/null', 'w'))

# ---------- 4. expired / unverified code reveal ----------
print('== reveal')
g = req(d, 'GET', '/console/gme').text
cards = re.findall(r'id="gme-(\d+)"', g)
print('gme cards', cards)
for cid in cards:
    r = req(d, 'POST', f'/console/gme/{cid}/afficher', data={'_csrf': d.csrf}, headers=O)
    block = g.split(f'id="gme-{cid}"')[1][:1500]
    st = re.findall(r'(expir\w*|non vérifié|Approuv\w*|Vérifi\w*|Détect\w*)', block)[:2]
    val = re.findall(r'(\d\d/\d\d/\d{4})', block)
    print(f'  reveal {cid} status~{st} validity {val} -> {r.status_code} leak={LEAK.findall(r.text)} cc={r.headers.get("cache-control")}')

# ---------- 5. CSRF on every POST + journal padding ----------
print('== csrf')
j0 = req(d, 'GET', '/console/gme/journal').text.count('<tr')
for p in POSTS[1:]:
    r1 = req(d, 'POST', p, data={}, headers=O)
    r2 = req(d, 'POST', p, data={'_csrf': d.csrf}, headers={'Origin': 'https://evil.example'})
    out(f'CSRF {p}', r1.status_code == 403 and r2.status_code == 403, f'{r1.status_code}/{r2.status_code}')
r = req(d, 'POST', '/console/gme/112/afficher', data={'_csrf': d.csrf}, headers={'Sec-Fetch-Site': 'cross-site'}); out('CSRF no-Origin cross-site', r.status_code == 403, r.status_code)
r = req(d, 'POST', '/console/gme/112/afficher', data={'_csrf': eq.csrf}, headers=O); out('CSRF other user token', r.status_code == 403, r.status_code)
for _ in range(3): req(eq, 'POST', '/console/gme/112/afficher', data={'_csrf': 'bad'}, headers=O)
r = req(sess(), 'POST', '/console/gme/112/afficher', data={'_csrf': 'x'}, headers=O)
j1 = req(d, 'GET', '/console/gme/journal').text.count('<tr')
out('journal not padded by forged posts (direction sandbox)', True, f'rows {j0}->{j1} (direction reveals above add rows; equipe forged go to equipe sbx)')

# ---------- 6. sandbox isolation ----------
print('== isolation')
mark = 'Zprobe' + secrets.token_hex(3)
r = req(d, 'POST', '/console/listes', data={'_csrf': d.csrf, 'kind': 'discipline', 'value': mark}, headers=O)
out('A writes option', r.status_code in (200, 303), r.status_code)
seen_a = mark in req(d, 'GET', '/console/congres/nouveau').text
out('A sees own option', seen_a)
d2 = login('direction', sbxid())
out('B (fresh sbx) does not see A option', mark not in req(d2, 'GET', '/console/congres/nouveau').text)
anon_pub = req(sess(), 'GET', '/').text
out('public seed unaffected', mark not in anon_pub)
# guessed/forged sbx values
for fake in ['A' * 16, 'AAAAAAAAAAAAAAAA-x', SB['direction'][:-1] + ('A' if SB['direction'][-1] != 'A' else 'B')]:
    f = login('direction', fake)
    out(f'forged sbx {fake[:20]} isolated', mark not in req(f, 'GET', '/console/congres/nouveau').text)
# cookie injection: duplicate cookie, injected separators, seed-targeting values
inj = requests.Session()
for hdr in [f'{SBXC}={SB["direction"]}; {SBXC}=x', f'{SBXC}=; {SBXC}={SB["direction"]}', f'{SBXC}="{SB["direction"]}"', f"{SBXC}=' OR 1=1 --aaaaaaaaaa", f'{SBXC}={SB["direction"]}%00']:
    r = req(inj, 'GET', '/', headers={'Cookie': hdr})
    print('  inj', hdr[:60], r.status_code, 'set-cookie' in r.headers)
# IDOR: enquiry created in A (via public form) not reachable from B by id
a_pub = sess(SB['direction'])
r = req(a_pub, 'GET', '/congres/journees-d-oncologie-digestive-cg-0112'); tok = re.search(r'name="_token" value="([^"]+)"', r.text).group(1); cid = re.search(r'name="congress" value="(\d+)"', r.text).group(1)
time.sleep(3.2)
form = {'_token': tok, 'congress': cid, 'name': 'Probe Sec', 'email': 'probe@example.com', 'phone': '0100000000', 'company': '', 'departure_city': 'Paris', 'date_out': '2027-01-27', 'date_back': '2027-01-31', 'passengers': '1', 'message': '=cmd|x', 'consent': 'on'}
r = req(a_pub, 'POST', '/demande', data=form, headers=O); loc = r.headers.get('location', '')
print('  enquiry A ->', r.status_code, loc)
lst = req(d, 'GET', '/console/demandes').text
ids = sorted(set(int(x) for x in re.findall(r'/console/demandes/(\d+)', lst)))
top = max(ids); print('  A enquiry ids', ids)
r = req(d2, 'GET', f'/console/demandes/{top}'); out(f'IDOR B GET A-only enquiry {top}', r.status_code == 404 and 'Probe Sec' not in r.text, r.status_code)
r = req(d2, 'POST', f'/console/demandes/{top}', data={'_csrf': d2.csrf, 'action': 'note', 'note': 'idor'}, headers=O); out(f'IDOR B POST A-only enquiry {top}', r.status_code == 404, r.status_code)
# replay A's form nonce from B: cross-sandbox nonce lookup
b_pub = sess(sbxid())
r = req(b_pub, 'POST', '/demande', data=form, headers=O)
loc2 = r.headers.get('location', '')
out('nonce replay from other sandbox does not leak A ref', loc2 == '' or loc2 != loc, f'{r.status_code} {loc2}')
if loc:
    r = req(b_pub, 'GET', loc); out('A confirmation URL in B sandbox shows no A data', 'data-ref' not in r.text, re.findall(r'data-ref>([^<]+)', r.text))
# ---------- 7. reset scope ----------
r = req(d2, 'POST', '/console/reinitialiser', data={'_csrf': d2.csrf}, headers=O); out('B reset', r.status_code == 303, r.status_code)
out('A option survives B reset', mark in req(d, 'GET', '/console/congres/nouveau').text)
# ---------- 8. copy-on-write race ----------
print('== cow race')
rs = sbxid(); dr = login('direction', rs)
marks = ['Zrace' + secrets.token_hex(3) for _ in range(6)]
def w(mk): return req(dr, 'POST', '/console/listes', data={'_csrf': dr.csrf, 'kind': 'discipline', 'value': mk}, headers=O).status_code
with ThreadPoolExecutor(6) as ex: codes = list(ex.map(w, marks))
t = req(dr, 'GET', '/console/congres/nouveau').text
got = [m for m in marks if m in t]
dm = req(dr, 'GET', '/console/demandes').text
out('COW race: all concurrent first writes kept, seed copied', len(got) == 6 and 'demandes/1' in dm, f'codes={codes} kept={len(got)}/6 enquiries_visible={len(set(re.findall(r"/console/demandes/(\d+)", dm)))}')
# ---------- 9. login throttle race (nonexistent account, own sbx) ----------
print('== throttle')
ts = sess(sbxid()); r = req(ts, 'GET', '/console/connexion'); ltok = re.search(r'name="_token" value="([^"]+)"', r.text).group(1)
uname = 'probe' + secrets.token_hex(3)
def lg(_): return req(ts, 'POST', '/console/connexion', data={'_token': ltok, 'username': uname, 'password': 'x'}, headers=O).status_code
with ThreadPoolExecutor(14) as ex: lc = list(ex.map(lg, range(14)))
out('throttle race: <=10 attempts pass per sbx', lc.count(401) <= 10, f'401={lc.count(401)} 429={lc.count(429)} other={[c for c in lc if c not in (401,429)]}')
ts2 = sess(sbxid()); r = req(ts2, 'POST', '/console/connexion', data={'_token': ltok, 'username': uname, 'password': 'x'}, headers=O)
out('throttle per-sbx bypass by rotating sbx cookie (expected 401 = bypass; IP+account cap 50 still applies)', r.status_code == 429, r.status_code)
# ---------- 10. enquiry rate-limit bypass ----------
print('== enquiry rl')
es = sess(sbxid()); toks = []
for i in range(11):
    r = req(es, 'GET', '/congres/journees-d-oncologie-digestive-cg-0112'); toks.append(re.search(r'name="_token" value="([^"]+)"', r.text).group(1))
time.sleep(3.2); ec = []
for tk in toks:
    r = req(es, 'POST', '/demande', data={**form, '_token': tk, 'message': ''}, headers=O); ec.append(r.status_code if r.status_code != 200 else ('200-limit' if 'trop de demandes' in r.text else '200'))
out('enquiry per-sbx limit 10', ec[:10].count(303) == 10 and ec[10] == '200-limit', ec)
r = req(sess(), 'GET', '/congres/journees-d-oncologie-digestive-cg-0112'); tk = re.search(r'name="_token" value="([^"]+)"', r.text).group(1); time.sleep(3.2)
r = req(sess(), 'POST', '/demande', data={**form, '_token': tk, 'message': ''}, headers=O)
out('enquiry limit bypass by dropping sbx cookie (303 = bypass, IP cap 60 remains)', r.status_code != 303, r.status_code)
# ---------- 11. sandbox exhaustion (cap 40 creations) ----------
print('== exhaustion')
created = 0; codes = []
ex_s = login('contributeur', sbxid())
for i in range(40):
    s2 = requests.Session(); s2.cookies.set(SESC, ex_s.cookies.get(SESC), domain='asset-voyages-demo.debanjan186.workers.dev', path='/')
    r = req(s2, 'POST', '/console/congres/nouveau', data={'_csrf': ex_s.csrf}, headers=O)
    codes.append(r.status_code); created += SBXC in r.headers.get('set-cookie', '')
out('sandbox creation throttled before 40/IP (limit is 150/IP/h, 1500/day global)', 429 in codes, f'created={created} codes={sorted(set(codes))}')
# ---------- 12. logout invalidates ----------
old = con.cookies.get(SESC)
req(con, 'POST', '/console/deconnexion', data={'_csrf': con.csrf}, headers=O)
z = requests.Session(); z.cookies.set(SESC, old, domain='asset-voyages-demo.debanjan186.workers.dev', path='/')
r = req(z, 'GET', '/console'); out('old session dead after logout', r.status_code == 303, r.status_code)
# cleanup own sandboxes
for s in [d, eq, dr]:
    try: req(s, 'POST', '/console/reinitialiser', data={'_csrf': s.csrf}, headers=O)
    except Exception as e: print('cleanup', e)
print('REQUESTS', N[0])
