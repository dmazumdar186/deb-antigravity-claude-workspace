// Hub crawl: the five site pages, every width, both locales; parses the task steps (C10) and the comparison table (D1).
import { newCtx, snap, flushErrors, probeButtons, finding, log, RUN, settle } from './core.mjs';

export const HUB = process.env.HUB || 'https://asset-voyages-redesign.pages.dev';
export const HUB_PAGES = ['/demo/', '/', '/pour-asset/', '/console/', '/questions/'];
export const WIDTHS6 = [320, 390, 768, 1280, 1440, 1920];
const OPT = 'HUB';
const SENDER = ['debanjan@prodcraft.fyi'];

export async function crawlHub(browser) {
  const parsed = {};
  for (const locale of ['fr-FR', 'en-GB']) {
    const widths = locale === 'fr-FR' ? WIDTHS6 : [1440, 390];
    for (const w of widths) {
      const { ctx, page } = await newCtx(browser, { width: w, locale, option: OPT });
      for (const p of HUB_PAGES) {
        await page.goto(HUB + p, { waitUntil: 'load' });
        // the hub's own language decides the B1 rule (the note for ASSET is in French)
        const r = await snap(page, { option: OPT, surface: 'hub', state: `hub${p}`, b4: true, allowEmails: SENDER, rules: (w === 1440 || w === 390) ? undefined : ['B4', 'C6', 'C4'] , shot: (w === 1440 || w === 390 || locale === 'fr-FR') });
        flushErrors(page, { option: OPT, state: `hub${p}` });
        if (!r) continue;
        if (p === '/demo/' && w === 1440 && locale === 'fr-FR') parsed.html = r.html;
        if ((w === 390 || w === 1440) && locale === 'fr-FR') {
          await probeButtons(page, { option: OPT, state: `hub${p}` });
          if (p === '/demo/') await anchorsUnderHeader(page, w);
        }
      }
      await ctx.close();
    }
  }
  return parsed;
}

// C6: in-page anchors must not land under the sticky header
async function anchorsUnderHeader(page, w) {
  await page.goto(HUB + '/demo/');
  await settle(page, 500);
  const hrefs = await page.$$eval('a[href^="#"]', (as) => [...new Set(as.filter((a) => a.offsetParent).map((a) => a.getAttribute('href')))]);
  for (const h of hrefs) {
    if (h === '#' || h === '#main') continue;
    const link = page.locator(`a[href="${h}"]:visible`).first();
    if (!(await link.count())) continue;
    try { await link.click({ timeout: 3000 }); } catch { continue; }
    await page.waitForTimeout(900);
    const r = await page.evaluate((id) => {
      const t = document.getElementById(id.slice(1));
      if (!t) return { missing: true };
      let sticky = 0;
      for (const el of document.querySelectorAll('*')) { const cs = getComputedStyle(el); if ((cs.position === 'sticky' || cs.position === 'fixed') && el.offsetParent !== null || cs.position === 'fixed') { const b = el.getBoundingClientRect(); if (b.top <= 1 && b.bottom > 0 && b.height < innerHeight / 2 && b.width > innerWidth / 2) sticky = Math.max(sticky, b.bottom); } }
      const tr = t.getBoundingClientRect();
      // the heading inside the target is what the reader looks for
      const head = t.matches('h1,h2,h3') ? t : t.querySelector('h1,h2,h3') || t;
      return { top: Math.round(head.getBoundingClientRect().top), sticky: Math.round(sticky), hidden: t.hidden };
    }, h);
    if (r.missing) finding({ check: 'A4', option: OPT, page: HUB + '/demo/', width: w, text: h, element: `a[href="${h}"]`, note: 'in-page link to a missing target' });
    else if (!r.hidden && r.top < r.sticky - 1) finding({ check: 'C6', option: OPT, page: HUB + '/demo/' + h, width: w, text: `heading top ${r.top}px < header bottom ${r.sticky}px`, element: h, note: 'anchor target hidden under the sticky header' });
  }
}

// Parse the hub: tasks per option (C10), the group section, the "What works" table (D1), A2 boot text.
export async function parseHub(browser) {
  const { ctx, page } = await newCtx(browser, { width: 1440, option: OPT });
  await page.goto(HUB + '/demo/');
  await settle(page, 600);
  const out = await page.evaluate(() => {
    const txt = (e) => (e ? e.innerText.replace(/\s+/g, ' ').trim() : '');
    const tasks = [];
    for (const li of document.querySelectorAll('[data-tasks] > li.task')) {
      const h = li.querySelector('h3');
      const opts = {};
      for (const blk of li.querySelectorAll('.task__opt')) {
        const key = blk.classList.contains('task__opt--a') ? 'A' : 'B';
        const ol = blk.querySelector('ol.steps');
        opts[key] = { which: txt(blk.querySelector('.task__which')), steps: ol ? [...ol.children].map((s) => ({ text: txt(s), links: [...s.querySelectorAll('a')].map((a) => ({ text: txt(a), href: a.href })) })) : [], notes: [...blk.querySelectorAll(':scope > p:not(.task__which)')].map(txt) };
      }
      tasks.push({ id: li.id, title: txt(h), opts });
    }
    const g = document.getElementById('group');
    const group = g ? { steps: [...((() => { const hd = [...g.querySelectorAll('h3,h4,p')].find((e) => /How to try it/i.test(e.textContent) && e.textContent.length < 40); let n = hd; while (n && n.nodeName !== 'OL') n = n.nextElementSibling; return n || (hd && hd.parentElement.querySelector('ol')) || document.createElement('ol'); })().children)].map((s) => ({ text: txt(s), links: [...s.querySelectorAll('a')].map((a) => ({ text: txt(a), href: a.href })) })), text: txt(g) } : null;
    const rows = [...document.querySelectorAll('table.cmp tbody tr')].map((tr) => ({ fn: txt(tr.querySelector('th')), A: txt(tr.querySelectorAll('td')[0]), B: txt(tr.querySelectorAll('td')[1]) }));
    const passA = txt(document.querySelector('.pass:not(.pass--b)'));
    const passB = txt(document.querySelector('.pass--b'));
    const buttons = [...document.querySelectorAll('a')].filter((a) => /playground\.wordpress\.net|workers\.dev/.test(a.href)).map((a) => ({ text: txt(a), href: a.href, near: txt(a.closest('article,li,p,div')) .slice(0, 400) }));
    return { tasks, group, rows, passA, passB, buttons, full: document.body.innerText };
  });
  await ctx.close();
  log('hub parsed: tasks', out.tasks.length, 'rows', out.rows.length, 'group steps', out.group ? out.group.steps.length : 0);
  return out;
}
