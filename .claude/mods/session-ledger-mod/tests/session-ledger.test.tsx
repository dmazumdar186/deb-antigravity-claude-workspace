import { expect, test } from 'claude-code/testing'
import type { On } from 'claude-code'
import type { Engine } from 'claude-code/testing'

const PANE = {
  plugin: 'session-ledger-mod',
  component: 'Pane',
  requestId: 'session-ledger',
  props: {
    title: 'Session ledger',
    isFocused: false,
    bodyColumns: 60,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 40 },
    view: {},
  },
} as const

const FILES = ['execution/a.py', 'directives/b.md', 'deliverables/c.md', 'projects/d.ts', 'tests/e.py']
const HEADINGS = [
  '# Workspace Handoff — ',
  '## Where we ended',
  '## What was NOT done today — gap list',
  '## Lessons captured today (do NOT repeat)',
  '## Live endpoints (for mobile spot-checks)',
  '## Recommended next-session opening',
]

function engine(on: On, writes: Array<{ path: string; text: string }>) {
  on('command.register', () => ({ value: { command: 'session-ledger' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.toast', () => ({ value: undefined }))
  on('session.root', () => ({ value: '/ws' }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('tool.call', () => ({ result: {} }))
  on('fs.write', (_, e) => {
    writes.push({ path: e.path, text: e.text })
    return { value: undefined }
  })
}

async function fiveEdits($: Engine) {
  await $.session.start({ cwd: '/ws', surface: 'desktop', isInteractive: true })
  for (const [i, f] of FILES.entries()) {
    if (i % 2 === 0) await $.tool.call({ tool: 'Edit', file_path: `/ws/${f}`, old_string: 'a', new_string: 'b' })
    else await $.tool.call({ tool: 'Write', file_path: f, content: 'x' })
  }
}

test('pane lists the 5 edited files under their group headings', async ($, on) => {
  const writes: Array<{ path: string; text: string }> = []
  engine(on, writes)
  await fiveEdits($)
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  let found = 0
  for (const [i, f] of FILES.entries()) {
    const group = ['execution/', 'directives/', 'deliverables/', 'projects/', 'tests/'][i]!
    if ((await ui.find({ type: 'Text', text: new RegExp(`^${group} \\(1\\)$`) })) && (await ui.find({ type: 'Text', text: new RegExp(f) })))
      found++
  }
  expect(found).toBe(5)
  expect((await ui.find({ type: 'Text', text: /Files edited this session \(5\)/ }))?.text).toBe('Files edited this session (5)')
  await ui.unmount()
})

test('flat edited-file set equals the git-status-style expected set', async ($, on) => {
  const writes: Array<{ path: string; text: string }> = []
  engine(on, writes)
  await fiveEdits($)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  const rows = await ui.findAll({ type: 'Text', text: /^  \S/ })
  const got = rows.map(r => (r.text ?? '').trim())
  expect([...new Set(got)].sort()).toEqual([...FILES].sort())
  expect(got.length).toBe(FILES.length)
  await ui.unmount()
})

test('turn.complete after 5 edits writes exactly one handoff with the six headings', async ($, on) => {
  const writes: Array<{ path: string; text: string }> = []
  engine(on, writes)
  on('prompt.submit', (_, e) => ({ text: e.text }) as never)
  on('turn.complete', () => ({ text: '' }))
  await $.prompt.submit({ text: 'Fix the lead scraper today please' } as never)
  await fiveEdits($)
  const turn = { answer: '', durationMs: 1, isAborted: false, turnId: 't1', reason: 'answer' } as const
  await $.turn.complete(turn)
  await $.turn.complete({ ...turn, turnId: 't2' })
  expect(writes.length).toBe(1)
  expect(writes[0]!.path).toMatch(/^\/ws\/\.claude\/handoffs\/HANDOFF_\d{4}-\d{2}-\d{2}_fix-the-lead-scraper\.md$/)
  const heads = writes[0]!.text.split('\n').filter(l => /^##? /.test(l))
  expect(heads.length).toBe(6)
  heads.forEach((h, i) => expect(h.startsWith(HEADINGS[i]!)).toBe(true))
  for (const f of FILES) expect(writes[0]!.text.includes(f)).toBe(true)
})

test('the Write handoff now button writes a file', async ($, on) => {
  const writes: Array<{ path: string; text: string }> = []
  engine(on, writes)
  await $.session.start({ cwd: '/ws', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  await ui.press({ key: 'write-handoff' })
  expect(writes.length).toBe(1)
  expect(writes[0]!.path).toMatch(/HANDOFF_.*_session\.md$/)
  await ui.unmount()
})
