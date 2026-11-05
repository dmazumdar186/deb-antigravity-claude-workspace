for (const role of roles) {
  const rnd = mulberry(SEED + role.length * 7 + role.charCodeAt(0)); const pick = (a) => a[Math.floor(rnd() * a.length)];
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'fr-FR' }); const page = await ctx.newPage();
  const bad = { s5xx: [], consoleErr: [], leak: [], deadEnd: [], actionErr: [] }; const log = []; const a4xx = new Set(); let lastReveal = false, revealOk = false;
  page.on('response', (r) => { const s = r.status(); if (s >= 500) bad.s5xx.push(`${s} ${r.url()} @${log.length}`); if (s >= 400) a4xx.add(r.url()); });
  page.on('pageerror', (e) => bad.consoleErr.push(`pageerror ${e.message} @${log.length}`));
  page.on('console', (m) => { if (m.type() !== 'error') return; const u = m.location()?.url || ''; if (/Failed to load resource/.test(m.text()) && a4xx.has(u)) return; bad.consoleErr.push(`${m.text()} @${log.length}`); });
  page.on('dialog', (d) => { bad.consoleErr.push('dialog ' + d.message()); d.dismiss(); });
  await page.goto(BASE + '/');
  if (role !== 'anon') { await page.goto(BASE + '/console/connexion'); await page.fill('input[name=username]', role); await page.fill('input[name=password]', 'demo-asset'); await Promise.all([page.waitForURL(/\/console(?!\/connexion)/), page.click('form [type=submit]')]); }
