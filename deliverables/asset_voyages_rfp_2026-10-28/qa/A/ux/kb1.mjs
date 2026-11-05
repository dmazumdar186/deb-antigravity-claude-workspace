import { chromium, ctx, login } from './lib.mjs';
const br=await chromium.launch();
for (const mode of ['enter','space','click','enter-noesc']) { const {c,p}=await ctx(br); await login(p,'direction'); await p.goto('/wp-admin/post-new.php?post_type=asset_congres'); await p.waitForTimeout(1500);
  await p.locator('#title').focus(); await p.keyboard.type('Congrès variante '+mode+' — exemple');
  await p.locator('#asset-field-asset_start').focus(); await p.keyboard.type('06142027'); await p.keyboard.press('Tab'); await p.keyboard.type('06162027');
  for (const v of ['Lille','France','Hépatologie']) { await p.keyboard.press('Tab'); await p.keyboard.type(v); if(mode!=='enter-noesc') await p.keyboard.press('Escape'); }
  const reqs=[]; p.on('request',r=>{ if(r.method()==='POST'&&/post\.php/.test(r.url())) reqs.push((r.postData()||'').length); });
  await p.locator('#publish').focus();
  if(mode==='click') await Promise.all([p.waitForNavigation({timeout:120000}),p.locator('#publish').click()]);
  else await Promise.all([p.waitForNavigation({timeout:120000}),p.keyboard.press(mode==='space'?'Space':'Enter')]);
  const navs=[]; p.on('framenavigated',f=>{ if(f===p.mainFrame()) navs.push(f.url().replace(/.*wp-admin\//,'')); }); await p.waitForTimeout(6000); await p.waitForLoadState('load');
  console.log(mode, p.url().replace(/.*wp-admin\//,''), 'postBodyLen', reqs, 'navs', navs, (await p.locator('#message, .notice').allInnerTexts()).join(' / ').replace(/\s+/g,' ').slice(0,140));
  await c.close(); }
await br.close();
