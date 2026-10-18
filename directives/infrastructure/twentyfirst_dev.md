# 21st.dev — component registry MCP

**Created 2026-10-18.** 21st.dev is a registry of ~12k React + TypeScript + Tailwind + shadcn/ui
components, templates and themes. Components are copied into the repo (no runtime dependency).
Wired in as the `21st` server in `.mcp.json` (HTTP, `https://21st.dev/api/mcp`, header
`x-api-key: ${API_KEY_21ST}`), so it is available to every client that reads that file: Claude Code
CLI, cloud sessions, and the Claude browser extension.

## Goal

Give design work (`/impeccable`, `/site-redesign`, ad-hoc UI builds) a searchable parts bin for
interactive components and visual inspiration, without replacing original design.

## Inputs

- `API_KEY_21ST` — create at https://21st.dev/mcp. Local: `.env`. Cloud: environment variables
  box (`directives/infrastructure/claude_code_web.md`). Missing key → server fails to connect;
  the session still works, just without the tools.
- Re-print the config any time with `npx @21st-dev/cli@latest init --client claude` (`--write`
  merges into `.mcp.json`; the committed block is already correct, do not re-run with `--write`).

## Tools (representative; the server's `tools/list` is authoritative)

| Tool | Cost | Use |
|---|---|---|
| `search` | free, metadata only | find components by description |
| `get_inspiration` | free | reference designs for a section/page |
| `search_logo` | free | brand SVG logos |
| `get_component` | **paid retrieval** — 2 free copies/day, unlimited on membership | pull the source into the repo |
| `generate` | **paid** (21st AI credits) | generate a component; ask before spending credits |

## Rules

1. **`search` and `get_inspiration` freely; `get_component` deliberately.** Decide from metadata
   first. The free tier is 2 copies a day, so one wrong pull burns half the budget.
2. **Stack fit.** This workspace's sites are Astro 5 + Tailwind 3 with no React. A 21st.dev
   component needs `@astrojs/react`, a `client:` directive, a `cn()` helper and shadcn's
   `components/ui` layout. Use it only for a React island that earns its weight (interactive
   hero, pricing toggle, bento grid). Static blocks stay hand-written Astro.
3. **It is a parts bin, not the design.** `/impeccable` and `/site-redesign` own the design
   decisions and tokens; a copied component is restyled to the project's tokens, never shipped
   as-is.
4. **Licence is per author.** The site says copies are yours but names no single licence. Check
   the author's terms on anything shipped to a client; note it in `HANDOFF.md`.
5. **`generate` burns credits** → ask first (operating principle 3, paid-credit exception).

## Outputs

Component source under the target project's `src/components/`, restyled; a `HANDOFF.md` line
naming the component, author and licence.

## Edge cases

- Tailwind 4 syntax in a component vs Tailwind 3 here: downgrade `@theme`/`@utility` to config
  entries by hand.
- Components assuming Next.js (`next/image`, `next/link`): swap for `<img>`/`<a>` in Astro.
- Rate-limit or 402 responses from `get_component`: daily quota spent; stop, do not retry.
