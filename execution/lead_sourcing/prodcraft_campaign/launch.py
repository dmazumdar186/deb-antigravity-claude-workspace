"""
description: Create (draft), fill and tag the ProdCraft Proposal Engine campaigns in Instantly; --activate starts them.inputs: .tmp/leadocean/campaigns_by_country/*.csv; env INSTANTLY_API_KEY; --activate
outputs: Instantly campaigns (draft, then active with --activate); .tmp/prodcraft_copy/launch_state.json
"""
import csv, json, os, re, sys, time
from pathlib import Path
import requests
ROOT = Path('/home/user/deb-antigravity-claude-workspace')
API = 'https://api.instantly.ai/api/v2'; H = {'Authorization': 'Bearer ' + os.environ['INSTANTLY_API_KEY']}
TAG = 'cebb93b4-b98d-4948-bd99-43b0495fa93f'  # Deb_Oct 6 26
COPY = json.loads((Path(__file__).with_name('copy.json')).read_text())
SRC = ROOT/'.tmp/leadocean/campaigns_by_country'; STATE = ROOT/'.tmp/prodcraft_copy/launch_state.json'
DATE = '2 Nov 2026'
SCHED = {'US': ('09:00', '12:00', 'America/Chicago'), 'UK': ('08:30', '11:30', 'Europe/Isle_of_Man')}

def req(m, path, **kw):
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

def leads(f):
    rows = list(csv.DictReader(open(f, encoding='utf-8')))
    return [{'email': r['email'], 'first_name': r['first_name'], 'last_name': r['last_name'], 'company_name': r['company_name'],
             'website': r['website'], 'custom_variables': {'project_reference': r['project_reference'], 'title': r['title'], 'city': r['city']}} for r in rows]

def main():
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    for p in plan():
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
        if '--activate' in sys.argv and not rec.get('active'):
            req('POST', f"/campaigns/{rec['id']}/activate"); rec['active'] = True; STATE.write_text(json.dumps(st, indent=1))
        print(p['name'], rec.get('expected'), rec['uploaded'], 'active' if rec.get('active') else 'draft')
    if '--only-first' in sys.argv: return

if __name__ == '__main__':
    main()
