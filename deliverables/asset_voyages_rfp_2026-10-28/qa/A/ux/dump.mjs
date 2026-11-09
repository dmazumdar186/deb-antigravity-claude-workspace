import { chromium, ctx, login } from './lib.mjs';
const br = await chromium.launch(); 
for (const [role, urls] of Object.entries({ equipe:['/wp-admin/','/wp-admin/admin.php?page=asset-gme'], direction:['/wp-admin/'], admin:['/wp-admin/edit.php?post_type=asset_congres'] })) {
  const { c, p } = await ctx(br); await login(p, role);
  for (const u of urls) { await p.goto(u);
    const menu = await p.$$eval('#adminmenu > li > a', as=>as.map(a=>a.innerText.trim().replace(/\s+/g,' ')).filter(Boolean));
    const body = await p.$$eval('#wpbody-content a, #wpbody-content button, #wpbody-content input[type=submit], #wpbody-content select, #wpbody-content textarea', es=>es.filter(e=>e.offsetParent).map(e=>e.tagName+':'+(e.innerText||e.value||e.getAttribute('aria-label')||e.name||'').trim().replace(/\s+/g,' ').slice(0,60)));
    console.log('==',role,u,'\nMENU',menu.join(' | '),'\nBODY',[...new Set(body)].join(' | ').slice(0,1500)); }
  await c.close(); }
await br.close();
