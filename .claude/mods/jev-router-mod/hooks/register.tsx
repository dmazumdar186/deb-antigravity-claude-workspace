import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { JevDecision } from '../types'

const last = atom({ plugin: 'jev-router-mod', key: 'last' } as const, null)
const isHidden = atom({ plugin: 'jev-router-mod', key: 'isHidden' } as const, false)

export const ARGV = ['python3', 'execution/infrastructure/jev_router.py', 'hook'] as const
export const TIMEOUT_MS = 10_000

async function isEnabled($: EngineInterface, root: string): Promise<boolean> {
  try {
    const text = await $.fs.read(`${root}/.claude/jev/state.json`)
    return !/"enabled": *false/.test(String(text))
  } catch {
    return true // absent = enabled, as in jev-router.sh
  }
}

export function routeOf(context: string): string {
  const tier = /Task tier(?: unclear \(|: )(\w+)/.exec(context)?.[1] ?? '?'
  const skill = /Skill match: `([^`]+)`/.exec(context)?.[1] ?? 'none'
  return `${tier}/${skill}`
}

async function route($: EngineInterface, prompt: string): Promise<string | null> {
  try {
    const root = await $.session.root()
    if (!(await isEnabled($, root))) return null
    let sessionId = ''
    try {
      sessionId = await $.session.id()
    } catch {
      sessionId = ''
    }
    const res = await $.process.run(ARGV, {
      cwd: root,
      stdin: JSON.stringify({ prompt, session_id: sessionId }),
      timeoutMs: TIMEOUT_MS,
    })
    if (res.exitCode !== 0 || !res.stdout.trim()) return null
    const out = JSON.parse(res.stdout)
    const ctx = out?.hookSpecificOutput?.additionalContext
    return typeof ctx === 'string' && ctx.length > 0 ? ctx : null
  } catch {
    return null // python missing, timeout, bad JSON: fail open
  }
}

export const register: Register = on => {
  on('prompt.submit', async ($, e, next) => {
    if (e.origin?.kind === 'plugin' || e.command || e.text.trimStart().startsWith('/')) {
      return next(e)
    }
    const context = await route($, e.text)
    if (context === null) return next(e)
    const decision: JevDecision = {
      route: routeOf(context),
      context,
      prompt: e.text,
      at: await $.clock.now(),
    }
    await update($, last, () => decision)
    await update($, isHidden, () => false)
    return next({ ...e, context: [...(e.context ?? []), context] })
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const d = await read($, last)
    if (e.props.hasSurvey || d === null || (await read($, isHidden))) return next(e)
    const { Box, Button, Text } = $.ui.resolve(e)
    const snippet = d.context.replace(/\s+/g, ' ').slice(0, 80)
    return (
      <Box>
        <Text dimColor>
          jev → {d.route} · {snippet}{' '}
        </Text>
        <Button key="hide" label="Hide" onPress={() => update($, isHidden, () => true)} />
      </Box>
    )
  })
}
