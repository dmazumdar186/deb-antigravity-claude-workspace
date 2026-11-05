import { chromium, B, ctx, login, logout } from './lib.mjs';
import fs from 'node:fs';
const W=+(process.argv[2]||1440); const out=[]; const br=await chromium.launch();
function counter(p){ let n=0; const log=[]; return { click: async (loc, what)=>{ await loc.click(); n++; log.push(what); await p.waitForLoadState(); }, get n(){return n}, log }; }
async function shot(p,name){ await p.screenshot({path:`evidence/${W}-${name}.png`, fullPage:false}); }
fs.mkdirSync('evidence',{recursive:true});
const rec=(gate,budget,k,ok,note='')=>{ out.push({gate,budget,clicks:k.n,path:k.log.join(' → '),ok:ok&&k.n<=budget,note}); };
const nav=(p,name)=>p.getByRole('navigation').getByRole('link',{name:new RegExp('^'+name)}).first();
const menuBtn=async p=>{ const m=p.getByRole('button',{name:/menu/i}); return (await m.count()) && await m.first().isVisible() ? m.first() : null; };
const navClick=async(p,k,name)=>{ const mb=await menuBtn(p); if(mb){ await k.click(mb,'Menu'); } await k.click(nav(p,name),name); };
const T=Date.now()%100000;
// S1-E1 direction create+publish
{ const {c,p}=await ctx(br,W); await login(p,'direction'); const k=counter(p);
  await navClick(p,k,'Congrès'); await k.click(p.getByRole('link',{name:'Nouveau congrès'}).first(),'Nouveau congrès');
  await p.getByLabel('Titre').fill(`Congrès UX ${T} — exemple`);
  await p.getByLabel('Discipline',{exact:false}).first().selectOption({label:'Cardiologie'});
  await p.getByLabel('Lieu').fill('Palais — exemple'); await p.getByLabel('Ville').fill('Lyon');
  await p.getByLabel('Pays',{exact:false}).first().selectOption({label:'France'});
  await p.getByLabel('Date de début').fill('2027-06-10'); await p.getByLabel('Date de fin').fill('2027-06-12');
  await p.getByLabel('Site officiel').fill('https://www.example.org/ux'); await p.getByLabel('Vérifié le').fill('2026-11-01');
  await k.click(p.getByRole('button',{name:'Publier'}),'Publier'); const msg=await p.locator('body').innerText();
  await shot(p,'S1-E1'); rec('S1-E1',4,k,/Congrès créé/.test(msg),'2 dropdown choices (Discipline, Pays) counted as filling');
  // S1-E2 edit
  await p.goto(B+'/console'); const k2=counter(p); await navClick(p,k2,'Congrès');
  await k2.click(p.getByRole('link',{name:`Congrès UX ${T} — exemple`}),'congress title');
  await p.getByLabel('Ville').fill('Marseille'); await k2.click(p.getByRole('button',{name:'Enregistrer',exact:true}),'Enregistrer');
  const m2=await p.locator('body').innerText(); await shot(p,'S1-E2'); rec('S1-E2',3,k2,/enregistr/i.test(m2));
  // S5 direction later; close
  await c.close(); }
// S1 contributeur draft/submit
{ const {c,p}=await ctx(br,W); await login(p,'contributeur'); const k=counter(p);
  await k.click(p.getByRole('main').getByRole('link',{name:'Nouveau congrès'}),'Nouveau congrès (home)');
  await p.getByLabel('Titre').fill(`Brouillon UX ${T} — exemple`);
  await p.getByLabel('Discipline',{exact:false}).first().selectOption({label:'Cardiologie'});
  await p.getByLabel('Lieu').fill('Palais — exemple'); await p.getByLabel('Ville').fill('Lyon');
  await p.getByLabel('Pays',{exact:false}).first().selectOption({label:'France'});
  await p.getByLabel('Date de début').fill('2027-06-10'); await p.getByLabel('Date de fin').fill('2027-06-12');
  await p.getByLabel('Site officiel').fill('https://www.example.org/ux'); await p.getByLabel('Vérifié le').fill('2026-11-01');
  await k.click(p.getByRole('button',{name:'Soumettre à relecture'}),'Soumettre à relecture');
  const m=await p.locator('body').innerText(); await shot(p,'S1-contrib'); rec('S1-contrib (info)',4,k,/relecture|relire|soumis/i.test(m), m.match(/[^\n]*(soumis|relecture)[^\n]*/i)?.[0]||''); await c.close(); }
// S2-E1
{ const {c,p}=await ctx(br,W); await p.goto(B+'/'); const k=counter(p);
  const filt=p.getByRole('link',{name:'Cardiologie',exact:true}); 
  if(!(await filt.isVisible())){ const s=p.getByText(/Discipline|Filtres/).first(); await k.click(s,'open filters'); }
  await k.click(filt,'Cardiologie'); const n=await p.locator('body').innerText(); const cnt=n.match(/\d+ congrès/)?.[0];
  await k.click(p.getByRole('main').getByRole('link',{name:/cardiologie.*exemple/i}).first(),'open first result');
  await shot(p,'S2-E1'); rec('S2-E1',2,k,/cardiologie/i.test(await p.locator('h1').innerText()),`count shown: ${cnt}`);
  // S2-E2 checks at this width
  await p.goto(B+'/'); const g=await p.evaluate(()=>({hs:document.documentElement.scrollWidth>innerWidth, inputs:[...document.querySelectorAll('input,select')].filter(e=>e.offsetParent).map(e=>parseFloat(getComputedStyle(e).fontSize)), small:[...document.querySelectorAll('a,button,input,select,summary')].filter(e=>e.offsetParent).map(e=>{const r=e.getBoundingClientRect();return {t:(e.innerText||e.name||'').trim().slice(0,30),h:Math.round(r.height),w:Math.round(r.width)}}).filter(r=>r.h<44&&r.h>0)}));
  out.push({gate:'S2-E2 geometry',W,...g, small:g.small.slice(0,15)}); await c.close(); }
// S3-E1 + error recovery
{ const {c,p}=await ctx(br,W); await p.goto(B+'/congres/journees-d-oncologie-digestive-cg-0112'); const t0=Date.now(); const k=counter(p);
  await p.getByLabel('Nom et prénom').fill('Testeur UX (exemple)'); await p.getByLabel('E-mail').fill('ux@example'); await p.getByLabel('Téléphone').fill('01 23 45 67 89');
  await p.getByLabel('Ville de départ').fill('Paris'); await p.getByLabel('Date aller').fill('2027-01-27'); await p.getByLabel('Date retour').fill('2027-01-31');
  await p.getByLabel('Passagers').fill('2'); await p.getByLabel(/J’accepte/).check();
  await p.waitForTimeout(Math.max(0,3200-(Date.now()-t0)));
  await k.click(p.getByRole('button',{name:'Envoyer la demande'}),'Envoyer (bad email)');
  const errText=await p.locator('body').innerText(); const kept=await p.getByLabel('Nom et prénom').inputValue(); const consentKept=await p.getByLabel(/J’accepte/).isChecked();
  const focused=await p.evaluate(()=>document.activeElement?.innerText?.slice(0,120)||document.activeElement?.tagName);
  await shot(p,'S3-error');
  out.push({gate:'S3-E1 error recovery', emailMsg: errText.match(/[^\n]*e-mail[^\n]*/gi)?.slice(0,3), kept, consentKept, focused});
  await p.getByLabel('E-mail').fill('ux@example.com'); await p.waitForTimeout(3200);
  const k2=counter(p); await k2.click(p.getByRole('button',{name:'Envoyer la demande'}),'Envoyer'); const conf=await p.locator('body').innerText();
  const ref=conf.match(/DV-2026-\d{4}/)?.[0]; await shot(p,'S3-E1'); rec('S3-E1',1,k2,!!ref,`ref ${ref}; consent kept after error: ${consentKept}`);
  // S4-E1 same browser → equipe sees own enquiry
  await login(p,'equipe'); const before=(await p.locator('main').innerText()).match(/(\d+)\s*Nouvelles?/)?.[1];
  const k3=counter(p); const newest=p.getByRole('main').getByRole('link',{name:/DV-2026-\d{4}/}).first(); const nt=await newest.innerText();
  await k3.click(newest,'newest enquiry'); await k3.click(p.getByRole('button',{name:'Qualifiée',exact:true}),'Qualifiée');
  const m=await p.locator('body').innerText(); await shot(p,'S4-E1');
  await p.goto(B+'/console'); const after=(await p.locator('main').innerText()).match(/(\d+)\s*Nouvelles?/)?.[1];
  rec('S4-E1',3,k3,nt.includes(ref||'@@'),`newest=${nt.replace(/\s+/g,' ')}; Nouvelles ${before}→${after}; msg: ${m.match(/[^\n]*(statut|enregistr)[^\n]*/i)?.[0]}`);
  await c.close(); }
// S5-E1
{ const {c,p}=await ctx(br,W); await login(p,'equipe'); let k=counter(p);
  await navClick(p,k,'Codes'); const form=p.locator('form').filter({has:p.getByRole('button',{name:'Demander l’accès'})}).first();
  await form.getByLabel(/Motif/).fill('Devis groupe pour un client (test UX)'); await k.click(form.getByRole('button',{name:'Demander l’accès'}),'Demander l’accès');
  const m1=await p.locator('body').innerText(); await shot(p,'S5-E1-request'); rec('S5-E1 equipe request',2,k,/envoy|attente/i.test(m1),m1.match(/[^\n]*(envoyée|attente)[^\n]*/i)?.[0]);
  await logout(p); await login(p,'direction'); k=counter(p);
  const todo=p.getByRole('main').getByRole('link',{name:/demandes? d’accès GM&E à décider/}); await k.click(todo,'À traiter: demande d’accès');
  const pend=await p.locator('main').innerText();
  await k.click(p.getByRole('button',{name:'Approuver pour 24 h'}).first(),'Approuver pour 24 h');
  const m2=await p.locator('body').innerText(); await shot(p,'S5-E1-approve'); rec('S5-E1 direction approve',2,k,/approuv|accord/i.test(m2),`first pending shown: ${pend.match(/Demandes en attente[\s\S]{0,160}/)?.[0]?.replace(/\s+/g,' ')}`);
  await logout(p); await login(p,'equipe'); k=counter(p);
  await navClick(p,k,'Codes'); await k.click(p.getByRole('button',{name:'Afficher le code'}).first(),'Afficher le code');
  const m3=await p.locator('body').innerText(); await shot(p,'S5-E1-reveal'); rec('S5-E1 equipe reveal',2,k,/DEMO-GME-\d{4}/.test(m3));
  out.push({gate:'console errors S5', errs:p.errs}); await c.close(); }
await br.close(); fs.writeFileSync(`usability-${W}.json`,JSON.stringify(out,null,1)); console.log(JSON.stringify(out,null,1));
