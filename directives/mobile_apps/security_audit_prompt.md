# Security Audit Prompt — Vibecoded Apps (canonical)

Paste this prompt verbatim into Claude Code after `/clear`. This is the prompt referenced by `directives/mobile_apps/security_audit.md`. Do NOT modify it per-session — if a new vulnerability class is discovered, update this file once so future audits benefit.

---

```
You are auditing this React Native + Expo app (and any associated Supabase
project / Cloudflare Worker / Modal cron) for security vulnerabilities. The
app was vibe-coded — generated largely by AI — so look for the classes of
mistake that AI codegen reliably introduces.

For each category below:
1. Walk every relevant file in the repo.
2. Mark the category as PASS / PARTIAL / FAIL.
3. For PARTIAL and FAIL, list every specific finding with: file path, line
   number (if applicable), one-sentence description, severity (CRITICAL,
   HIGH, MEDIUM, LOW), and the CWE ID where one obviously applies.
4. After the categories, output a ranked finding list, highest severity
   first. Do not summarize at the end — leave the raw list.

Do NOT suggest fixes in this pass. Findings only.

═══════════════════════════════════════════════════════════════════════════

## Category 1 — Hardcoded secrets / credential leaks

Check for:
- API keys, tokens, passwords pasted directly into source files (search for
  `sk-`, `sb_`, `eyJ` JWT prefixes, `Bearer ` literals)
- Hardcoded Supabase service-role keys in client code (they MUST only live
  in Edge Functions / server side)
- `.env`-style values committed to git (grep for the specific provider key
  prefixes in tracked files only — ignore `.env` itself if gitignored)

## Category 2 — gitignore coverage

Check that `.gitignore` excludes:
- `.env`, `.env.*` (all variants)
- `credentials.json`, `token.json`, `service-account-*.json`
- `node_modules/`, `.expo/`, `*.keystore`, `*.p12`, `*.mobileprovision`
- Any provider-specific local cache (e.g. `.wrangler/`, `.modal/`)

## Category 3 — Public-prefix env leaks

In Expo, env vars prefixed `EXPO_PUBLIC_` get inlined into the bundle and
SHIP to the client. Verify NOTHING sensitive uses that prefix:
- No `EXPO_PUBLIC_*_SECRET`, `EXPO_PUBLIC_*_KEY` for paid APIs
  (Anthropic, OpenAI, OpenRouter, Stripe). Only the Supabase anon key and
  public URLs are safe under `EXPO_PUBLIC_`.

## Category 4 — Console error leaks

Production builds should not leak stack traces or secret values via
`console.error` / `console.log`. Check:
- No `console.log(error)` of raw caught exceptions
- No `console.log(process.env.*)` anywhere
- No catch blocks that print the entire error object

## Category 5 — Startup config validation

The app and any backend MUST fail fast at boot if required env vars / secrets
are missing. Check:
- Backend (Worker / Edge Function / Modal app) has a startup check that
  enumerates required env vars and throws if any are missing
- Failed startup must NOT silently swallow — must log the missing var name
  (not the value)

## Category 6 — Protected API routes

Every backend route that mutates data, costs money, or returns user-specific
data MUST require authentication. Check:
- Supabase: Row-Level Security (RLS) enabled on every user-data table; the
  default policies are NOT `(true)` / wide-open
- Cloudflare Worker: every non-`/health` route checks an `Authorization`
  header or `X-Worker-Secret`
- Modal: every `@modal.web_endpoint` checks auth before invoking the
  expensive path

## Category 7 — Default-open database policies

Supabase-specific:
- Every table has RLS enabled (`alter table <name> enable row level security`)
- No policies of the shape `using (true)` or `with check (true)` unless the
  table is intentionally public
- Service-role key is used ONLY inside Edge Functions, never on the client

## Category 8 — Inconsistent OAuth / auth middleware

If the app uses Supabase Auth (or any other OAuth provider):
- Every screen that reads user data calls `useUser()` / equivalent and
  redirects if null — no screen renders user data without an auth check
- The Edge Function / backend extracts the JWT, verifies it, and uses the
  authenticated user ID for all subsequent queries (never trusts a
  client-provided `user_id` field)

## Category 9 — Error information leaks

Production responses must not leak:
- Database schema details in error messages
- Stack traces (5xx responses)
- Internal endpoint URLs or service names
Check the global error handler / Edge Function catch blocks.

## Category 10 — Expensive-operation cost amplification

ANY backend route that calls a paid API (Anthropic, OpenAI, OpenRouter,
SerpAPI, etc.) MUST have at least one of:
- Auth check (only authenticated users can trigger paid calls)
- Per-user rate limit (e.g. 10 calls/day)
- Per-IP rate limit as a fallback for unauthed endpoints
An unauthed, unrate-limited paid-API endpoint = "credit-drain DoS attack
surface". Flag as CRITICAL.

## Category 11 — Hallucinated package imports

AI codegen sometimes imports packages that don't exist or substitute a
similarly-named typo-squatted package. Check:
- Every import in `package.json` resolves to a real published package
- No suspicious substitutions (`react-natve` instead of `react-native`,
  etc.)

## Category 12 — Missing server-side validation

Every endpoint that accepts user input must validate it on the server,
not just the client. Specifically:
- Length limits on text fields (Claude prompts, especially)
- Type checks (no `eval`-style processing of user input)
- Enum / allowlist checks on category fields

## Category 13 — Schema validations

For backend routes accepting JSON: use a schema validator (Zod / Yup /
JSON Schema) at the route boundary. Inline `if (body.foo)` checks are
PARTIAL at best.

## Category 14 — Unused / outdated dependencies

Check:
- Any package with a known CVE in its installed version (you do not have
  CVE data; flag suspiciously old `react-native` / `expo` versions only)
- Unused packages still in `package.json` (these expand attack surface)

═══════════════════════════════════════════════════════════════════════════

## Final output shape

After the 14 categories, output:

### Ranked findings

| # | Severity | Category | File:Line | Finding | CWE |
|---|---|---|---|---|---|
| 1 | CRITICAL | 10 | ... | ... | CWE-770 |
| 2 | HIGH | 6 | ... | ... | CWE-285 |
| ... |

Highest severity first. Do not summarize or recommend fixes — that's a
second prompt.
```

---

## Update history

- 2026-06-08 — initial canonical prompt, adapted from Nick Saraev's "security for vibecoded apps" module (transcript chapter 23). Added Supabase-specific checks (categories 6, 7, 8) not in Nick's original.
