export type JevDecision = {
  route: string
  context: string
  prompt: string
  at: number
}

declare module 'claude-code' {
  interface PluginState {
    'jev-router-mod': { last: JevDecision | null; isHidden: boolean }
  }
}
