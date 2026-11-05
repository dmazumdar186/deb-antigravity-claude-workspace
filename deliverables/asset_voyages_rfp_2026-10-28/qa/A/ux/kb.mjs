// Keyboard-only run of each story: Tab/Shift+Tab/Enter/Space/Arrow + typing. Records tab counts and focus visibility.
import fs from 'fs'; import { chromium, ctx, CODES } from './lib.mjs';
const R=[]; const br=await chromium.launch();
async function info(p){ return p.evaluate(()=>{ const e=document.activeElement; if(!e||e===document.body) return {d:'body'}; const cs=getComputedStyle(e); const vis=(cs.outlineStyle!=='none'&&parseFloat(cs.outlineWidth)>0)||cs.boxShadow!=='none';
  return { d:(e.tagName+'#'+(e.id||'')+' '+(e.innerText||e.value||e.getAttribute('aria-label')||e.name||'')).replace(/\s+/g,' ').slice(0,70), vis }; }); }
async function tabTo(p,re,max=150,story,label){ for(let i=1;i<=max;i++){ await p.keyboard.press('Tab'); const f=await info(p); if(re.test(f.d)){ R.push({story,label,tabs:i,focus:f.d,focusVisible:f.vis}); return f; } } R.push({story,label,tabs:'>'+max,focus:'NOT REACHED',focusVisible:null}); throw new Error('not reached '+label); }
async function kLogin(p,u,pw){ await p.goto('/wp-login.php'); await p.keyboard.press('Tab'); await p.locator('#user_login').focus(); await p.keyboard.type(u); await p.keyboard.press('Tab'); await p.keyboard.type(pw); await Promise.all([p.waitForURL(/wp-admin/,{timeout:120000}), p.keyboard.press('Enter')]); }
const run=async(story,fn)=>{ try{ await fn(); R.push({story,label:'STORY RESULT',result:'PASS'}); }catch(e){ R.push({story,label:'STORY RESULT',result:'FAIL '+e.message.slice(0,150)}); } console.log(story, R.filter(r=>r.story===story).map(r=>`${r.label}:${r.tabs??''}${r.focusVisible===false?'(NO FOCUS RING)':''}${r.result??''}`).join(' | ')); };
// S2 + S3
await run('S2+S3', async()=>{ const {c,p}=await ctx(br); await p.goto('/');
  await tabTo(p,/A#.*Cardiologie$/,80,'S2+S3','chip Cardiologie'); await Promise.all([p.waitForLoadState('load'),p.keyboard.press('Enter')]); await p.waitForTimeout(500);
  await tabTo(p,/^A#.* — exemple/,80,'S2+S3','first card link'); await Promise.all([p.waitForURL(/congres\//),p.keyboard.press('Enter')]);
  await tabTo(p,/INPUT#\S*nom|Nom/i,120,'S2+S3','field Nom et prénom'); await p.keyboard.type('Clavier Seul');
  const vals=['clavier@example.com','+33 6 00 00 00 00','',"Paris"]; for(const v of vals){ await p.keyboard.press('Tab'); if(v) await p.keyboard.type(v); }
  const f=await info(p); // now on ville de départ presumably; continue: dates
  await p.keyboard.press('Tab'); await p.keyboard.type('26082027'); await p.keyboard.press('Tab'); await p.keyboard.type('30082027'); await p.keyboard.press('Tab'); await p.keyboard.type('2');
  await tabTo(p,/INPUT#.*(consent|rgpd)|checkbox/i,6,'S2+S3','consent checkbox').catch(async()=>{ await tabTo(p,/INPUT#\S*/i,6,'S2+S3','next input'); });
  await p.keyboard.press('Space'); await p.waitForTimeout(3200);
  await tabTo(p,/Envoyer ma demande/,6,'S2+S3','Envoyer ma demande'); await Promise.all([p.waitForLoadState('load'),p.keyboard.press('Enter')]); await p.waitForTimeout(800);
  const t=await p.locator('body').innerText(); const m=t.match(/DV-\d{4}-\d{4}/); if(!m){ const err=(t.match(/Merci de corriger[\s\S]{0,300}/)||['?'])[0]; throw new Error('no reference; '+err.replace(/\s+/g,' ')); } R.push({story:'S2+S3',label:'confirmation',focus:m[0]}); await c.close(); });
// S1
await run('S1', async()=>{ const {c,p}=await ctx(br); await kLogin(p,'direction','demo-asset');
  await tabTo(p,/^A#\S* Congrès$/,60,'S1','menu Congrès'); await Promise.all([p.waitForURL(/asset_congres/),p.keyboard.press('Enter')]);
  await tabTo(p,/A#.*Ajouter un congrès/,80,'S1','Ajouter un congrès'); await Promise.all([p.waitForURL(/post-new/),p.keyboard.press('Enter')]); await p.waitForTimeout(1500);
  await p.locator('#title').focus(); await p.keyboard.type('Congrès clavier — exemple');
  await tabTo(p,/asset-field-asset_start/,120,'S1','Date de début (from title)'); await p.keyboard.type('14062027'); await p.keyboard.press('Tab'); await p.keyboard.type('16062027');
  for(const v of ['Lille','France','Hépatologie']){ await p.keyboard.press('Tab'); await p.keyboard.type(v); await p.keyboard.press('Escape'); }
  await tabTo(p,/INPUT#publish/,120,'S1','Publier (forward)').catch(async()=>{ for(let i=1;i<=150;i++){ await p.keyboard.press('Shift+Tab'); const f=await info(p); if(/publish/.test(f.d)){ R.push({story:'S1',label:'Publier (Shift+Tab)',tabs:i,focus:f.d,focusVisible:f.vis}); return; } } throw new Error('publish unreachable'); });
  await Promise.all([p.waitForLoadState('load'),p.keyboard.press('Enter')]); await p.locator('#message').waitFor({timeout:60000}); R.push({story:'S1',label:'notice',focus:(await p.locator('#message').innerText()).slice(0,60)}); await c.close(); });
// S4
await run('S4', async()=>{ const {c,p}=await ctx(br); await kLogin(p,'equipe','demo-asset');
  await tabTo(p,/A#.*DV-2026-\d{4}/,80,'S4','Dernière demande link'); await Promise.all([p.waitForURL(/action=view/),p.keyboard.press('Enter')]);
  await tabTo(p,/SELECT#asset-statut/,120,'S4','Statut select'); await p.keyboard.press('ArrowDown');
  await tabTo(p,/Enregistrer/,10,'S4','Enregistrer'); await Promise.all([p.waitForLoadState('load'),p.keyboard.press('Enter')]); await p.locator('.notice-success').waitFor(); await c.close(); });
// S5
await run('S5', async()=>{ const e=await ctx(br); await kLogin(e.p,'equipe','demo-asset');
  await tabTo(e.p,/A#.*Accès GM&E/,60,'S5','menu Accès GM&E'); await Promise.all([e.p.waitForURL(/asset-gme/),e.p.keyboard.press('Enter')]);
  await tabTo(e.p,/TEXTAREA/,60,'S5','first reason textarea'); await e.p.keyboard.type('Accès clavier (UAT).');
  await tabTo(e.p,/Demander l’accès/,4,'S5','Demander l’accès'); await Promise.all([e.p.waitForLoadState('load'),e.p.keyboard.press('Enter')]); await e.p.locator('.notice-success').waitFor();
  const d=await ctx(br); await kLogin(d.p,'direction','demo-asset');
  await tabTo(d.p,/Approuver/,120,'S5','Approuver (24 h) in widget'); await Promise.all([d.p.waitForLoadState('load'),d.p.keyboard.press('Enter')]); await d.p.locator('.notice-success').waitFor();
  await e.p.goto('/wp-admin/'); await tabTo(e.p,/A#.*Accès GM&E/,60,'S5','menu Accès GM&E (2)'); await Promise.all([e.p.waitForURL(/asset-gme/),e.p.keyboard.press('Enter')]);
  await tabTo(e.p,/Révéler/,80,'S5','Révéler le code'); await Promise.all([e.p.waitForLoadState('load'),e.p.keyboard.press('Enter')]);
  const html=await e.p.content(); if(!CODES.some(k=>html.includes(k))) throw new Error('no code revealed');
  // revoke to restore
  await d.p.goto('/wp-admin/admin.php?page=asset-gme-acces'); const b=d.p.getByRole('button',{name:/Révoquer/}); if(await b.count()) { await b.first().focus(); await Promise.all([d.p.waitForLoadState('load'),d.p.keyboard.press('Enter')]); }
  await e.c.close(); await d.c.close(); });
fs.writeFileSync('kb-result.json',JSON.stringify(R,null,1)); await br.close();
