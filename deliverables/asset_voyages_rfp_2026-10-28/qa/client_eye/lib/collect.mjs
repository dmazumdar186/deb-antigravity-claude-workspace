// In-page collectors for the client-eye gate. Each function below is passed to page.evaluate(), so it must be
// self-contained (no closures over Node variables).

// Init script: records layout shifts (C4) and mutations (C2) from the very first paint.
export const INIT_SCRIPT = `
(() => {
  window.__cls = 0; window.__shifts = [];
  try {
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) {
        if (e.hadRecentInput) continue;
        window.__cls += e.value;
        window.__shifts.push({ v: +e.value.toFixed(4), t: Math.round(e.startTime), src: (e.sources || []).slice(0, 3).map((s) => s.node ? (s.node.nodeName + (s.node.id ? '#' + s.node.id : '') + (s.node.className && typeof s.node.className === 'string' ? '.' + s.node.className.trim().split(/\\s+/).slice(0,2).join('.') : '')) : '?') });
      }
    }).observe({ type: 'layout-shift', buffered: true });
  } catch (e) {}
})();`;

// Main collector. opts: { b4: bool }
export function collectPage(opts) {
  const out = { url: location.href, title: document.title, lang: document.documentElement.lang || '', texts: [], attrs: [], inputs: [], links: [], media: [], videos: [], favicons: [], overflow: null, b4: [], styles: {}, empties: [], clickables: [], sticky: 0, cls: window.__cls || 0, shifts: (window.__shifts || []).slice(0, 8), bodyText: '' };
  const vw = window.innerWidth;
  const cssPath = (el) => {
    const parts = [];
    let e = el;
    while (e && e.nodeType === 1 && parts.length < 4 && e !== document.body) {
      let s = e.nodeName.toLowerCase();
      if (e.id) { s += '#' + e.id; parts.unshift(s); break; }
      const cls = typeof e.className === 'string' ? e.className.trim().split(/\s+/).filter(Boolean).slice(0, 2) : [];
      if (cls.length) s += '.' + cls.join('.');
      parts.unshift(s);
      e = e.parentElement;
    }
    return parts.join(' > ');
  };
  const visibleEl = (el) => {
    if (!el || !el.isConnected) return false;
    if (el.checkVisibility && !el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return false;
    // visually hidden (screen-reader only) patterns
    let e = el;
    while (e && e !== document.body) {
      const cs = getComputedStyle(e);
      if (cs.clip === 'rect(0px, 0px, 0px, 0px)' || cs.clipPath === 'inset(50%)' || (cs.position === 'absolute' && parseFloat(cs.width) <= 1 && parseFloat(cs.height) <= 1)) return false;
      if (cs.overflow === 'hidden' && (parseFloat(cs.width) <= 1 || parseFloat(cs.height) <= 1)) return false;
      e = e.parentElement;
    }
    if (r.right < -5 || r.bottom < -5 && window.scrollY === 0) {
      // off-screen left/top (classic skip-link pattern) counts as hidden
      if (r.right < 0 || r.left < -1000 || r.top < -1000) return false;
    }
    return true;
  };
  const visCache = new Map();
  const vis = (el) => { if (!visCache.has(el)) visCache.set(el, visibleEl(el)); return visCache.get(el); };
  const ctxOf = (el) => ({
    code: !!el.closest('code,kbd,samp,pre'),
    quoted: false,
    lang: (el.closest('[lang]') || document.documentElement).getAttribute('lang') || '',
    path: cssPath(el),
    tag: el.nodeName.toLowerCase(),
  });

  // 1. Visible text nodes (text of each node merged per parent element, so « Congrès » spans stay whole)
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, { acceptNode: (n) => (n.nodeValue.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT) });
  const textNodes = [];
  while (walker.nextNode()) {
    const n = walker.currentNode;
    const p = n.parentElement;
    if (!p || ['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'OPTION'].includes(p.nodeName)) continue;
    if (!vis(p)) continue;
    textNodes.push(n);
  }
  // Selected <option> text is visible in a closed <select>; other options become visible when it opens (count them).
  for (const sel of document.querySelectorAll('select')) {
    if (!vis(sel)) continue;
    for (const o of sel.options) out.texts.push({ t: o.text, ...ctxOf(sel), tag: 'option' });
  }
  // Group consecutive text nodes by block ancestor to build readable lines
  const blockOf = (el) => { let e = el; while (e && e !== document.body) { const d = getComputedStyle(e).display; if (!d.startsWith('inline')) return e; e = e.parentElement; } return document.body; };
  const blocks = new Map();
  for (const n of textNodes) {
    const p = n.parentElement;
    const b = blockOf(p);
    if (!blocks.has(b)) blocks.set(b, { parts: [], code: [] });
    // A <br> or a line box change between two text nodes is a visual space even when the source has none
    // (« ProdCraft<br>debanjan@… » must not read as one word).
    const parts = blocks.get(b).parts;
    let sep = '';
    if (parts.length) {
      // a whitespace-only text node between two elements (« <strong>ASSET Voyages</strong> <span>demos</span> ») is a space
      const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); tw.currentNode = n; const pv = tw.previousNode();
      if (pv && pv !== parts[parts.length - 1].node && !pv.nodeValue.trim()) sep = ' ';
      let e = n.previousSibling; while (e && e.nodeType === 3 && !e.nodeValue.trim()) e = e.previousSibling;
      const boxy = (el) => el && /^inline-(block|flex|grid|table)$/.test(getComputedStyle(el).display);
      const prevNode = parts[parts.length - 1].node;
      if (e && e.nodeType === 1 && (e.nodeName === 'BR' || !getComputedStyle(e).display.startsWith('inline') || boxy(e))) sep = ' ';
      else if (prevNode.parentElement !== p && (boxy(p.closest('*')) || boxy(prevNode.parentElement))) sep = ' '; // two chips side by side
      else {
        const prev = parts[parts.length - 1].node;
        try { const r1 = document.createRange(); r1.selectNodeContents(prev); const a = [...r1.getClientRects()].pop(); const r2 = document.createRange(); r2.selectNodeContents(n); const c = r2.getClientRects()[0]; if (a && c && c.top >= a.bottom - 1) sep = ' '; } catch (err) { sep = ''; }
      }
    }
    parts.push({ t: sep + n.nodeValue, code: !!p.closest('code,kbd,samp,pre'), node: n });
  }
  for (const [b, v] of blocks) {
    const t = v.parts.map((x) => x.t).join('').replace(/\s+/g, ' ').trim();
    const tNoCode = v.parts.map((x) => (x.code ? ' ⟦code⟧ ' : x.t)).join('').replace(/\s+/g, ' ').trim();
    if (t) out.texts.push({ t, tNoCode, ...ctxOf(b), code: v.parts.every((x) => x.code) });
  }
  // 2. Attributes shown to people (tooltips, alt, placeholders, labels for assistive tech)
  for (const el of document.querySelectorAll('[alt],[title],[aria-label],[placeholder]')) {
    if (el.nodeName === 'HTML' || el.nodeName === 'LINK' || el.nodeName === 'META') continue;
    for (const a of ['alt', 'title', 'aria-label', 'placeholder']) {
      const v = el.getAttribute(a);
      if (v && v.trim()) out.attrs.push({ a, t: v.trim(), visible: vis(el), ...ctxOf(el) });
    }
  }
  // 3. Input values (D4 includes hidden inputs)
  for (const el of document.querySelectorAll('input,textarea,select')) {
    const v = el.value;
    if (v && String(v).trim()) out.inputs.push({ name: el.name || el.id || '', type: el.type || el.nodeName.toLowerCase(), t: String(v).slice(0, 300), visible: vis(el), path: cssPath(el) });
  }
  // 4. Links and media sources (A4)
  for (const el of document.querySelectorAll('a[href],area[href]')) out.links.push({ href: el.href, raw: el.getAttribute('href'), text: (el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 80), visible: vis(el), path: cssPath(el), target: el.target || '' });
  for (const el of document.querySelectorAll('[src],link[href],video[poster],source[srcset],img[srcset]')) {
    if (el.nodeName === 'LINK') { const rel = el.rel || ''; if (/preconnect|dns-prefetch/.test(rel)) continue; out.media.push({ kind: 'link:' + rel, url: el.href, path: cssPath(el) }); if (/icon/.test(rel)) out.favicons.push(el.href); continue; }
    if (el.getAttribute('src')) out.media.push({ kind: el.nodeName.toLowerCase(), url: el.src || new URL(el.getAttribute('src'), location.href).href, path: cssPath(el) });
    if (el.nodeName === 'VIDEO' && el.poster) out.media.push({ kind: 'poster', url: el.poster, path: cssPath(el) });
  }
  for (const v of document.querySelectorAll('video')) {
    out.videos.push({ path: cssPath(v), poster: v.getAttribute('poster'), controls: v.hasAttribute('controls'), playsinline: v.hasAttribute('playsinline') || v.playsInline, preload: v.getAttribute('preload'), sources: [...v.querySelectorAll('source')].map((s) => s.src).concat(v.getAttribute('src') ? [v.src] : []), visible: vis(v), width: v.getBoundingClientRect().width });
  }
  // 5. Overflow (C6)
  const se = document.scrollingElement || document.documentElement;
  const offenders = [];
  if (se.scrollWidth > vw + 1) {
    for (const el of document.body.querySelectorAll('*')) {
      const r = el.getBoundingClientRect();
      if (r.right > vw + 1 && r.width > 0 && vis(el)) { offenders.push({ path: cssPath(el), right: Math.round(r.right), text: (el.innerText || '').slice(0, 60) }); if (offenders.length > 6) break; }
    }
  }
  out.overflow = { scrollWidth: se.scrollWidth, innerWidth: vw, offenders };
  // Sticky/fixed header bottom (C6 anchors)
  for (const el of document.querySelectorAll('header,nav,[class*=top],[class*=bar],[class*=mini]')) {
    const cs = getComputedStyle(el);
    if ((cs.position === 'sticky' || cs.position === 'fixed') && vis(el)) { const r = el.getBoundingClientRect(); if (r.top <= 2 && r.height < window.innerHeight / 2) out.sticky = Math.max(out.sticky, r.bottom); }
  }
  // 6. Style samples (C5)
  const fam = (el) => el ? getComputedStyle(el).fontFamily.split(',')[0].replace(/["']/g, '').trim() : null;
  const firstVis = (sel) => [...document.querySelectorAll(sel)].find((e) => vis(e));
  // Body = the family carrying most of the running text (p, li, td, dd); display = the family of h1/h2 headings.
  // Weighted by characters so one mono caption does not count as the page's body font.
  const weigh = (sel) => { const w = new Map(); for (const e of document.querySelectorAll(sel)) { if (!vis(e)) continue; const n = (e.innerText || '').length; if (!n) continue; const f = fam(e); w.set(f, (w.get(f) || 0) + n); } return [...w.entries()].sort((a, b) => b[1] - a[1]); };
  const bw = weigh('p, li, td, dd');
  out.styles.body = bw.length ? bw[0][0] : fam(document.body);
  out.styles.bodyMix = bw.slice(0, 4).map(([f, n]) => `${f}:${n}`);
  out.styles.display = [...new Set(weigh('h1, h2').slice(0, 1).map((x) => x[0]))];
  out.styles.buttons = [];
  for (const b of [...document.querySelectorAll('button, input[type=submit], a.btn, a.button, .button, .wp-element-button, [class*=btn]')].filter((e) => vis(e)).slice(0, 40)) {
    const cs = getComputedStyle(b);
    out.styles.buttons.push({ label: (b.innerText || b.value || '').trim().slice(0, 40), font: cs.fontFamily.split(',')[0].replace(/["']/g, '').trim(), radius: cs.borderTopLeftRadius, bg: cs.backgroundColor, color: cs.color, border: cs.borderTopColor + ' ' + cs.borderTopWidth, weight: cs.fontWeight, transform: cs.textTransform, path: cssPath(b) });
  }
  out.styles.links = [...new Set([...document.querySelectorAll('main a, article a, .content a, a')].filter((e) => vis(e) && !e.closest('nav,header,footer,#adminmenu,#wpadminbar')).slice(0, 60).map((a) => getComputedStyle(a).color))];
  // 7. Empty boxes (C3): visible containers with no content at all
  for (const el of document.querySelectorAll('ul,ol,tbody,table,dl,[class*=list],[class*=feed],[class*=widget],[class*=card],[class*=panel],.postbox,.inside,section,article')) {
    if (!vis(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.height < 8) continue;
    if ((el.innerText || '').trim()) continue;
    if (el.querySelector('img,svg,canvas,input,select,textarea,video,iframe,button,picture,object')) continue;
    if (el.closest('[aria-hidden=true]') || el.closest('#wpadminbar')) continue;
    out.empties.push({ path: cssPath(el), h: Math.round(r.height), w: Math.round(r.width) });
  }
  // 8. Clickables (C2, C10)
  for (const el of document.querySelectorAll('a[href],button,input[type=submit],input[type=button],summary,[role=button],[role=tab]')) {
    if (!vis(el)) continue;
    const form = el.form || el.closest('form');
    out.clickables.push({ kind: el.nodeName.toLowerCase(), type: el.type || '', label: (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 80), href: el.getAttribute('href') || '', formMethod: form ? (form.getAttribute('method') || 'get').toLowerCase() : '', path: cssPath(el) });
  }
  // 9. B4 layout probe: mid-word breaks and orphaned French punctuation
  if (opts && opts.b4) {
    const lineTop = (node, i) => { const r = document.createRange(); r.setStart(node, i); r.setEnd(node, i + 1); const rs = r.getClientRects(); return rs.length ? rs[0] : null; };
    for (const n of textNodes) {
      const s = n.nodeValue;
      if (s.length > 4000) continue;
      const p = n.parentElement;
      const ws = getComputedStyle(p).whiteSpace;
      if (ws === 'nowrap' || ws === 'pre') continue;
      // word wraps: a word (no spaces) whose range has more than one line box
      const re = /[^\s  ]+/g; let m;
      while ((m = re.exec(s))) {
        const w = m[0];
        if (w.length < 3) continue;
        const r = document.createRange(); r.setStart(n, m.index); r.setEnd(n, m.index + w.length);
        const rects = [...r.getClientRects()].filter((x) => x.width > 0.5);
        if (rects.length > 1) {
          const tops = [...new Set(rects.map((x) => Math.round(x.top)))];
          if (tops.length > 1) {
            // find the break position; a break right after '-', '/', '–' or soft hyphen is acceptable
            let brk = -1; let prevTop = null;
            for (let i = 0; i < w.length; i++) { const lr = lineTop(n, m.index + i); if (!lr) continue; const t = Math.round(lr.top); if (prevTop !== null && t > prevTop + 2) { brk = i; break; } prevTop = t; }
            const before = brk > 0 ? w[brk - 1] : '';
            if (!/[-\/–—­_.@]/.test(before)) out.b4.push({ kind: 'mid-word', word: w, at: brk, path: cssPath(p) });
          }
        }
      }
      // punctuation at the start of a line, or « at the end of a line
      for (let i = 0; i < s.length; i++) {
        const ch = s[i];
        if (!'»;:!?«—'.includes(ch)) continue;
        const cur = lineTop(n, i); if (!cur) continue;
        if (ch === '«') {
          let j = i + 1; while (j < s.length && /[\s  ]/.test(s[j])) j++;
          if (j < s.length) { const nx = lineTop(n, j); if (nx && Math.round(nx.top) > Math.round(cur.top) + 2) out.b4.push({ kind: 'line-ends-with-«', text: s.slice(Math.max(0, i - 20), i + 20), path: cssPath(p) }); }
          continue;
        }
        let k = i - 1; while (k >= 0 && /[\s  ]/.test(s[k])) k--;
        if (k < 0) continue; // starts the node: cannot judge inside this node
        const pv = lineTop(n, k);
        if (pv && Math.round(cur.top) > Math.round(pv.top) + 2) {
          if (ch === '—') {
            const rest = s.slice(i + 1).trim().split(/\s+/);
            if (rest.length <= 2) out.b4.push({ kind: 'orphan-dash', text: s.slice(Math.max(0, i - 25), i + 20), path: cssPath(p) });
          } else out.b4.push({ kind: 'line-starts-with-' + ch, text: s.slice(Math.max(0, i - 25), i + 10), path: cssPath(p) });
        }
      }
    }
  }
  out.bodyText = (document.body.innerText || '').slice(0, 200000);
  return out;
}

// C2: mutation sentinel, attached before clicking a non-submit button.
export function armMutation() {
  window.__mut = 0;
  if (window.__mo) window.__mo.disconnect();
  window.__mo = new MutationObserver((l) => { window.__mut += l.length; });
  window.__mo.observe(document.body, { subtree: true, childList: true, attributes: true, characterData: true });
  return true;
}
