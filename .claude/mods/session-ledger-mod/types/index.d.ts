// session-ledger-mod contract: its own $.state, plus an ambient mirror of
// safety-guard-mod's `ledger` state contract (read cross-plugin, never written).
export type SessionLedgerHook = { tool: string; outcome: 'ok' | 'isError' | 'deny' }
export type SessionLedgerHandoff = { path: string; fileCount: number }
export type SafetyGuardLedgerEntry = {
  at: number | string
  kind: 'rewrite' | 'block' | 'ask'
  rule: string
  command: string
  rewritten?: string
}

declare module 'claude-code' {
  interface PluginState {
    'session-ledger-mod': {
      files: string[]
      hooks: SessionLedgerHook[]
      directives: string[]
      firstPrompt: string
      handoff: SessionLedgerHandoff | null
    }
    'safety-guard-mod': {
      ledger: SafetyGuardLedgerEntry[]
    }
  }
}
