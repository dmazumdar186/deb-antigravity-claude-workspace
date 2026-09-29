'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { descHtml } = require('./adbuilder.js');
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

test('test_adbuilder_desc_renders_and_escapes', () => {
  assert.equal(descHtml('<script>alert(1)</script>', esc), '<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>');
  assert.equal(descHtml('line one\nline two', esc), '<p>line one<br>line two</p>');
  assert.equal(descHtml('para one\n\npara two', esc), '<p>para one</p><p>para two</p>');
  assert.equal(descHtml('para one\r\n \r\npara two', esc), '<p>para one</p><p>para two</p>', 'CRLF and whitespace-only blank lines split paragraphs');
  assert.equal(descHtml('Duties\n• Survey\n- Report\n* Plan & write', esc), '<p>Duties</p><ul><li>Survey</li><li>Report</li><li>Plan &amp; write</li></ul>');
  assert.equal(descHtml('', esc), '');
});
