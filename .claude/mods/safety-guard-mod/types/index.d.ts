export type SafetyGuardEntry = {
  at: string
  kind: 'rewrite' | 'block' | 'ask'
  rule: string
  command: string
  rewritten?: string
  outcome?: 'allow' | 'block'
}

export type SafetyGuardPending = {
  rule: string
  command: string
}

declare module 'claude-code' {
  interface PluginState {
    'safety-guard-mod': {
      ledger: SafetyGuardEntry[]
      pending: SafetyGuardPending | null
    }
  }
}
