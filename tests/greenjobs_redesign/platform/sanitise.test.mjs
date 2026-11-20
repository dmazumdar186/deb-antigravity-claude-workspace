// The Worker's description sanitiser (port of build_site.sanitise_html): hostile employer HTML never
// survives into a job page. Benign-sample parity with Python is in parity.test.mjs.
import assert from 'node:assert/strict';
import test from 'node:test';
import { workerModule } from './helpers.mjs';

const { sanitiseHtml, stripTags, descriptionHtml } = await workerModule('render/sanitise.js');
const { renderDescription } = await workerModule('validate.js');
const BASE = 'https://greenjobs.ie/';
const UNSAFE = /<script|<iframe|<img|<svg|<object|<embed|<form|<input|<style|\son[a-z]+\s*=|javascript:|vbscript:|data:text|style=/i;

const HOSTILE = [
  '<script>alert(1)</script>',
  '<SCRIPT SRC=//evil.example/x.js></SCRIPT>',
  '<script src=//evil.example/x.js>',
  '<img src=x onerror=alert(1)>',
  '<img src=x onerror=alert(1)',
  '<p onclick="alert(1)" style="x">t</p>',
  '<a href="javascript:alert(1)">x</a>',
  '<a href="  JaVaScRiPt:alert(1)">x</a>',
  '<a href="&#106;avascript:alert(1)">x</a>',
  '<a href="java\tscript:alert(1)">x</a>',
  '<a href="data:text/html;base64,PHNjcmlwdD4=">x</a>',
  '<a href="vbscript:msgbox(1)">x</a>',
  '<svg onload=alert(1)><circle/></svg>',
  '<iframe src="https://evil.example"></iframe>',
  '<a<x> onmouseover=alert(1)>hover</a>',
  '<scr<script>ipt>alert(1)</scr</script>ipt>',
  '<p>ok</p><img src=x onerror=alert(1) ',
  '<form action=//evil><input name=q></form>',
  '<div style="background:url(javascript:alert(1))">x</div>',
  '<!-- <script>alert(1)</script> --><p>after</p>',
  '<math><mi xlink:href="javascript:alert(1)">x</mi></math>',
];

test('sanitiser: script, event handlers, styles and javascript:/data:/vbscript: URLs never survive', () => {
  for (const h of HOSTILE) {
    const out = sanitiseHtml(h, BASE);
    for (const tag of out.match(/<[^>]*>/g) || []) assert.doesNotMatch(tag, UNSAFE, `${h} -> ${out}`);
    assert.doesNotMatch(out, /<(script|iframe|img|svg)/i, `${h} -> ${out}`);
    // Nothing left can open a tag inside the page template that follows the description.
    assert.doesNotMatch(out, /<[a-z][^>]*$/i, `${h} leaves an open tag: ${out}`);
  }
});

test('sanitiser: safe links are absolutised with rel="noopener nofollow"; structure is kept', () => {
  assert.equal(sanitiseHtml('<p>See <a href="/about">us</a></p>', BASE), '<p>See <a href="https://greenjobs.ie/about" rel="noopener nofollow">us</a></p>');
  assert.equal(sanitiseHtml('<a href="mailto:jobs@example.com">mail</a>', BASE), '<a href="mailto:jobs@example.com" rel="noopener nofollow">mail</a>');
  assert.equal(sanitiseHtml('<h1>Role</h1><ul><li>A</li></ul>', BASE), '<h3>Role</h3><ul><li>A</li></ul>');
  assert.equal(sanitiseHtml('<a href="https://x.example/?a=1&b=&quot;2">q</a>', BASE), '<a href="https://x.example/?a=1&amp;b=%222" rel="noopener nofollow">q</a>');
});

test('plain-text descriptions (console) render as escaped paragraphs; HTML ones are sanitised', () => {
  assert.equal(descriptionHtml('Salary < 50k & bonus\n\nSecond para', BASE, renderDescription), '<p>Salary &lt; 50k &amp; bonus</p><p>Second para</p>');
  assert.equal(descriptionHtml('<p>Hi</p><script>x</script>', BASE, renderDescription), '<p>Hi</p>');
  assert.equal(stripTags('<p>A&amp;B</p><script>bad()</script>'), 'A&B');
});
