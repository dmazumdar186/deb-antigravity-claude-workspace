import { chromium, B, ctx } from './lib.mjs';
import fs from 'node:fs';
const W=+(process.argv[2]||1440); const br=await chromium.launch(); const out=[]; const noFocus=new Map();
const info=()=>{const e=document.activeElement; if(!e||e===document.body) return null; const cs=getComputedStyle(e); const r=e.getBoundingClientRect();
  const name=(e.labels&&e.labels[0]?e.labels[0].innerText:'')||e.getAttribute('aria-label')||e.innerText||e.value||'';
  const vis=(cs.outlineStyle!=='none'&&parseFloat(cs.outlineWidth)>0)||(cs.boxShadow&&cs.boxShadow!=='none');
  const inView=r.bottom>0&&r.top<innerHeight&&r.width>0;
  return {tag:e.tagName,type:e.type||'',name:name.replace(/\s+/g,' ').trim().slice(0,60),vis,inView,outline:cs.outlineStyle+' '+cs.outlineWidth+' '+cs.outlineColor};};
async function tabTo(p,re,max=150){ for(let i=0;i<max;i++){ await p.keyboard.press('Tab'); let f; try{ f=await p.evaluate(info);}catch{ await p.waitForLoadState('load'); f=await p.evaluate(info);} if(!f) continue; if(!f.vis||!f.inView) noFocus.set(p.url().replace(B,'').replace(/\d+/g,'N')+' :: '+f.tag+' '+f.name, f.outline+(f.inView?'':' OFFSCREEN')); if(re.test(f.name)) return {f,tabs:i+1}; } throw new Error('not reached by Tab: '+re+' on '+p.url()); }
async function type(p,re,txt){ await tabTo(p,re); await p.keyboard.type(txt); }
async function act(p,re,key='Enter'){ const r=await tabTo(p,re); const u=p.url(); await p.keyboard.press(key); await p.waitForTimeout(700); await p.waitForLoadState('load'); await p.locator('body').waitFor(); return r; }
async function selType(p,re,txt){ await tabTo(p,re); await p.keyboard.type(txt); }
async function kbLogin(p,who){ await p.goto(B+'/console/connexion'); await type(p,/Identifiant/,who); await type(p,/Mot de passe/,'demo-asset'); await act(p,/Se connecter/); }
async function kbLogout(p){ await p.goto(B+'/console'); await act(p,/Se déconnecter/); }
const res=async(story,fn)=>{ const {c,p}=await ctx(br,W); try{ const note=await fn(p); out.push({story,W,pass:true,note}); }catch(e){ out.push({story,W,pass:false,note:e.message.split('\n')[0]}); await p.screenshot({path:`evidence/kb-${W}-${story}.png`}); } await c.close(); };
const T=Date.now()%100000;
// skip link
await res('skip-link',async p=>{ await p.goto(B+'/'); await p.keyboard.press('Tab'); const f=await p.evaluate(info); await p.keyboard.press('Enter'); const after=await p.evaluate(()=>document.activeElement?.tagName+'#'+document.activeElement?.id); await p.keyboard.press('Tab'); const next=await p.evaluate(info); return `first Tab: ${f?.name} (vis ${f?.vis}); Enter → ${after}; next Tab → ${next?.name}`; });
await res('S1',async p=>{ await kbLogin(p,'direction'); await act(p,/^Congrès$/); await act(p,/^Nouveau congrès/);
  await type(p,/^Titre/,`Clavier ${T} — exemple`); await selType(p,/^Discipline/,'Card'); await type(p,/^Lieu/,'Salle — exemple'); await type(p,/^Ville/,'Nice'); await selType(p,/^Pays/,'Fran');
  await type(p,/Date de début/,'10062027'); await type(p,/Date de fin/,'12062027'); await type(p,/Site officiel/,'https://www.example.org/kb'); await type(p,/Vérifié le/,'01112026');
  await act(p,/^Publier/); const t=await p.locator('body').innerText(); if(!/Congrès créé/.test(t)) throw new Error('no « Congrès créé »: '+t.match(/[^\n]*(corriger|erreur)[^\n]*/i)?.[0]);
  // edit
  await p.goto(B+'/console'); await act(p,/^Congrès$/); await act(p,new RegExp(`Clavier ${T}`)); await tabTo(p,/^Ville/); await p.keyboard.press('Control+A'); await p.keyboard.type('Nantes'); await act(p,/^Enregistrer$/);
  const t2=await p.locator('body').innerText(); if(!/Modifications enregistrées/.test(t2)) throw new Error('edit not saved'); return 'create+publish+edit by keyboard'; });
await res('S2',async p=>{ await p.goto(B+'/'); await act(p,/^Cardiologie$/); const r=await act(p,/\d{4}.*cardiologie/i); const h=await p.locator('h1').innerText(); if(!/cardiologie/i.test(h)) throw new Error('h1 '+h); 
  await p.goto(B+'/'); await type(p,/^Recherche/,'vienne'); await act(p,/^Rechercher$/); const n=(await p.locator('body').innerText()).match(/\d+ congrès/)?.[0]; return `filter+open; search vienne → ${n}; tabs to first result ${r.tabs}`; });
await res('S3',async p=>{ await p.goto(B+'/congres/journees-d-oncologie-digestive-cg-0112'); const t0=Date.now();
  await type(p,/^Nom et prénom/,'Clavier (exemple)'); await type(p,/^E-mail/,'kb@example.com'); await type(p,/^Téléphone/,'0123456789'); await type(p,/^Ville de départ/,'Lyon');
  await type(p,/^Date aller/,'27012027'); await type(p,/^Date retour/,'31012027'); await tabTo(p,/^Passagers/); await p.keyboard.press('Control+A'); await p.keyboard.type('3');
  await tabTo(p,/J’accepte/); await p.keyboard.press('Space'); await p.waitForTimeout(Math.max(0,3300-(Date.now()-t0)));
  await tabTo(p,/Envoyer la demande/); await Promise.all([p.waitForURL(u=>!u.pathname.startsWith('/congres/')||u.search!==''||true,{waitUntil:'load'}),p.keyboard.press('Enter')]); await p.waitForTimeout(1500); console.log('S3 url',p.url()); const t=await p.locator('body').innerText(); const ref=t.match(/DV-2026-\d{4}/)?.[0]; if(!ref) throw new Error('no ref: '+t.slice(0,300)); return ref; });
await res('S4',async p=>{ await kbLogin(p,'equipe'); await act(p,/DV-2026-0006/); await act(p,/^Qualifiée$/); const t=await p.locator('body').innerText(); if(!/Enregistré/.test(t)) throw new Error('status not saved');
  await tabTo(p,/^Attribuer à/); await p.keyboard.press('ArrowDown'); await act(p,/^Attribuer$/); await type(p,/Visible uniquement/,'Note clavier'); await act(p,/Ajouter la note/); const t2=await p.locator('body').innerText(); return 'status+assign+note; note shown: '+/Note clavier/.test(t2); });
await res('S5',async p=>{ await kbLogin(p,'equipe'); await act(p,/^Codes/); await type(p,/Motif/,'Devis client clavier'); await act(p,/Demander l’accès/); if(!/Demande envoyée/.test(await p.locator('body').innerText())) throw new Error('request not sent');
  await kbLogout(p); await kbLogin(p,'direction'); await act(p,/demandes? d’accès GM&E à décider/); await act(p,/Approuver pour 24 h/); 
  await kbLogout(p); await kbLogin(p,'equipe'); await act(p,/^Codes/); await act(p,/Afficher le code/); const t=await p.locator('body').innerText(); const code=t.match(/DEMO-GME-\d{4}/)?.[0]; if(!code) throw new Error('no reveal');
  await act(p,/Masquer le code/); return 'request→approve→reveal→hide by keyboard'; });
await br.close(); const nf=[...noFocus].map(([k,v])=>k+' -> '+v);
fs.writeFileSync(`kb-${W}.json`,JSON.stringify({out,noFocus:nf},null,1)); console.log(JSON.stringify(out,null,1)); console.log('focus not visible / offscreen:',nf.length); console.log(nf.slice(0,40).join('\n'));
