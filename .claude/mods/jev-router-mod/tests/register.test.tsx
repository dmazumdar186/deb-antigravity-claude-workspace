import { expect, test } from 'claude-code/testing'

const CTX =
  "[jev] Task tier: standard (confidence 0.91). Delegate the work to ONE sub-agent with model `claude-opus-5-5`.\n[jev] Skill match: `gmail` (confidence 0.80). Load it with the Skill tool before working."
const BAND = {
  plugin: 'jev-router-mod',
  component: 'AbovePrompt',
  surface: 'terminal',
  props: { hasSurvey: false },
} as const

function engine(on: any, run: (argv: readonly string[], init: any) => any) {
  const seen: { argv?: readonly string[]; init?: any; submitted?: any } = {}
  on('session.root', () => ({ value: '/work' }))
  on('session.id', () => ({ value: 'sess-1' }))
  on('clock.now', () => ({ value: 1000 }))
  on('fs.read', () => {
    throw new Error('ENOENT')
  })
  on('process.run', (_: any, e: any) => {
    seen.argv = e.argv
    seen.init = e.init
    return { value: run(e.argv, e.init) }
  })
  on('prompt.submit', (_: any, e: any) => {
    seen.submitted = e
    return { text: e.text, context: e.context }
  })
  return seen
}

const ok = (stdout: string, exitCode = 0) => ({
  exitCode, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false,
})

test('attaches the routing line as context and draws the band', async ($, on) => {
  const seen = engine(on, () =>
    ok(JSON.stringify({ hookSpecificOutput: { hookEventName: 'UserPromptSubmit', additionalContext: CTX } })),
  )
  await $.prompt.submit({ text: 'fix the failing gmail test please' } as any)
  expect(seen.argv).toEqual(['python3', 'execution/infrastructure/jev_router.py', 'hook'])
  expect(seen.init.cwd).toBe('/work')
  expect(seen.init.timeoutMs).toBe(10000)
  expect(JSON.parse(seen.init.stdin)).toEqual({ prompt: 'fix the failing gmail test please', session_id: 'sess-1' })
  expect(seen.submitted.text).toBe('fix the failing gmail test please')
  expect(seen.submitted.context).toEqual([CTX])

  const ui = await $.ui.mount(BAND as any)
  const line = await ui.find({ type: 'Text', text: /jev → standard\/gmail/ })
  expect(line).toBeDefined()
  await ui.unmount()
})

test('fails open on a bad exit or bad JSON', async ($, on) => {
  let n = 0
  const seen = engine(on, () => (n++ === 0 ? ok('', 1) : ok('not json')))
  await $.prompt.submit({ text: 'first prompt that fails' } as any)
  expect(seen.submitted.context).toBeUndefined()
  await $.prompt.submit({ text: 'second prompt that fails' } as any)
  expect(seen.submitted.context).toBeUndefined()
})
