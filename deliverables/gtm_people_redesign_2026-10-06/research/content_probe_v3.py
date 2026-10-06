# 7-word-probe: every live line with >= 6 words must appear in index.html + main.js text.
import re,html,sys,json
live=[l.strip() for l in open('research/live_site_text.txt',encoding='utf-8')]
hay=html.unescape(open('site/index.html',encoding='utf-8').read()+open('site/js/main.js',encoding='utf-8').read())
hay=hay.replace('\\/','/').replace("\\'","'").replace('\\"','"')
norm=lambda s: re.sub(r'\s+',' ',s.replace('’',"'").replace(' ',' ')).strip().lower()
H=norm(hay)
skip=re.compile(r'^GTM People — Specialist SaaS GTM Recruitment Agency|Hold Ctrl / Cmd|cookie|Accept analytics|Reject non-essential',re.I)
miss=[]; checked=0
for l in live:
    if len(l.split())<6 or skip.search(l): continue
    checked+=1
    if norm(l) not in H: miss.append(l)
print(json.dumps({'checked':checked,'missing':len(miss),'lines':miss},ensure_ascii=False,indent=1))
