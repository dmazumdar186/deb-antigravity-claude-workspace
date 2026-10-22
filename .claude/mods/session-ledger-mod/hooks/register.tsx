import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { SafetyGuardLedgerEntry, SessionLedgerHook } from '../types'

const PANE = 'session-ledger'
const TITLE = 'Session ledger'
const EDIT_TOOLS = ['Edit', 'Write', 'MultiEdit', 'NotebookEdit']
const DIR_TOOLS = ['Read', 'Edit', 'Write']
export const GROUPS = ['execution/', 'directives/', 'deliverables/', 'projects/', '.claude/', 'tests/', 'other']
export const HEADINGS = [
  '## Where we ended',
  '## What was NOT done today — gap list',
  '## Lessons captured today (do NOT repeat)',
  '## Live endpoints (for mobile spot-checks)',
  '## Recommended next-session opening',
]

const files = atom({ plugin: 'session-ledger-mod', key: 'files' } as const, [])
const hooks = atom({ plugin: 'session-ledger-mod', key: 'hooks' } as const, [])
const directives = atom({ plugin: 'session-ledger-mod', key: 'directives' } as const, [])
const firstPrompt = atom({ plugin: 'session-ledger-mod', key: 'firstPrompt' } as const, '')
const handoff = atom({ plugin: 'session-ledger-mod', key: 'handoff' } as const, null)
const guardLedger = { plugin: 'safety-guard-mod', key: 'ledger' } as const

type $ = EngineInterface

async function rootOf($: $): Promise<string> {
  try {
    return (await $.session.root()).replace(/\\/g, '/').replace(/\/+$/, '')
  } catch {
    return ''
  }
}

export function relative(root: string, path: string): string {
  const p = path.replace(/\\/g, '/')
  if (root && p.startsWith(root + '/')) return p.slice(root.length + 1)
  return p.replace(/^\.\//, '').replace(/^\/+/, '')
}

export function groupOf(rel: string): string {
  const top = rel.split('/')[0] + '/'
  return GROUPS.includes(top) ? top : 'other'
}

export function grouped(list: readonly string[]): Array<[string, string[]]> {
  return GROUPS.map(g => [g, list.filter(f => groupOf(f) === g)] as [string, string[]]).filter(
    ([, l]) => l.length > 0,
  )
}

async function readGuard($: $): Promise<SafetyGuardLedgerEntry[] | null> {
  try {
    const { value } = await $.state.get(guardLedger)
    return value ?? []
  } catch {
    return null
  }
}

function slugOf(prompt: string): string {
  const s = prompt
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 4)
    .join(' ')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return s || 'session'
}

function summarize(list: readonly SessionLedgerHook[]): string[] {
  const by = new Map<string, { ok: number; isError: number; deny: number }>()
  for (const h of list) {
    const c = by.get(h.tool) ?? { ok: 0, isError: 0, deny: 0 }
    c[h.outcome]++
    by.set(h.tool, c)
  }
  return [...by].map(([t, c]) => `${t}: ok ${c.ok}, isError ${c.isError}, deny ${c.deny}`)
}

export async function writeHandoff($: $): Promise<string> {
  const list = await read($, files)
  const date = new Date().toISOString().slice(0, 10)
  const path = `.claude/handoffs/HANDOFF_${date}_${slugOf(await read($, firstPrompt))}.md`
  const guard = await readGuard($)
  const lines: string[] = [`# Workspace Handoff — ${date}`, '', HEADINGS[0]!, '', '### Files edited this session', '']
  for (const [g, l] of grouped(list)) {
    lines.push(`**${g}** (${l.length})`, ...l.map(f => `- ${f}`), '')
  }
  lines.push('### Hooks fired (last 50 tool calls)', '', ...summarize(await read($, hooks)).map(s => `- ${s}`), '')
  lines.push('### Safety-guard rewrites/blocks', '')
  if (guard === null) lines.push('- safety-guard-mod not loaded')
  else if (guard.length === 0) lines.push('- none')
  else lines.push(...guard.map(g => `- ${g.kind} [${g.rule}] ${g.command}${g.rewritten ? ` -> ${g.rewritten}` : ''}`))
  lines.push('')
  for (const h of HEADINGS.slice(1)) lines.push(h, '', '_Operator: fill in._', '')
  const root = await rootOf($)
  await $.fs.write(root ? `${root}/${path}` : path, lines.join('\n'))
  await update($, handoff, () => ({ path, fileCount: list.length }))
  $.ui.toast(`Handoff written: ${path}`)
  return path
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'session-ledger', description: 'Open the session ledger pane' })
    void $.ui.open({ id: PANE, title: TITLE })
    return next(e)
  })

  on('command.run', { command: 'session-ledger' }, async $ => {
    await $.ui.open({ id: PANE, title: TITLE })
    return { text: 'Session ledger pane opened.' }
  })

  on('prompt.submit', async ($, e, next) => {
    if ((await read($, firstPrompt)) === '' && e.text.trim()) await update($, firstPrompt, () => e.text)
    return next(e)
  })

  on('tool.call', async ($, e, next) => {
    const tool = String(e.tool)
    const input = e as unknown as { file_path?: unknown; notebook_path?: unknown }
    const raw = typeof input.file_path === 'string' ? input.file_path : typeof input.notebook_path === 'string' ? input.notebook_path : undefined
    const rel = raw === undefined ? undefined : relative(await rootOf($), raw)
    if (rel !== undefined && EDIT_TOOLS.includes(tool)) {
      await update($, files, l => (l.includes(rel) ? l : [...l, rel]))
    }
    if (rel !== undefined && DIR_TOOLS.includes(tool) && rel.startsWith('directives/')) {
      await update($, directives, l => (l.includes(rel) ? l : [...l, rel]))
    }
    const ran = await next(e)
    const r = ran as { deny?: unknown; isError?: unknown }
    const outcome: SessionLedgerHook['outcome'] = typeof r.deny === 'string' ? 'deny' : r.isError ? 'isError' : 'ok'
    await update($, hooks, l => [...l, { tool, outcome }].slice(-50))
    return ran
  })

  on('turn.complete', async ($, e, next) => {
    if (e.agentId === undefined) {
      const count = (await read($, files)).length
      const last = await read($, handoff)
      if (count >= 5 && (last === null || last.fileCount !== count)) await writeHandoff($)
    }
    return next(e)
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button } = $.ui.resolve(e)
    const list = await read($, files)
    const hookList = await read($, hooks)
    const dirs = await read($, directives)
    const guard = await readGuard($)
    const room = Math.max(1, (e.viewport?.rows ?? 24) - 12)
    const paths = list.slice(0, room)
    return (
      <Box flexDirection="column">
        <Text bold>Files edited this session ({list.length})</Text>
        {list.length === 0 && <Text dimColor>None yet.</Text>}
        {grouped(paths).map(([g, l]) => (
          <Box flexDirection="column">
            <Text>{`${g} (${list.filter(f => groupOf(f) === g).length})`}</Text>
            {l.map(f => (
              <Text dimColor>{`  ${f}`}</Text>
            ))}
          </Box>
        ))}
        <Text bold>Hooks fired (last {hookList.length})</Text>
        {summarize(hookList).map(s => (
          <Text dimColor>{s}</Text>
        ))}
        <Text bold>Safety-guard rewrites/blocks</Text>
        {guard === null ? (
          <Text dimColor>safety-guard-mod not loaded</Text>
        ) : guard.length === 0 ? (
          <Text dimColor>None.</Text>
        ) : (
          guard.slice(-room).map(g => <Text dimColor>{`${g.kind} ${g.rule}: ${g.command}`}</Text>)
        )}
        <Text bold>Directives touched ({dirs.length})</Text>
        {dirs.slice(0, room).map(d => (
          <Text dimColor>{d}</Text>
        ))}
        <Button key="write-handoff" label="Write handoff now" onPress={() => void writeHandoff($)} />
      </Box>
    )
  })
}
