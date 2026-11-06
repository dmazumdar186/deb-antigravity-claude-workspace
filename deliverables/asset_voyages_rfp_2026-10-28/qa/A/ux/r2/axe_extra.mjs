// Extra axe screens not covered by uat.mjs: front-end at 390, congress edit (plain editor), contributor screens, Journal GM&E empty states.
import fs from 'fs';
import AxeBuilderPkg from '@axe-core/playwright';
import { chromium, ctx, login } from '../lib.mjs';
const AxeBuilder = AxeBuilderPkg.default || AxeBuilderPkg;
const R = [];
async function axe(p, screen) {
  const r = await new AxeBuilder({ page: p }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice']).analyze();
  for (const v of r.violations) for (const n of v.nodes) {
    const html = n.html.slice(0, 160); const tgt = n.target.join(' ');
    const owner = /asset|catalogue|devis|gme|demande/i.test(html + tgt) ? 'plugin/theme' : (/wp-block|wp-site|wp-container/.test(html + tgt) ? 'theme' : 'core');
    R.push({ screen, id: v.id, impact: v.impact, target: tgt.slice(0, 120), html, owner });
  }
  console.log(screen, r.violations.map(v => `${v.id}:${v.impact}:${v.nodes.length}`).join(' ') || 'clean');
}
const br = await chromium.launch();
try {
  { const { c, p } = await ctx(br, 390); await p.goto('/'); await axe(p, '390 catalogue');
    await p.locator('.asset-card a').first().click(); await p.waitForLoadState('load'); await axe(p, '390 fiche');
    await p.waitForTimeout(3500); await p.getByRole('button', { name: 'Envoyer ma demande' }).click(); await p.waitForLoadState('load'); await axe(p, '390 form errors'); await c.close(); }
  { const { c, p } = await ctx(br, 1440); await login(p, 'direction');
    await p.goto('/wp-admin/edit.php?post_type=asset_congres'); await axe(p, 'admin congress list');
    await p.locator('table.wp-list-table tbody tr a.row-title').first().click(); await p.waitForLoadState('load'); await axe(p, 'admin congress edit (plain editor)');
    await p.goto('/wp-admin/post-new.php?post_type=asset_congres'); await axe(p, 'admin new congress');
    await p.goto('/wp-admin/edit-tags.php?taxonomy=asset_discipline&post_type=asset_congres'); await axe(p, 'admin disciplines');
    await c.close(); }
  { const { c, p } = await ctx(br, 1440); await login(p, 'contributeur'); await axe(p, 'admin dashboard (contributeur)');
    await p.goto('/wp-admin/post-new.php?post_type=asset_congres'); await axe(p, 'admin new congress (contributeur)'); await c.close(); }
  { const { c, p } = await ctx(br, 390); await login(p, 'equipe'); await axe(p, '390 admin dashboard (equipe)');
    await p.goto('/wp-admin/admin.php?page=asset-demandes'); await axe(p, '390 admin demandes'); await p.goto('/wp-admin/admin.php?page=asset-gme'); await axe(p, '390 admin GM&E (equipe)'); await c.close(); }
} finally { fs.writeFileSync('axe-extra.json', JSON.stringify(R, null, 1)); await br.close(); }
