# ProdCraft weekly notes · wk 03 — "One senior role. 158 profiles. Who do you call first?"

Format: same as wk 02. 1080×1350 (4:5), ~31 s, 30 fps, code-rendered with lemo-opuscar,
original score from CC0 samples (Versilian Studios), no voice, no generated footage.
Paper / ink / gold editorial look (dataviz paper palette + swiss-motion kinetic type).
Audience: recruiters and recruitment-agency owners, any market. Goal: they finish thinking
"so that's what he builds — I want that on my desk."

Anonymity rules (hard): no client name, no city/country, no sector, no role title, no employer,
no candidate names. Candidates appear only as "Candidate A / B / C". No client feedback quotes.
The delivered client page is not shown. Every figure traces to FACTS.md.

## Beat sheet (on-screen text verbatim; the red-team draft is the source of truth)

| # | Time | On screen | Motion |
|---|---|---|---|
| 1 | 0.0–3.5 | Header `ProdCraft` · `wk 03`. **One senior role. 158 profiles. Who do you call first?** | grid of 158 person-dots |
| 2 | 3.5–8.0 | `the pool, counted` · `158 profiles assessed` → `594 claims pulled from public sources` → `446 survived the quote check` → `18 passed every hard rule` → `10 on the shortlist` · *"A shortlist without a denominator is a claim, not a finding."* | dots fade in waves until 10 stay gold |
| 3 | 8.0–13.5 | **Every claim carries a quote. No match, no claim.** Code card `• from my own build · verbatim` (`validate_claim`, 6 lines). Notes: `quote not in the source → claim dropped` · `148 of 594 caught and dropped, not softened` · `the rules are code, not a model` | a claim card turns red and slides off; next gets ✓ |
| 4 | 13.5–19.0 | **One row per candidate.** `Candidate A · Tier B` (B, C stacked behind) · Why them (placeholder bars) · chips `LinkedIn note` · `Email` · `Follow-up, about a week later` · `privacy notice + STOP line in every email, fixed text` | chips light in channel order |
| 5 | 19.0–24.0 | **Nothing sends until you approve it.** `verified address + resolved profile → listed first (6 of 10)` · `professional network first, then email, then the switchboard` | gold underline; ✓ approved stamp |
| 6 | 24.0–28.5 | **Your team reads 10 rows instead of 158 profiles.** · `I build systems like this for recruiting desks, around your roles and your rules.` | huge "10", small "of 158" |
| 7 | 28.5–31.0 | Empty dot grid returns (loop). Credit: `Made in code with lemo-opuscar (MIT) · music: original, CC0 samples (Versilian Studios)` | loop to frame 1 |

Footer on every frame: `ProdCraft · weekly notes` + `03`.

## LinkedIn post

> One senior role. 158 profiles. Who do you call first?
>
> That was the starting point of a sourcing system I built for a recruiting team.
>
> It reads public sources and pulls out claims about each candidate. Each claim has to come with a quote, and code checks that the quote actually appears in the source. The check caught 148 of 594 claims whose quote wasn't there. They were dropped, not softened.
>
> The hard requirements are code, not a model. 18 people passed every one. 10 made the page.
>
> The recruiter gets one row per candidate: why them, the evidence, and the messages ready to copy. That's a LinkedIn note, an email with the privacy notice and STOP line built in, and a follow-up for about a week later. Nothing goes out until a person approves it.
>
> So the team reads 10 rows instead of 158 profiles.
>
> I build systems like this for recruiting desks, around your roles and your rules. If your consultants spend their mornings on research instead of conversations, my DMs are open.
>
> (Video made in code. Candidates anonymised, client unnamed.)

## Decisions (Claim → Objection → Resolution)

- Lead with 158 → 10. Objection: one engagement can look cherry-picked. Resolution: keep; the funnel shows the denominator, which is the point.
- "Saves X hours". Objection: no measured hour figure in the source. Resolution: drop; "10 rows instead of 158 profiles" is countable.
- "Wired into the tools you already use". Objection (4/4 lenses): only a dry-run CRM hand-off exists; agency owners will read it as a promise to integrate with their ATS. Resolution: amend to "around your roles and your rules" (per-role brief + hard rules are delivered). Integration is a conversation in the DMs, not a public promise.
- Name the GDPR article. Objection: reads EU-only and hints at the client's market. Resolution: "privacy notice + STOP line".
- Keep the code card. Objection (counterparty): recruiters gain nothing from code; a competitor can call it "a string compare". Resolution: keep, with the plain-language headline above it; it is the "built in code, checkable" proof and mirrors wk 02.
