import { expect, test } from 'claude-code/testing'

const stub = (on: any) => {
  const toasts: string[] = []
  on('ui.toast', (_: unknown, e: { text: string }) => { toasts.push(e.text); return { value: undefined } })
  on('clock.now', () => ({ value: 1_000_000 }))
  on('ui.notify', () => ({ value: { isSent: false, reason: 'no-surface' } }))
  on('tool.call', () => ({ result: {} }))
  on('turn.start', (_: unknown, e: { turnId?: string }) => ({ turnId: e.turnId ?? 't1' }))
  on('turn.complete', () => ({ text: 'ok' }))
  on('classic.Notification', () => ({}))
  return toasts
}

test('turn.start -> turn.complete gives one toast with elapsed and tokens', async ($, on) => {
  const toasts = stub(on)
  await $.turn.start({ text: 'hi', turnId: 't1' } as any)
  await $.turn.complete({
    answer: 'ok', durationMs: 65000, isAborted: false, turnId: 't1',
    usage: { model: 'm', input_tokens: 10, output_tokens: 20, cache_read_input_tokens: 30, cache_creation_input_tokens: 40 },
  } as any)
  expect(toasts.length).toBe(1)
  expect(toasts[0]).toContain('1m5s')
  expect(toasts[0]).toContain('100 tokens')
})

test('a Notification event gives one toast', async ($, on) => {
  const toasts = stub(on)
  await $.classic.Notification({ message: 'Claude needs your permission', notification_type: 'permission_prompt' })
  expect(toasts.length).toBe(1)
  expect(toasts[0]).toContain('Notification: Claude needs your permission')
})

test('an AskUserQuestion tool.call gives one toast', async ($, on) => {
  const toasts = stub(on)
  await $.tool.call({ tool: 'AskUserQuestion', questions: [] } as any)
  expect(toasts.length).toBe(1)
  expect(toasts[0]).toContain('Question waiting')
})
