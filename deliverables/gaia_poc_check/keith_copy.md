# Keith page — copy and design plan (source of truth for `render/check_page.py`)

Every sentence below is final copy unless marked {computed}. Numbers marked {computed} come from `check_results.json`; never hard-code them. Banned words anywhere on the page: AI, LLM, model, platform, pipeline, automated, system, agent, algorithm.

## Design plan

Honour the existing Gaia artifact family (the shortlist site): ink `#16211C`, muted `#5C6B63`, line `#DFE5E0`, panel `#F6F8F6`, accent moss `#1D6F4F`, warn `#8A5A00` on `#FFF6E5`. Add for this page: paper `#F7F8F6` (page ground, cool off-white with the green bias), stamp red `#9B2C1F` on `#FBEFEC` for OUT. Dark theme: ground `#121815`, panel `#1A231E`, ink `#E8EDE9`, muted `#9AA79F`, line `#2A3630`, accent `#4FBF8E`, warn `#E0B46A`, stamp `#E07A6B`.

Type: display and headings IBM Plex Sans 600/700 (Google Fonts, fallback Segoe UI, Helvetica, Arial); body IBM Plex Sans 400 at 16px/1.55, max 65ch; data and stamps IBM Plex Mono with `tabular-nums`. Uppercase labels at 11.5px with 0.06em tracking, as the shortlist site does.

Layout concept: an engineer's checked drawing. A title block at the top (Project / Brief / Names in / Checked on / Checked against), then the verdict in one line, then the ledger of 13 names with a stamp per row, then the paste box, then the arithmetic, then how it fits, then what it is not, then why not the tools already paid for. One column, 1100px max, 16px gutters, prints cleanly. No hero image, no cards-for-everything: the ledger rows are the object; stamps (PASS / NEAR MISS / OUT / NOT CHECKED) are the only coloured elements. Every row opens to show its proof lines (quote + source), closed by default, and the print stylesheet opens them all.

## Title block

- `<title>`: Shortlist Check
- Eyebrow: Gaia Talent Ltd · prepared by Prodcraft
- H1: Your 20 August list, checked.
- Title block fields: Project: Senior Structural Engineer, TOBIN / AtkinsRéalis · Brief: Senior Engineer grade, Republic of Ireland residence with direct evidence, CEng + Engineers Ireland · Names in: {computed submitted} · Checked on: {computed date} · Checked against: the brief as agreed on 10 September

## The verdict (one paragraph, large)

{computed submitted} names went in. {computed pass} pass the brief. {computed out} are out and {computed near_miss} miss by one rule. Every name below says which rule it failed, in one line, with the proof underneath.

Sub-line (muted): You said this list was too senior and that some were not in Ireland. You were right on both. This is the list you were sent on 20 August. The check was run again on 11 September against the brief you set on the call. Nothing here was typed by hand; every line is a quote from a public page, checked character by character against that page.

## The ledger

Columns: Name · Firm · Stamp · The one line · Proof (toggle)
Row order: PASS first, then NEAR MISS, then OUT (by rule: seniority first, then residence, then chartership), then NOT CHECKED.
Stamp text: PASS / NEAR MISS / OUT / NOT CHECKED. The one line is {computed one_line}. The proof drawer lists {computed evidence} as “quote” — source link, and the contact label in words: "email verified", "catch-all domain", "email was a guess", "no email found", "not looked up".

Under the ledger, small: Rules applied, in plain words: {computed rules[].label — rule_text}.

## Try a name

Label: Try any name from your own lists.
Input placeholder: Type or paste names, one per line
Button: Check
Result rows use the same stamps. For a name not in the pool: stamp NOT CHECKED, line "Not checked yet. A new name takes one working day and comes back with the same proof lines."
Footnote: {computed pool count} engineers are already checked for this brief. The box looks them up by name; it does not search the internet.

## The arithmetic

H2: What a wrong list costs

Paragraph: Checking one name by hand means opening the profile, the firm's page and the Engineers Ireland register, confirming where the person lives, and finding an address that is not a guess. Set your own minutes below; the figures update.

Three inputs with defaults from {computed time_value.assumptions}: Minutes per name checked by hand (15) · Names your team checks in a week (40) · Cost of a consultant hour, € (45).

Outputs, large, tabular: Hours a week spent checking: {computed} · Per month: € {computed} · The 20 August list alone: {computed consultant_hours_spent} consultant hours on a list where {computed pass} of {computed submitted} qualified, and {computed emails_to_unplaceable} emails written to people the brief could never place.

Small print: You said Isadora and you could take on 50 to 100 jobs with Maddie's screener doing the first pass. The names per week above is where that ambition meets a consultant's hours; set it to your number. The 15 minutes is my estimate. Replace it with yours and the page recomputes. The cost of a wrong CV reaching TOBIN or AtkinsRéalis is not on this page; you know that number better than I do.

## How it fits with what you have

Three boxes in a row (stack on phone), plain borders, no icons:
1. Recruit CRM and LinkedIn Recruiter find names. They keep doing that.
2. Shortlist Check proves the names before anyone calls: chartered, resident, right grade, real contact, with the quote. Names that fail come back with the reason, so nobody spends an hour on them.
3. Maddie's screener takes over exactly where it does today. A checked name lands in Recruit CRM as a candidate on the job, with the proof as a note, and can show in the dashboard Maddie built as one more column beside her score: checked, with the proof. Nothing sends on its own; a consultant always makes the call.

## What it is not

- Not a database. It checks names you already have.
- Not a replacement for Recruit CRM, LinkedIn Recruiter or what Maddie built.
- Not something that contacts candidates. Your consultants do, from their own seats.
- Not a score. A name passes the brief or it does not, and the page says why.
- Not another thing to learn. One list in, one page back. Isadora can run it without you.

## Why this cannot come from the tools you already pay for

You read me their upgrade note on Thursday: job change alerts, backdoor hire detection, sourcing across 800 million profiles with a 0 to 100 match score, cheaper enrichment. Keep all of it; none of it is touched here. The difference is one line: a score says how similar a person looks to the job. A check says whether they meet the brief, and shows why. Read from Recruit CRM's own pages on 11 September 2026:
- Their sourcing returns profiles with no quote and no source link, so a consultant still has to check each one.
- Their matching is a single 0 to 100 score. A rule like "must be chartered" or "must live in the Republic" lowers a score; it does not remove the name.
- No credential check exists in the product. Their own blog treats it as something you buy elsewhere.
- Their sequences send and pause; they do not read the reply, and "not now" is not remembered for 90 days.
- "Verified emails" is claimed with no method stated. Here every address carries its label: verified, catch-all, guess, or none.

And why from me: this is built around Gaia's brief and Irish public records (planning oral hearings, Engineers Ireland post-nominals, the firms' own people pages), with one rule that no product sells: no quote, no claim. You own every output. There is no per-seat fee. And you have already seen the wrong version of this list and the corrected one, with the count told straight both times.

## Footer

Prepared for Keith Molony, Gaia Talent Ltd, by Debanjan Mazumdar, Prodcraft, {computed date}. Campaign {computed campaign}. Public sources only; every candidate receives the Article 14 notice with the source cited.
