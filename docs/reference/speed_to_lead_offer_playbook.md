# Speed to Lead: 0 → 1 Offer Playbook

Written 2026-10-05. Companion to `directives/personalization/speed_to_lead.md`
(the build directive) and the Jonatan LinkedIn outreach guide (the channel
playbook). This document covers everything those two don't: what you are
selling, to whom, for how much, how to prove it, and how to turn the generic
LinkedIn material into a campaign that gets replies.

---

## 1. What Speed to Lead actually is (plain English)

A business pays for leads (ads, SEO, referrals). A lead fills a form or calls.
Then nothing happens for 2 hours, or 2 days, because the owner is on a job or
the receptionist is at lunch. By the time someone replies, the lead has
called three competitors and hired the one who picked up.

Speed to Lead (S2L) is a system that **responds to every new lead within 60
seconds, on the channels they actually read (SMS, WhatsApp, email, a callback),
qualifies them, and books them into a calendar, 24/7, without a human.**

Why it works (the numbers to use, all public):

| Claim | Source |
|---|---|
| Responding within 5 min vs 30 min makes a lead 21× more likely to qualify | Lead Response Management study (MIT / InsideSales) |
| 78% of buyers go with the first company that responds | Lead Connect / Velocify |
| Average B2B response time is 42 hours; ~40% of inbound leads never get a reply | Harvard Business Review audit of 2,241 companies |
| Nick's case: home-services business $3M → $9M/mo after S2L | Course notes §5 |

**The one-sentence mechanism:** a lead's motivation decays by the minute. S2L
captures them while they are still motivated. Nothing else in the funnel
changes, so the lift is almost pure margin for the client.

**What it is not:** a chatbot, a CRM migration, a "full automation agency"
retainer. Keep it to one narrow, measurable promise: *first response in under
60 seconds, every lead, every hour.*

---

## 2. Pick the niche and ICP

### 2.1 Scoring criteria

A niche is right for S2L when all five are true:

1. **Leads are high-ticket** ($2k+ per closed job) so one saved lead pays for
   the system.
2. **Leads arrive hot and perishable** (someone with a burst pipe, a toothache,
   a house to sell), not researched over months.
3. **The business is demonstrably slow today.** You can prove it with a
   mystery-shop (see §5.3).
4. **Volume exists.** At least 30–50 leads/month, or the system has nothing to
   do.
5. **The decision maker is reachable on LinkedIn** (because that is your
   channel). This is the filter most people forget.

### 2.2 Ranked shortlist

| Rank | Niche | Ticket | Perishability | On LinkedIn? | Verdict |
|---|---|---|---|---|---|
| 1 | **Lead-gen / paid-ads agencies serving local service clients (1–50 staff)** | Resold to 10–50 clients each | Their clients' leads are hot | Yes, very | **Primary ICP.** One close = many deployments. They already own the lead flow and feel the pain when clients churn over "bad leads". |
| 2 | **Multi-location med-spa / aesthetic / dental-implant groups** | $1.5k–$15k per treatment | High (consult requests) | Owners and practice managers, yes | **Secondary ICP.** Direct, high-margin, slow to respond. |
| 3 | Real-estate brokerages and mortgage brokers | $5k–$15k commission | Very high | Yes | Good, but heavily regulated texting in some markets, and agents are cheap buyers. |
| 4 | Home services (roofing, HVAC, solar, plumbing) | $5k–$30k | Highest | Owners rarely on LinkedIn | Best *fit* for S2L, wrong *channel*. Reach them through ICP #1 (white-label). |
| 5 | Law firms (PI, immigration) | $5k+ | High | Partners yes | Compliance-heavy; park for later. |

**Recommendation:** lead with #1 and keep #2 as a parallel list. Jonatan picked
marketing agencies for the same reasons. Your edge over him: tighten to
*agencies that run paid ads or LSA for local service businesses*, because
those agencies get blamed for leads their clients never called back.

### 2.3 SalesNav filters for ICP #1

- Job title: Founder, Owner, CEO, Managing Director, Head of Growth
- Company headcount: 1–50
- Industry: Advertising Services, Marketing Services
- Keywords (any): "lead generation", "paid ads", "Google Ads", "Meta ads",
  "home services", "dental", "med spa", "local businesses", "performance marketing"
- Geography: start **UK, UAE, Australia** (Jonatan's data: 27% reply rate Dubai vs 10% US; also WhatsApp is the default channel in UAE which makes the demo land harder)
- Must-have: *Posted on LinkedIn in last 30 days*; exclude viewed profiles; exclude 1st-degree

### 2.4 Disqualifiers (say no fast)

- Agency does branding / SEO only, no lead flow to respond to
- Under 30 leads/month across all clients
- No CRM or forms you can hook into (pure phone-call businesses need the voice tier, sell later)
- Wants "an AI agent for everything"

---

## 3. The system you deliver

### 3.1 Architecture (one diagram in words)

```
Intent event ─► Intake ─► Orchestrator ─► Responder ─► Qualifier ─► Booker ─► Handoff
(form, Meta     (webhook,   (dedup, pacing,  (SMS/WA +    (2-way AI    (calendar  (CRM note,
 Lead Ad, chat,  CRM        quiet hours,     email in     SMS, 3–5     link or    owner alert,
 missed call,    trigger,   STOP handling,   <60s, human  questions,   direct     dashboard)
 email)          email      logging)         paraphrase)  score)       booking)
                 parse)
```

### 3.2 Three tiers (this is also your pricing ladder)

| Tier | What fires | Build time | Who buys |
|---|---|---|---|
| **Starter: Instant Reply** | Form/ad lead → personalised SMS + email within 60s, owner gets an alert with the lead summary | 1–2 days | Single-location businesses, agency pilot client |
| **Pro: Reply + Qualify + Book** | Starter + two-way AI SMS/WhatsApp that asks 3–5 qualifying questions, scores the lead, sends a booking link or books directly, follow-ups at 1h / 24h / 72h if silent | 3–5 days | Agencies (white-label), multi-location clinics |
| **Elite: Voice + Call-merge + Dashboard** | Pro + AI voice callback or simultaneous ring to rep, missed-call text-back, CRM sync, weekly response-time dashboard | 1–2 weeks | Agencies with 10+ clients, groups with a sales team |

Sell Pro. Use Starter as the free/paid pilot. Use Elite as the upsell after
30 days of data.

### 3.3 Stack (pick for ownership, not elegance)

| Layer | Default | Why | Alternative |
|---|---|---|---|
| Intake | Webhook from website form / Meta Lead Ads / GoHighLevel / HubSpot / Typeform; email-parse fallback | Covers 90% of local-service lead sources | Zapier/Make catch-hook for odd sources |
| Orchestration | **n8n** (self-hosted or cloud) for client-owned builds; Cloudflare Worker (`execution/infrastructure/`) for your own | Agencies can see and own n8n; the Worker is cheaper for you | Make.com |
| SMS / WhatsApp | **Twilio** (global) ; WhatsApp Business API via Twilio or 360dialog | US needs A2P 10DLC (2–14 days). UK/UAE/AU: alphanumeric sender or local number, much faster. UAE: WhatsApp first | OpenPhone (US only) |
| Email | Client's Gmail/Outlook via API, or Resend/Postmark | Replies must come from a real human mailbox for deliverability and trust | |
| AI | `claude-fable-5-1` via `execution/modules/llm_client` | Paraphrase slot + qualifier conversation; template-locked | |
| Booking | Cal.com (free, API) or client's GHL/Calendly | | |
| CRM | GoHighLevel (agency default), HubSpot, or a Google Sheet for pilots | | |
| Voice (Elite) | Twilio Programmable Voice for call-merge; Vapi or Retell for AI voice | | |
| Dashboard | Static site on Cloudflare Pages fed by the orchestrator log (`site-redesign` skill pattern) | "Dashboards are just websites" | |

### 3.4 Build order (first client)

1. **Intake first.** Get one test lead from their real form into your webhook. Nothing else matters until this works.
2. Dedup + log (lead id, timestamp, `seconds_to_first_response`). That number is your whole sales deck.
3. Email + SMS templates, human-written, one AI-filled paraphrase slot (≤15 words). Hard 160-char check on SMS.
4. **Pacing:** fire at ~30–45s, never under 10s. Instant replies read as bots.
5. Owner alert (SMS/Slack/WhatsApp) with lead summary and a one-tap call link.
6. Qualifier (Pro): 3–5 questions max, each answer appended to the CRM note, exit to booking link on qualification, exit to "I'll have X call you" on anything weird.
7. Follow-up cadence for silent leads: 1h, 24h, 72h, then stop.
8. Guardrails: STOP/opt-out handling, quiet hours (no SMS 9pm–8am local), max 1 outbound per lead per hour, empty-LLM-output fallback to the static template, error channel.
9. End-to-end test with 20 fake leads to your own phone before any live traffic.
10. Weekly report: leads in, median seconds-to-response, % qualified, % booked, % booked that showed.

### 3.5 Compliance (one paragraph, do not skip)

Leads who submitted a form have given consent to be contacted about that
enquiry. Keep the first message about their enquiry, include an opt-out, honour
STOP instantly, no marketing blasts. US: TCPA + A2P 10DLC. UK: PECR (business
enquiries are fine, add opt-out). UAE: WhatsApp templates must be pre-approved;
SMS promo hours are restricted. AU: Spam Act, opt-out required. Put this in the
contract as the client's responsibility, with your system enforcing the
mechanics.

### 3.6 What to build *before* you have a client

Build the full Pro tier against your own demo landing page (a fake "Dubai
Dental" or "Sunrise Roofing" site via `site-redesign`). This gives you:

- A live demo link for Looms ("fill this form, watch your phone")
- Screen recordings for posts
- A template you clone per client in under a day
- Honest social proof: "here is my own system, 100 test leads, median 38 seconds"

---

## 4. The offer

### 4.1 Positioning statement

> I install speed-to-lead systems for lead-gen agencies, so every lead their
> clients pay for gets a personalised reply, is qualified, and is booked within
> 60 seconds, 24/7. If response time doesn't drop under a minute, you don't pay.

### 4.2 Pricing

Jonatan sells "pay on results". That is a strong hook and a weak business:
attribution is messy and you carry all the risk. Use a hybrid.

| Model | Price | When |
|---|---|---|
| **Pilot** | Free or $500, 14 days, one client of theirs, Starter tier | Your first 3 deals. Price is the case study. |
| **Core (recommended)** | $2,000–$3,500 setup + $750–$1,500/mo per deployment, Pro tier | After you have one case study |
| **Agency white-label** | $1,500 setup per client + $400–600/mo per client, minimum 3 clients, agency marks up to its clients | ICP #1 at scale |
| **Performance** | $0 setup, $50–150 per *qualified booked appointment*, 90-day minimum | Only when the client has clean booking data you control |

**The guarantee (risk reversal that is actually safe):** "Median first response
under 60 seconds on every lead for 30 days, or the setup fee is refunded." You
control that metric completely. Never guarantee revenue.

### 4.3 ROI math for the pitch (make it theirs on the call)

```
Client leads/month:          80
Current contact rate:        ~40%  (industry average for slow follow-up)
With S2L contact rate:       ~70%
Extra contacted leads:       24
Close rate:                  20%   → ~5 extra jobs
Avg job value:               $4,000
Extra revenue/month:         ~$20,000
Your fee:                    $1,000/mo
```

Ask the client for their three numbers (leads/mo, close rate, job value), fill
this live on the call. It sells itself or it tells you they're not a fit.

### 4.4 Deliverables list (put in the proposal)

- Intake connected to every lead source they name (max 3 per deployment)
- SMS/WhatsApp + email first-response within 60s, personalised, from their number/domain
- AI qualifier with their 3–5 questions, hand-off rules written with them
- Booking integration with their calendar
- Owner alerts + missed-lead escalation
- 3-touch silent-lead follow-up
- Weekly response-time report
- 30-day tuning window, then monthly maintenance

---

## 5. The pitch

### 5.1 Why the current material reads generic

The existing ad/landing copy says "speed", "AI", "automation", "never miss a
lead". Every competitor says the same. What is missing is **specificity you can
only have if you've done it**: a niche named in the headline, a number with a
unit, a mechanism in one sentence, and proof from a mystery shop. Fix: every
asset must contain (a) the ICP by name, (b) "60 seconds", (c) one real
timestamp or screenshot, (d) one line of how it works.

### 5.2 Profile assets

**Banner:** "Lead-gen agencies: your clients' leads are going cold in the
inbox. I make sure every one gets a reply in under 60 seconds, 24/7. ↓ Watch
the 90-second demo"

**Headline options (test two at a time):**
- "Helping Lead-Gen Agencies Turn More Paid Leads Into Booked Calls With 60-Second Speed-to-Lead Systems"
- "I reply to your clients' leads in under 60 seconds so they stop churning over 'bad leads' | Speed-to-Lead Systems"
- "Speed-to-Lead Systems for Paid-Ads Agencies | Every lead qualified + booked in <60s, 24/7"

**About (first two lines are the hook):**

> I filled out the contact form on 40 home-service websites last month. Average
> time to a human reply: 3 hours 12 minutes. Eleven never replied at all.
>
> Those were paid leads. Someone's agency got blamed.
>
> I build speed-to-lead systems for lead-gen agencies: the moment a lead comes
> in from Meta, Google or the website, it gets a personalised text and email in
> under 60 seconds, answers 3 qualifying questions, and books straight into the
> calendar. 24/7, in the client's voice, from the client's number.
>
> If median response time isn't under a minute in 30 days, the setup fee comes
> back. DM me "60" and I'll mystery-shop one of your clients for free.

**Top skills:** Lead Response Automation, Marketing Automation, CRM Integration,
Twilio, n8n, Conversion Rate Optimisation.

### 5.3 The mystery-shop hook (your unfair advantage)

Before you Loom anyone, fill the contact form on one of *their clients'*
websites (or their own) and time the response. Then your Loom opens with the
proof:

> "I submitted a quote request on [Client]'s site at 10:14 this morning as a
> test. It's now [time] and nobody has replied."

Nobody else is doing this. It converts the pitch from "I sell automation" to
"here is money you are losing right now". Track it: `mystery_shop_minutes` in
your sheet; the aggregate becomes your content.

### 5.4 Loom script (≈70 seconds)

```
Hey [FIRST], thanks for watching this.                                  (greet, wave)

I can see you run [AGENCY] and you're doing paid ads for [local service
niche] clients, so quick question: do your clients ever complain that the
leads are bad, when really nobody called them back fast enough?           (qualify)

If that's not a thing for you, click off, no worries.

But if it is... yesterday I filled out the form on [CLIENT SITE] as a test.
[X hours] later, still no reply.                                          (mystery-shop proof)

What I do is install a speed-to-lead system: the second a lead comes in,
it gets a personalised text and email in under 60 seconds, answers 3
qualifying questions, and books into the calendar. 24/7. From your
client's number, in their voice.                                          (mechanism)

I did this for [PROOF: my own demo / first client]: [N] leads, median
reply [38] seconds, [Y]% booked.                                          (proof, switch tab)

Setup is guaranteed: median reply under a minute in 30 days, or the
setup fee comes back.                                                     (risk reversal)

If you want me to mystery-shop one more of your clients and show you the
numbers, just drop a 👍 and I'll send over the results plus my calendar.  (CTA, thumbs up)

Cheers [FIRST].                                                           (wave)
```

Until you have a client, the proof line is your own demo system. Say so
plainly; honesty reads better than vague "my clients".

### 5.5 DM, follow-ups, voice note

**DM with the Loom (video embedded, not linked):**
> Hey [First]! Saw you run [Agency] for [niche] clients.
> I mystery-shopped [Client] yesterday and recorded a short video on what I found and how I'd fix it in a week.
> Drop a 👍 if you want the numbers.

**Follow-up 1 (48h):**
> Hey [First], just checking: want me to send the response-time numbers from [Client]'s form? Just give me a 👍

**Follow-up 2 (4 days):**
> No stress if the timing's off. I'll close the loop on my end unless you want the mystery-shop results, in which case 👍 and I'll send them over.

**Follow-up 3 (7 days):**
> Last one from me [First]. If getting your clients' leads answered in under 60 seconds is on the list this quarter, I'm here. If not, all good.

**Voice note (reactivation, ≤30s):**
> Hey [First], hope you're good. Checking in since you run [Agency]. I ran a test on one of your clients' forms a while back and the reply took hours. I fix that: every lead answered and booked in under a minute, and the setup's guaranteed. If that's worth 15 minutes, drop a thumbs up and I'll send my calendar. Cheers.

### 5.6 Posts (30-day content calendar, 4/week)

Rotate five pillars. Write them yourself; use AI only to generate angles from
call transcripts.

1. **Mystery-shop results** (weekly): "I filled 20 forms this week. Here's the response-time distribution." Screenshot the table. This is your best post.
2. **Mechanism**: one screenshot of the n8n flow or the SMS thread. "This is what a lead sees 40 seconds after submitting."
3. **Math**: the ROI table from §4.3 with a real client's numbers (anonymised).
4. **Build-in-public**: what broke this week (double-send, quiet hours, a WhatsApp template rejection) and the fix.
5. **Personal** (every 10th post): why you left X, what you learned shipping this.

Each post ends with the same soft CTA: "DM me '60' and I'll mystery-shop one of your clients."

---

## 6. The LinkedIn campaign, operationalised

### 6.1 Tracking sheet columns (ClickUp or Google Sheet)

`name, role, company, niche_served, country, connect_sent, accepted, mystery_shop_site, mystery_shop_minutes, loom_sent, fu1, fu2, fu3, voice_note, reply_type (positive/neutral/no), call_booked, closed (won/lost), notes`

### 6.2 Weekly targets (first 8 weeks)

| Metric | Target | If below |
|---|---|---|
| Connection requests | 150–180/wk, ≤40/day, never >50 | Fine |
| Acceptance rate (2-week lag) | ≥25% | Fix profile/banner/list |
| Looms sent | 50/wk (match acceptances) | Mystery-shop takes 2 min, fine |
| Reply rate (after FU3) | ≥20% | Change opener or geography |
| Positive replies | ≥8/wk | Tighten qualification line |
| Calls booked | ≥3/wk | Fix the thumbs-up → calendar handoff speed (reply within 1 min, practise what you sell) |

### 6.3 Daily block (≈60–75 min)

1. 10 min: open next 10 accepted connections, re-check ICP, add to sheet
2. 10 min: mystery-shop one client site each (just the form submit; the timer runs in the background)
3. 20 min: record 10 Looms, split screen: their profile | your demo dashboard
4. 10 min: download, embed, send with DM; run the follow-up skill
5. 10 min: 40 connection requests in SalesNav
6. Sundays: bulk-update acceptances, record mystery-shop results, write the weekly results post

Automate with what exists: `linkedin-response` skill for replies, a Claude
skill for DM/follow-up generation (Jonatan's pattern), the `scrape-leads` /
`classify-leads` flow for list building, `site-redesign` for the demo site.

---

## 7. Discovery call (20 minutes)

1. **Open with the mystery-shop result** for their client. Let them react.
2. **Three numbers:** leads/month across clients, average close rate, average job value. Fill the ROI table live.
3. **Current process:** who replies, how fast, what tools (forms, CRM, calendar, phone).
4. **Which client first:** pick the one with the most leads and the angriest feedback.
5. **Offer:** Pro tier for that client, 30-day guarantee, price from §4.2. For agencies: white-label from client #2.
6. **Close on a date:** "I need the form access and a number by Thursday, you'll have live leads answered by Monday."

Qualify out if: <30 leads/mo, no CRM/forms, wants a full AI agent, can't name a client.

---

## 8. 30 / 60 / 90 plan

**Days 1–14 (build + warm up):**
- Build the Pro tier on your own demo site; run 100 fake leads; screenshot everything
- Rewrite banner, headline, about per §5.2
- Start connections (10/day → 40/day) and 4 posts/week; no Looms yet
- Mystery-shop 40 sites in the niche; publish the results post

**Days 15–45 (outreach):**
- 50 Looms/week with mystery-shop openers
- Offer 3 free/cheap pilots to the first positive replies, in exchange for a written case study and a LinkedIn post from them
- Deliver each pilot in ≤5 days

**Days 46–90 (convert + productise):**
- Switch pricing to Core / white-label
- Template the build (clone per client in <1 day); write the client-onboarding directive
- Add voice-note reactivation week
- Weekly: results post from real client numbers

**Success at day 90:** 3 case studies, 2–4 paying deployments, $3–6k MRR, a build you can hand to a worker agent.

---

## 9. Mistakes to avoid

- Selling "AI automation" instead of one measurable outcome. Keep it to 60 seconds.
- Guaranteeing revenue. Guarantee response time.
- Building before you have a demo site to point the Loom at.
- US-first texting. A2P registration will eat two weeks; start UK/UAE/AU.
- Replying slowly to a 👍. You sell speed. Reply within a minute, every time.
- Letting AI write the posts before you've written 20 yourself.
- Pending requests >600; withdraw after 3 weeks.
