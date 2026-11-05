import { chromium, ctx, login } from './lib.mjs';
const br=await chromium.launch(); const {c,p}=await ctx(br); await login(p,'direction');
const log=[]; p.on('response',r=>{ if(/admin-ajax/.test(r.url())) log.push(r.status()+' '+r.request().postData()?.slice(0,60)); }); p.on('requestfailed',r=>{ if(/admin-ajax/.test(r.url())) log.push('FAILED '+r.failure()?.errorText); });
await p.goto('/wp-admin/post-new.php?post_type=asset_congres'); console.log('ids', await p.$$eval('form input, form select, form textarea',es=>[]));
const v=await ctx(br); await v.p.goto('/'); await v.p.locator('.asset-card a').first().click(); console.log('front ids', await v.p.$$eval('form.asset-enquiry input, form.asset-enquiry select, form.asset-enquiry textarea, form input, form textarea',es=>es.filter(e=>e.type!=='hidden').map(e=>e.id+':'+e.type+':'+e.tabIndex+(e.offsetParent?'':'(hidden)')).join(' ')));
await p.waitForTimeout(75000); console.log(log.join('\n')); console.log('lost visible', await p.locator('#lost-connection-notice').isVisible());
await br.close();
