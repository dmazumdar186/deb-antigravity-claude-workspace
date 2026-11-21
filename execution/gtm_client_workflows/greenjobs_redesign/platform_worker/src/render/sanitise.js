// Port of build_site.py's employer-HTML sanitiser (sanitise_html and the line tidiers it chains),
// so a description rendered by the Worker is the markup the static build would ship. Allow-list:
// structural tags only, no attributes except an absolute http(s)/mailto/tel href (rel="noopener nofollow").
// Scripts, styles, media, forms, event handlers, style attributes and javascript:/data:/vbscript:/file:
// URLs never survive. Tests: tests/greenjobs_redesign/platform/sanitise.test.mjs.

import { esc } from './lib.js';

const KEEP = new Set(['p', 'br', 'ul', 'ol', 'li', 'b', 'strong', 'i', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'a', 'div', 'span', 'table', 'thead', 'tbody', 'tr', 'td', 'th', 'blockquote', 'hr', 'sup', 'sub']);
const NAMED = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', bull: '•', ndash: '–', mdash: '—', pound: '£', euro: '€', hellip: '…', rsquo: '’', lsquo: '‘', rdquo: '”', ldquo: '“', middot: '·', copy: '©', reg: '®' };

/** html.unescape for the entities employer adverts use (numeric + common named). */
export function unescapeHtml(s) {
  return String(s ?? '').replace(/&(#[0-9]+|#[xX][0-9a-fA-F]+|[a-zA-Z]+);?/g, (m, e) => {
    if (e[0] === '#') {
      const n = e[1] === 'x' || e[1] === 'X' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
      if (!Number.isFinite(n) || n === 0 || n > 0x10ffff || (n >= 0xd800 && n <= 0xdfff)) return '�';
      return String.fromCodePoint(n);
    }
    return Object.prototype.hasOwnProperty.call(NAMED, e) ? NAMED[e] : m;
  });
}

/** strip_tags(): visible text of a fragment, whitespace collapsed. */
export function stripTags(markup) {
  let t = String(markup || '').replace(/<(script|style)\b[\s\S]*?<\/\1>/gi, ' ');
  t = t.replace(/<[^>]+>/g, ' ');
  return unescapeHtml(t).replace(/\s+/g, ' ').trim();
}

const ATTR = /\s+([a-zA-Z:-]+)(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?/g;

function urljoin(base, href) {
  try {
    return new URL(href, base).href;
  } catch {
    return '';
  }
}

export function sanitiseHtml(markup, baseUrl) {
  let out = String(markup || '').replace(/<(script|style|iframe|object|embed|form|input|button|svg|video|audio)\b[\s\S]*?<\/\1\s*>/gi, ' ');
  out = out.replace(/<(img|iframe|input|source|link|meta|br\s*\/?)\b[^>]*>/gi, (m, t) => (t.toLowerCase().startsWith('br') ? '<br>' : ' '));
  out = out.replace(/<!--[\s\S]*?-->/g, ' ');
  // clean_tag pass, repeated until stable: removing one tag can splice a new one together
  // ("<a<x> onmouseover=...>" becomes "<a onmouseover=...>" after one pass; build_site.py runs one pass only).
  for (let i = 0; i < 8; i++) {
    const next = cleanTags(out, baseUrl);
    if (next === out) break;
    out = next;
  }
  // A stray "<" that never formed a tag (e.g. a truncated "<img src=x onerror=..." at the end) can no longer
  // open one inside the page template.
  out = out.replace(/<(?![/a-z])/gi, '&lt;').replace(/<(\/?)([a-z][a-z0-9]*)(?=[^>]*$)/gi, '&lt;$1$2');
  out = out.replace(/[ \t]+/g, ' ');
  out = divsToParagraphs(out);
  out = unwrapBoldLines(out);
  out = bulletsToLists(out);
  out = collapseBlankLines(out).trim();
  return plainHeadings(factsList(out));
}

function cleanTags(markup, baseUrl) {
  return markup.replace(/<(\/?)([a-zA-Z][a-zA-Z0-9]*)((?:\s+[^>]*)?)\s*\/?>/g, (m, closing, rawTag, attrs) => {
    let tag = rawTag.toLowerCase();
    if (!KEEP.has(tag)) return ' ';
    if (tag === 'h1' || tag === 'h2') tag = 'h3';
    if (closing) return `</${tag}>`;
    let keep = '';
    if (tag === 'a') {
      let href = '';
      for (const am of (attrs || '').matchAll(ATTR)) {
        if (am[1].toLowerCase() === 'href') {
          href = am[0].includes('=') ? am[0].split('=').slice(1).join('=').trim().replace(/^["']+|["']+$/g, '') : '';
        }
      }
      if (href && !/^\s*(javascript|data|vbscript|file):/i.test(href)) {
        href = urljoin(baseUrl, unescapeHtml(href));
        if (/^(https?:\/\/|mailto:|tel:)/.test(href)) keep = ` href="${esc(href)}" rel="noopener nofollow"`;
      }
    }
    return `<${tag}${keep}>`;
  });
}

// build_site.MID_SENTENCE_BREAK (eye review r2 m4): a sentence wrapped across two <div>s is one paragraph.
const MID_SENTENCE_BREAK = /([a-z,])[ \t]*<\/div>[ \t]*<div>[ \t]*(?=[a-z])/g;
export function divsToParagraphs(markup) {
  let out = String(markup || '').replace(MID_SENTENCE_BREAK, '$1 ').replace(/<\/?div>/g, (m) => (m.startsWith('</') ? '</p>' : '<p>'));
  for (const [pat, rep] of [[/<p>(?:\s|&nbsp;|&#160;)*<p>/, '<p>'], [/<\/p>(?:\s|&nbsp;|&#160;)*<\/p>/, '</p>']]) {
    const g = new RegExp(pat.source, 'g');
    while (pat.test(out)) out = out.replace(g, rep);
  }
  return out;
}

const SHORT_LINE = /<p>((?:(?!<\/p>|<br>|<ul|<h3)[\s\S]){1,90}?)<\/p>/y;
export function factsList(markup) {
  let pos = 0;
  const items = [];
  for (;;) {
    SHORT_LINE.lastIndex = pos;
    const m = SHORT_LINE.exec(markup);
    if (!m || m[1].replace(/<\/?(?:strong|b|em|i)>/g, '').includes('<')) break;
    items.push(m[1].trim());
    pos = SHORT_LINE.lastIndex;
  }
  if (items.length < 3 || !items.some((i) => i.includes(':'))) return markup;
  return '<ul class="facts">' + items.map((i) => `<li>${i}</li>`).join('') + '</ul>' + markup.slice(pos);
}

const HEADING_LINE = /<p>((?:[A-Z][A-Za-z'&/-]*)(?: (?:[A-Za-z'&/-]+)){0,4})<\/p>(?=\s*(?:<[uo]l>|<p>[^<]{20,}))/g;
export const plainHeadings = (markup) => markup.replace(HEADING_LINE, (m, h) => `<h3>${h}</h3>`);

const BULLET_LINE = /^\s*(?:[*•·▪–-]|&bull;|&#8226;)\s+([\s\S]*\S)\s*$/;
const LINE_SEPS = new Set(['<p>', '</p>', '<br>', '<div>', '</div>']);
export function bulletsToLists(markup) {
  const tokens = String(markup || '').split(/(<\/?p>|<br>|<\/?div>)/);
  const out = [];
  const items = [];
  let held = [];
  const flush = () => {
    if (!items.length) return;
    if (out.length && out[out.length - 1] === '<p>') {
      out.pop();
      if (held.length && held[0] === '</p>') held.shift();
    }
    out.push('<ul>' + items.map((i) => `<li>${i}</li>`).join('') + '</ul>');
    items.length = 0;
  };
  for (const t of tokens) {
    if (LINE_SEPS.has(t)) {
      (items.length ? held : out).push(t);
      continue;
    }
    const m = BULLET_LINE.exec(t);
    if (m) {
      items.push(m[1].trim());
      held = [];
      continue;
    }
    if (!t.trim() && items.length) continue;
    flush();
    out.push(...held);
    held = [];
    out.push(t);
  }
  flush();
  out.push(...held);
  return out.join('');
}

export function unwrapBoldLines(markup) {
  let out = String(markup || '').replace(/<(strong|b)>((?:\s|<br>|&nbsp;|&#160;)*)<\/\1>/g, '$2');
  out = out.replace(/(?:(?<=<p>)|(?<=<br>)|(?<=<li>)|^)\s*<(strong|b)>((?:(?!<\/?(?:strong|b)>)[\s\S])*?)<\/\1>\s*(?=<br>|<\/p>|<\/li>|$)/g, '$2');
  return out;
}

export function collapseBlankLines(markup) {
  let out = String(markup || '').replace(/<p>(?:\s|&nbsp;|&#160;|<br>)*<\/p>/g, '');
  out = out.replace(/(<p>)(?:\s*<br>)+\s*/g, '$1');
  out = out.replace(/\s*(?:<br>\s*)+(<\/p>)/g, '$1');
  out = out.replace(/(<\/p>|<\/ul>|<\/ol>|<\/h3>)(?:\s*<br>)+\s*/g, '$1');
  return out.replace(/(\s*<br>\s*){3,}/g, '<br><br>');
}

// A description is stored as employer HTML (imports) or plain text (console). Plain text renders as escaped
// paragraphs (validate.renderDescription); HTML goes through the allow-list above.
const LOOKS_HTML = /<\/?(p|br|ul|ol|li|div|b|strong|em|i|u|h[1-6]|a|span|table|tr|td|blockquote)\b[^>]*>/i;
export function descriptionHtml(text, baseUrl, renderPlain) {
  const s = String(text || '');
  return LOOKS_HTML.test(s) ? sanitiseHtml(s, baseUrl) : renderPlain(s);
}
