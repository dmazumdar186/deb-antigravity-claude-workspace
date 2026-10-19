import pw from '/opt/node-tools/node_modules/playwright/index.js'; const { chromium } = pw;
const b = await chromium.launch(); let fail=0;
for (const [w,h] of [[1882,832],[1440,900],[1366,768],[1920,1080],[2560,1440],[3840,2160],[1280,720]]) {
  const c = await b.newContext({viewport:{width:w,height:h}}); const p = await c.newPage();
  await p.goto('http://localhost:8793/', {waitUntil:'load'}); await p.waitForTimeout(900);
  const r = await p.evaluate(()=>{const f=document.querySelector('[data-plate="1"]'); const i=f.querySelector('img'); const hb=document.querySelector('.hdr').getBoundingClientRect(); const ir=i.getBoundingClientRect(); const fr=f.getBoundingClientRect(); const cs=getComputedStyle(f); return {hdr:hb.bottom, imgTop:ir.top, imgH:ir.height, imgW:ir.width, figTop:fr.top, figBottom:fr.bottom, op:cs.opacity}});
  const ok = r.imgTop >= r.hdr + 8 && r.figBottom <= h && r.imgW > 120;
  if(!ok) fail++; console.log(w+'x'+h, JSON.stringify(r), ok?'OK':'CLIP');
  if (w===1882) await p.screenshot({path:'deliverables/prodcraft_site_2026-10-19/screens/cover-1882-plate.png'});
  await c.close();
}
await b.close(); process.exit(fail?1:0);
