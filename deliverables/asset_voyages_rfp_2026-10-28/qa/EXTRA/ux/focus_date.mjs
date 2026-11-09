import { chromium, B, ctx } from './lib.mjs';
const br = await chromium.launch(); const { c, p } = await ctx(br, 390);
await p.goto(B + '/g/GSKql7ARlf1lQZb0wz24B5PlOwlAESjj81qRCrM4_x4');
await p.getByLabel('Ville de départ').focus(); await p.keyboard.press('Tab');
const st = await p.evaluate(() => { const e = document.activeElement; const cs = getComputedStyle(e); return { id: e.id, outline: cs.outlineStyle + ' ' + cs.outlineWidth + ' ' + cs.outlineColor, shadow: cs.boxShadow, fv: e.matches(':focus-visible'), border: cs.borderColor }; });
console.log(JSON.stringify(st));
await p.locator('#g-out').screenshot({ path: 'eye/390-focus-date.png' }).catch(() => {});
await p.locator('.cg__aside').screenshot({ path: 'eye/390-focus-date-ctx.png' });
await br.close();
