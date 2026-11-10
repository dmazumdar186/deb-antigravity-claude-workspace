# ProdCraft weekly notes · wk 04 — "12 emails a day, by hand. Then 800 a day."

Format: same as wk 03. 1080×1350 (4:5), ~32 s, 30 fps, code-rendered with lemo-opuscar, original score
from CC0 samples (Versilian Studios), no voice, no generated footage. Paper #EFEDE6 / ink / one gold accent,
Newsreader + IBM Plex Mono. Header `ProdCraft · wk 04`, footer `ProdCraft · weekly notes · 04`.
Audience: founders, sales leaders, GTM and sales engineers at companies that sell by outbound. Not technical.
Goal: they finish thinking "my team should be on calls, not in spreadsheets; he builds the machine."
Also hosted as a standalone explainer for prospects (operator request 2026-11-10).

Anonymity (hard): no client name, sector, city, people, domains. "One client" only. No tool screenshots.
Every figure traces to FACTS.md.

## Beats (≈ seconds)

1. 0–3.5 Hook (full headline on frame 0, LinkedIn thumbnail): "12 emails a day, by hand." / "Then 800 a day." Small tally counter 12 → 800 in gold.
2. 3.5–8 Inboxes scale: grid of small inbox squares fills 32 at launch → 64 → later 96 in three steps, label counts up. Caption "one client · sending inboxes".
3. 8–19 The pipeline, plain words. Six rows light up one after another, a gold line draws down through them:
   Find the right people · Verify every address · Send from many inboxes, every day ·
   AI reads every reply: hot · interested · neutral · not interested ·
   Hot lead → a person takes over, and the client's phone pings · Interested → an automatic reply, and a call on the calendar ·
   Every interested lead is logged in the CRM
4. 19–23 Payoff: "revenue up almost $128K in 4 months" (big gold $128K).
5. 23–27.5 The point: "The machine does the volume." / "Your people do the conversations."
6. 27.5–32 Offer: "I build GTM pipelines like this, around your market and your offer." / "prodcraft.fyi · my DMs are open". Credit in footer, loop to frame 1.

## On-screen text (final, verbatim)

```
ProdCraft · wk 04
12 emails a day, by hand.
Then 800 a day.
32 inboxes at launch
then 64
later 96
the pipeline
Find the right people
Check each address before sending
Send from many inboxes, every day
AI sorts the replies: hot · interested · neutral · not interested
Hot lead → the client's phone pings, and a person takes over
Interested → an automatic reply, asking for a call
Interested leads go into the CRM; booked calls land on the calendar
revenue up almost $128K in 4 months
The machine does the volume.
Your people do the conversations.
I build GTM pipelines like this, around your market and your offer.
prodcraft.fyi · my DMs are open
Made in code with lemo-opuscar (MIT) · music: original, CC0 samples (Versilian Studios)
ProdCraft · weekly notes · 04
```

## LinkedIn post

> 12 emails a day, by hand. Then 800 a day.
>
> One client used to send cold email one at a time. I built them an outbound pipeline: it finds the right people, checks each address before sending, and sends from many inboxes every day.
>
> AI sorts the replies: hot, interested, neutral, not interested. On a hot lead the client's phone pings and a person takes over. An interested one gets an automatic reply asking for a call. Interested leads go into the CRM, and booked calls land on the client's calendar.
>
> They launched on 32 sending inboxes, scaled to 64, and later 96. Over 4 months their revenue went up almost $128K.
>
> The machine does the volume. Your people do the conversations, the part that closes deals.
>
> I build GTM pipelines like this, around your market and your offer. My DMs are open.
>
> (Video made in code.)

## Decisions (Claim → Objection → Resolution)

- Name the tools (Instantly, GoHighLevel, AnymailFinder, MillionVerifier). Objection: operator asked "not too technical"; buyers buy outcomes. Resolution: drop names; plain verbs. "CRM" stays (buyers know it).
- Name lead sources Surfe/Prospeo. Objection: code uses Serper (Maps) with Prospeo for enrichment only; "Surfe" never appears. Resolution: drop; "Find the right people".
- "Positive reply → book on cal.com". Objection: auto-reply contains no booking link (a call ask only); this client's booking was Calendly/GHL. Resolution: "a reply asking for a call".
- Telegram + auto-reply for every positive. Objection: hot replies get a human, not an auto-reply. Resolution: two rows, hot → person + phone ping, interested → auto reply. This also carries the pitch (people do the conversations).
- $128K, 64 and 96 inboxes. Objection: no repo record; the only recorded money figure is a modeled $1M+ pipeline. Resolution: keep, sourced to the operator's own statement (2026-11-10), flagged to the operator for a written record; never shown next to the modeled pipeline figure.
- "800+" vs "800". Objection: 800 is the designed rate (32 × 25); the "+" adds an unmeasured claim. Resolution: "800 a day".
- Sector of the client. Objection: hints at the client. Resolution: "one client".
- "Positive reply → book" revisited (operator 2026-11-10, binding): interested leads get a reply and book a call on the client's calendar; tools named only as "calendar" and "CRM". Row: "Interested → an automatic reply, and a call on the calendar".
- "Log every lead in the CRM". Objection (red team): code routes only hot + interested replies to the CRM (index.js:517-519). Resolution: "Every interested lead is logged in the CRM", moved after the reply row.
- "not now" for the fourth class. Objection (red team): the class is negative (not interested / remove); "not now" changes its meaning. Resolution: "not interested".
- "emails sent per day". Objection (red team): 800 is the designed rate, not a send log. Resolution: "emails a day".
- Inbox scale wording (operator 2026-11-10, binding): 32 at launch → 64 → later 96; post "We launched on 32 sending inboxes, scaled to 64, and later 96."
- "within minutes". Objection (red team): replies are polled every 30 min (wrangler.toml crons; index.js:729-738), worst case ~1 hour. Resolution: drop the timing; "an automatic reply".
- Red team round 1 (all 4 FAIL): "books a call" → the system asks for a call; booked calls land on the calendar. "Verify every address" → "Check each address before sending" (catch-all results accepted). "Every interested lead is logged" → "Interested leads go into the CRM". "runs on its own" dropped (the client's manager runs the sending platform). "We launched" → "They launched" (inboxes were the client's scope). "+$128K"/"about" → "almost $128K" (operator's word). Two stray chart captions deleted.
- 96 inboxes vs the public "48,000+ emails / month" (metrics_canonical.md:13). Objection (counterparty, reputation): cross-check shows two scales. Resolution: keep 96 (operator's explicit ask); the film states no monthly volume; operator decides whether to update metrics_canonical.md.
- Red team round 2 (2 PASS, 2 FAIL) → operator decisions 2026-11-10: keep 96 inboxes and update metrics_canonical.md (volume now 70,000+ / month, inboxes and revenue rows added); revenue period is 4 months; wording "their revenue went up" (client revenue, not credited to the machine alone). "64" → "then 64".
