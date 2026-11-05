"""Follow-up to probe.py: re-runs isolation/IDOR/reset/COW-race checks probe.py got wrong (digit in option value, consent=on). ~28 requests."""
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


def word(): return 'Zsec' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
import random, string
A = login('direction', sbxid()); Bs = login('direction', sbxid())
mk = word()
r = req(A, 'POST', '/console/listes', data={'_csrf': A.csrf, 'kind': 'discipline', 'value': mk}, headers=O); print('A add', r.status_code, r.headers.get('location'))
out('A sees own option', mk in req(A, 'GET', '/console/congres/nouveau').text)
out('B does not see A option', mk not in req(Bs, 'GET', '/console/congres/nouveau').text)
# enquiry in A
p = sess(A.cookies.get(SBXC)); r = req(p, 'GET', '/congres/journees-d-oncologie-digestive-cg-0112')
tok = re.search(r'name="_token" value="([^"]+)"', r.text).group(1); cid = re.search(r'name="congress" value="(\d+)"', r.text).group(1)
time.sleep(3.3)
form = {'_token': tok, 'congress': cid, 'name': 'Probe Sec', 'email': 'probe@example.com', 'phone': '0100000000', 'departure_city': 'Paris', 'date_out': '2027-01-27', 'date_back': '2027-01-31', 'passengers': '1', 'message': '=HYPERLINK("x")', 'consent': '1'}
r = req(p, 'POST', '/demande', data=form, headers=O); print('enquiry', r.status_code, r.headers.get('location'))
ids = sorted(set(int(x) for x in re.findall(r'/console/demandes/(\d+)', req(A, 'GET', '/console/demandes').text))); print('A ids', ids)
top = max(ids)
r = req(Bs, 'GET', f'/console/demandes/{top}'); out(f'IDOR B GET A-only enquiry {top}', r.status_code == 404 and 'Probe Sec' not in r.text, r.status_code)
r = req(Bs, 'POST', f'/console/demandes/{top}', data={'_csrf': Bs.csrf, 'action': 'note', 'note': 'idor'}, headers=O); out(f'IDOR B POST A-only enquiry {top}', r.status_code == 404, r.status_code)
r = req(Bs, 'POST', '/console/reinitialiser', data={'_csrf': Bs.csrf}, headers=O); print('B reset', r.status_code)
out('A option survives B reset', mk in req(A, 'GET', '/console/congres/nouveau').text)
# COW race
C = login('direction', sbxid()); marks = [word() for _ in range(5)]
def w(m): return req(C, 'POST', '/console/listes', data={'_csrf': C.csrf, 'kind': 'discipline', 'value': m}, headers=O).status_code
with ThreadPoolExecutor(5) as ex: codes = list(ex.map(w, marks))
t = req(C, 'GET', '/console/congres/nouveau').text; kept = [m for m in marks if m in t]
nd = len(set(re.findall(r'/console/demandes/(\d+)', req(C, 'GET', '/console/demandes').text)))
out('COW race keeps all 5 concurrent first writes + seed copy', len(kept) == 5 and nd >= 6, f'codes={codes} kept={len(kept)}/5 enquiries={nd} options_in_page={t.count("<option")}')
for s in (A, C): req(s, 'POST', '/console/reinitialiser', data={'_csrf': s.csrf}, headers=O)
print('REQUESTS', N[0])
