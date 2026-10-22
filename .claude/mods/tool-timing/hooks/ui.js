// Pure UI helpers. No engine access; each plugin contains its own copy.
export function clean(value, limit = 9000) {
  return String(value ?? '').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f]/g, '').slice(0, limit)
}
export function text(E, value, props = {}) {
  return E.Text({ ...props, children: [clean(value)] })
}
export function code(E, value, language = 'text') {
  return E.Code({ source: clean(value), language })
}
export function row(E, children) {
  return E.Box({ flexDirection: 'row', columnGap: 2, flexWrap: 'wrap', children })
}
export function frame(E, title, subtitle, children) {
  return E.Box({ flexDirection: 'column', gap: 1, children: [
    text(E, title, { bold: true, color: 'cyan' }),
    text(E, subtitle, { dimColor: true }), ...children,
  ] })
}
export function bar(percent, width = 24) {
  const p = Math.max(0, Math.min(100, Number(percent) || 0))
  const n = Math.round(p / 100 * width)
  return '[' + '#'.repeat(n) + '-'.repeat(width - n) + '] ' + p.toFixed(1) + '%'
}
export function pretty(value) { return JSON.stringify(value, null, 2) }
export function bounded(value, max = 9000) {
  if (value.length > max) throw new Error('Input exceeds ' + max + ' characters. Use a smaller selection.')
  return value
}
export function entries(value) { return value && typeof value === 'object' ? Object.entries(value) : [] }
export function safePath(value) {
  const path = value.trim()
  if (!path || path.startsWith('-') || /[\x00-\x1f]/.test(path)) throw new Error('Enter a path without control characters or leading flags.')
  return path
}
