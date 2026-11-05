const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  for (const role of ['direction','contributeur','equipe']) {
    for (let i=0;i<3;i++){
    const ctx = await b.newContext({ baseURL: 'http://127.0.0.1:9400' });
    const p = await ctx.newPage();
    p.on('pageerror', e => console.log(role, 'ERR', e.message, (e.stack||'').split('\n').slice(0,4).join(' | ')));
    await p.goto('/wp-login.php'); await p.fill('#user_login', role); await p.fill('#user_pass','demo-asset');
    await Promise.all([p.waitForURL(/wp-admin/), p.click('#wp-submit')]);
    await p.waitForLoadState('networkidle');
    await p.goto('/wp-admin/'); await p.waitForLoadState('networkidle');
    await ctx.close();
    }
  }
  await b.close();
})();
