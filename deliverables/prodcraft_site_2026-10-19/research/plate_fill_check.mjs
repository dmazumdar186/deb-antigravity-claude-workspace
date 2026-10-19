import pw from '/opt/node-tools/node_modules/playwright/index.js'; const { chromium } = pw;
const base = process.argv[2] || 'http://localhost:8793/'; const b = await chromium.launch(); let fail = 0;
const VP = [[360,640],[390,844],[412,915],[844,390],[600,960],[960,600],[820,1180],[1180,820],[1024,1366],[1366,1024],[1280,720],[1366,768],[1536,864],[1440,900],[1882,832],[1920,1080],[2560,1440],[3840,2160],[1080,1920]];
for (const [w,h] of VP) {
  const c = await b.newContext({viewport:{width:w,height:h}, ignoreHTTPSErrors:true}); const p = await c.newPage();
  await p.goto(base, {waitUntil:'load'}); await p.waitForTimeout(700);
  const r = await p.evaluate(()=>{const out=[]; for (const f of document.querySelectorAll('.cplate')) { const cs=getComputedStyle(f); if (cs.display==='none' || getComputedStyle(f.parentElement).display==='none') { out.push({hidden:true}); continue; } const i=f.querySelector('img'); const fr=f.getBoundingClientRect(), ir=i.getBoundingClientRect(); const pad=parseFloat(cs.paddingLeft); const hdr=document.querySelector('.hdr').getBoundingClientRect().bottom; out.push({fw:+(fr.width-2*pad-2).toFixed(1), iw:+ir.width.toFixed(1), ih:+ir.height.toFixed(1), ratio:+(ir.width/ir.height).toFixed(3), top:+fr.top.toFixed(0), bottom:+fr.bottom.toFixed(0), hdr:+hdr.toFixed(0)}); } return out;});
  const vis = r.filter(x=>!x.hidden);
  const ok = vis.every(x => Math.abs(x.fw - x.iw) <= 1.5 && x.iw >= 100 && x.top >= x.hdr + 6 && x.bottom <= h);
  if (!ok) fail++; console.log(`${w}x${h}`, ok ? 'OK' : 'FAIL', JSON.stringify(vis[0] || r[0]));
  await c.close();
}
await b.close(); console.log(fail ? `FAIL ${fail}` : 'ALL OK'); process.exit(fail ? 1 : 0);
