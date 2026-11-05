import fs from 'fs'; import { chromium } from 'playwright';
const px=process.env.HTTPS_PROXY||process.env.https_proxy;
const br=await chromium.launch({ proxy: px?{server:px}:undefined });
const out={};
for (const kind of ['visitor','admin']) {
  const c=await br.newContext({locale:'fr-FR',viewport:{width:1440,height:900}}); const p=await c.newPage(); const errs=[]; p.on('pageerror',e=>errs.push(e.message));
  const url=`https://playground.wordpress.net/?blueprint-url=https://asset-voyages-redesign.pages.dev/demo-wordpress/blueprint-${kind}.json`;
  const t0=Date.now(); let ok=false, text='', firstPaint=null;
  try { await p.goto(url,{timeout:60000});
    const target = kind==='visitor' ? /Catalogue des congrès/ : /Demandes de devis/;
    while (Date.now()-t0<180000) { for (const f of p.frames()) { try { const b=await f.locator('body').innerText({timeout:1000}); if(!firstPaint && b.trim().length>20) firstPaint=Date.now()-t0; if(target.test(b)&&/congr|Demandes/.test(b)&&f!==p.mainFrame()){ ok=true; text=b.slice(0,600); break; } } catch{} } if(ok) break; await p.waitForTimeout(1000); }
  } catch(e){ text='ERR '+e.message.split('\n')[0]; }
  out[kind]={url, loaded:ok, seconds:((Date.now()-t0)/1000).toFixed(1), firstTextAt:firstPaint, sample:text.replace(/\s+/g,' ').slice(0,500), errs:errs.slice(0,5)};
  await p.screenshot({path:`evidence/hosted-${kind}-1440.png`}).catch(()=>{});
  console.log(kind, JSON.stringify(out[kind]).slice(0,800)); await c.close(); }
fs.writeFileSync('hosted-result.json',JSON.stringify(out,null,1)); await br.close();
