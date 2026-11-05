import { chromium, B, ctx, login } from './lib.mjs';
const br=await chromium.launch(); 
for (const W of [1440,1280,1024]){ const {p}=await ctx(br,W); await login(p,'equipe');
for (const u of ['/console/demandes','/console/congres','/console/gme/journal','/console/notifications']){ await p.goto(B+u);
 const r=await p.evaluate(()=>[...document.querySelectorAll('table')].map(t=>{const w=t.closest('.wrap')||t.parentElement; return {ths:[...t.querySelectorAll('th')].map(x=>x.innerText), tw:t.scrollWidth, cw:w.clientWidth, sw:w.scrollWidth, ov:getComputedStyle(w).overflowX, hint:!!w.getAttribute('aria-label')}}));
 console.log(W,u,JSON.stringify(r)); } }
await br.close();
