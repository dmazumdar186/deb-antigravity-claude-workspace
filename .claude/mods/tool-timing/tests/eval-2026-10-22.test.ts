import { expect, test } from 'claude-code/testing'
import { world, site } from './fixtures'
const ID = 'tool-timing'

// Eval row: count matches actual calls in a 10-call test.
test('eval: 10 tool calls are counted as 10', async ($, on) => {
  const { state } = world(on)
  await $.session.start({ surface: 'terminal', isInteractive: true, cwd: '/work' })
  for (let i = 0; i < 7; i++) await $.tool.call({ tool: 'Bash', command: 'ls ' + i })
  for (let i = 0; i < 3; i++) await $.tool.call({ tool: 'Read', file_path: '/work/f' + i })
  expect(state.downstream).toBe(10)
  await $.command.run({ command: ID, args: '' })
  const ui = await $.ui.mount(site(ID, 'terminal', 60))
  const bash = await ui.find({ type: 'Text', text: /^Bash\s+7\s/ })
  const read = await ui.find({ type: 'Text', text: /^Read\s+3\s/ })
  console.log('EVAL tool-timing bash=' + (bash ? 7 : 0) + ' read=' + (read ? 3 : 0) + ' of 10')
  expect(bash).toBeDefined()
  expect(read).toBeDefined()
  await ui.unmount()
})
