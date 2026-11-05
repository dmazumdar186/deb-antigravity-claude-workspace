import { chromium, B, ctx } from './lib.mjs';
const br=await chromium.launch(); const {p}=await ctx(br); await p.goto(B+'/'); await p.getByRole('link',{name:'Cardiologie',exact:true}).click();
console.log(p.url()); console.log((await p.locator('main').innerHTML()).match(/<a [^>]*>/g).slice(0,30).join('\n')); console.log(await p.locator('h1').allInnerTexts());
await br.close();
