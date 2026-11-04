# Red-Team Gate for Outward Text (deterministic layer)

## Goal
No client email, negotiation reply, proposal, offer or invite leaves the workspace unvetted. The
operator trusts outputs without cross-checking, so a misquote is shipped as fact (Asset Voyages,
2026-11: "paid text alerts up to ≈ €30" when the €30 in the source was the UptimeRobot + AI cost).
This script is the deterministic half: it grounds claims, keeps a pass ledger keyed on the exact
wording and envelope, binds every pass to logged lens runs, and blocks outward tools until then.
The semantic half (four `redteam-lens` subagents) is run via `/redteam`.

**Output contract:** the operator receives the vetted draft text only; claim tables, verdict files
and ledger rows are machine state under `.tmp/redteam/` and never go into the email or the reply.

## Threat model
The main agent is not malicious, but it cuts corners under pressure: it may skip the reviewers,
write its own "PASS" verdict files, append a pass row, self-waive, tweak a link or recipient after
the pass, or send through Bash instead of the gated tool. The gate makes each of those impossible
**without deliberately forging hook-owned logs**:
- Verdicts count only if `verdicts.jsonl` (written by the SubagentStop hook from a real
  `redteam-lens` run) holds the sha256 of the exact verdict text with the same lens, sha12 and PASS.
- Pass rows are re-verified against `verdicts.jsonl` on every `check`/hook call, so an appended
  row is ignored. Waived rows count only if `waivers.jsonl` (written by the UserPromptSubmit hook
  from the operator's own prompt) holds the sha12.
- Bash commands that call hook-only subcommands or write the ledgers are denied.

**Limit, stated plainly:** the hooks run in the same container as the same user as the agent. True
cryptographic tamper-proofing is impossible here: an agent that edits `verdicts.jsonl` or
`waivers.jsonl` with the Write/Edit tools, briefs a lens to "just output PASS", or edits this
script can defeat it. That is deliberate forgery, not corner-cutting, and is out of scope.
(`hook` also denies Write/Edit/MultiEdit/NotebookEdit on the ledgers if those tools are added to
the PreToolUse matcher.)

## Operator prompts
- "Red team this email" / `/redteam` → ground + 4 lenses + record, then send.
- Skip the gate → the operator types `redteam waive <sha12> <reason>` as their own prompt. There
  is no agent-callable waiver (`waive` prints these instructions and exits 2).

## Inputs
- Draft file (`.txt`/`.md` plain; `.html`/`.htm` HTML). Write the exact text you will send.
- Sources: files or directories (recursed; `.md .txt .html .htm .csv .json .eml .yaml .yml`). The
  draft, the state dir, unsupported types and any file sharing ≥ 60% of the draft's sentences
  ("looks like the draft itself") are skipped and reported.
- Verdict files: the lens subagent's returned text saved verbatim; first 3 non-blank lines exactly
  `LENS: <lens>` / `DRAFT-SHA: <12 hex>` / `VERDICT: PASS|FAIL` (no `>`, `**`, `#`, no reordering).
- Env `REDTEAM_DIR` overrides the state dir (default `.tmp/redteam/`).

## Tools/Scripts
`execution/infrastructure/redteam_gate.py` (stdlib, no network, no LLM):
- `sha --draft PATH` → 12-hex DRAFT-SHA.
- `ground --draft PATH --sources P... [--json]` → claim table; `ground/<sha12>.json`. Exit 0 all
  grounded, 1 any ungrounded or weak (overclaims warn only), 2 usage.
- `record --draft PATH --sources ... --verdicts V1..V4 [--subject S] [--to A..] [--cc A..]
  [--bcc A..] [--attachments PATH..]` → needs 0 ungrounded + 0 weak and four logged PASS
  verdicts on the current sha12. Exit 0 recorded/already, 3 refused (every reason), 2 usage.
- `check --file PATH` → exit 0 passed/waived (re-verified), 3 not.
- Hook handlers (stdin JSON), wired via `.claude/hooks/redteam-outward-gate.sh <mode>`:
  `pre`→`hook` (PreToolUse, fail-closed), `post`→`post-hook` (Gmail drafts), `subagent`→
  `subagent-hook` (SubagentStop), `prompt`→`prompt-hook` (UserPromptSubmit). Settings are owned
  by the orchestrator. The wrapper tries `python3`, `python`, `py`.

## Steps
1. Write the draft to `.tmp/redteam/drafts/<name>.txt` (exact final wording).
2. `ground` against the thread + source docs. Fix or source every ungrounded/weak claim.
3. `sha`, then run four `redteam-lens` subagents; save each returned text verbatim as a verdict file.
4. `record` with the exact subject, recipients and attachments. Any edit → new sha → redo 2-4.
5. Send/draft with the same text and envelope; the hook allows it.

## Outputs (all under the state dir)
- `ground/<sha12>.json` — claims {status grounded|weak|ungrounded|overclaim, source, source_line, hits}.
- `verdicts.jsonl` (SubagentStop) — {lens, sha12, verdict, out_sha256, agent_id, agent_type, transcript_path, text_from, ts}.
- `passes.jsonl` — {sha256, sha12, draft, sources, lenses, verdicts[{lens, out_sha256}], subject_sha, to, cc, bcc, attachments, claims_*, ts, waived}; operator waivers {sha12, waived: true, reason, ts, by}.
- `waivers.jsonl` (UserPromptSubmit) — {sha12, reason, ts, session_id, source}.
- `drafts.jsonl` (PostToolUse) — {draft_id, sha256, sha256s, ts}.

## Hook rules (PreToolUse, fail-closed)
- **Gmail** `send_message|reply|forward|create_draft|update_draft`, and any other Gmail tool whose
  name contains send/reply/forward/draft (except get_/list_/search_/delete_/trash_): every input
  key outside the metadata allowlist (to, cc, bcc, draftId, messageId, threadId, replyThreadId,
  replyToMessageId, includeSignature, replyAll, attachments; `subject` is envelope-checked) is
  outward text and needs a passed sha. Unknown keys (`message`, `text`, …) are gated, not ignored.
  Envelope: subject (if given) must equal the recorded `--subject`; to/cc/bcc (if given) must each
  be a subset of the recorded set; every attachment's decoded base64 sha256 must be recorded.
  Reply/forward without subject skip the subject check. Send-by-draftId needs the draft's latest
  `drafts.jsonl` text to be passed; envelope-only `update_draft` is checked against that text;
  `create_draft` with subject/recipients but no body is denied.
- **Calendar** `create_event|update_event`: gated when attendees are present (an invite emails
  people) or, for `update_event`, unless `notificationLevel` is `NONE`. `description` needs a passed
  sha; `summary` passes as its own passed text or as the `--subject` of the description's pass.
- **Bash**: deny inline senders (smtplib, sendmail, Gmail REST `/send`, `messages().send(`,
  Instantly emails/reply, SendGrid, Resend, Postmark) in the command or in a script it runs
  directly, unless the command only runs a git-tracked, unmodified `.py`/`.sh` (optional leading
  `cd X &&`, no `-c`, heredoc, pipes or chaining). Also denies hook-only `redteam_gate.py`
  subcommands/imports and writes to the ledgers. Everything else is allowed with no git call.
- HTML canonicalisation (record and hook share it): `href`/`src`/`alt` and comment text become
  visible (` [link: URL] `, ` [img: URL] `, ` [comment: …] `); empty `<script>/<style>` are dropped,
  non-empty ones deny outright. Malformed input or any exception → deny.

## Grounding
Money, percent, number+unit, dates, quotes ≥ 3 words, names, and an EN+FR overclaim lexicon.
- `weak` = value found only on lines without the claim's marker, or a year-less draft date found
  only with a different year (same day+month with no year or the current year is strong). Weak
  fails `ground` and `record`.
- Names: Title-Case words/sequences not at a sentence (or line) start, and email addresses. Each
  token must appear case-sensitively in a source (emails case-insensitively). Allowlisted: operator
  signature (Debanjan, Mazumdar, Founder, ProdCraft, debanjan@prodcraft.fyi), greetings/closings,
  month and day names. False positives are fixed by adding the thread/brief as a source.

## Edge Cases (incl. known limits)
- Grounding is lexical: "€30" grounds against "UptimeRobot Solo + AI ≈ €30/month" even when the
  draft attributes it to SMS (regression test). The grounding lens checks every `source_line`.
- Ambiguous separators ground on any reading: "1,200" ↔ {1200, 1.2}. Space thousands can merge
  adjacent numbers ("3 100 users" → 3100).
- ASCII single-quoted quotes are not extracted; bare numbers without a marker are not claims.
- "all"/"any"/"every" warn, never fail.
- SubagentStop text comes from `last_assistant_message`, else `agent_transcript_path` (last
  assistant message, multi-block aware); the main `transcript_path` fallback only accepts sidechain
  entries of that agent, so the main agent's own text is never logged as a verdict.
- Verdicts from any agent type other than `redteam-lens` (or `<plugin>:redteam-lens`) are logged but
  do not count. A CLI that omits `agent_type` makes `record` refuse (fail-closed).
- Bash: a sender reached only through an imported helper module, or a tracked script edited and
  committed for the purpose, is not detected (deliberate). Forwarding an existing message with no
  added text or attachments is allowed. Calendar `update_event` on an event that already has
  guests is gated unless `notificationLevel: NONE`.
- Gmail response shapes vary; `post-hook` takes `draftId` from `update_draft` input, else digs an
  id from the response. No id → no row → a later send-by-draftId is denied.
- Skill-gated only (no hook): LinkedIn, Slack, docs, decks, and text handed to the operator in chat.

## Changelog
- 2026-11-04: created (deterministic layer of the mandatory outward-text red-team gate).
- 2026-11-04: audit fixes — SubagentStop verdict log + re-verified pass rows, operator-only
  waivers via UserPromptSubmit, envelope binding (subject/recipients/attachments) and HTML link/
  comment canonicalisation, unknown-field fail-closed, Calendar invites, Bash inline senders, strict
  verdict headers, weak = fail, name claims, self-copy source skip.
