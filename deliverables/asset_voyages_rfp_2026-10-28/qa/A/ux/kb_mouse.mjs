// Keyboard-only run of each story: Tab/Shift+Tab/Enter/Space/Arrow + typing. Records tab counts and focus visibility.
import fs from 'fs'; import { chromium, ctx, CODES } from './lib.mjs';
const R=[]; const br=await chromium.launch();
async function info(p){ return p.evaluate(()=>{ const e=document.activeElement; if(!e||e===document.body) return {d:'body'}; const cs=getComputedStyle(e); const vis=(cs.outlineStyle!=='none'&&parseFloat(cs.outlineWidth)>0)||cs.boxShadow!=='none';
  return { d:(e.tagName+'#'+(e.id||'')+' '+(e.innerText||e.value||e.getAttribute('aria-label')||e.name||'')).replace(/\s+/g,' ').slice(0,70), vis }; }); }
async function tabTo(p,re,max=150,story,label){ for(let i=1;i<=max;i++){ await p.keyboard.press('Tab'); const f=await info(p); if(re.test(f.d)){ R.push({story,label,tabs:i,focus:f.d,focusVisible:f.vis}); return f; } } R.push({story,label,tabs:'>'+max,focus:'NOT REACHED',focusVisible:null}); throw new Error('not reached '+label); }
async function kLogin(p,u,pw){ await p.goto('/wp-login.php'); await p.keyboard.press('Tab'); await p.locator('#user_login').focus(); await p.keyboard.type(u); await p.keyboard.press('Tab'); await p.keyboard.type(pw); await Promise.all([p.waitForURL(/wp-admin/,{timeout:120000}), p.keyboard.press('Enter')]); }
const ONLY=(process.env.ONLY||'S2+S3,S1,S4,S5').split(',');
const run=async(story,fn)=>{ if(!ONLY.includes(story)) return; try{ await fn(); R.push({story,label:'STORY RESULT',result:'PASS'}); }catch(e){ R.push({story,label:'STORY RESULT',result:'FAIL '+e.message.slice(0,150)}); if(globalThis.NET) console.log(globalThis.NET.slice(-25).join('\n')); } console.log(story, R.filter(r=>r.story===story).map(r=>`${r.label}:${r.tabs??''}${r.focusVisible===false?'(NO FOCUS RING)':''}${r.result??''}`).join(' | ')); };
// S2 + S3
await run('S2+S3', async()=>{ const {c,p}=await ctx(br); await p.goto('/');
  await tabTo(p,/A#.*Cardiologie$/,80,'S2+S3','chip Cardiologie'); await Promise.all([p.waitForNavigation({timeout:120000}),p.keyboard.press('Enter')]); await p.waitForTimeout(500);
  await tabTo(p,/^A#.* — exemple/,80,'S2+S3','first card link'); await Promise.all([p.waitForURL(/congres\//),p.keyboard.press('Enter')]);
  const fld=async(id,val,lbl)=>{ await tabTo(p,new RegExp('INPUT#asset-q-'+id+'|TEXTAREA#asset-q-'+id),15,'S2+S3',lbl); if(val) await p.keyboard.type(val); };
  await fld('nom','Clavier Seul','Nom et prénom'); await fld('email','clavier@example.com','E-mail'); await fld('telephone','+33 6 00 00 00 00','Téléphone'); await fld('ville_depart','Paris','Ville de départ');
  await fld('date_aller','08262027','Date aller'); await fld('date_retour','08302027','Date retour'); await fld('passagers','2','Nombre de passagers'); await fld('consentement','','consent checkbox');
  await p.keyboard.press('Space'); await p.waitForTimeout(3200);
  await tabTo(p,/Envoyer ma demande/,6,'S2+S3','Envoyer ma demande'); await Promise.all([p.waitForNavigation({timeout:120000}),p.keyboard.press('Enter')]); await p.waitForTimeout(800);
  const t=await p.locator('body').innerText(); const m=t.match(/DV-\d{4}-\d{4}/); if(!m){ const err=(t.match(/Merci de corriger[\s\S]{0,300}/)||['?'])[0]; throw new Error('no reference; '+err.replace(/\s+/g,' ')); } R.push({story:'S2+S3',label:'confirmation',focus:m[0]}); await c.close(); });
// S1
await run('S1', async()=>{ const {c,p}=await ctx(br); const net=[]; p.on('response',async r=>{ if(/admin-ajax/.test(r.url())&&r.request().method()==='POST'){ let t='';try{t=await r.text();}catch{} net.push('AJAX '+r.status()+' req='+decodeURIComponent(r.request().postData()||'').slice(0,90)+' RESP='+t.slice(0,160)); return; } if(/admin-ajax|post\.php|post-new/.test(r.url())) net.push(r.request().method()+' '+r.url().replace(/.*wp-admin\//,'').slice(0,50)+' '+r.status()+' body='+(r.request().postData()||'').length); }); p.on('requestfailed',r=>net.push('FAIL '+r.url().slice(-40)+' '+r.failure()?.errorText)); globalThis.NET=net; await kLogin(p,'direction','demo-asset');
  await tabTo(p,/^A#\S* Congrès$/,60,'S1','menu Congrès'); await Promise.all([p.waitForURL(/asset_congres/),p.keyboard.press('Enter')]);
  await tabTo(p,/A#.*Ajouter un congrès/,80,'S1','Ajouter un congrès'); await Promise.all([p.waitForURL(/post-new/),p.keyboard.press('Enter')]); await p.waitForTimeout(1500);
  await p.locator('#title').focus(); await p.keyboard.type('Congrès clavier — exemple');
  await tabTo(p,/asset-field-asset_start/,120,'S1','Date de début (from title)'); await p.keyboard.type('06142027');
  const f1=async(id,val,lbl)=>{ await tabTo(p,new RegExp('asset-field-asset_'+id),8,'S1',lbl); await p.keyboard.type(val); };
  await f1('end','06162027','Date de fin'); await f1('city','Lille','Ville'); await f1('pays','France','Pays'); await f1('discipline','Hépatologie','Discipline');
  await p.waitForFunction(()=>!document.querySelector('#publish')?.disabled && !(document.querySelector('#lost-connection-notice')?.offsetParent),null,{timeout:90000}); for(let i=1;i<=150;i++){ await p.keyboard.press('Shift+Tab'); const f=await info(p); if(/INPUT#publish/.test(f.d)){ R.push({story:'S1',label:'Publier (Shift+Tab from Discipline)',tabs:i,focus:f.d,focusVisible:f.vis}); break; } }
  R.push({story:'S1',label:'INVALID',focus:JSON.stringify(await p.evaluate(()=>[...document.querySelectorAll('#post input,#post select,#post textarea')].filter(e=>!e.checkValidity()).map(e=>e.id+'='+e.value+' :'+e.validationMessage)))}); R.push({story:'S1',label:'VALUES',focus:JSON.stringify(await p.evaluate(()=>['title','asset-field-asset_start','asset-field-asset_end','asset-field-asset_city','asset-field-asset_pays','asset-field-asset_discipline'].map(i=>i+'='+document.getElementById(i)?.value)))}); await p.locator('#publish').click({noWaitAfter:true}); R.push({story:'S1',label:'MOUSE click on Publier instead of Enter',focus:String(await p.locator('#lost-connection-notice').isVisible())});
  await p.waitForLoadState('load'); await p.waitForTimeout(4000); if(await p.locator('#lost-connection-notice').isVisible().catch(()=>false)){ R.push({story:'S1',label:'« Connexion perdue » after Publier; waited and pressed Enter on Publier again',focus:''}); await p.waitForFunction(()=>!document.querySelector('#publish')?.disabled && !(document.querySelector('#lost-connection-notice')?.offsetParent),null,{timeout:120000}); await p.locator('#publish').focus(); await Promise.all([p.waitForNavigation({timeout:120000}),p.keyboard.press('Enter')]); } await p.locator('#message').waitFor({timeout:60000}).catch(async e=>{ throw new Error('no notice; page says: '+(await p.locator('#wpbody-content .notice, .asset-save-errors').allInnerTexts()).join(' / ').slice(0,200)); }); R.push({story:'S1',label:'notice',focus:(await p.locator('#message').innerText()).slice(0,60)}); await c.close(); });
// S4
await run('S4', async()=>{ const {c,p}=await ctx(br); await kLogin(p,'equipe','demo-asset');
  await tabTo(p,/A#.*DV-2026-\d{4}/,80,'S4','Dernière demande link'); await Promise.all([p.waitForURL(/action=view/),p.keyboard.press('Enter')]);
  await tabTo(p,/SELECT#asset-statut/,120,'S4','Statut select'); await p.keyboard.press('ArrowDown');
  await tabTo(p,/Enregistrer/,10,'S4','Enregistrer'); await Promise.all([p.waitForNavigation({timeout:120000}),p.keyboard.press('Enter')]); await p.locator('.notice-success').waitFor(); await c.close(); });
// S5
await run('S5', async()=>{ const e=await ctx(br); await kLogin(e.p,'equipe','demo-asset');
  await tabTo(e.p,/A#.*Accès GM&E/,60,'S5','menu Accès GM&E'); await Promise.all([e.p.waitForURL(/asset-gme/),e.p.keyboard.press('Enter')]);
  await tabTo(e.p,/TEXTAREA/,60,'S5','first reason textarea'); await e.p.keyboard.type('Accès clavier (UAT).');
  await tabTo(e.p,/Demander l’accès/,4,'S5','Demander l’accès'); await Promise.all([e.p.waitForNavigation({timeout:120000}),e.p.keyboard.press('Enter')]); await e.p.locator('.notice-success').waitFor();
  const d=await ctx(br); await kLogin(d.p,'direction','demo-asset');
  await tabTo(d.p,/Approuver/,120,'S5','Approuver (24 h) in widget'); await Promise.all([d.p.waitForNavigation({timeout:120000}),d.p.keyboard.press('Enter')]); await d.p.locator('.notice-success').waitFor();
  await e.p.goto('/wp-admin/'); await tabTo(e.p,/A#.*Accès GM&E/,60,'S5','menu Accès GM&E (2)'); await Promise.all([e.p.waitForURL(/asset-gme/),e.p.keyboard.press('Enter')]);
  await tabTo(e.p,/Révéler/,80,'S5','Révéler le code'); await Promise.all([e.p.waitForNavigation({timeout:120000}),e.p.keyboard.press('Enter')]);
  const html=await e.p.content(); if(!CODES.some(k=>html.includes(k))) throw new Error('no code revealed');
  // revoke to restore
  await d.p.goto('/wp-admin/admin.php?page=asset-gme-acces'); const b=d.p.getByRole('button',{name:/Révoquer/}); if(await b.count()) { await b.first().focus(); await Promise.all([d.p.waitForNavigation({timeout:120000}),d.p.keyboard.press('Enter')]); }
  await e.c.close(); await d.c.close(); });
fs.writeFileSync(process.env.OUT||'kb-result.json',JSON.stringify(R,null,1)); await br.close();
