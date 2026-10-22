// session-ledger-mod contract: its own $.state. safety-guard-mod's `ledger` contract comes
// from that plugin (listed under `dependencies`); the engine lays it beside this mod's types.
// SafetyGuardLedgerEntry below only names the row shape this mod reads.
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
  }
}
