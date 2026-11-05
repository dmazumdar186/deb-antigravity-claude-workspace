import { chromium, B, ctx } from './lib.mjs';
const br=await chromium.launch(); const {p}=await ctx(br); await p.goto(B+'/congres/journees-d-oncologie-digestive-cg-0112');
await p.getByLabel('Ville de départ').focus(); await p.keyboard.press('Tab'); await p.keyboard.type('27');
const box=await p.getByLabel('Date aller').boundingBox(); await p.screenshot({path:'evidence/focus-date.png',clip:{x:box.x-20,y:box.y-40,width:box.width+40,height:box.height+60}});
console.log(await p.getByLabel('Date aller').evaluate(e=>[getComputedStyle(e).outline, e.matches(':focus-visible'), e.matches(':focus')]));
await p.getByLabel('Ville de départ').focus(); await p.keyboard.press('Shift+Tab'); await p.keyboard.press('Tab');const b2=await p.getByLabel('Ville de départ').boundingBox(); await p.screenshot({path:'evidence/focus-text.png',clip:{x:b2.x-20,y:b2.y-40,width:b2.width+40,height:b2.height+60}});
await br.close();
