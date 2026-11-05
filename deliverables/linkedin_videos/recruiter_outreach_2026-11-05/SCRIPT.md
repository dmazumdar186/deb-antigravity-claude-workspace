# ProdCraft weekly notes · wk 03 — "One senior role. 158 profiles. Who do you call first?"

Format: same as wk 02. 1080×1350 (4:5), ~31 s, 30 fps, code-rendered with lemo-opuscar,
original score from CC0 samples (Versilian Studios), no voice, no generated footage.
Paper / ink / gold editorial look (dataviz paper palette + swiss-motion kinetic type).
Audience: recruiters and recruitment-agency owners, any market. Goal: they finish thinking
"so that's what he builds — I want that on my desk."

Anonymity rules (hard): no client name, no city/country, no sector, no role title, no employer,
no candidate names. Candidates appear only as "Candidate A / B / C". No client feedback quotes.
The delivered client page is not shown. Every figure traces to FACTS.md.

## Beats

1. Hook over 158 dots. 2. Funnel 158 → 18 → 10 (dots fade to 10 gold) + denominator quote. 3. Rule card: quote must be found in the cached source; no match → dropped. 4. One row per candidate (Candidate A/B/C, no names), message chips in channel order. 5. "The system drafts. Your team sends." 6. Payoff + offer. 7. Loop to frame 1, credit in footer. Full headline on frame 0 (LinkedIn thumbnail).

## LinkedIn post

> One senior role. 158 profiles. Who do you call first?
>
> That was the starting point of a sourcing system I built for one recruiting team. The counts are real; the team is not named.
>
> It reads public sources and pulls out claims about each candidate. Each factual claim has to come with a quote, and code checks that the quote can be found in the cached source. No match, no claim: it is dropped before the page is built. A shortlist without a denominator is a claim, not a finding.
>
> The hard requirements are code, not a model. 18 people passed every hard rule in the brief. The brief asked for 10, so 10 made the page.
>
> The recruiter gets one row per candidate: why them, the evidence, and the messages ready to copy. That's a LinkedIn note, an email with the privacy notice and STOP line built in, and a follow-up for about a week later. Rows with a verified address and a resolved profile come first. Drafts wait for a consultant's approval. The system drafts; your team sends.
>
> So the team reads 10 rows, with the full funnel from 158 next to them.
>
> I build systems like this for recruiting desks, around your roles and your rules. If your consultants spend their mornings on research instead of conversations, my DMs are open.
>
> (Video made in code.)

## On-screen text (final, verbatim)

```
ProdCraft · wk 03
One senior role. 158 profiles. Who do you call first?
the pool, counted
158 profiles assessed
18 passed every hard rule in the brief
10 on the shortlist, as the brief asked
"A shortlist without a denominator is a claim, not a finding."
Every factual claim carries a quote. No match, no claim.
the rule
keep a claim only if its quote is found in the cached source
no match → dropped · never reaches the page
the hard rules are code, not a model
One row per candidate.
Candidate A
Why them
Message to send: LinkedIn note · Email · Follow-up, about a week later
privacy notice + STOP line in every email, fixed text
The system drafts. Your team sends.
ready-to-contact rows first: verified address, resolved profile
professional network first, then email, then the switchboard
Your team reads 10 rows, with the full funnel from 158 next to them.
I build systems like this for recruiting desks, around your roles and your rules.
Made in code with lemo-opuscar (MIT) · music: original, CC0 samples (Versilian Studios)
ProdCraft · weekly notes · 03
```

## Decisions (Claim → Objection → Resolution)

- Lead with 158 → 10. Objection: one engagement can look cherry-picked. Resolution: keep; the funnel shows the denominator, which is the point.
- "Saves X hours". Objection: no measured hour figure in the source. Resolution: drop; "10 rows, with the full funnel from 158 next to them" is countable (and avoids a second, different 148).
- "Wired into the tools you already use". Objection (4/4 lenses): only a dry-run CRM hand-off exists; agency owners will read it as a promise to integrate with their ATS. Resolution: amend to "around your roles and your rules" (per-role brief + hard rules are delivered). Integration is a conversation in the DMs, not a public promise.
- Name the GDPR article. Objection: reads EU-only and hints at the client's market. Resolution: "privacy notice + STOP line".
- Show the validator code, as wk 02 did. Objection (downside BLOCKER, round 2): it was written inside a paid client engagement and no IP terms are on record. Resolution: drop; a plain-language rule card replaces it. wk 02's code came from the operator's own outbound system, so it did not have this problem.
- Exact funnel counts. Objection (reputation): they echo the client's public page. Resolution: keep the counts (page sends `x-robots-tag: noindex, nofollow, noarchive, nosnippet`, robots.txt disallows all) but drop the page's wording ("6 of 10 ready to contact now").
- Present 158 → 18 → 10 as the finished answer. Objection (counterparty, round 4): those counts are the first run, which the client sent back as too senior; the client can rebut it. Resolution: say "every rule written into that version of the brief" and make re-cutting the selling point.
- Publish claim counts (594 → 446, 148 dropped). Objection (rounds 4-5, three lenses): ~25% reads as "AI wrong one time in four", includes missing-source drops, and contradicts the 0.9% drop rate the client was given for a later run. Resolution: drop all claim counts; keep the rule.
- Concrete CTA ("send me a live brief"). Objection: unbounded free work + confidential briefs over DM. Resolution: "my DMs are open".
