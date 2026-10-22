import type { EngineInterface, Register } from 'claude-code'

import type { SafetyGuardEntry, SafetyGuardPending } from '../types'

const LEDGER = { plugin: 'safety-guard-mod', key: 'ledger' } as const
const PENDING = { plugin: 'safety-guard-mod', key: 'pending' } as const
const AUTO_BLOCK_MS = 20_000
const LEDGER_MAX = 500

type Outcome = 'allow' | 'block'

// Hard rules: no safe rewrite, blocked silently. Ported from
// .claude/hooks/safety-guard.sh (case-insensitive substring). The four
// settings.json permissions.deny entries are hardcoded rather than read per
// call: Bash(rm -rf *) and Bash(git reset --hard *) are covered by the
// rewrite-or-block path below, Bash(git push --force *) and Bash(git push -f *)
// by this list.
const HARD = [
  'rm -r /',
  'git push --force',
  'git push -f ',
  'drop table',
  'drop database',
  'format c:',
  'mkfs',
  'dd if=',
  ':(){:|:&};',
]
const ROOT_RM = /\brm\s+(-[a-z]+\s+)*(\/|\/\*)(\s|$)/i
// Shell-script rules that are rewritable; blocked when the command is too
// complex (chained, quoted) to rewrite safely.
const REWRITABLE = ['rm -rf', 'git reset --hard', 'git checkout -- .', 'git clean -f']
// A command simple enough to rewrite: no chaining, substitution or quoting.
const SIMPLE = /^[\w@%+=:,./~*\s-]+$/
// Fast pre-filter: a command with none of these never reaches the rules.
const TRIGGER = /rm|git|drop|delete|truncate|format|mkfs|dd|:\(\)/i

const has = (cmd: string, pat: string) => cmd.toLowerCase().includes(pat.toLowerCase())
const stamp = (ms: number) => new Date(ms).toISOString().replace(/[:.]/g, '-')

type Rewrite = { rule: string; command: string } | { rule: string; ask: true }

function rewrite(cmd: string, ts: string, iso: string): Rewrite | undefined {
  const c = cmd.trim()
  if (!SIMPLE.test(c)) return undefined
  const rm = /^rm((?:\s+-[rRf]+)*)\s+(.+)$/.exec(c)
  if (rm) {
    const paths = (rm[2] ?? '').split(/\s+/)
    const outside = paths.some(
      p =>
        p.startsWith('/') ||
        p.startsWith('~') ||
        p.startsWith('-') ||
        p.split('/').includes('..') ||
        /^[*.]+$/.test(p),
    )
    if (outside) return { rule: 'rm outside repo', ask: true }
    const dir = `state/.trash/${ts}`
    return { rule: 'rm', command: `mkdir -p ${dir} && mv ${paths.join(' ')} ${dir}/` }
  }
  if (/^git\s+reset\s+--hard(\s+.*)?$/i.test(c)) {
    return { rule: 'git reset --hard', command: `git stash push -u -m "safety-guard ${iso}" ; ${c}` }
  }
  if (/^git\s+checkout\s+--\s+\.$/.test(c)) {
    return { rule: 'git checkout -- .', command: `git stash push -m "safety-guard ${iso}" ; ${c}` }
  }
  const clean = /^git\s+clean\s+(.*)$/i.exec(c)
  const flags = clean?.[1] ?? ''
  if (clean && /(^|\s)-[a-z]*f/i.test(flags)) {
    const dry = flags.replace(/(^|\s)-([a-z]*)f([a-z]*)/gi, '$1-$2n$3')
    return {
      rule: 'git clean -f',
      command: `git clean ${dry} # safety-guard-mod: dry run of "${c}" (git clean -f deletes untracked files)`,
    }
  }
  return undefined
}

function hardRule(cmd: string): string | undefined {
  if (ROOT_RM.test(cmd)) return 'rm on /'
  return HARD.find(p => has(cmd, p))
}

function softRule(cmd: string): string | undefined {
  const lower = cmd.toLowerCase()
  if (lower.includes('delete from')) return /\bwhere\b/.test(lower) ? 'DELETE FROM' : 'DELETE FROM without WHERE'
  if (lower.includes('truncate table')) return 'truncate table'
  if (lower.includes('git clean')) return 'git clean'
  return undefined
}

async function log($: Pick<EngineInterface, 'state'>, entry: SafetyGuardEntry) {
  const held = await $.state.get(LEDGER)
  await $.state.set(LEDGER, [...(held.value ?? []), entry].slice(-LEDGER_MAX))
}

export const register: Register = on => {
  let answer: ((o: Outcome) => void) | undefined

  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const cmd = e.command
    if (!TRIGGER.test(cmd)) return next(e)

    const now = await $.clock.now()
    const iso = new Date(now).toISOString()

    // Step 2 (checked first so a rewrite never launders a hard rule).
    const hard = hardRule(cmd)
    if (hard) {
      await log($, { at: iso, kind: 'block', rule: hard, command: cmd })
      return { deny: `safety-guard-mod: blocked ${hard}: ${cmd}` }
    }

    // Step 1: silent safe rewrite.
    const rw = rewrite(cmd, stamp(now), iso)
    if (rw && 'command' in rw) {
      await log($, { at: iso, kind: 'rewrite', rule: rw.rule, command: cmd, rewritten: rw.command })
      $.ui.toast(`safety-guard: rewrote ${rw.rule} to a safe form`)
      return next({ ...e, command: rw.command })
    }

    const soft = rw ? rw.rule : softRule(cmd)
    const unrewritable = REWRITABLE.find(p => has(cmd, p))
    if (!soft && unrewritable) {
      await log($, { at: iso, kind: 'block', rule: unrewritable, command: cmd })
      return { deny: `safety-guard-mod: blocked ${unrewritable}: ${cmd}` }
    }
    if (!soft) return next(e)

    // Step 3: the band; Block by default after 20 s.
    await $.state.set(PENDING, { rule: soft, command: cmd } satisfies SafetyGuardPending)
    const outcome = await new Promise<Outcome>(resolve => {
      const timer = $.clock.after(AUTO_BLOCK_MS, () => resolve('block'))
      answer = o => {
        timer.cancel()
        resolve(o)
      }
    })
    answer = undefined
    await $.state.set(PENDING, null)
    await log($, { at: iso, kind: 'ask', rule: soft, command: cmd, outcome })
    return outcome === 'allow' ? next(e) : { deny: `safety-guard-mod: blocked ${soft}: ${cmd}` }
  }).catch(($, e, next) =>
    // Failed or overran the 10 s hook budget: fall to the band's default, Block.
    next.called ? next(e) : { deny: `safety-guard-mod: blocked (guard failed or timed out): ${e.command}` },
  )

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const { value: pending } = await $.state.get(PENDING)
    if (!pending) return next(e)
    const { Box, Button, Text } = $.ui.resolve(e)
    return (
      <Box flexDirection="column">
        <Text color="yellow">safety-guard: {pending.rule}</Text>
        <Text>{pending.command}</Text>
        <Box>
          <Button key="allow" label="Allow once" onPress={() => answer?.('allow')} />
          <Button key="block" label="Block (default in 20 s)" onPress={() => answer?.('block')} />
        </Box>
      </Box>
    )
  })
}
