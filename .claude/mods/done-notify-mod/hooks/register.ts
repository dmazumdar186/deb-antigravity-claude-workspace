import type { Register, TurnUsage } from 'claude-code'

// Main-loop turn tracking only (agentId === undefined). Kept in module scope.
let startedAt: number | undefined
let tokens = 0

/** Tokens summed: input + output + cache read + cache creation (write). */
export const sumUsage = (u?: TurnUsage): number =>
  u ? u.input_tokens + u.output_tokens + u.cache_read_input_tokens + u.cache_creation_input_tokens : 0

export const fmtElapsed = (ms: number): string => {
  const s = Math.max(0, Math.round(ms / 1000))
  return `${Math.floor(s / 60)}m${s % 60}s`
}

export const register: Register = (on) => {
  const elapsed = (now: number): string => fmtElapsed(startedAt === undefined ? 0 : now - startedAt)
  const quietNotify = async (n: (t: string) => Promise<unknown>, text: string) => {
    try { await n(text) } catch { /* no surface / refused: ignore */ }
  }

  on('turn.start', async ($, e, next) => {
    if (e.agentId === undefined) { startedAt = await $.clock.now(); tokens = 0 }
    return next(e)
  })

  // Per-step usage so "tokens so far" is live mid-turn.
  on('turn.step', async function* ($, e, next) {
    const r = yield* next(e)
    if (e.agentId === undefined) tokens += sumUsage(r.usage ?? undefined)
    return r
  })

  on('turn.complete', async ($, e, next) => {
    if (e.agentId !== undefined) return next(e)
    const now = await $.clock.now()
    const ms = typeof e.durationMs === 'number' ? e.durationMs : now - (startedAt ?? now)
    const t = e.usage ? sumUsage(e.usage) : tokens
    const text = `Done in ${fmtElapsed(ms)} · ${t} tokens`
    $.ui.toast(text)
    await quietNotify((x) => $.ui.notify(x), text)
    startedAt = undefined
    return next(e)
  })

  // Engine-raised notifications arrive as the settings hook event `Notification`.
  on('classic.Notification', async ($, e, next) => {
    if (!e.message.startsWith('Question waiting') && !e.message.startsWith('Done in')) {
      $.ui.toast(`Notification: ${e.message} · ${elapsed(await $.clock.now())} · ${tokens} tokens`)
    }
    return next(e)
  }).catch(($, e, next) => (next.called ? {} : next(e)))

  on('tool.call', async ($, e, next) => {
    if (e.tool === 'AskUserQuestion') {
      const text = `Question waiting · ${elapsed(await $.clock.now())} · ${tokens} tokens`
      $.ui.toast(text)
      void quietNotify((x) => $.ui.notify(x), text)
    }
    return next(e)
  }).catch(($, e, next) => (next.called ? { result: { text: '', isError: false } } : next(e)))
}
