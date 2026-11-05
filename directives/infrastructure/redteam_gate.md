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
**without deliberately forging signed rows**:
- Every row in `passes/verdicts/waivers/drafts.jsonl` carries `mac` = HMAC-SHA256 over canonical
  JSON (sort_keys, `,`/`:` separators, ensure_ascii=False) of the row without `mac`, keyed by
  `$REDTEAM_KEY_FILE` or `~/.claude/redteam/hmac.key` (32 random bytes, dir 0700, file 0600,
  created atomically on first use; chmod best-effort on Windows). Readers ignore unsigned or
  invalid rows; `check` prints `ignored unsigned rows: N`. Only gate-owned paths sign: the hooks,
  and `record` after every check passes. Appending or editing a row by hand therefore does nothing.
- Verdicts count only if a signed `verdicts.jsonl` row (SubagentStop, real `redteam-lens` run whose
  `agent_transcript_path` is `<~/.claude/projects or $REDTEAM_TRANSCRIPT_ROOT>/**/agent-<agent_id>.jsonl`)
  holds the sha256 of the exact verdict text with the same lens, sha12 and PASS.
- Waived rows count only with a signed `waivers.jsonl` row (operator's own UserPromptSubmit prompt).
- `hook`, `post-hook`, `subagent-hook`, `prompt-hook` refuse (exit 2) unless `REDTEAM_HOOK=1`,
  which only the hook wrapper sets.

**Limit, stated plainly:** the hooks run as the same user as the agent. An agent that reads the
key and signs rows itself, sets `REDTEAM_HOOK=1` by hand, fakes a transcript file, briefs a lens to
"just output PASS", or edits this script defeats the gate. That is deliberate forgery, not
corner-cutting, and is out of scope (threat model = corner-cutting agent). Bash commands that
merely mention the gate or ledgers are no longer blocked (removed 2026-11-05: false positives).

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
- Env `REDTEAM_DIR` overrides the state dir (default `.tmp/redteam/`); `REDTEAM_KEY_FILE` the
  HMAC key; `REDTEAM_TRANSCRIPT_ROOT` the transcript root (tests); `REDTEAM_HOOK=1` (hook wrapper).

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
  Attendees (attendees/attendeeEmails/addedAttendees/addedAttendeeEmails) must be a subset of the
  `--to/--cc/--bcc` of one passing record (an operator waiver allows any).
- **Bash**: scanned only when the command (heredoc bodies excluded) runs a program in command
  position: python/node/deno/bun/ruby/perl/php/curl/wget/sendmail/mail/msmtp/sh/bash (incl. `-c`).
  Pure file writes (`cat > f <<EOF`, `echo … > f`), reads, greps and commits are never scanned.
  Deny inline senders (smtplib, sendmail, Gmail REST `/send`, `messages().send(`, Instantly
  emails/reply, SendGrid, Resend, Postmark) in the command, in a heredoc fed to a program
  (`python3 - <<EOF`, `cat <<EOF | python3`), in a script it runs, or in a `python -m mod` module
  resolved under cwd/repo; `base64 -d | <interpreter>` denies outright. Allowed if the command only
  runs a git-tracked, unmodified `.py`/`.sh` or `-m` module (optional leading `cd X &&`, no `-c`,
  heredoc, pipes or chaining). Ordinary commands cost ~80 ms (no git call). A crash on Bash allows
  (wrapper); Gmail/Calendar fail closed.
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
- SubagentStop is ignored unless `agent_transcript_path` checks out (see Threat model). Text
  comes from `last_assistant_message`, else that transcript (last assistant message, multi-block
  and SubagentHandback aware). The main `transcript_path` is never used.
- Verdicts from any agent type other than `redteam-lens` (or `<plugin>:redteam-lens`) are logged but
  do not count. A CLI that omits `agent_type` makes `record` refuse (fail-closed).
- Bash: a sender reached only through an imported helper module, split-literal or otherwise
  obfuscated code (`"smt"+"plib"`, `getattr`, `exec(bytes…)`), or a tracked script edited and
  committed for the purpose, is not detected (out of scope). Forwarding an existing message with no
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
- 2026-11-05: HMAC-signed ledger rows (replaces the Bash forge/ledger-write classifier and Write/Edit
  ledger protection), REDTEAM_HOOK-only hook subcommands, transcript-root check, Bash scan narrowed
  to executing commands (+ `python -m`, stdin heredoc, base64→interpreter), Calendar attendees ⊆
  recorded recipients; PreToolUse matcher drops Write|Edit.
- 2026-11-05 (audit): exec detection = any program word outside quotes (covers timeout/uv/poetry
  wrappers); mail programs (mail/mailx/msmtp/swaks/mutt/sendmail) as a command's program deny;
  smtp(s)://, --mail-rcpt, drafts().send( are sender hits; hook crash denies only Gmail/Calendar
  (Bash/other exit 1 → allowed), null command allows; Calendar `location` gated (own pass or
  verbatim inside the passed description).
- 2026-11-05 (re-audit): when a command executes anything, every heredoc body and every existing
  file named as an unquoted word or redirect source (any suffix, recursing into `sh -c` strings,
  ≤ 40 words) is scanned; dict recipients/attendees without a parseable `email` are unparseable;
  any attendee/guest/invitee key triggers the attendee-subset rule (invites with no vetted text
  deny); Mailgun/Brevo/Sendinblue/SES hosts and `aws ses|sesv2 send-email` are senders. Limit: a
  command that executes something and names any file containing a sender literal is denied.
