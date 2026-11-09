"""Adversarial probes against the live ASSET Voyages option B demo. ~90 requests. Resets demo at end."""
import re, time, sys, requests
B = 'https://asset-voyages-demo.debanjan186.workers.dev'
O = {'Origin': B}
N = 0
LEAK = re.compile(r'DEMO-GME-\d{4}')
def req(s, m, p, **kw):
    global N; N += 1
    kw.setdefault('allow_redirects', False)
    r = s.request(m, B + p, timeout=20, **kw)
    return r
def out(tag, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + tag + (' | ' + detail if detail else ''))
def login(u):
    s = requests.Session()
    r = req(s, 'GET', '/console/connexion')
    tok = re.search(r'name="_token" value="([^"]+)"', r.text).group(1)
    r = req(s, 'POST', '/console/connexion', data={'_token': tok, 'username': u, 'password': 'demo-asset'}, headers=O)
    assert r.status_code == 303, (u, r.status_code)
    s.csrf = re.search(r'name="_csrf" value="([^"]+)"', req(s, 'GET', '/console').text).group(1)
    return s
def leak(r): return LEAK.findall(r.text + str(r.headers))

anon = requests.Session()
for p in ['/console/demandes', '/console/demandes/export.csv', '/console/notifications', '/console/gme', '/console/demandes/1', '/console/congres/112']:
    r = req(anon, 'GET', p); out('anon GET ' + p, r.status_code == 303 and not leak(r) and 'Dupont' not in r.text, str(r.status_code))
r = req(anon, 'POST', '/console/gme/112/afficher', data={'_csrf': 'x'}, headers=O); out('anon reveal', r.status_code == 401 and not leak(r), str(r.status_code))
r = req(anon, 'GET', '/demande/confirmation?ref=DV-2026-0001&k=AAAAAAAAAAAAAAAAAAAAAA'); out('confirm forged sig hides ref', 'data-ref' not in r.text)
for p in ['/', '/congres/x', '/nope', '/assets/../src/data.js', '/assets/%2e%2e/src/data.js']:
    r = req(anon, 'GET', p); out('anon leak ' + p, not leak(r), str(r.status_code))

con = login('contributeur')
for p in ['/console/demandes', '/console/demandes/export.csv', '/console/demandes/1', '/console/notifications', '/console/gme', '/console/gme/acces', '/console/gme/journal']:
    r = req(con, 'GET', p); out('contrib GET ' + p, r.status_code == 403 and not leak(r), str(r.status_code))
for c in [112, 103, 101, 113]:
    r = req(con, 'GET', f'/console/congres/{c}'); out(f'contrib congres {c} no code/gme', not leak(r) and 'gme/' not in r.text, str(r.status_code))
r = req(con, 'POST', '/console/gme/112/afficher', data={'_csrf': con.csrf}, headers=O); out('contrib reveal', r.status_code == 403 and not leak(r), str(r.status_code))
r = req(con, 'POST', '/console/congres/113', data={'_csrf': con.csrf, 'action': 'publish'}, headers=O); out('contrib raw publish', r.status_code == 403, str(r.status_code))
r = req(con, 'POST', '/console/congres/112/gme', data={'_csrf': con.csrf, 'code': 'PWN1', 'status': 'approuve'}, headers=O); out('contrib gmeSave', r.status_code == 403, str(r.status_code))

eq = login('equipe')
r = req(eq, 'GET', '/console/gme'); out('equipe list masked', not leak(r))
for c in [112, 103, 108, 101, 105]:
    r = req(eq, 'POST', f'/console/gme/{c}/afficher', data={'_csrf': eq.csrf}, headers=O); out(f'equipe reveal {c} no grant', r.status_code == 403 and not leak(r), str(r.status_code))
r = req(eq, 'POST', '/console/gme/112/afficher', data={'_csrf': con.csrf}, headers=O); out('csrf cross-user', r.status_code == 403, str(r.status_code))
r = req(eq, 'POST', '/console/gme/112/afficher', data={'_csrf': eq.csrf}, headers={'Origin': 'https://evil.example'}); out('csrf cross-origin', r.status_code == 403, str(r.status_code))
r = req(eq, 'POST', '/console/gme/112/demande', data={'_csrf': eq.csrf, 'reason': 'devis DV-2026-0002 <script>alert(1)</script>'}, headers=O); out('equipe request', r.status_code == 303, str(r.status_code))
d = login('direction')
acc = req(d, 'GET', '/console/gme/acces').text
rid = re.findall(r'/console/gme/acces/(\d+)', acc)
out('reason escaped on acces', '<script>alert(1)' not in acc and '&lt;script&gt;' in acc)
r = req(eq, 'POST', f'/console/gme/acces/{rid[0]}', data={'_csrf': eq.csrf, 'decision': 'approuver'}, headers=O); out('equipe self-approve', r.status_code == 403, str(r.status_code))
r = req(eq, 'POST', '/console/gme/112/afficher', data={'_csrf': eq.csrf}, headers=O); out('still denied while pending', r.status_code == 403 and not leak(r))
r = req(d, 'POST', f'/console/gme/acces/{rid[0]}', data={'_csrf': d.csrf, 'decision': 'approuver'}, headers=O)
r = req(eq, 'POST', '/console/gme/112/afficher', data={'_csrf': eq.csrf}, headers=O)
out('granted reveal 112 shows only own code', leak(r) == ['DEMO-GME-4821'], str(leak(r)) + ' cc=' + r.headers.get('cache-control', ''))
r = req(eq, 'POST', '/console/gme/103/afficher', data={'_csrf': eq.csrf}, headers=O); out('grant IDOR to 103', r.status_code == 403 and not leak(r))
r = req(eq, 'GET', '/console/gme'); out('after reveal list masked', not leak(r))
r = req(d, 'POST', f'/console/gme/acces/{rid[0]}', data={'_csrf': d.csrf, 'decision': 'revoquer'}, headers=O)
r = req(eq, 'POST', '/console/gme/112/afficher', data={'_csrf': eq.csrf}, headers=O); out('after revoke denied', r.status_code == 403 and not leak(r))
r = req(d, 'POST', f'/console/gme/acces/{rid[0]}', data={'_csrf': d.csrf, 'decision': 'approuver'}, headers=O)
r = req(eq, 'POST', '/console/gme/112/afficher', data={'_csrf': eq.csrf}, headers=O); out('re-approve revoked blocked', r.status_code == 403 and not leak(r))

# enquiry: XSS + CSV formula + validation
pg = req(anon, 'GET', '/congres/' + re.search(r'href="/congres/([a-z0-9-]+)"', req(anon, 'GET', '/').text).group(1)).text
cid = re.search(r'name="congress" value="(\d+)"', pg).group(1)
def tok(): return re.search(r'name="_token" value="([^"]+)"', req(anon, 'GET', '/congres/' + re.search(r'href="/congres/([a-z0-9-]+)"', req(anon,'GET','/').text).group(1)).text).group(1)
base = dict(congress=cid, name='"><img src=x onerror=alert(1)>', email='a@b.fr', phone='0102030405', company='=HYPERLINK("http://x","c")', departure_city='-2+3', date_out='2026-12-01', date_back='2026-12-05', passengers='2', message='@SUM(1)\n=1+1', consent='1')
bad = [('passengers', '0'), ('passengers', '51'), ('passengers', '1e1'), ('date_back', '2026-11-30'), ('date_out', '2020-01-01'), ('consent', ''), ('email', 'x@y')]
t = tok(); time.sleep(3.5)
for k, v in bad:
    r = req(anon, 'POST', '/demande', data={**base, '_token': t, k: v}, headers=O); out(f'reject {k}={v!r}', r.status_code == 422, str(r.status_code))
r = req(anon, 'POST', '/demande', data={**base, '_token': t, 'congress': '113'}, headers=O); out('enquiry on draft congress', r.status_code == 404, str(r.status_code))
r = req(anon, 'POST', '/demande', data={**base, '_token': t}, headers=O); out('valid hostile enquiry accepted', r.status_code == 303, str(r.status_code))
r2 = req(anon, 'POST', '/demande', data={**base, '_token': t}, headers=O); out('token replay idempotent', r2.headers.get('location') == r.headers.get('location'))
for p in ['/console/demandes', '/console/notifications', '/console', '/console/demandes?q=img']:
    h = req(d, 'GET', p).text; out('xss escaped ' + p, '<img src=x' not in h)
csv = req(d, 'GET', '/console/demandes/export.csv').content.decode('utf-8-sig')
line = [l for l in csv.split('\r\n') if 'HYPERLINK' in l]
print('CSV row:', line[:1])
out('csv formula neutralised', line and '"\'=HYPERLINK' in line[0] and '"\'-2+3"' in line[0] and '"\'@SUM' in line[0])

# defacement: equipe publishes directly
r = req(eq, 'POST', '/console/congres/nouveau', data={'_csrf': eq.csrf, 'action': 'publish', 'title': 'AUDIT-DEFACE-PROBE', 'discipline': 'X', 'city': 'X', 'country': 'X', 'venue': 'X', 'start_date': '2027-01-01', 'end_date': '2027-01-02', 'official_url': 'https://evil.example', 'verified_on': '2026-11-01', 'description': 'probe'}, headers=O)
r = req(anon, 'GET', '/?q=AUDIT-DEFACE'); out('DEFACEMENT: equipe-published title NOT on public catalogue', 'AUDIT-DEFACE-PROBE' not in r.text)
# throttle on dummy username
s = requests.Session(); codes = []
lt = re.search(r'name="_token" value="([^"]+)"', req(s, 'GET', '/console/connexion').text).group(1)
for i in range(11):
    codes.append(req(s, 'POST', '/console/connexion', data={'_token': lt, 'username': 'audit-dummy', 'password': 'x'}, headers=O).status_code)
out('login throttle 11th=429', codes[-1] == 429, str(codes))
# reset
r = req(d, 'POST', '/console/reinitialiser', data={'_csrf': d.csrf}, headers=O); out('reset', r.status_code == 303)
r = req(anon, 'GET', '/?q=AUDIT-DEFACE'); out('defacement gone after reset', 'AUDIT-DEFACE-PROBE' not in r.text)
print('requests:', N)
