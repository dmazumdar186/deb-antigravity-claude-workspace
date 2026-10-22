# done-notify-mod

Replaces the old `.claude/hooks/notify-done.sh` sound hooks (Stop, Notification, AskUserQuestion) with toasts plus a native notification. No audio, no network.

## What it hooks
- `turn.start` / `turn.step` (main loop only, `agentId === undefined`): records start time and sums per-step usage.
- `turn.complete` (main loop): toast `Done in <m>m<s>s · <tokens> tokens`, plus `$.ui.notify`.
- `classic.Notification` (the engine's Notification hook event): toast `Notification: <message> · <elapsed> · <tokens>`.
- `tool.call` with `AskUserQuestion`: before the call runs, toast `Question waiting · <elapsed> · <tokens>`, plus `$.ui.notify`.

Tokens = input + output + cache read + cache creation (write). Elapsed uses `e.durationMs` on completion, else the `$.clock.now()` delta from turn start.
`$.ui.notify` failures / `{ isSent: false }` are ignored silently.

## What it draws
Toasts only (top-right stack, or the notification bar in scrollback mode).

## Disable
Run `/plugin`, find `done-notify-mod`, and disable or uninstall it.

## Test
`claude plugin validate .claude/mods/done-notify-mod` and `claude plugin test .claude/mods/done-notify-mod`.
