import { expect, mock, test } from 'claude-code/testing'

const DANGEROUS: [string, 'rewrite' | 'block'][] = [
  ['rm -rf node_modules', 'rewrite'],
  ['rm -rf /', 'block'],
  ['git push --force origin main', 'block'],
  ['git push -f origin main', 'block'],
  ['git reset --hard HEAD~1', 'rewrite'],
  ['git checkout -- .', 'rewrite'],
  ['git clean -fd', 'rewrite'],
  ['psql -c "DROP TABLE users"', 'block'],
  ['dd if=/dev/zero of=/dev/sda', 'block'],
  [':(){:|:&};:', 'block'],
]

const SAFE = [
  'python execution/infrastructure/jev_router.py status',
  'python3 execution/generate_registry.py',
  'git status',
  'git diff --stat',
  'ls -la',
  'cat README.md',
  'echo hi',
  'pip install requests',
  'grep -rn foo .',
  'npm test',
]

function world(on: Parameters<Parameters<typeof test>[1]>[1]) {
  const clock = mock.clock(on, { now: Date.parse('2026-10-22T09:00:00Z') })
  const seen: string[] = []
  const toasts: string[] = []
  const writes: { key: string; value: any }[] = []
  on('state.set', (_$, e, next) => {
    const ev = e as unknown as { key: string; value: unknown }
    writes.push({ key: ev.key, value: ev.value })
    return next(e)
  })
  on('ui.toast', (_$, e) => {
    toasts.push(e.text)
    return { value: undefined }
  })
  on('tool.call', (_$, e) => {
    seen.push((e as { command?: string }).command ?? '')
    return { result: {} }
  })
  return { clock, seen, toasts, writes }
}

test('dangerous commands: blocked or rewritten without the band', async ($, on) => {
  const { seen, toasts, writes } = world(on)
  let handled = 0
  for (const [command, want] of DANGEROUS) {
    seen.length = 0
    const r = await $.tool.call({ tool: 'Bash', command })
    if (want === 'block') {
      expect(r.deny).toContain('safety-guard-mod: blocked')
      expect(seen.length).toBe(0)
    } else {
      expect(r.deny).toBeUndefined()
      expect(seen.length).toBe(1)
      expect(seen[0]).not.toBe(command)
    }
    handled += 1
  }
  expect(toasts.length).toBe(4)
  expect(writes.filter(w => w.key === 'pending').length).toBe(0)
  const ledger = writes.filter(w => w.key === 'ledger').at(-1)?.value as { kind: string }[]
  expect(ledger.length).toBe(10)
  expect(ledger.filter(x => x.kind === 'ask').length).toBe(0)
  console.log(`EVAL dangerous handled ${handled}/10, without prompt ${handled}/10`)
})

test('rewrites have the expected shape', async ($, on) => {
  const { seen } = world(on)
  await $.tool.call({ tool: 'Bash', command: 'rm -rf node_modules' })
  await $.tool.call({ tool: 'Bash', command: 'git reset --hard HEAD~1' })
  await $.tool.call({ tool: 'Bash', command: 'git clean -fd' })
  expect(seen[0]).toMatch(/^mkdir -p state\/\.trash\/2026-10-22T09-00-00-000Z && mv node_modules state\/\.trash\//)
  expect(seen[1]).toMatch(/^git stash push -u -m "safety-guard .*" ; git reset --hard HEAD~1$/)
  expect(seen[2]).toMatch(/^git clean -nd # safety-guard-mod/)
})

test('quoted dangerous text is still blocked (shell parity)', async ($, on) => {
  world(on)
  const r = await $.tool.call({ tool: 'Bash', command: 'echo "rm -rf is dangerous"' })
  expect(r.deny).toContain('rm -rf')
})

test('safe commands pass untouched', async ($, on) => {
  const { seen } = world(on)
  let ok = 0
  for (const command of SAFE) {
    seen.length = 0
    const r = await $.tool.call({ tool: 'Bash', command })
    expect(r.deny).toBeUndefined()
    expect(seen).toEqual([command])
    ok += 1
  }
  console.log(`EVAL safe untouched ${ok}/10`)
})

test('latency: 100 safe calls average under 50 ms', async ($, on) => {
  world(on)
  const t0 = Date.now()
  for (let i = 0; i < 100; i++) {
    await $.tool.call({ tool: 'Bash', command: SAFE[i % SAFE.length] ?? 'ls' })
  }
  const mean = (Date.now() - t0) / 100
  console.log(`EVAL latency mean ${mean.toFixed(2)} ms`)
  expect(mean).toBeLessThan(50)
})

test('band shows and auto-selects Block after 20 s', async ($, on) => {
  const { clock, seen, writes } = world(on)
  const pending = $.tool.call({ tool: 'Bash', command: 'psql -c "DELETE FROM users"' })
  await clock.settle()
  expect(writes.find(w => w.key === 'pending')?.value?.rule).toBe('DELETE FROM without WHERE')
  await clock.advance(20_000)
  const r = await pending
  expect(r.deny).toContain('blocked DELETE FROM')
  expect(seen.length).toBe(0)
  expect(writes.filter(w => w.key === 'ledger').at(-1)?.value.at(-1)).toMatchObject({ kind: 'ask', outcome: 'block' })
})

// Eval row: HITL prompts in a scripted 30-tool-call session (target <= 1).
// 20 safe, 4 rewritable, 5 hard-blocked, 1 ambiguous (the only command that may raise the band).
test('eval: scripted 30-call session raises at most one band', async ($, on) => {
  const { clock, writes } = world(on)
  const script = [
    ...SAFE,
    ...SAFE,
    DANGEROUS[0][0], DANGEROUS[4][0], DANGEROUS[5][0], DANGEROUS[6][0],
    DANGEROUS[1][0], DANGEROUS[2][0], DANGEROUS[7][0], DANGEROUS[8][0], DANGEROUS[9][0],
    'psql -c "DELETE FROM users"',
  ]
  expect(script.length).toBe(30)
  for (const command of script) {
    const p = $.tool.call({ tool: 'Bash', command })
    await clock.settle()
    await clock.advance(21_000)
    await p
  }
  const prompts = writes.filter(w => w.key === 'pending' && w.value).length
  console.log('EVAL hitl prompts=' + prompts + ' of 30 calls')
  expect(prompts).toBeLessThanOrEqual(1)
})
