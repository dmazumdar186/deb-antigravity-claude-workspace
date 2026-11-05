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

**Trusted operator code (by spec):** a script or `-m` module whose realpath is inside this
workspace and is tracked + unmodified in the workspace's own git (e.g.
`execution/google/gmail_send_digest.py`) may send: it is committed operator code, governed by its
own directive, `--dry-run` default and budget guards. Any edit shows as uncommitted, so the file
is scanned and denied; a `git init` repo elsewhere (or nested) never counts.

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
  position: python/node/deno/bun/ruby/perl/php/curl/wget/send-mail/mail/msmtp/sh/bash (incl. `-c`).
  Pure file writes (`cat > f <<EOF`, `echo … > f`), reads, greps and commits are never scanned.
  Deny inline senders (smtp-lib, send-mail, Gmail REST `/send`, the Gmail API messages-send call, Instantly
  emails/reply, SendGrid, Resend, Postmark) in the command, in a heredoc fed to a program
  (`python3 - <<EOF`, `cat <<EOF | python3`), in a script it runs, or in a `python -m mod` module
  resolved under cwd/repo; `base64 -d | <interpreter>` denies outright. Allowed if the command only
  runs a git-tracked, unmodified `.py`/`.sh` or `-m` module (optional leading `cd X &&`, no `-c`,
  heredoc, pipes or chaining). Ordinary commands cost ~80 ms (no git call). A crash on Bash allows
  (wrapper); Gmail/Calendar fail closed.
- **Bash, non-email channels** (same scan surfaces, same tracked-pipeline trust; patterns in
  `_OUTWARD_SIMPLE`/`_OUTWARD_RES`): Slack webhooks + chat post/ephemeral/schedule/update
  methods, file uploads and the Python/Node SDK post-message calls;
  Discord webhooks; Teams office-webhook / Logic Apps hosts; Google Chat API; LinkedIn REST
  ugcPosts/posts/messages/shares/invitations and voyager messaging/invitation endpoints; Instantly campaign activate/launch, leads add, emails send/reply; lemlist API;
  Smartlead (email list); X/Twitter `2/tweets`, DMs, tweepy-style SDK calls; Meta Graph
  feed/media_publish/messages (incl. WhatsApp); Telegram `bot*/send*`; Twilio Messages.
- **Deploys** (`wrangler pages deploy|publish`, `wrangler deploy`, `vercel --prod`, `netlify
  deploy --prod`, incl. via npx/pnpm/yarn/bunx and `cd X &&`): denied unless the deployed dir
  is a workspace subdirectory (never the root) with tracked files and no modified, untracked or
  ignored files (node_modules/.wrangler/.vercel/.netlify skipped), or is gitignored build output
  (dist/, build/, out/, .vercel/output) whose project subfolder (nearest package.json/wrangler/
  vercel/netlify config, never the root) has tracked files and no modified/untracked files.
  `npm|pnpm|yarn|bun run X` follows the package.json script (3 levels). Page text is covered by the
  build-contract audit; this only stops deploying uncommitted content. Expansions deny.
- **MCP share** (any server; name contains share/permission, not get_/list_/search_/read_/
  resolve_/download_/delete_/remove_/revoke_/...): a message-like field (message/emailMessage/
  note/text) must be passed; recipients (emailAddress/recipients/to/...) must be a subset of
  one passed record's `--to/--cc/--bcc` (that text's record, or any record if no text);
  non-address audiences (permissionId e.g. anyoneWithLink, chatSpaceId, domain) need a waived
  text; no recipient denies.
- **MCP post/send/publish** (name contains post_message/send_/publish, same read exclusions):
  every non-metadata text field must be passed; no text denies; address recipients as above;
  channel/space audiences need a waiver. These tools fail closed in the wrapper.
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
- Skill-gated only (no hook): docs/decks content, text handed to the operator in chat, and
  outward channels reached only through an MCP tool whose name lacks share/permission/
  post_message/send_/publish (or a Bash sender not in the literal lists below).
- Non-email Bash channels match send endpoints only, lexically: Graph `/feed|/photos|/videos`
  and Instantly `/leads` also match a GET of those paths (fail safe); Slack/LinkedIn/X reads
  (`conversations.list`, `/v2/me`) pass. Repo LinkedIn automation (connect/DM scripts under
  `execution/`) stays trusted only when run tracked + unmodified, like every pipeline.
- Deploys: the gate only proves the deployed dir is committed; it does not read the pages.
  Ignored build output is trusted as a product of the committed project; a build step that pulls
  in uncommitted files from outside that project is not detected.
- MCP post/share: a Slack-style `channel`/Drive `permissionId`/`chatSpaceId` audience has no
  address to check, so it needs the passed text to be operator-waived.

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
  wrappers); mail programs (mail/mailx/msmtp/swaks/mutt/send-mail) as a command's program deny;
  SMTP URLs, curl's mail-recipient flag and the drafts-send call are sender hits; hook crash denies only Gmail/Calendar
  (Bash/other exit 1 → allowed), null command allows; Calendar `location` gated (own pass or
  verbatim inside the passed description).
- 2026-11-05 (re-audit): when a command executes anything, every heredoc body and every existing
  file named as an unquoted word or redirect source (any suffix, recursing into `sh -c` strings,
  ≤ 40 words) is scanned; dict recipients/attendees without a parseable `email` are unparseable;
  any attendee/guest/invitee key triggers the attendee-subset rule (invites with no vetted text
  deny); Mailgun/Brevo/Sendinblue/SES hosts and the `aws ses|sesv2` send verbs are senders. Limit: a
  command that executes something and names any file containing a sender literal is denied.
- 2026-11-05 (third audit): nested-CLI waiver forgery closed twice: Bash denies any `claude`
  invocation whose text, heredoc or file args contain `redteam waive`; prompt-hook refuses to sign
  when /proc ancestry shows ≥ 2 Claude CLI processes (env markers like CLAUDECODE are inherited by
  both top-level hooks and children, so they do not distinguish). Residual: on Windows/macOS (no
  /proc) only the Bash rule applies; a waiver smuggled via an obfuscated prompt file still needs
  the ancestry check. `record` refuses re-binding a recorded sha to a different envelope. Bash file
  scan expands `$VAR`/`${VAR}` (command assignments + env), globs, `cd` targets and PYTHONPATH for
  `-m`; unresolvable `$VAR` paths are allowed (no file to scan). Senders added: SendGrid SDK,
  yag-mail, Mailjet, Mandrill, Smartlead, ssmtp/exim and the perl mail CLI. Boolean `guestsCan*` keys are not
  attendee keys.
- 2026-11-05 (fourth audit): trusted = realpath in workspace + tracked/clean in its git; quoted
  paths with spaces scanned whole; scan limits fail closed when code runs (file > 2 MB unless a
  compiled binary, > 64 file args, oversize glob/brace); runners pwsh/powershell, go, npx, tsx,
  ts-node, deno, bun, npm/pnpm/yarn run (package.json script + its files); senders
  the Node googleapis messages-send chain, PowerShell's mail cmdlet, MailerSend, Mailtrap, SparkPost, Loops, Postmark, Resend;
  Gmail forward with a subject denied; any `mcp__*` send_email/send_message/create_draft tool gated
  as email (settings matcher + wrapper fail-closed widened); quote-aware heredoc openers;
  `$(pwd)`, `$(which X)`, backticks, `P=python3; $P`, `{a,b}` expansion; package-install args
  (pip/uv pip/npm i ...) are not scanned. Residual: a big data file passed to a script is denied.
- 2026-11-05 (fifth audit): direct script exec (`./x`, `/abs/x`, `dir/x`, bare name in cwd with
  a shebang) counts as running code and is scanned; bare PATH console scripts (pytest, etc.) are
  scanned themselves but their arguments are not. Runners uv/uvx/pdm/poetry/hatch/pipx/ipython/
  make (Makefile scanned). Sender chains split by whitespace/newlines, the SendGrid node package,
  Brevo's transactional call, Gmail upload endpoint, Ruby's SMTP class, PHP's mail function
  (.php files, `php -r`);
  quoted interpreter words; Calendar `quick_add_event` always gated (settings matcher updated).
- 2026-11-05 (sixth audit): SDK call forms (whitespace-tolerant; the exact patterns live in
  `_SENDER_SIMPLE`/`_SENDER_MULTI_RE`, not here, so this doc never matches them): Resend emails
  send, Postmark send calls (plain and template), SES v3 commands and boto3 SES send calls in an SES
  context, Mailgun message create when the file names Mailgun, Brevo transactional send calls,
  the legacy Gmail v1 REST host;
  every listed SDK/host has a test. `make -C/--directory/-f/--file` resolved; `~user` that does
  not resolve stays literal; `find ROOT [-name P] -exec|-execdir <interpreter>` scans matching
  files under ROOT (fail closed past 64).
- 2026-11-05 (seventh audit, FP): tracked pipeline runs allow output redirects, `\`-newline,
  `timeout N`/env prefixes and `&&`/`||`/`;` chains: tracked segments are dropped and the rest
  is scanned together (pipes, background `&`, heredocs, `$(`, stdin `<` keep normal rules).
  Calendar recurrence/conferenceData/reminders/transparency/guestsCan* are metadata.
- 2026-11-05 (eighth audit): code-loading env vars set in any executing command (prefix,
  `env`, `export`) — PYTHONPATH/STARTUP/HOME/USERBASE, BASH_ENV, ENV, NODE_OPTIONS
  (--require/--import/--loader), NODE_PATH, LD_PRELOAD, LD_LIBRARY_PATH, RUBYOPT/RUBYLIB,
  PERL5OPT/PERL5LIB, PHP_INI_SCAN_DIR — must resolve to tracked/unmodified or scan-clean paths;
  dirs with untracked sitecustomize/usercustomize or importing .pth, missing paths, `$VAR`
  values and any LD_* deny. Prefix skip handles `timeout -k 5 --signal=KILL 30`, nice/stdbuf/
  ionice/env flags. Env inherited from the session (not set in the command) is out of scope.
- 2026-11-05 (ninth audit): non-Python loader vars (NODE_OPTIONS, NODE_PATH, PHP_INI_SCAN_DIR,
  RUBYOPT, PERL5OPT) pointing at a directory deny unless the dir is tracked + clean; LD_PRELOAD
  always denies; LD_LIBRARY_PATH allowed only when every entry is a root-owned, non-writable
  system lib dir (as root, nothing is non-writable, so it denies).
- 2026-11-05 (tenth audit): `source`/`.`/`eval` count as exec (files and eval text scanned);
  heredoc bodies fed to a program are resolved recursively like the outer command (depth ≤ 3);
  invoking the hook wrapper, a `redteam_gate.py` hook subcommand, or setting REDTEAM_HOOK from
  Bash denies ("hook paths are harness-only"); naming them (git add, grep, commit messages) and
  `sha|ground|record|check` stay allowed. Tracked runs may pipe into read-only sinks (tail, head,
  tee FILE, grep, wc, less, cat, sort, uniq).
- 2026-11-05 (eleventh audit): hook-path checks also run on scanned files, heredoc bodies,
  package.json scripts and a shlex-joined form of the command, only when it executes something
  (greps/cats of the hook files stay allowed). Only shell-fed heredocs are re-parsed as shell.
  prompt-hook records a waiver only if `transcript_path` is under the transcript root and its
  last `user` row is a genuine operator prompt (not tool_result/isMeta/isSidechain) containing
  the waive line. Timing-robust: the line may be in either of the last 2 genuine prompts, so if
  the harness writes the prompt after the hook, the operator is told "waiver not recorded yet;
  send the same `redteam waive …` line once more" and the re-send succeeds.
  `xargs <interpreter>` without a named script file denies. This doc avoids literal sender
  patterns so reading it next to an executing command is not denied.
- 2026-11-05 (channels): gate extended beyond email/calendar: Bash chat/social/SMS/LinkedIn/
  cold-email send endpoints and SDK calls, production deploys only from committed dirs, MCP
  share/permission and post_message/send_/publish tools (recipient ⊆ recorded pass; fail closed
  in the wrapper; settings matcher widened). Reads and non-prod deploys stay allowed.
- 2026-11-05 (channels audit): deploys found per quote-aware simple command through wrappers
  and runners (timeout/env/nice, npx/pnpx/bunx/`bun x`/`pnpm|yarn dlx|exec`, `tool@ver`,
  `node …/wrangler.js`), `ntl` alias; wrangler `pages deployment create`, `versions
  deploy|upload`; vercel bare/`deploy`/`promote`/`alias set` (previews count);
  netlify `--prod-if-unlocked`. No explicit dir → the cwd project must be committed + clean.
  Non-mail MCP `send_message` tools route through the share/post rules (only names containing
  mail, plus any `create_draft`, take the email path). Twilio call needs twilio context;
  host:port forms normalised; Discord channel messages, MS Graph Teams/chat messages, Slack
  me-message and v2 file upload, discord.py sends (with discord import), httpie/xh calls added.
  Posts with public visibility need a waiver. Settings matcher case-insensitive.
- 2026-11-05 (channels re-audit): deploy detection also runs on `sh|bash -c` strings, `eval`,
  `$VAR` expansion, `echo|printf … | sh`, Makefile recipes (`make X`, incl. from package
  scripts) and on script files the command runs (a spawn call within 3 lines of deploy words;
  tracked scripts included, since the deploy publishes the cwd project, which must be clean).
  `--dry-run` and vercel git/rollback/init/open/env/logs/ls/inspect are not deploys.
  Read-capable endpoints (Discord channel messages, MS Graph messages, Google Chat spaces,
  Twilio Messages, Meta Graph feed/messages) need a write signal (POST/PUT/PATCH, -d/--data/-F/
  --json, httpie key=value, `.post(`/`.create(`); a GET passes. discord.js ESM/dynamic import
  context and Telegram `bot.send_*(` added. MCP post verbs add reply_to_thread, create_post,
  tweet, create_message, send_dm, comment (incl. GitHub issue/PR comments), schedule_message.
  Wrapper read-exclusion matches the tool segment after the server only.
- 2026-11-05 (channels third audit): MCP post/send/comment text is an allow-list of keys
  (body/text/message/content/comment/title/description/subject/caption/status/note/reply/
  markdown/html/summary/blocks/attachments/embeds and *_text/*_body forms); ids and handles
  (owner, repo, issue_number, user_id, tweet_id) are not text. Deploy scans only files the
  command EXECUTES (interpreter arg, `sh f`, `source f`/`. f`, `./f`, `cat f | sh`,
  `python3 -c` code) and Makefile recipes of the invoked target (+ prerequisites; pattern
  rules scan the whole file); a deploy script is checked against its own project folder
  (nearest project marker, else its directory), never the cwd or the repo root. Combined
  shell flags (`-lc`, `-ec`, `-euc`), `yarn|pnpm <bin>`, `--dry-run=false` and nested var
  expansions are covered. Write signals add `-d@f`/`-d'…'`, `--data-*`, `--form*`, `-T`,
  `--upload-file`, wget `--post-*`/`--method`, `.request('POST'`, `Request(data=`, fetch
  `method:'POST'`. MCP read prefixes need no underscore (`getpermissions`), same as the hook.
  Flags are matched case-sensitively on command text (`-F` form = write, `-f`/`--fail` not);
  in scanned files (lowercased) `-f` still counts as a write.
- 2026-11-05 (channels fourth audit): tracked scripts get the invoking command's positional
  args bound (`$1`, `${1:?}`, `SITE="$1"`), so `deploy.sh <dir> <proj>` checks `<dir>` by the
  normal rule; if still unresolvable, a tracked clean script checks the project of its path
  args (else its own folder). Inline code deploys: python/node heredocs, `python3 -c
  "exec(open(f).read())"`, `sh < f`, `python3 - < f`, array-literal spawns
  (`spawnSync('wrangler',['pages','deploy'])`). Runners: `vc`, `npx -p pkg bin`,
  `pnpm --filter x exec`, `yarn|bun run <bin>`, corepack, `env -C dir`, setsid/flock/unbuffer/
  doas/`script -c`. Channels: versioned Discord webhooks, Slack WebhookClient/IncomingWebhook
  `.send(`, Instagram/Threads publish, Telegram forward/copy, Outlook webhooks. MCP outward
  tools: every string field is text except an id/target/enum key list (`channel_name`/
  `Channel` are audiences needing a waiver); kinds add postMessage, files_upload,
  create/update_issue, create_pull_request, pull_request_review_write; push_files/
  create_or_update_file are code (build-contract audit), not outward text.
- 2026-11-05 (channels fifth audit): a tracked deploy script with an unresolvable/default
  target is checked against every folder it names as a literal (repo-, script- or cwd-relative;
  `.tmp/` staging skipped) and its path args; with none, its project and all of `deliverables/`
  must be clean. Deploy detection resolves `$(echo X)`, `$(cat f)`, `$(pwd)` and scans every
  `$(…)`/backtick body; covers `xargs -I`, `cat|head|tail f | sh`, `| at|batch`, tmux/screen/
  su/runuser/systemd-run command strings, `env -S`, `php -r`/`perl -e`/`ruby -e` system calls.
  `$PWD`/`$(pwd)`/`` `pwd` `` in script paths resolve for the sender scan too. MCP id/enum keys
  add camelCase review/issue fields; tools with only ids/enums (approve, close) pass. Channels:
  Telegram media-group/forward/copy and `bot.telegram.sendMessage`, Outlook 365 webhooks, Slack
  `files_upload(`/AsyncWebhookClient, GitHub REST comments/issues/pulls/reviews/releases.
  `gh issue|pr|release|discussion comment|create|review|edit` with `--body/-b/--title/-t/
  --notes/--body-file`: every given text must be passed (`--fill`/`--approve` need none).
- Out of scope (documented): `-c 'import deploy'`-style helper modules, shell-escaped or split
  literals, browser/Playwright UI sends (LinkedIn UI automation included); the hook gates API
  endpoints, and tracked repo automation stays trusted.
