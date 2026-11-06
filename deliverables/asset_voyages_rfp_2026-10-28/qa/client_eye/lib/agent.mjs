// The literal agent for C10: it acts only through labels a reader can see on screen, and counts its clicks.
// A label that is visible but not clickable, or not visible at all, is a failed step (never a fallback to a URL).
import { finding, log } from './core.mjs';

const N = (s) => String(s || '').replace(/[  ]/g, ' ').replace(/\s+/g, ' ').trim();

export class Agent {
  constructor(page, option) { this.page = page; this.option = option; this.clicks = 0; this.trace = []; }
  note(s) { this.trace.push(s); }
  // Click the visible element whose own visible text is the label (exact, then « starts with »). Returns a reason on failure.
  async click(label, { exact = true, within, roles } = {}) {
    const p = this.page;
    const res = await p.evaluate(({ label, exact, within, roles }) => {
      const N = (s) => String(s || '').replace(/[  ]/g, ' ').replace(/\s+/g, ' ').trim();
      const root = within ? document.querySelector(within) : document.body;
      if (!root) return { why: 'no ' + within };
      const vis = (e) => { if (!e.checkVisibility || !e.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) return false; const r = e.getBoundingClientRect(); return r.width > 1 && r.height > 1; };
      const interactive = 'a[href],button,input[type=submit],input[type=button],summary,[role=button],[role=tab],[role=menuitem],label';
      const cand = [...root.querySelectorAll(interactive + ',p,span,div,h1,h2,h3,h4,li,td,th,strong,b')].filter(vis);
      // what the eye reads: text nodes of the element minus screen-reader-only spans (clip / 1 px boxes)
      const srOnly = (el) => { for (let x = el; x && x !== e0; x = x.parentElement) { const cs = getComputedStyle(x); if (cs.clip === 'rect(0px, 0px, 0px, 0px)' || cs.clipPath === 'inset(50%)' || (cs.position === 'absolute' && parseFloat(cs.width) <= 1)) return true; } return false; };
      let e0 = null;
      const own = (e) => { if (e.value && e.nodeName === 'INPUT') return N(e.value); e0 = e; const w = document.createTreeWalker(e, NodeFilter.SHOW_TEXT); let s = ''; while (w.nextNode()) { const p = w.currentNode.parentElement; if (p && !srOnly(p)) s += w.currentNode.nodeValue; } e0 = null; return N(s); };
      let hits = cand.filter((e) => own(e) === N(label));
      if (!hits.length && !exact) hits = cand.filter((e) => own(e).startsWith(N(label)) && own(e).length < N(label).length + 40);
      if (!hits.length) return { why: `label « ${label} » not visible` };
      if (roles) hits.sort((a, b) => (a.matches(roles) ? -1 : 0) - (b.matches(roles) ? -1 : 0));
      // prefer the smallest interactive element
      for (const e of hits) {
        const i = e.matches(interactive) ? e : e.closest(interactive);
        if (i && vis(i)) { i.setAttribute('data-agent-target', '1'); return { ok: true, tag: i.nodeName, href: i.getAttribute('href') || '' }; }
      }
      return { why: `label « ${label} » is visible (${hits[0].nodeName.toLowerCase()}) but is not a link or a button` };
    }, { label, exact, within, roles });
    if (!res.ok) return res.why;
    const t = p.locator('[data-agent-target="1"]').first();
    const nav = p.waitForNavigation({ timeout: 8000 }).catch(() => null);
    await t.click({ timeout: 5000 });
    await p.evaluate(() => document.querySelectorAll('[data-agent-target]').forEach((e) => e.removeAttribute('data-agent-target'))).catch(() => {});
    if (res.tag === 'A' && res.href && !res.href.startsWith('#')) await nav; else await p.waitForTimeout(600);
    try { await p.waitForLoadState('load', { timeout: 30000 }); } catch {}
    this.clicks++;
    this.note(`click « ${label} »`);
    return null;
  }
  async fill(label, value, { exact = false } = {}) {
    const l = this.page.getByLabel(label, { exact }).filter({ visible: true }).first();
    if (!(await l.count())) return `field « ${label} » not visible`;
    const type = await l.getAttribute('type');
    const tag = await l.evaluate((e) => e.nodeName);
    if (tag === 'SELECT') await l.selectOption({ label: value }).catch(async () => l.selectOption(value));
    else if (type === 'checkbox') { if (value) await l.check(); else await l.uncheck(); }
    else await l.fill(value);
    this.note(`fill « ${label} »`);
    return null;
  }
  async sees(re) { const t = await this.page.locator('body').innerText(); return typeof re === 'string' ? N(t).includes(N(re)) : re.test(t); }
}

// Record one replayed step.
export function stepResult(rows, { option, task, n, text, ok, why, clicks, page, role, shot, extra }) {
  rows.push({ option, task, n, text, ok, why: why || '', clicks, page, role, shot: shot || '', extra: extra || '' });
  if (!ok) finding({ check: 'C10', option, page, role, width: 1440, text: `${task} step ${n}: ${text}`, element: 'instruction replay', note: why, shot });
  log(`C10 ${option} ${task}.${n} ${ok ? 'OK' : 'FAIL'} (${clicks} clicks) ${why || ''}`);
}
