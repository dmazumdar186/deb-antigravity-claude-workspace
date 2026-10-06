# GTM People v3 — brainstorm before building (2026-10-06)

## Why v1 and v2 both missed
All three pages (live, deck, scroll-story) are brochures: the visitor reads, then hunts. The deck compressed the brochure (dense); the story stretched it (long). Neither changed the *job* the page does. The job: a founder arrives with an intent ("Series A, London, need an AE") and wants the answer: who is in play, what it costs, how fast, what it will cost me in fees. Ian wants the same page to show his edge without a sales call. So v3 must be an **answer engine**, not a brochure. Content becomes the knowledge base the engine answers from; nothing is lost, but nothing is pushed at the reader unasked.

## Candidate concepts (brain)
1. **Intent bar → answer board.** One input at the top ("I'm a Series A SaaS in London hiring a founding AE"), parsed instantly (client-side grammar now, LLM Worker later). Below it the page *assembles itself*: matching live roles, salary band, recommended TaaS tier + fee vs traditional, 5-day timeline, the two FAQs that matter. Everything else lives in drawers. Wow: typing changes the page. Risk: empty-input state must still sell.
2. **Two doors, two cockpits.** "Hiring" / "Looking" switch flips the whole page into a client cockpit or a candidate cockpit, each a single dashboard screen with expand-in-place tiles. Wow: it knows who you are. Risk: still a dashboard; pricing tile dense.
3. **Role finder first.** The 25 live roles as a filter-first board in the hero (location · type · stage · comp slider) with instant counts, candidate-side and client-side read of the same board ("4 London AEs open · typical £55–90k"). Wow: data in the first second. Risk: roles are a snapshot; client story weaker.
4. **Fee simulator as hero.** Drag base salary, pick tier: live number "£15,000 not £30,000", with the tier table folding out. Wow for founders; nothing for candidates.
5. **Command palette site (⌘K).** Every fact, role, price, FAQ reachable by typing. Wow for Ian; too hidden for first-time visitors.
6. **"Ian's desk" live view.** A simulated recruiter desk: today's shortlists, outreach replies, 30/60/90 check-ins ticking. Wow but theatre; invents activity (rule 3 forbids invented numbers).

## Synthesis → build this: **"Brief it" — intent-first answer board**
- **First 5 s:** a single sentence input with rotating example briefs typed in ("Series A · London · founding AE", "SDR in New York, Seed", "VP Sales, Series B, remote UK"), plus three chips (Hiring / Looking / Just curious). Behind it, a quiet animated field of 25 role dots that *sort themselves* as you type.
- **≤ 2 interactions, zero scroll:** type or tap a chip → the board under the input renders in place (no navigation): Roles in play (live 25, filtered, with comp in local currency; card layout with NO numeral overlap), Market rate (salary band for the parsed role/stage), Your fee (recommended TaaS tier + calculator, vs traditional), Timeline (brief → shortlist in 5 days → 30/60/90), Why us (the 3 pillars relevant to the stage), and the 2 FAQs that match. Each tile expands in place to the full verbatim content (drawer), so all 4,373 words are one tap away but never on screen unasked.
- **Candidate path:** "Looking" flips the board: roles first, register, intro-call-in-48h, JobSearchBud, salary guide.
- **Ian's edge:** a "How we'd run this search" strip generated from the brief (named steps, dates from today, guarantee length by tier) — the proposal he would otherwise write by hand. Plus a copy-link button: `/#brief=series-a+london+ae` reproduces the board, so he can paste tailored links into LinkedIn DMs.
- **AI layer:** client-side intent grammar (stage, role family, location, seniority, side) + a knowledge base built from the live copy; `data-ask-url` hook for a Cloudflare Worker + any LLM later. No invented facts: every tile cites the live sentence it came from.
- **Density target:** ≤ 90 visible words per viewport in default state, board ≤ 1.5 screens, roles reachable with 0 px scroll, pricing with 0 px scroll.
- **Reference remains:** a compact "Everything" index at the bottom (one line per section → drawer) so the brochure content is still browsable; `/deck/` and `/story/` kept for comparison.

## Independent ideation (second agent, no sight of the list above)
Brief Line · Hiring Plan Builder (stage dial → team org-chart with salaries + fees) · Live Board (roles as departures board) · Talk to Ian (conversational dossier with footnotes) · Comparator (with us vs alone) · Answer Sheet (A4 proposal that rewrites as you type). Ranked Brief Line first; recommended fusing it with the stage dial as the visible fallback and Talk-to-Ian's footnote format for answers.

## Decision
Both lists converge: **Brief it** = intent bar + answer board, with (from the second list) an auto-typing demo brief on load, a stage dial as the no-typing fallback, and every answer tile footnoting the live sentence it came from. Build it as v3 at `/`; keep `/deck/` (v1) and `/story/` (v2) for comparison.
