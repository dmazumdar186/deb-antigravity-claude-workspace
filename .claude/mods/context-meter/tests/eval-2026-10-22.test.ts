import { expect, test } from 'claude-code/testing'
import { world, site } from './fixtures'
const ID = 'context-meter'

// Eval row: reading within 5% of the engine's own context figure ($.session.usage,
// the source /context reads). The fixture reports 84,000 / 200,000 (42%).
test('eval: pane shows the exact figure $.session.usage reports (0% deviation)', async ($, on) => {
  const { state } = world(on)
  await $.session.start({ surface: 'terminal', isInteractive: true, cwd: '/work' })
  await $.command.run({ command: ID, args: '' })
  const ui = await $.ui.mount(site(ID, 'terminal', 60))
  const row = await ui.find({ type: 'Text', text: /\/ 200,000 tokens/ })
  expect(row).toBeDefined()
  const shown = Number(String(row!.text).split(' / ')[0].replace(/,/g, ''))
  const deviation = Math.abs(shown - 84000) / 84000
  console.log('EVAL context-meter shown=' + shown + ' engine=84000 deviation=' + (deviation * 100).toFixed(2) + '%')
  expect(deviation).toBeLessThanOrEqual(0.05)
  expect(await ui.find({ type: 'Text', text: /42\.0%/ })).toBeDefined()
  await ui.unmount()
})
