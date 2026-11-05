import { chromium, B, ctx, login, logout } from './lib.mjs';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';
const br=await chromium.launch(); const res=[];
async function scan(p,name,W){ const r=await new AxeBuilder({page:p}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa','best-practice']).analyze();
  for(const v of r.violations) res.push({W,screen:name,url:p.url().replace(B,''),id:v.id,impact:v.impact,n:v.nodes.length,help:v.help,targets:v.nodes.slice(0,3).map(x=>x.target.join(' ')),sum:v.nodes[0]?.failureSummary?.slice(0,200)});
  res.push({W,screen:name,ok:true,violations:r.violations.length,passes:r.passes.length,incomplete:r.incomplete.map(i=>i.id)}); }
for (const W of [1440,390]){
  const {c,p}=await ctx(br,W);
  await p.goto(B+'/'); await scan(p,'catalogue',W);
  await p.goto(B+'/?discipline=Cardiologie'); await scan(p,'catalogue-cardiologie',W);
  await p.goto(B+'/?q=zzzzqqq'); await scan(p,'catalogue-aucun-resultat',W);
  await p.goto(B+'/?page=2'); await scan(p,'catalogue-page2',W);
  await p.goto(B+'/congres/journees-d-oncologie-digestive-cg-0112'); await scan(p,'fiche',W);
  await p.getByLabel('Passagers').fill('0'); await p.getByRole('button',{name:'Envoyer la demande'}).click(); await p.waitForLoadState(); await scan(p,'fiche-erreurs',W);
  await p.goto(B+'/congres/journees-d-oncologie-digestive-cg-0112'); const t0=Date.now();
  await p.getByLabel('Nom et prénom').fill('Axe (exemple)'); await p.getByLabel('E-mail').fill('axe@example.com'); await p.getByLabel('Téléphone').fill('0123456789'); await p.getByLabel('Ville de départ').fill('Paris'); await p.getByLabel('Date aller').fill('2027-01-27'); await p.getByLabel('Date retour').fill('2027-01-31'); await p.getByLabel('Passagers').fill('1'); await p.getByLabel(/J’accepte/).check(); await p.waitForTimeout(3300);
  await p.getByRole('button',{name:'Envoyer la demande'}).click(); await p.waitForLoadState(); await scan(p,'confirmation',W);
  await p.goto(B+'/page-inexistante'); await scan(p,'404',W);
  await p.goto(B+'/console/connexion'); await scan(p,'connexion',W);
  await p.getByLabel('Identifiant').fill('equipe'); await p.getByLabel('Mot de passe').fill('faux'); await p.getByRole('button',{name:'Se connecter'}).click(); await p.waitForLoadState(); await scan(p,'connexion-erreur',W);
  for (const [who,urls] of [['equipe',['/console','/console/demandes','/console/demandes?statut=nouvelle','/console/demandes/1','/console/notifications','/console/gme','/console/congres','/console/congres/101']],['direction',['/console','/console/gme','/console/gme/acces','/console/gme/journal','/console/congres','/console/congres/nouveau','/console/congres/101','/console/listes']],['contributeur',['/console','/console/congres','/console/congres/nouveau']]]){
    await login(p,who); for(const u of urls){ await p.goto(B+u); await scan(p,`${who} ${u}`,W);} 
    if(who==='direction'){ await p.goto(B+'/console/gme'); const b=p.getByRole('button',{name:'Afficher le code'}).first(); if(await b.count()){await b.click(); await p.waitForLoadState(); await scan(p,'direction gme code affiché',W);} }
    await logout(p); }
  await c.close(); }
await br.close(); fs.writeFileSync('axe.json',JSON.stringify(res,null,1));
const v=res.filter(r=>!r.ok); console.log('screens',res.filter(r=>r.ok).length,'violations',v.length);
const by={}; for(const x of v){ const k=x.id+'|'+x.impact; (by[k]??=[]).push(`${x.W} ${x.screen} (${x.n}) ${x.targets[0]}`);} for(const k in by) console.log('\n'+k+' '+v.find(x=>x.id===k.split('|')[0]).help+'\n  '+by[k].slice(0,8).join('\n  ')+(by[k].length>8?`\n  …+${by[k].length-8}`:''));
const inc=new Set(res.filter(r=>r.ok).flatMap(r=>r.incomplete)); console.log('incomplete ids:',[...inc]);
