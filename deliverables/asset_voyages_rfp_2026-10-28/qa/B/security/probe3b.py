"""probe3 follow-up: debug the congress-edit COW check, then reset the contributeur's sandbox. ~20 requests."""
import sys, re, html as _h
sys.argv = ['x']
exec(open('probe3.py').read().split("print('== sessions')")[0])
SA, SB_ = sbxid(), sbxid(); A = login('direction', SA); Bd = login('direction', SB_)
f = req(A, 'GET', '/console/congres/101').text
form = f.split('action="/console/congres/101"')[1].split('</form>')[0] if 'action="/console/congres/101"' in f else f
fields = {}
for tag in re.findall(r'<input[^>]*>', form):
    n = re.search(r'name="([^"]+)"', tag); v = re.search(r'value="([^"]*)"', tag)
    if n and 'type="radio"' not in tag and 'type="checkbox"' not in tag: fields[n.group(1)] = _h.unescape(v.group(1)) if v else ''
for n, v in re.findall(r'<textarea[^>]*name="([^"]+)"[^>]*>([\s\S]*?)</textarea>', form): fields[n] = _h.unescape(v)
for n, blk in re.findall(r'<select[^>]*name="([^"]+)"[^>]*>([\s\S]*?)</select>', form):
    s = re.search(r'<option[^>]*value="([^"]*)"[^>]*selected', blk); fields[n] = _h.unescape(s.group(1)) if s else ''
mk = word(); fields['title'] = 'Congres ' + mk; fields['_csrf'] = A.csrf
print('fields', sorted(fields))
r = req(A, 'POST', '/console/congres/101', data=fields, headers=O); print('edit', r.status_code, r.headers.get('location'))
if r.status_code == 200: print('errors', re.findall(r'class="(?:err|error|alert)[^"]*"[^>]*>([^<]{0,160})', r.text)[:5])
out('A sees own edit', mk in req(A, 'GET', '/console/congres').text)
out('A public page shows own edit', mk in req(sess(SA), 'GET', '/').text)
out('B does not see A edit', mk not in req(Bd, 'GET', '/console/congres').text)
out('anon public does not see A edit', mk not in req(sess(), 'GET', '/').text)
r = req(Bd, 'POST', '/console/reinitialiser', data={'_csrf': Bd.csrf}, headers=O)
out('A edit survives B reset', mk in req(A, 'GET', '/console/congres').text)
req(A, 'POST', '/console/reinitialiser', data={'_csrf': A.csrf}, headers=O)
out('A reset restores seed title', mk not in req(A, 'GET', '/console/congres').text)
SC = sys.argv[1] if len(sys.argv) > 1 else None
print('REQUESTS', N[0])
