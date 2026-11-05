"""
description: Create (draft), fill and tag the ProdCraft Proposal Engine campaigns in Instantly. Default prints the plan only (no API call); --apply performs the writes; --apply --activate also starts them.
inputs: .tmp/leadocean/campaigns_by_country/*.csv; env INSTANTLY_API_KEY (only with --apply); flags --apply, --activate (requires --apply), --only-first
outputs: stdout plan (default); with --apply: Instantly campaigns (draft, then active with --activate) and .tmp/prodcraft_copy/launch_state.json
"""
import argparse, csv, json, os, re, sys, time
from pathlib import Path
import requests
try:
    from dotenv import load_dotenv
except ImportError:  # dotenv is optional; env vars still work without it
    load_dotenv = None
ROOT = Path(__file__).resolve().parents[3]
if load_dotenv:
    load_dotenv(ROOT / '.env')
API = 'https://api.instantly.ai/api/v2'
TAG = 'cebb93b4-b98d-4948-bd99-43b0495fa93f'  # Deb_Oct 6 26
COPY = json.loads((Path(__file__).with_name('copy.json')).read_text())
SRC = ROOT/'.tmp/leadocean/campaigns_by_country'; STATE = ROOT/'.tmp/prodcraft_copy/launch_state.json'
DATE = '2 Nov 2026'
SCHED = {'US': ('09:00', '12:00', 'America/Chicago'), 'UK': ('08:30', '11:30', 'Europe/Isle_of_Man')}

def headers():
    key = os.environ.get('INSTANTLY_API_KEY', '').strip()
    if not key: sys.exit('INSTANTLY_API_KEY not set (needed only with --apply)')
    return {'Authorization': 'Bearer ' + key}

def req(m, path, **kw):
    H = headers()
    for a in range(4):
        r = requests.request(m, API + path, headers=H, timeout=60, **kw)
        if r.status_code == 429: time.sleep(2 ** a * 2); continue
        if r.status_code >= 400: raise RuntimeError(f'{m} {path} {r.status_code} {r.text[:400]}')
        return r.json() if r.text else {}
    raise RuntimeError('429 x4')

SPIN = re.compile(r"\{\{RANDOM\s*\|((?:[^{}]|\{\{[a-zA-Z_]+\}\})*)\}\}")
def tidy(t):
    return SPIN.sub(lambda m: '{{RANDOM|' + '|'.join(o.strip() for o in m.group(1).split('|')) + '}}', t)
def html(t):
    return ''.join(f'<div>{p}</div><div><br /></div>' for p in tidy(t).split('\n\n')).removesuffix('<div><br /></div>')

def plan():
    out = []
    for f in sorted(SRC.glob('*.csv')) + sorted((SRC/'catchall').glob('*.csv')):
        if f.name.startswith(('_', 'REVIEW')): continue
        parts = f.stem.split('_'); niche, country, pers = parts[0], parts[1], parts[2]
        ca = f.parent.name == 'catchall'
        key = 'FitoutUS' if (niche, country) == ('Fitout', 'US') else 'FitoutUK' if niche == 'Fitout' else niche
        name = f"DM_{niche} - {country} - {pers}{' CatchAll' if ca else ''} - {DATE}"
        out.append(dict(file=f, name=name, key=key, country=country, pers=pers, catchall=ca))
    return out

def payload(p):
    c = COPY[p['key']]; s1 = c['step1_personalized' if p['pers'] == 'Personalized' else 'step1_nopersonalization']
    fr, to, tz = SCHED[p['country']]
    steps = [{'type': 'email', 'delay': 3, 'delay_unit': 'days', 'variants': [{'subject': tidy(sj), 'body': html(s1)} for sj in c['subjects']]},
             {'type': 'email', 'delay': 4, 'delay_unit': 'days', 'variants': [{'subject': '', 'body': html(c['step2'])}]},
             {'type': 'email', 'delay': 1, 'delay_unit': 'days', 'variants': [{'subject': '', 'body': html(c['step3'])}]}]
    return {'name': p['name'], 'sequences': [{'steps': steps}],
            'campaign_schedule': {'schedules': [{'name': f"{p['country']} mornings", 'timing': {'from': fr, 'to': to},
                                   'days': {'0': False, '1': True, '2': True, '3': True, '4': True, '5': False, '6': False}, 'timezone': tz}]},
            'email_tag_list': [TAG], 'daily_limit': 5 if p['catchall'] else 30, 'text_only': True, 'first_email_text_only': True,
            'open_tracking': False, 'link_tracking': False, 'stop_on_reply': True, 'stop_on_auto_reply': False,
            'prioritize_new_leads': True, 'insert_unsubscribe_header': True, 'match_lead_esp': True, 'stop_for_company': True,
            'allow_risky_contacts': False, 'disable_bounce_protect': False}

def unguard(v):
    """Undo pipeline_utils.csv_safe_cell (a "'" added before = + - @ TAB CR) so Instantly gets the real value."""
    return v[1:] if isinstance(v, str) and len(v) > 1 and v[0] == "'" and v[1] in '=+-@\t\r' else v

def leads(f):
    with open(f, encoding='utf-8', newline='') as fh:
        rows = [{k: unguard(v) for k, v in r.items()} for r in csv.DictReader(fh)]
    return [{'email': r['email'], 'first_name': r['first_name'], 'last_name': r['last_name'], 'company_name': r['company_name'],
             'website': r['website'], 'custom_variables': {'project_reference': r['project_reference'], 'title': r['title'], 'city': r['city']}} for r in rows]

def show_plan(plans, st, activate):
    """Dry run: print what --apply would do. Reads local files only; makes no network call."""
    print('PLAN ONLY (no Instantly calls). Re-run with --apply to write' + (' and activate' if activate else '') + '.')
    for p in plans:
        rec = st.get(p['name'], {})
        todo = [s for s, done in (('create', 'id' in rec), ('upload', 'uploaded' in rec), ('tag', 'tagged' in rec)) if not done]
        if activate and not rec.get('active'): todo.append('activate')
        print(f"{p['name']} | {p['file'].name} | leads={len(leads(p['file']))} | todo={','.join(todo) or 'nothing'}")

def main(argv=None):
    ap = argparse.ArgumentParser(description='Create/fill/tag ProdCraft Instantly campaigns (plan-only by default).')
    ap.add_argument('--apply', action='store_true', help='perform the Instantly writes (create, upload leads, tag)')
    ap.add_argument('--activate', action='store_true', help='also start the campaigns; requires --apply')
    ap.add_argument('--only-first', action='store_true', help='stop after the first campaign')
    a = ap.parse_args(argv)
    if a.activate and not a.apply:
        ap.error('--activate requires --apply')
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    plans = plan()
    if a.only_first: plans = plans[:1]
    if not a.apply:
        show_plan(plans, st, a.activate); return
    STATE.parent.mkdir(parents=True, exist_ok=True)
    for p in plans:
        rec = st.get(p['name'], {})
        if 'id' not in rec:
            rec['id'] = req('POST', '/campaigns', json=payload(p))['id']; st[p['name']] = rec; STATE.write_text(json.dumps(st, indent=1))
        if 'uploaded' not in rec:
            L = leads(p['file'])
            res = req('POST', '/leads/add', json={'campaign_id': rec['id'], 'skip_if_in_workspace': True, 'leads': L})
            rec['uploaded'] = {k: res.get(k) for k in ('leads_uploaded', 'skipped_count', 'in_blocklist', 'duplicated_leads', 'invalid_email_count', 'total_sent')}
            rec['expected'] = len(L); STATE.write_text(json.dumps(st, indent=1))
        if 'tagged' not in rec:
            req('POST', '/custom-tags/toggle-resource', json={'tag_ids': [TAG], 'resource_ids': [rec['id']], 'resource_type': 2, 'assign': True})
            rec['tagged'] = True; STATE.write_text(json.dumps(st, indent=1))
        if a.activate and not rec.get('active'):
            req('POST', f"/campaigns/{rec['id']}/activate"); rec['active'] = True; STATE.write_text(json.dumps(st, indent=1))
        print(p['name'], rec.get('expected'), rec['uploaded'], 'active' if rec.get('active') else 'draft')

if __name__ == '__main__':
    main()
