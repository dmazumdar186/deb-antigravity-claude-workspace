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
| 2 | 3.5–8.0 | `the pool, counted` · `158 profiles assessed` → `594 claims pulled from public sources` → `446 survived the quote check` → `18 passed every hard rule in the brief` → `10 on the shortlist, as the brief asked` · *"A shortlist without a denominator is a claim, not a finding."* | dots fade in waves until 10 stay gold |
| 3 | 8.0–13.5 | **Every factual claim carries a quote. No match, no claim.** Rule card `the rule`: `keep a claim only if its quote is found in the cached source`. Notes: `148 of 594 couldn't be matched · none reached the page` · `the hard rules are code, not a model` · `rule changes → the whole pool is re-cut` | a claim card turns red and slides off; next gets ✓ |
| 4 | 13.5–19.0 | **One row per candidate.** `Candidate A` (B, C stacked behind) · Why them (placeholder bars) · chips `LinkedIn note` · `Email` · `Follow-up, about a week later` · `privacy notice + STOP line in every email, fixed text` | chips light in channel order |
| 5 | 19.0–24.0 | **Drafts wait for your approval. Nothing sends on its own.** `ready-to-contact rows first: verified address, resolved profile` · `professional network first, then email, then the switchboard` | gold underline; ✓ approved stamp |
| 6 | 24.0–28.5 | **Your team reads 10 rows, with the full funnel from 158 next to them.** · `I build systems like this for recruiting desks, around your roles and your rules.` | huge "10", small "of 158" |
| 7 | 28.5–31.0 | Empty dot grid returns (loop). Credit: `Made in code with lemo-opuscar (MIT) · music: original, CC0 samples (Versilian Studios)` | loop to frame 1 |

Footer on every frame: `ProdCraft · weekly notes` + `03`.

## LinkedIn post

> One senior role. 158 profiles. Who do you call first?
>
> That was the starting point of a sourcing system I built for one recruiting team. The counts are real; the team is not named.
>
> It reads public sources and pulls out claims about each candidate. Each factual claim has to come with a quote, and code checks that the quote can be found in the cached source. Of 594 claims the AI proposed, 148 had no quote that matched. That is the AI's error rate, measured instead of guessed, and code caught every one of the 148 before the page was built. They were dropped, not softened. A shortlist without a denominator is a claim, not a finding.
>
> The hard requirements are code, not a model: 18 people passed every rule written into that version of the brief. The brief asked for 10, so 10 made the page. When a rule changes, the code changes and the whole pool is re-cut, not re-argued.
>
> The recruiter gets one row per candidate: why them, the evidence, and the messages ready to copy. That's a LinkedIn note, an email with the privacy notice and STOP line built in, and a follow-up for about a week later. Rows with a verified address and a resolved profile come first. Drafts wait for a consultant's approval; nothing sends on its own.
>
> So the team reads 10 rows, with the full funnel from 158 next to them.
>
> I build systems like this for recruiting desks, around your roles and your rules. If your consultants spend their mornings on research instead of conversations, send me one live brief and I'll tell you what a first cut would look like for it. My DMs are open.
>
> (Video made in code.)

## Decisions (Claim → Objection → Resolution)

- Lead with 158 → 10. Objection: one engagement can look cherry-picked. Resolution: keep; the funnel shows the denominator, which is the point.
- "Saves X hours". Objection: no measured hour figure in the source. Resolution: drop; "10 rows, with the full funnel from 158 next to them" is countable (and avoids a second, different 148).
- "Wired into the tools you already use". Objection (4/4 lenses): only a dry-run CRM hand-off exists; agency owners will read it as a promise to integrate with their ATS. Resolution: amend to "around your roles and your rules" (per-role brief + hard rules are delivered). Integration is a conversation in the DMs, not a public promise.
- Name the GDPR article. Objection: reads EU-only and hints at the client's market. Resolution: "privacy notice + STOP line".
- Show the validator code, as wk 02 did. Objection (downside BLOCKER, round 2): it was written inside a paid client engagement and no IP terms are on record. Resolution: drop; a plain-language rule card replaces it. wk 02's code came from the operator's own outbound system, so it did not have this problem.
- Exact funnel counts. Objection (reputation): they echo the client's public page. Resolution: keep the counts (page sends `x-robots-tag: noindex, nofollow, noarchive, nosnippet`, robots.txt disallows all) but drop the page's wording ("6 of 10 ready to contact now").
- Present 158 → 18 → 10 as the finished answer. Objection (counterparty, round 4): those counts are the first run, which the client sent back as too senior; the client can rebut it. Resolution: say "every rule written into that version of the brief" and make re-cutting the selling point.
