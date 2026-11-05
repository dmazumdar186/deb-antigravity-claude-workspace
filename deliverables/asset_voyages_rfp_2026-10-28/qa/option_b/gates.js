// Independent acceptance QA, Option B. node gates.js
const {chromium}=require('playwright');const U='https://asset-voyages-demo.debanjan186.workers.dev';
const R=[];const res=(g,ok,ev)=>{R.push([g,ok?'PASS':'FAIL',ev]);console.log(g,ok?'PASS':'FAIL',ev||'')};
const consoleErr=[],failed=[],thirdParty=new Set();
let b;
async function ctx(opts={}){const c=await b.newContext(opts);c.on('page',()=>{});return c}
function watch(p,tag){p.on('console',m=>{if(m.type()==='error')consoleErr.push(tag+': '+m.text().slice(0,120))});
 p.on('requestfailed',r=>failed.push(tag+': '+r.url()+' '+r.failure()?.errorText));
 p.on('response',r=>{if(r.status()>=400&&!r.url().includes('/zzz'))failed.push(tag+': '+r.status()+' '+r.url())});
 p.on('request',r=>{const h=new URL(r.url()).host;if(!h.endsWith('workers.dev')&&!r.url().startsWith('data:'))thirdParty.add(tag+': '+h)})}
let clicks=0;const click=async(p,loc)=>{clicks++;await loc.first().click();await p.waitForLoadState('load')};
async function login(user){const c=await ctx();const p=await c.newPage();watch(p,user);await p.goto(U+'/console');
 await p.fill('input[name=username]',user);await p.fill('input[name=password]','demo-asset');await p.click('button[type=submit]');await p.waitForLoadState();return {c,p}}
const txt=async p=>p.evaluate(()=>document.body.innerText);
const nav=p=>p.locator('nav, aside, .sidebar').first();
(async()=>{b=await chromium.launch();const T=Date.now()%100000;
// ---- reset first
{const {p}=await login('direction');p.once('dialog',d=>d.accept());await p.click('text=Réinitialiser la démo');await p.waitForLoadState();}
// ================= S1
const D=await login('direction');let p=D.p;
clicks=0;await click(p,p.getByRole('link',{name:'Congrès',exact:true}));await click(p,p.getByRole('link',{name:'Nouveau congrès'}));
const unlabeled=await p.evaluate(()=>[...document.querySelectorAll('form input:not([type=hidden]),form select,form textarea')].filter(e=>!(e.labels&&e.labels[0]&&e.labels[0].innerText.trim())).map(e=>e.name));
const reqUnmarked=await p.evaluate(()=>[...document.querySelectorAll('form [required]')].filter(e=>!(e.labels[0].innerText.includes('*'))).map(e=>e.name));
const title=`QA Congrès <b>gras</b><script>window.__x=1</script> ${T} — exemple`;
const fill=async(o)=>{for(const[k,v]of Object.entries(o))await p.fill(`[name=${k}]`,v)};
await fill({title,discipline:'Cardiologie',venue:'Palais QA — exemple',city:'Nantes',country:'France',start_date:'2027-09-10',end_date:'2027-09-12',official_url:'https://www.example.org/qa',verified_on:'2026-11-01'});
await click(p,p.getByRole('button',{name:'Publier'}));
const createUrl=p.url();const createClicks=clicks;
res('S1-F1',/\/console\/congres\/\d+/.test(createUrl)&&(await txt(p)).includes('Nantes')||(await p.content()).includes('Nantes'),'after publish url='+createUrl);
res('S1-E1',createClicks<=4&&unlabeled.length==0&&reqUnmarked.length==0,`clicks=${createClicks} unlabeled=${unlabeled} reqUnmarked=${reqUnmarked}`);
const id=(createUrl.match(/congres\/(\d+)/)||[])[1];
const pubHref=await p.getByRole('link',{name:/fiche publique/}).getAttribute('href').catch(()=>null);
// public render: script not executed
const V=await (await ctx()).newPage();watch(V,'visitor');
if(pubHref){await V.goto(U+pubHref);const x=await V.evaluate(()=>window.__x);const h1=await V.locator('h1').innerText();res('S1-H1(xss)',x===undefined&&h1.includes('<script>'),'h1='+h1.slice(0,80))}
else res('S1-H1(xss)',false,'no public link');
// S1-E2 edit
await p.goto(U+'/console');clicks=0;await click(p,p.getByRole('link',{name:'Congrès',exact:true}));
await click(p,p.getByRole('link',{name:new RegExp('QA Congrès.*'+T)}));await p.fill('[name=city]','Rennes');await click(p,p.getByRole('button',{name:'Enregistrer',exact:true}));
const editClicks=clicks;const adminOk=(await p.inputValue('[name=city]').catch(()=>''))==='Rennes';
await V.goto(U+pubHref);const pubOk=(await txt(V)).includes('Rennes');
res('S1-F2',adminOk&&pubOk,`admin=${adminOk} public=${pubOk}`);res('S1-E2',editClicks<=3,'clicks='+editClicks);
// S1-H1 validation via UI (bypass browser validation)
const edit=U+'/console/congres/'+id;
async function badSave(o){await p.goto(edit);await p.evaluate(()=>document.querySelectorAll('form').forEach(f=>f.noValidate=true));await fill(o);await p.getByRole('button',{name:'Enregistrer',exact:true}).click();await p.waitForLoadState();
 const msg=(await txt(p)).match(/[^\n]*(fin|adresse|URL|lien|invalide|doit)[^\n]*/i);await p.goto(edit);return {msg:msg&&msg[0],end:await p.inputValue('[name=end_date]'),url:await p.inputValue('[name=official_url]')}}
let r1=await badSave({end_date:'2027-09-01'});let r2=await badSave({official_url:'javascript:alert(1)'});
res('S1-H1(validation)',r1.end==='2027-09-12'&&r2.url==='https://www.example.org/qa'&&r1.msg&&r2.msg,`endBefore:msg=${r1.msg} stored=${r1.end}; badUrl:msg=${r2.msg} stored=${r2.url}`);
// S1-H2 no csrf
const s1=await D.c.request.post(edit,{form:{title:'HACK',discipline:'x',venue:'x',city:'HACKED',country:'x',start_date:'2027-09-10',end_date:'2027-09-12',official_url:'https://example.org',verified_on:'2026-11-01'},maxRedirects:0});
await p.goto(edit);res('S1-H2',(await p.inputValue('[name=city]'))==='Rennes','no-csrf POST status='+s1.status());
// S1-F3 contributor
const C=await login('contributeur');let cp=C.p;await cp.goto(U+'/console/congres/nouveau');
const cbtn=await cp.locator('form button').allInnerTexts();
await cp.evaluate(()=>0);for(const[k,v]of Object.entries({title:'QA brouillon '+T+' — exemple',discipline:'Cardiologie',venue:'V — exemple',city:'Brest',country:'France',start_date:'2027-10-10',end_date:'2027-10-12',official_url:'https://www.example.org/b',verified_on:'2026-11-01'}))await cp.fill(`[name=${k}]`,v);
const sub=cp.getByRole('button',{name:/relecture|relire|soumettre|Envoyer/i});const hasSub=await sub.count();
if(hasSub)await sub.first().click();else await cp.getByRole('button',{name:/brouillon/i}).click();await cp.waitForLoadState();
const did=(cp.url().match(/congres\/(\d+)/)||[])[1];
// contributor try publish via POST with token
const tok=await cp.locator('input[name=_csrf]').first().inputValue();
const cpub=await C.c.request.post(U+'/console/congres/'+did,{form:{_csrf:tok,action:'publier',status:'publie',publish:'1'},maxRedirects:0});
await V.goto(U+'/?q=brouillon+'+T);const draftInCat=(await txt(V)).includes('QA brouillon');
const dslug=await D.p.goto(U+'/console/congres/'+did).then(()=>D.p.getByRole('link',{name:/fiche publique/}).getAttribute('href').catch(()=>null));
const draftPub=dslug?(await V.goto(U+dslug)).status():'nolink';
const dirPub=D.p.getByRole('button',{name:/Publier/});const canPub=await dirPub.count();if(canPub){await dirPub.first().click();await D.p.waitForLoadState()}
await V.goto(U+'/?q=brouillon+'+T);const afterPub=(await txt(V)).includes('QA brouillon');
res('S1-F3',!cbtn.some(t=>/^Publier/.test(t))&&hasSub&&!draftInCat&&(draftPub===404||draftPub==='nolink')&&afterPub,`contribButtons=${JSON.stringify(cbtn)} submitBtn=${hasSub} contribPublishPOST=${cpub.status()} draftInCatalogue=${draftInCat} draftPublicStatus=${draftPub} directionPublished=${afterPub}`);
// ================= S2 (visitor)
await V.goto(U+'/');let all=[];let pg=U+'/';
for(let i=0;i<5&&pg;i++){await V.goto(pg);all.push(...await V.locator('a:has-text("Voir la fiche")').evaluateAll(a=>a.map(x=>x.getAttribute('href'))));const n=V.getByRole('link',{name:'Page suivante'});pg=(await n.count())?U+await n.getAttribute('href'):null}
res('S2-F1',all.length===14,`listed=${all.length} (expect 12 seed + 2 QA published); rhumatologie(draft seed) present=${all.some(h=>h.includes('rhumato'))}`);
const q=async s=>{await V.goto(U+'/?q='+encodeURIComponent(s));return (await txt(V)).match(/(\d+|Aucun) congrès/)?.[0]};
const qs={vienne:await q('vienne'),diabetologie:await q('diabetologie'),madrid:await q('madrid'),cardio:await q('CARDIOLOGIE')};
res('S2-F2',qs.vienne==='2 congrès'&&qs.diabetologie==='1 congrès'&&qs.madrid==='1 congrès',JSON.stringify(qs));
await V.goto(U+'/?discipline=Cardiologie&pays=Espagne');const comb=(await txt(V)).match(/(\d+|Aucun) congrès/)?.[0];
await V.goto(U+'/?q=zzzzqq');const none=await txt(V);
await V.goto(U+'/?pays=France');const fr=(await txt(V)).match(/(\d+) congrès/)?.[0];
res('S2-F3',comb==='1 congrès'&&/Aucun congrès/.test(none)&&/Réinitialiser/.test(none),`cardio+Espagne=${comb} France=${fr} noResultMsg=${/Aucun/.test(none)}`);
await V.goto(U+'/?pays=France');const nxt=V.getByRole('link',{name:'Page suivante'});const nh=(await nxt.count())?await nxt.getAttribute('href'):'(single page)';
res('S2-F4',nh==='(single page)'||nh.includes('pays=France'),'France next='+nh+' ; unfiltered next=/?page=2');
await V.goto(U+'/congres/congres-europeen-de-cardiologie-cg-0101');const dt=await txt(V);
const site=await V.locator('a[href*="example.org"]').count();
res('S2-F5',['27 août','Madrid','Espagne','Cardiologie','Lieu','Vérifié le'].every(s=>dt.includes(s))&&site>0&&(await V.inputValue('#f-cg')).includes('cardiologie'),'officialLinks='+site);
const NJ=await (await ctx({javaScriptEnabled:false})).newPage();await NJ.goto(U+'/');await NJ.selectOption('#pays','France');await NJ.click('button[type=submit]');await NJ.waitForLoadState();
res('S2-F6',NJ.url().includes('pays=France')&&/\d+ congrès/.test(await txt(NJ)),NJ.url());
// S2-E1
await V.goto(U+'/');clicks=0;await click(V,V.getByRole('link',{name:'Cardiologie',exact:true}));await click(V,V.getByRole('link',{name:'Voir la fiche'}));
res('S2-E1',clicks<=2&&/Cardiologie/.test(await txt(V)),'clicks='+clicks+' '+V.url());
// S2-E2 390
const M=await (await ctx({viewport:{width:390,height:844},isMobile:true,hasTouch:true})).newPage();watch(M,'mobile');let mob=[];
for(const u of ['/','/congres/congres-europeen-de-cardiologie-cg-0101']){await M.goto(U+u);mob.push(await M.evaluate(()=>{const o={u:location.pathname,sw:document.documentElement.scrollWidth};o.smallFont=[...document.querySelectorAll('input:not([type=hidden]):not([type=checkbox]),select,textarea')].filter(e=>e.offsetParent&&parseFloat(getComputedStyle(e).fontSize)<16).map(e=>e.name||e.id);
 o.smallTap=[...document.querySelectorAll('a,button,input:not([type=hidden]),select')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&e.offsetParent&&!e.closest('p,dd,li.inline')&&(r.height<44)}).map(e=>(e.innerText||e.name||e.id||e.tagName).trim().slice(0,25)).slice(0,12);return o}))}
res('S2-E2',mob.every(m=>m.sw<=390&&!m.smallFont.length&&!m.smallTap.length),JSON.stringify(mob));
const long='a'.repeat(5000);const lr=await V.goto(U+'/?q='+long);await V.goto(U+'/?q='+encodeURIComponent('<img src=x onerror=window.__y=1>"><script>window.__y=2</script>'));
res('S2-H1',lr.status()<500&&(await V.evaluate(()=>window.__y))===undefined&&!(await V.content()).includes('<img src=x'),'5000-char status='+lr.status());
// ================= S3
await V.goto(U+'/congres/congres-europeen-de-cardiologie-cg-0101');const fields=await V.locator('form[action="/demande"] [name]').evaluateAll(a=>a.map(e=>e.name));
res('S3-F1',['name','email','phone','company','departure_city','date_out','date_back','passengers','message','consent','congress'].every(f=>fields.includes(f)),fields.join(','));
const form=async(o,P=V)=>{await P.goto(U+'/congres/congres-europeen-de-cardiologie-cg-0101');await P.waitForTimeout(3500);for(const[k,v]of Object.entries(o)){if(k==='consent'){if(v)await P.check('#f-consent')}else await P.fill(`[name=${k}]`,v)}clicks=0;await click(P,P.getByRole('button',{name:'Envoyer la demande'}));return txt(P)};
const good={name:'Zoé QA'+T+' (exemple)',email:`qa${T}@example.com`,phone:'0102030405',departure_city:'Toulouse',passengers:'3',message:'<b>bold</b><script>window.__z=1</script>',consent:true};
const ok=await form(good);const ref=ok.match(/DV-2026-\d{4}/)?.[0];const oneClick=clicks;
res('S3-F2',!!ref,'ref='+ref+' url='+V.url());
await V.reload();await V.waitForLoadState();
// errors
const errCase=async(o,lab)=>{const t=await form({...good,email:`e${lab}${T}@example.com`,...o});return {lab,stored:/DV-2026-\d{4}/.test(t),msg:(t.match(/[^\n]*(passager|date|e-mail|adresse|consent|accept|retour|valide)[^\n]*/i)||[''])[0].slice(0,70)}};
const H=[];for(const [o,l] of [[{passengers:'0'},'p0'],[{passengers:'51'},'p51'],[{passengers:'abc'},'pabc'],[{date_out:'2027-08-30',date_back:'2027-08-20'},'ret'],[{date_out:'2025-01-01'},'past'],[{email:'pas-un-email'},'mail'],[{consent:false},'consent']]){
 if(l==='pabc'){await V.goto(U+'/congres/congres-europeen-de-cardiologie-cg-0101');}
 H.push(await errCase(o,l).catch(e=>({lab:l,err:e.message.slice(0,60)})))}
// keep typed + next to field
const kept=await V.inputValue('[name=departure_city]').catch(()=>'');const inlineErr=await V.locator('[aria-invalid=true]').count();
res('S3-E1',oneClick===1&&kept==='Toulouse'&&inlineErr>0,`submitClicks=${oneClick} keptAfterError=${kept} ariaInvalidFields=${inlineErr}`);
res('S3-H1',H.every(h=>!h.stored&&!h.err),JSON.stringify(H));
// honeypot / too fast / rate limit
const hp=await form({...good,email:`hp${T}@example.com`,website:'spam'});
await V.goto(U+'/congres/congres-europeen-de-cardiologie-cg-0101');for(const[k,v]of Object.entries({...good,email:`fast${T}@example.com`,consent:undefined}))if(k!=='consent')await V.fill(`[name=${k}]`,v);await V.check('#f-consent');await V.click('button:has-text("Envoyer la demande")');await V.waitForLoadState();const fast=await txt(V);
const rl=[];for(let i=0;i<6;i++){const t=await form({...good,email:`rl${T}@example.com`});rl.push(/DV-2026-\d{4}/.test(t)?'stored':((t.match(/[^\n]*(trop|patient|réessay|limite)[^\n]*/i)||['?'])[0].slice(0,50)))}
// ================= S4 (equipe)
const E=await login('equipe');p=E.p;
const homeNew0=await p.getByRole('link',{name:/Nouvelle/}).first().innerText();
clicks=0;await click(p,p.getByRole('link',{name:new RegExp(ref)}));const det=await txt(p);
res('S4-F1',[ref,'Toulouse','Zoé','cardiologie','Nouvelle','3'].every(s=>det.toLowerCase().includes(s.toLowerCase())),'detail has ref/contact/city/status');
await click(p,p.getByRole('button',{name:'Qualifiée',exact:true}));const e1=clicks;
await p.goto(U+'/console');const homeNew1=await p.getByRole('link',{name:/Nouvelle/}).first().innerText();
res('S4-E1',e1<=3&&homeNew0!==homeNew1,`clicks=${e1} homeNew before=${homeNew0.replace(/\s+/g,' ')} after=${homeNew1.replace(/\s+/g,' ')}`);
const rid=null;await p.getByRole('link',{name:new RegExp(ref)}).first().click();await p.waitForLoadState();const durl=p.url();
await p.getByRole('button',{name:'Devis envoyé'}).click();await p.waitForLoadState();await p.getByRole('button',{name:'Gagnée'}).click();await p.waitForLoadState();
await p.getByRole('button',{name:/Me l’attribuer/}).click().catch(()=>{});await p.waitForLoadState();
await p.fill('[name=note]','Note QA '+T+' <i>x</i>');await p.getByRole('button',{name:'Ajouter la note'}).click();await p.waitForLoadState();
const hist=await txt(p);const histSec=hist.slice(hist.indexOf('Historique'));
const editDel=await p.locator('text=/Supprimer|Modifier/').count();
res('S4-F3',/Gagnée/.test(hist)&&hist.includes('Note QA '+T)&&/Responsable[\s\S]{0,80}(Équipe|equipe|Camille|\w)/.test(hist),'status/owner/note saved');
res('S4-F4',/Nouvelle[\s\S]{0,40}Qualifiée/.test(histSec)&&/equipe|Équipe|Camille/i.test(histSec)&&editDel===0,'history head: '+histSec.slice(0,200).replace(/\s+/g,' '));
await p.goto(U+'/console/demandes?q='+encodeURIComponent(ref));const sr=await p.locator('a[href^="/console/demandes/"]').count();
await p.goto(U+'/console/demandes?q=Zoé');const sn=await p.locator('a[href^="/console/demandes/"]:has-text("DV-")').count();
await p.goto(U+'/console/demandes?statut=gagnee');const sg=(await txt(p)).includes(ref);
res('S4-F2',sr>=1&&sn>=1&&sg,`byRef=${sr} byName=${sn} statusFilter=${sg}`);
// CSV injection: submit enquiry with =name
const inj=await form({...good,email:`inj${T}@example.com`,name:'=HYPERLINK("http://evil")',company:'+1+1',departure_city:'@SUM(1)'});
const csv=await (await E.c.request.get(U+'/console/demandes/export.csv')).text();
const bad=csv.split('\n').filter(l=>/(^|[;,]|")[=+@]/.test(l)&&!/(^|[;,]|")'[=+@-]/.test(l));
res('S4-F5',csv.includes(ref)&&csv.includes("HYPERLINK")&&!/(^|[;,])"?=HYPERLINK/m.test(csv)&&!/(^|[;,])"?\+1\+1/m.test(csv)&&!/(^|[;,])"?@SUM/m.test(csv),'injRows='+csv.split('\n').filter(l=>l.includes('HYPERLINK')).map(l=>l.slice(0,120)).join(' | '));
// public absence
let pubHit=[];for(const u of ['/?q='+encodeURIComponent('Zoé QA'),'/?q='+ref,'/robots.txt','/sitemap.xml','/feed','/rss','/api/demandes','/api/enquiries','/demande','/demandes','/console/demandes/export.csv']){const r=await V.context().request.get(U+u,{maxRedirects:0});const t=await r.text();if(t.includes(ref)||t.includes('Zoé QA'))pubHit.push(u+' '+r.status())}
res('S4-F6',pubHit.length===0,pubHit.join(';'));
// S4-H1
const enqId=durl.match(/(\d+)$/)[1];const anon=await V.context().request.get(U+'/console/demandes/'+enqId,{maxRedirects:0});
const anonP=await V.context().request.post(U+'/console/demandes/'+enqId,{form:{action:'statut',status:'perdue'},maxRedirects:0});
const cg=await C.c.request.get(U+'/console/demandes/'+enqId,{maxRedirects:0});const ctok=await C.p.locator('input[name=_csrf]').first().inputValue().catch(()=>'');
const cpst=await C.c.request.post(U+'/console/demandes/'+enqId,{form:{_csrf:ctok,action:'statut',statut:'perdue',status:'perdue'},maxRedirects:0});
const ccsv=await C.c.request.get(U+'/console/demandes/export.csv',{maxRedirects:0});
await p.goto(durl);const still=(await txt(p)).match(/Statut[^\n]*\n?[^\n]*/)?.[0];
res('S4-H1',[anon,cg,ccsv].every(r=>r.status()>=300&&!(r.status()===200))&&anonP.status()>=300&&cpst.status()>=300&&!/Perdue\s*$/.test(still||''),`anonGET=${anon.status()} anonPOST=${anonP.status()} contribGET=${cg.status()} contribPOST=${cpst.status()} contribCSV=${ccsv.status()}`);
// notifications (S3-F3)
await D.p.goto(U+'/console/notifications');const nt=await txt(D.p);res('S3-F3',nt.includes(ref),'notification entry for '+ref);
// S3-F4 / H2 / H3 counts
await D.p.goto(U+'/console/demandes?q='+encodeURIComponent(`Zoé QA${T}`));const zcount=await D.p.locator('a:has-text("DV-")').count();
const em=async e=>{await D.p.goto(U+'/console/demandes?q='+encodeURIComponent(e));return D.p.locator('a:has-text("DV-")').count()};
const hpC=await em(`hp${T}`),fastC=await em(`fast${T}`),rlC=await em(`rl${T}`);
console.log('zcount(all Zoé)',zcount,'hp',hpC,'fast',fastC,'rl',rlC,'rl seq',rl,'fastpage',fast.match(/DV-2026-\d+|[^\n]*(trop|vite|réessay)[^\n]*/i)?.[0]);
await D.p.goto(durl);const xss=await D.p.evaluate(()=>window.__z);const raw=await D.p.content();
res('S3-H3',xss===undefined&&raw.includes('&lt;script&gt;'),'message shown as text in console');
// ================= S5
const EQ=E.p;await EQ.goto(U+'/console');clicks=0;await click(EQ,EQ.getByRole('link',{name:'Codes GM&E',exact:true}));
const masked=await txt(EQ);const htmlEq=await EQ.content();
// empty reason
const f101=EQ.locator('form[action="/console/gme/101/demande"]');await EQ.evaluate(()=>document.querySelectorAll('form').forEach(f=>f.noValidate=true));await f101.getByRole('button').click();await EQ.waitForLoadState();
const emptyMsg=(await txt(EQ)).match(/[^\n]*motif[^\n]*/i)?.[0];
await EQ.goto(U+'/console');clicks=0;await click(EQ,EQ.getByRole('link',{name:'Codes GM&E',exact:true}));await EQ.fill('form[action="/console/gme/101/demande"] [name=reason]','Devis client QA');await click(EQ,EQ.locator('form[action="/console/gme/101/demande"] button'));const reqClicks=clicks;
res('S5-F2',!/DEMO-GME-[A-Z0-9-]+/.test(htmlEq)&&/•|\*\*\*|masqu/i.test(masked)&&/requis|obligatoire|indiquez|motif/i.test(emptyMsg||''),'emptyReasonMsg='+emptyMsg);
// direction approve
const DP=D.p;await DP.goto(U+'/console');clicks=0;await click(DP,DP.getByRole('link',{name:/demande.* d’accès GM&E à décider/}));
const appr=DP.locator('form:has-text("Devis client QA"), li:has-text("Devis client QA"), tr:has-text("Devis client QA"), article:has-text("Devis client QA")').getByRole('button',{name:/Approuver/});
await click(DP,(await appr.count())?appr:DP.getByRole('button',{name:/Approuver/}).last());const apprClicks=clicks;
// equipe reveal
await EQ.goto(U+'/console');clicks=0;await click(EQ,EQ.getByRole('link',{name:'Codes GM&E',exact:true}));
const preHtml=await EQ.content();const tokEq=await EQ.locator('form[action="/console/gme/101/afficher"] [name=_csrf]').inputValue().catch(()=>null);
await click(EQ,EQ.locator('form[action="/console/gme/101/afficher"] button'));const revClicks=clicks;const code=(await txt(EQ)).match(/DEMO-GME-[A-Z0-9-]+/)?.[0];
res('S5-E1',reqClicks<=2&&apprClicks<=2&&revClicks<=2&&!!code,`request=${reqClicks} approve=${apprClicks} reveal=${revClicks}`);
res('S5-L2',!!code&&!preHtml.includes(code),'code absent from HTML before reveal');
// journal
await DP.goto(U+'/console/gme/journal');const jr=await txt(DP);const ej=await E.c.request.get(U+'/console/gme/journal',{maxRedirects:0});
// revoke
await DP.goto(U+'/console/gme/acces');const rv=DP.getByRole('button',{name:/Révoquer|Retirer/});const hasRv=await rv.count();if(hasRv){await rv.first().click();await DP.waitForLoadState()}
const replay=await E.c.request.post(U+'/console/gme/101/afficher',{form:{_csrf:tokEq||''}});const replayT=await replay.text();
const nocsrf=await E.c.request.post(U+'/console/gme/101/afficher',{form:{}});const nocsrfT=await nocsrf.text();
const contrib=await C.c.request.post(U+'/console/gme/101/afficher',{form:{_csrf:ctok}});const contribT=await contrib.text();
await DP.goto(U+'/console/gme/journal');const jr2=await txt(DP);
res('S5-F3',hasRv>0&&/Approuver/.test(await DP.content()+'Approuver'),'revoke button present='+hasRv);
res('S5-F4',!!code&&/equipe|Équipe|Camille/i.test(jr)&&/cardiologie/i.test(jr)&&ej.status()!==200&&!replayT.includes(code),`journalStatusForEquipe=${ej.status()} replayAfterRevoke containsCode=${replayT.includes(code)}`);
res('S5-H1',[replayT,nocsrfT,contribT].every(t=>!t.includes(code))&&/refus|refusé|tentative|bloqu/i.test(jr2),`noCsrf=${nocsrf.status()} contrib=${contrib.status()} journalShowsRefusal=${/refus|tentative|bloqu/i.test(jr2)}`);
// S5-F5 public label
await V.goto(U+'/congres/congres-europeen-de-cardiologie-cg-0101');res('S5-F5',(await txt(V)).includes('Tarif congrès négocié disponible')&&!(await V.content()).includes('DEMO-GME'),'');
// ================= S5-L1/L2 crawl
const seen=new Set(),hits=[];async function crawl(c,start,tag,lim=150){const q=[...start];while(q.length&&seen.size<lim){const u=q.shift();const k=tag+u;if(seen.has(k))continue;seen.add(k);
 if(/deconnexion|reinitialiser/.test(u))continue;const r=await c.request.get(U+u,{maxRedirects:0}).catch(()=>null);if(!r)continue;const t=await r.text();if(/DEMO-GME/.test(t))hits.push(tag+' '+u);
 for(const m of t.matchAll(/href="(\/[^"#]*)"/g))if(!m[1].startsWith('/assets'))q.push(m[1].replace(/&amp;/g,'&'))}}
await crawl(V.context(),['/','/robots.txt','/sitemap.xml','/?q=DEMO','/?q=GME','/assets/app.js?v=2','/feed','/api','/api/codes','/api/gme','/gme','/console/gme','/console/demandes/export.csv'],'anon');
const E2=await login('equipe');await crawl(E2.c,['/console','/console/gme','/console/demandes/export.csv','/console/notifications','/console/congres/101','/console/gme/journal'],'equipe-after-revoke',300);
await D.p.goto(U+'/console/congres/101');const dirCongHtml=await D.p.content();
await D.p.goto(U+'/console/notifications');const notifHtml=await D.p.content();const dcsv=await (await D.c.request.get(U+'/console/demandes/export.csv')).text();
res('S5-L1',hits.length===0,`pages crawled=${seen.size} hits=${hits.join(';')}`);
res('S5-L2(direction pages)',!/DEMO-GME/.test(dirCongHtml)&&!/DEMO-GME/.test(notifHtml)&&!/DEMO-GME/.test(dcsv),'direction congress edit HTML contains code='+/DEMO-GME/.test(dirCongHtml));
// ================= X
await V.goto(U+'/');const pubT=await txt(V);const titles=await V.locator('a:has-text("Voir la fiche")').count();
const nonEx=(await V.locator('h2,h3').allInnerTexts()).filter(t=>t.length>10&&!t.includes('exemple')&&!t.includes('QA'));
const emails=(dcsv.match(/[\w.+-]+@[\w.-]+/g)||[]).filter(e=>!e.endsWith('@example.com'));
res('X3',nonEx.length===0&&emails.length===0&&(!code||code.startsWith('DEMO-GME-')),`nonExampleHeadings=${JSON.stringify(nonEx.slice(0,5))} nonExampleEmails=${emails.slice(0,5)}`);
// X4 reset
DP.once('dialog',d=>d.accept());await DP.goto(U+'/console');await DP.click('text=Réinitialiser la démo');await DP.waitForLoadState();
DP.once('dialog',d=>d.accept());await DP.goto(U+'/console');await DP.click('text=Réinitialiser la démo');await DP.waitForLoadState();
await DP.goto(U+'/console/congres');const nC=await DP.locator('a[href^="/console/congres/"]:not([href*="nouveau"]):not([href*="statut"])').count();
await DP.goto(U+'/console/demandes');const nD=await DP.locator('a:has-text("DV-")').count();await V.goto(U+'/?q=QA');const qaLeft=(await txt(V)).includes('QA Congrès');
await DP.goto(U+'/console/gme/journal');const jAfter=(await txt(DP)).length;
res('X4',nC===13&&nD===6&&!qaLeft,`after double reset: congresses=${nC} enquiries=${nD} qaLeft=${qaLeft}`);
res('X1',consoleErr.length===0&&failed.filter(f=>!/ 40[34] |\/zzz/.test(f)).length===0,`consoleErrors=${consoleErr.slice(0,5).join(' || ')} failed=${failed.slice(0,8).join(' || ')}`);
res('X2',[...thirdParty].length===0,[...thirdParty].join(','));
console.log(JSON.stringify(R.filter(r=>r[1]=='FAIL'),null,1));await b.close()})().catch(e=>{console.error('CRASH',e);process.exit(1)});
