# Accessory Masters — Product Requirements Document

**Project:** Cold Email System for Business Acquisition Outreach
**Client:** Aleksandar & Simon (Accessory Masters)
**Manager:** Bryce Lindberg (DoubleClick AI)
**Builder:** Debanjan Mazumdar (AntiGravity)
**Contract:** $2,500 fixed — 2 milestones of $1,250 each via Upwork
**Date:** April 28, 2026
**Target delivery:** May 11, 2026 (2 weeks) with 1-week buffer through May 18

---

## Product Vision

Accessory Masters buys small businesses. Aleksandar has been finding sellers manually — sending cold emails one by one with a short, blunt message: "Want to sell your business?" It works. He gets a 4% reply rate, which is exceptional for cold email. But it doesn't scale. He can send maybe a dozen emails a day by hand.

This project turns that manual approach into a machine. The machine finds 800 business owners per day who match the profile, verifies their email addresses, writes a personalized opening line for each one, sends the email through 32 inboxes spread across 10 domains, detects when someone replies with interest, pushes that lead into the CRM, and alerts the team within 3 hours so they can get on a call and close the deal.

The goal is 24,000 emails per month, generating 30-60 positive conversations, filling Aleksandar and Simon's calendar with calls from business owners ready to sell. The system preserves what already works — Aleksandar's blunt, direct tone — and adds scale, automation, and AI personalization on top of it.

Beyond the immediate build, this system positions Accessory Masters to expand into new cities and new industries without hiring more people. The infrastructure (domains, inboxes, scripts, CRM integration) is reusable. Houston is the starting market. Once it's proven, the same machine can target Dallas, Phoenix, Atlanta — any US metro — by changing a few configuration parameters.

### Success Metrics

- 24,000 emails sent per month (~800/day across 32 inboxes)
- 1%+ reply rate (240+ replies/month)
- 30-60 positive conversations per month (prospects interested in selling)
- Booked calls tracked in GoHighLevel
- Pipeline dollar value visible on dashboard
- All positive replies surfaced to the team within 3 hours

### Competitive Advantage

- Aleksandar's proven copy: 4% reply rate on manual sends is the baseline, not the ceiling
- Hedgestone's reputation: $100M+ in deals closed, referenced for credibility
- AI personalization: every email opens with a line specific to the prospect's industry and business
- Scale without quality loss: 800/day with the same personal touch Aleksandar brings manually

---

## How the System Works — The Three Pillars

The system has three stages, like an assembly line:

**Pillar 1 — Sourcing: Find the right business owners.** We use Serper.dev (Google Maps API) to search for businesses in Houston matching the target niches — car washes, pizzerias, laundromats, marinas, and others. For B2B niches that don't show up on Google Maps (manufacturing, professional services), we use Prospeo as a secondary lead database. The output is a raw list of businesses with their names, locations, websites, and industries.

**Pillar 2 — Outreach: Send personalized cold emails at scale.** Each business owner gets their email found (via AnymailFinder) and verified (via Million Verifier) before any email is sent. An AI generates a personalized first line for each prospect. The enriched leads are uploaded to Instantly.ai, which handles campaign management, email sequences, warmup, A/B testing, and the unified inbox. Bryce manages Instantly directly — creating campaigns, writing sequences, running A/B tests. The system's job is to feed Instantly with clean, personalized leads.

**Pillar 3 — Routing: Handle replies and notify the team.** When a prospect replies, the system detects it via Instantly's webhook or API, classifies the reply as positive/negative/neutral using an AI classifier, and for positive replies: creates a contact and opportunity in GoHighLevel (the CRM), and fires a Slack or SMS notification to the team. The website also feeds leads into GHL through a contact form (name, company, email, approximate revenue).

---

## Who We're Targeting — The Ideal Customer Profile (ICP)

| Attribute | Value |
|-----------|-------|
| **Employee count** | 5-50 employees (sweet spot: 5-20) |
| **Revenue** | $1M - $20M per year |
| **Valuation** | $1M - $10M |
| **Industries** | 10 niches (examples discussed: car washes, pizzerias, laundromats, marinas, small oil companies) |
| **Geography** | Houston, TX + Houston suburbs (starting market) |
| **Decision maker** | The owner/founder — not a manager or employee |

**Why these people:** Typically older business owners looking to retire, cash out, or move on. They want certainty — a legitimate buyer, not tire-kickers. Accessory Masters offers that through Hedgestone's track record.

**What's still not finalized (needs client input by May 1):**
- The explicit list of 10 niches
- Exclusions (industries or sizes to avoid)
- Whether to use first-person "I" or "We" in emails
- Differentiator ("what makes you different from other brokers")
- Things they should never say or reference

---

## Who Does What — Role Assignments

This project has three parties. The division of labor is strict and non-overlapping.

### Bryce Lindberg (Manager — DoubleClick AI)
Bryce is client-facing and handles all email infrastructure:
- Buys domains on GoDaddy, sets up DNS records (SPF, DKIM, DMARC)
- Provisions inboxes via Inboxology and connects them to Instantly.ai
- Manages warmup, campaigns, email sequences, and A/B testing in Instantly
- Writes email copy (with client feedback via text)
- Buys pre-warmed test inboxes for the validation phase
- Adds SEO to the website
- Handles domain rotation when sending domains burn out (month 3-6)

### Debanjan Mazumdar (Builder — AntiGravity)
Debanjan builds all custom software:
- Lead sourcing pipeline (Serper.dev scraper + Prospeo integration)
- Email enrichment pipeline (AnymailFinder + Million Verifier)
- AI personalized opener generator
- Website deployment on Vercel (port client's design, wire contact form, embed Calendly)
- GoHighLevel integration (contacts, opportunities, pipeline, appointments)
- Reply classification system (AI reads replies, classifies positive/negative/neutral)
- Dashboard on Vercel (campaign metrics, pipeline data)
- Notification system (Slack/SMS alerts for positive replies)
- Weekly report generator
- Backend automation deployment to Cloudflare Workers
- End-to-end orchestration pipeline

### Client — Aleksandar & Simon (Accessory Masters)
The client provides:
- Service account credentials and API keys for all third-party services
- GoHighLevel admin access
- Finalized ICP (the 10 niches, exclusions, geography)
- Copy inputs (offer, proof, tone, differentiator, never-say list)
- A separate domain for the website (not a sending domain)
- Instantly.ai plan upgrade
- Payment milestones via Upwork

---

## What I Have Right Now

These items are confirmed done as of the April 27 call:

1. **Inboxes are purchased and being licensed.** They'll be added to Instantly within 1-2 days to start the 3-week warmup timer. (Bryce: "The inboxes are bought, they're licensing right now.")
2. **Website design is complete.** Aleksandar finalized it and sent it to Bryce during the April 27 call. (Aleksandar: "I just made the final change to the site.")
3. **Pre-warmed test phase is agreed.** 1 domain + 5 inboxes via Instantly at $50/month, targeting restaurants as a non-core industry for system validation. Cancelable after 1 month.
4. **Separate website domain agreed.** The website will NOT use a sending domain. Client is shopping for a dedicated domain.
5. **Contact form fields defined.** Name, company name, email, approximate revenue.
6. **Contact form → GHL agreed.** Form submissions will create contacts in GoHighLevel.
7. **SEO approach agreed.** General keywords (not local): "sell your business", "sell your business fast", "how do I sell my business", "business broker."
8. **Bryce handles all DNS/domain configuration.** Client doesn't touch this.
9. **Milestone structure agreed.** M1 = systems validated and working. M2 = main inboxes live and sending.
10. **Cloudflare $5/month confirmed.** For hosting backend automation scripts.
11. **Copy review is informal.** Bryce sends copy via text; client responds "change this" or "looks good."
12. **GHL API is fully capable.** V2 API supports contact creation, opportunity creation, inbound webhook triggers for workflows, appointment creation. Auth via Private Integration Tokens. Rate limit: 100 req/10sec.
13. **Instantly.ai API V2 is comprehensive.** Lead creation (`POST /api/v2/leads`), campaign analytics (overview, daily, per-step), reply webhooks (on Hyper Growth plan), Bearer token auth.

## What I Need From Bryce (Before I Can Build)

These are blocking items that only Bryce can provide:

| # | Item | Why I need it | When I need it |
|---|------|---------------|---------------|
| 1 | **Website design file** | Aleksandar sent it to Bryce during Call 3. I need Bryce to forward it to me so I can deploy on Vercel. | **April 29** (tomorrow) |
| 2 | **Instantly.ai API key** | I need access to research endpoint behavior, test lead upload, and build the reply detection system. | **April 30** |
| 3 | **GHL auto-reply workflow scope** | The contact form → GHL → auto-reply email: does Bryce build this in GHL's native workflow UI, or do I build it via API? I need to know which side owns this. | **April 30** |
| 4 | **Instantly.ai plan confirmation** | Reply webhooks require the Hyper Growth plan. If the client is on a lower plan, I need to build polling instead of webhooks. This changes the architecture. | **May 1** |
| 5 | **Pre-warmed inbox campaign ID** | Once Bryce sets up the test campaign in Instantly for restaurants, I need the campaign ID to push test leads into it. | **May 3** |

## What I Need From the Client (Before I Can Test)

These are items the client provides. Most were supposed to be done during onboarding but are delayed by card payment issues.

| # | Item | Why I need it | When I need it |
|---|------|---------------|---------------|
| 1 | **Serper.dev API key** | Powers the Google Maps lead sourcing scraper | **May 1** |
| 2 | **AnymailFinder API key** | Powers the email lookup step | **May 1** |
| 3 | **Million Verifier API key** | Powers the email verification step | **May 1** |
| 4 | **Prospeo API key** | Powers the secondary lead database for B2B niches | **May 1** |
| 5 | **GoHighLevel admin access** | I need API access to build contact/opportunity creation and pipeline integration | **May 1** |
| 6 | **Vercel login** | I need to deploy the website and dashboard (do NOT add Bryce as team member — $20/user charge) | **May 1** |
| 7 | **Cloudflare login** | I need to deploy backend Workers scripts ($5/mo plan, must be Workers, not just DNS) | **May 3** |
| 8 | **Finalized ICP** | The explicit 10 niches, any exclusions, geography confirmation — needed to configure the sourcing pipeline | **May 1** |
| 9 | **Copy inputs** | I vs We, differentiator, never-say list — needed for AI opener generator config | **May 3** |
| 10 | **Website domain** | A dedicated domain (not a sending domain) for the client's website | **May 3** |

---

## The Tech Stack

| Service | What It Does | Cost | Who Integrates |
|---------|-------------|------|----------------|
| **GoDaddy** | 10 sending domains + 1 website domain | ~$121/year ($11 each) | Bryce buys + configures DNS |
| **Inboxology** | 32 email inboxes (Google + Microsoft, ~50/50 split) | ~$112/month | Bryce provisions |
| **Instantly.ai** | Sending platform: campaigns, sequences, warmup, Unibox, A/B testing, webhooks | Subscription TBD (Hyper Growth plan needed for webhooks) | Bryce manages campaigns; Debanjan integrates API |
| **AnymailFinder** | Find business owner email addresses | Starter plan (~1,000 lookups/month) | Debanjan builds script |
| **Million Verifier** | Verify emails are deliverable | Pay-as-you-go ~$0.0004/email | Debanjan builds script |
| **Prospeo** | Secondary lead database for B2B niches | Plan with 1,000+ credits/month | Debanjan builds script |
| **Serper.dev** | Google Maps scraping API | ~$50 for 2,500 credits to start | Debanjan builds script |
| **Vercel** | Hosts website + dashboard | Free tier | Debanjan deploys |
| **Cloudflare Workers** | Hosts backend automation scripts | $5/month | Debanjan deploys |
| **GoHighLevel** | CRM: contacts, pipeline, appointments, workflow triggers | Client's existing account | Debanjan integrates via V2 API |
| **Calendly** | Booking form embedded on website | Client's existing or new account | Debanjan embeds |
| **Slack** | Notification channel for positive reply alerts | Free (incoming webhook) | Debanjan configures |
| **Claude API** | AI opener generation + reply classification | Usage-based (Debanjan covers during build) | Debanjan builds |

### Cost Summary

**One-time costs (client pays):**
- Build fee: $2,500 (2x $1,250 milestones)
- 11 GoDaddy domains: ~$121
- Serper.dev initial credits: ~$50
- Million Verifier initial credits: $20-50
- **Total one-time: ~$2,691-2,721**

**Monthly recurring (client pays):**
- Inboxology (32 inboxes): ~$112
- Instantly.ai subscription: TBD (plan upgrade needed)
- Cloudflare Workers: $5
- AnymailFinder, Prospeo, Million Verifier: varies by usage
- **Estimated total monthly: ~$250-350**

**Temporary (during warmup only):**
- Pre-warmed test inboxes (1 domain + 5 inboxes via Instantly): $50/month for ~1 month

---

## What Gets Built — Every Deliverable

### Deliverable 1: Lead Sourcing Pipeline
**What:** A Python script that takes ICP parameters (industry, location) and outputs a list of matching businesses with their names, addresses, websites, and basic info.
**How:** Calls Serper.dev's Maps/Places API for Google Maps listings. Falls back to Prospeo for B2B niches not found on Maps. Deduplicates results by domain or business name + address.
**Input:** Industry keyword + city (e.g., "car wash Houston TX")
**Output:** Structured JSON/CSV with business name, address, phone, website, industry, source
**Script:** `execution/lead_sourcing/serper_maps_scraper.py` + `execution/lead_sourcing/prospeo_leads.py`

### Deliverable 2: Email Enrichment Pipeline
**What:** A two-step process that finds the business owner's email and verifies it's real.
**How:** Step 1: AnymailFinder API takes a business name + domain and returns email addresses with confidence scores. Step 2: Million Verifier API pings the mail server to confirm the email exists. Only verified emails pass through.
**Input:** Business list from Deliverable 1
**Output:** Same list, enriched with verified owner email addresses. Invalid emails discarded.
**Script:** `execution/enrichment/anymailfinder_lookup.py` + `execution/enrichment/million_verifier.py`

### Deliverable 3: AI Personalized Opener Generator
**What:** An LLM-based script that generates a unique first line for each prospect, referencing something specific about their industry, business, or location.
**How:** Takes prospect data (business name, industry, location, website) and generates an opener like "I noticed your car wash on Main St has great reviews..." using the Claude API. Respects the client's tone (blunt, direct), voice (I vs We), and never-say list.
**Input:** Enriched lead list from Deliverable 2
**Output:** Same list with a `personalized_opener` field appended to each lead
**Script:** `execution/personalization/ai_opener_generator.py`

### Deliverable 4: Website Deployment
**What:** Deploy the client's website design to Vercel, wire up the contact form, embed the Calendly booking page.
**How:** Port the client's design files (received by Bryce from Aleksandar on April 27). Deploy on Vercel's free tier. Connect to a dedicated website domain (NOT a sending domain). Contact form fields: name, company name, email, approximate revenue. Form submissions POST to GoHighLevel to create a new contact.
**Dependencies:** Website design file from Bryce. Website domain from client.
**URL:** TBD (e.g., accessorymasters.com or similar)

### Deliverable 5: GoHighLevel Integration
**What:** Wire the CRM so it receives leads automatically from three sources: cold email replies, website contact form, and Calendly bookings.
**How:** Uses GHL V2 API (`https://services.leadconnectorhq.com/`). Auth via Private Integration Token.
**Integration points:**
- Positive email reply → `POST /contacts/` (create contact with name, email, company, industry, source tag "cold email", reply text in notes) + `POST /opportunities/` (create opportunity in pipeline at "New" stage)
- Website contact form → `POST /contacts/` (name, company, email, revenue as custom field)
- Calendly booking → `POST /calendars/events/appointments/` (or via Calendly → GHL native integration)
- GHL workflow trigger for auto-reply email: if Bryce builds this in GHL's UI, I just POST to the inbound webhook URL. If I build it, I use the GHL API to send an email via workflow.
**Pipeline stages:** New → Contacted → Interested → Booked → Closed
**Script:** Part of `execution/gtm_client_workflows/accessory_masters_pipeline.py`

### Deliverable 6: Reply Classification System
**What:** Detects new replies from Instantly.ai and classifies each one as positive, negative, or neutral using an AI classifier.
**How:** Two options depending on the client's Instantly plan:
- **Option A (Hyper Growth plan):** Instantly fires a webhook POST to our endpoint when a reply arrives. Our Cloudflare Worker receives it, calls Claude API to classify, and routes accordingly.
- **Option B (lower plan):** A cron job polls Instantly's Unibox API (`/api/v2/unibox/emails`) every 30 minutes, checks for new replies, classifies each one, and routes.
**Classification categories:**
- Positive: "yes, tell me more", "interested", "what's the process", "call me"
- Negative: "not interested", "remove me", "stop emailing", "unsubscribe"
- Neutral: auto-replies, out-of-office, bouncebacks
**Routing:** Positive → GHL contact + opportunity + notification. Negative → log only. Neutral → log only.
**Latency target:** Positive reply to notification within 3 hours.
**Script:** Part of `execution/gtm_client_workflows/accessory_masters_pipeline.py`

### Deliverable 7: Dashboard
**What:** A web-based metrics dashboard showing campaign performance in real-time.
**How:** Hosted on Vercel (free tier). Pulls data from two sources:
- Instantly.ai API → emails sent (today/week/month), deliverability health (bounce rate, spam rate per inbox), reply rate, positive reply rate. Endpoints: `GET /api/v2/campaigns/analytics`, `GET /api/v2/campaigns/analytics/daily`, `GET /api/v2/campaigns/analytics/overview`.
- GoHighLevel API → booked calls (appointments), pipeline $ (opportunities with monetary values).
**URL:** TBD (e.g., accessorymasters-dashboard.vercel.app)

### Deliverable 8: Notification System
**What:** Real-time alerts when a positive reply is detected.
**How:** Slack incoming webhook POST with prospect name, company, reply snippet, and link to GHL contact. Configurable to switch to SMS (Twilio) if client prefers.
**Latency:** Within 3 hours of the reply (determined by webhook speed or polling frequency).

### Deliverable 9: Weekly Report Generator
**What:** An automated summary email sent to the client every week.
**Contents:** Emails sent, deliverability rate, reply rate, positive reply count, booked calls, pipeline $ value.
**How:** Cron job on Cloudflare Workers pulls data from Instantly + GHL APIs, formats a summary, and sends via email (GHL or direct SMTP).

### Deliverable 10: Backend Deployment
**What:** All pipeline scripts deployed to Cloudflare Workers on the $5/month plan.
**What runs there:**
- Cron-triggered lead sourcing (daily or weekly, configurable)
- Reply polling (if webhooks are not available — every 30 minutes)
- Webhook receiver (if on Instantly Hyper Growth plan)
- Weekly report generation
- Notification dispatch

### Deliverable 11: End-to-End Orchestration Pipeline
**What:** A master script that ties everything together: sourcing → enrichment → personalization → upload to Instantly.
**How:** Reads ICP config, runs the sourcing pipeline, enriches results, generates openers, deduplicates against previously sent leads, and pushes the batch to Instantly via `POST /api/v2/leads` with campaign assignment and custom variable mapping for the opener.
**Script:** `execution/gtm_client_workflows/accessory_masters_pipeline.py`

---

## Build Timeline — 2-Week Delivery Plan

Bryce's deadline is 3 weeks from April 27 (May 18). I am targeting **2-week delivery by May 11** — everything functioning, tested, and built — leaving a 1-week buffer (May 12-18) for fixes and issues.

### Block 1: April 29-30 (Days 1-2) — Foundation

**What I build (no blockers — can start immediately):**

| Task | Time | Output |
|------|------|--------|
| Research Serper.dev, AnymailFinder, Million Verifier, Prospeo APIs — read docs, understand endpoints, rate limits, auth | 3 hours | API integration notes |
| Write the master project directive | 2 hours | `directives/gtm_client_workflows/accessory_masters_gtm.md` |
| Write subsystem directives (lead sourcing, enrichment, personalization, infrastructure) | 3 hours | 4 directive files |
| Write lead sourcing scripts (Serper.dev Maps scraper + Prospeo integration) with mock data | 4 hours | `execution/lead_sourcing/serper_maps_scraper.py`, `prospeo_leads.py` |
| Write email enrichment scripts (AnymailFinder + Million Verifier) with mock data | 3 hours | `execution/enrichment/anymailfinder_lookup.py`, `million_verifier.py` |
| Write AI opener generator script | 2 hours | `execution/personalization/ai_opener_generator.py` |

**What I need by end of Day 2:**
- Website design file from Bryce (asked for April 29)
- Instantly.ai API key from Bryce (asked for April 30)

**Parallel work by Bryce (happening in background):**
- Adding inboxes to Instantly, starting warmup timer
- Buying pre-warmed test domain + 5 inboxes
- DNS configuration on sending domains

### Block 2: May 1-2 (Days 3-4) — Integrations + Website

**What I build:**

| Task | Time | Depends on |
|------|------|------------|
| Deploy website to Vercel (port design, wire contact form, embed Calendly) | 4 hours | Website design file from Bryce |
| Build GHL integration — contact creation, opportunity creation, pipeline setup | 4 hours | GHL admin access from client |
| Build reply classification system (webhook receiver or polling, AI classifier) | 4 hours | Instantly API key from Bryce |
| Wire website contact form → GHL (POST to /contacts/) | 2 hours | GHL access |
| Build Slack notification system (incoming webhook) | 2 hours | None |

**What I need by end of Day 4:**
- All API keys from client (Serper, AnymailFinder, Million Verifier, Prospeo)
- Vercel login from client
- Confirmation from Bryce: GHL auto-reply workflow scope

**Two parallel streams running:**
- **Stream A:** Website + GHL integration (website deployment, contact form wiring, CRM setup)
- **Stream B:** Reply classification + notifications (Instantly API integration, AI classifier, Slack alerts)

### Block 3: May 3-5 (Days 5-7) — Dashboard + Pipeline Testing

**What I build:**

| Task | Time | Depends on |
|------|------|------------|
| Test lead sourcing with REAL API keys (Serper: "car wash Houston TX", etc.) | 2 hours | Serper API key |
| Test email enrichment with real data (AnymailFinder + Million Verifier on 10 sample businesses) | 2 hours | AnymailFinder + MV keys |
| Build the orchestration pipeline (source → enrich → personalize → upload to Instantly) | 4 hours | Instantly API key |
| Build the dashboard (Vercel, pull from Instantly analytics + GHL APIs) | 6 hours | Instantly + GHL API access |
| Build weekly report generator | 2 hours | Same data sources as dashboard |
| Wire website domain (connect client's purchased domain to Vercel) | 1 hour | Domain from client |

**Critical path checkpoint:** By the end of Day 7 (May 5), every individual component should work in isolation. The remaining days are for integration and full system testing.

### Block 4: May 6-8 (Days 8-10) — Cloudflare Deployment + Integration

**What I build:**

| Task | Time | Depends on |
|------|------|------------|
| Deploy all scripts to Cloudflare Workers | 4 hours | Cloudflare login |
| Set up cron triggers (daily lead sourcing, reply polling if needed, weekly reports) | 2 hours | Workers deployed |
| End-to-end integration test: source → enrich → personalize → upload to Instantly campaign | 3 hours | Pre-warmed campaign ID from Bryce |
| End-to-end integration test: reply → classify → GHL → notification | 3 hours | Everything wired |
| End-to-end integration test: website form → GHL → auto-reply | 1 hour | GHL workflow built |
| Fix issues found during integration | 4 hours | Buffer |

### Block 5: May 9-11 (Days 11-14) — Pre-Warmed Test + Milestone 1

**What happens:**

| Task | Time | Depends on |
|------|------|------------|
| Source restaurant leads in Houston via pipeline | 1 hour | Pipeline working |
| Push enriched leads to pre-warmed test campaign in Instantly | 1 hour | Bryce has campaign ready |
| Monitor: emails delivering to inbox (not spam)? | Ongoing | Test campaign sending |
| Monitor: reply detection working? | Ongoing | Test replies |
| Monitor: GHL receiving contacts from positive replies? | Ongoing | GHL integration |
| Monitor: website form → GHL working? | 1 test | Website live |
| Monitor: notifications firing? | 1 test | Slack webhook |
| Dashboard showing real data? | 1 check | Dashboard deployed |
| Fix any issues found | Buffer | - |
| **Milestone 1 demonstration to client** | - | All above pass |

**Milestone 1 acceptance (all must pass):**
- Website is live on dedicated domain
- Contact form submits to GHL
- Pre-warmed test emails are sending
- Reply detection and classification works
- Positive reply → GHL contact + opportunity
- Notification fires for positive reply
- Lead sourcing pipeline produces verified leads
- Dashboard displays data

**Client releases Milestone 1 ($1,250) on Upwork.**

### Buffer Week: May 12-18 (Days 15-21) — Fixes + Milestone 2

This week is buffer for:
- Fixing any issues found during the test phase
- Tuning the AI opener prompts based on client feedback
- Adjusting reply classification thresholds
- Performance optimization (Cloudflare Worker execution times, API call batching)
- Preparing for main launch

**May 18 (Day 21):** Main 32 inboxes complete their 3-week warmup (started ~April 28). Bryce switches from test campaign to real ICP campaigns. System begins sending ~800 emails/day to actual prospects.

**Milestone 2 acceptance:**
- Main 32 inboxes are warmed and sending real campaigns
- AI openers generating for real ICP leads
- Dashboard showing real metrics
- Weekly report configured
- Full pipeline operational at scale

**Client releases Milestone 2 ($1,250) on Upwork.**

---

## Parallel vs Sequential — What Saves Time

### Things that can run in parallel (saving ~5 days)

| Stream A | Stream B | Stream C |
|----------|----------|----------|
| Lead sourcing + enrichment scripts (Days 1-2) | API research + directive writing (Days 1-2) | Bryce: warmup + DNS + pre-warmed setup |
| Website deployment (Days 3-4) | Reply classification + notifications (Days 3-4) | Bryce: campaign creation in Instantly |
| Dashboard build (Days 5-7) | Cloudflare deployment (Days 8-10) | Client: API keys, accounts, ICP |

### Things that MUST be sequential

1. Lead sourcing script → must be written before enrichment script (enrichment consumes sourcing output)
2. Enrichment script → must be written before AI opener script (opener consumes enrichment output)
3. All three above → must work before orchestration pipeline can be tested
4. GHL access → must be granted before any CRM integration can be tested
5. Instantly API key → must be received before reply classification can be built
6. Pre-warmed campaign → must be running before Milestone 1 test phase
7. Milestone 1 → must pass before Milestone 2 work begins

### Critical Path

The longest chain of dependent tasks that determines the earliest possible completion:

```
API keys from client (May 1)
    → Test sourcing + enrichment with real data (May 3)
    → Push test leads to pre-warmed campaign (May 6)
    → Monitor test emails + reply flow (May 9-11)
    → Milestone 1 demonstration (May 11)
```

**If API keys are delayed past May 1, the entire timeline shifts.** This is the single biggest risk to on-time delivery.

---

## Assumptions

These are things I believe to be true but have not independently verified. Each one is stated explicitly so that if any assumption is wrong, we can adjust before it becomes a problem.

| # | Assumption | Impact if wrong |
|---|-----------|----------------|
| A1 | Instantly.ai V2 API allows lead creation via `POST /api/v2/leads` with custom variable fields (for the personalized opener) | If custom variables aren't supported via API, I'd need to format leads as CSV and upload through the Instantly UI — adds manual step for Bryce |
| A2 | Instantly.ai exposes reply webhooks on the Hyper Growth plan | If the client's plan doesn't include webhooks, I build a polling system instead (every 30 min via Cloudflare cron). Latency goes from near-real-time to 30 min worst case. Still within the 3-hour SLA. |
| A3 | GoHighLevel V2 API supports Private Integration Tokens (static API keys) for our use case | If not, we need to set up OAuth 2.0 app registration, which adds 2-4 hours of auth flow work |
| A4 | The client will be on the Standard volume tier (10 domains, 32 inboxes, ~800/day) | If they pick Starter (16 inboxes, 400/day) or Scale (48 inboxes, 1,200/day), the scripts work unchanged — only pipeline config changes |
| A5 | Serper.dev's Maps endpoint returns business owner names or enough data to pass to AnymailFinder | If Maps only returns business name + address (no owner), I'll need to add a step that finds the owner name via the company website or LinkedIn before email lookup |
| A6 | Million Verifier supports single-email real-time verification via API, not just batch CSV upload | If only batch, I'll need to collect emails in batches of 50-100, submit, wait for results, then continue — adds latency to the pipeline but doesn't break it |
| A7 | Cloudflare Workers $5/month plan is sufficient for our workload (lead sourcing daily + reply polling every 30 min + weekly reports) | The $5 plan gives 10M requests/month. Our volume is ~50-100 requests/day. This is well within limits. |
| A8 | Claude API is the right LLM for opener generation and reply classification | Could use a cheaper model (Haiku) for classification and a stronger one (Sonnet) for openers. Cost optimization happens during tuning. |
| A9 | The website design file from the client is deployable on Vercel (HTML/CSS/JS, Next.js, or similar static site) | If it's a Wix/Squarespace export or a Figma file, porting will take longer (add 4-8 hours) |
| A10 | GHL auto-reply workflow for contact form submissions is built by Bryce in GHL's native UI | If I need to build it, add 3-4 hours for email sending integration via GHL API or external SMTP |

## Hypotheses

These are predictions I'm making about system behavior. They will be validated during the test phase.

| # | Hypothesis | How we validate |
|---|-----------|----------------|
| H1 | Reply classification can achieve 90%+ accuracy using a simple prompt with Claude Haiku | Test with 20 sample replies during the pre-warmed test phase. If accuracy < 90%, upgrade to Sonnet or add few-shot examples. |
| H2 | Polling Instantly's API every 30 minutes meets the 3-hour notification SLA | Time the flow: poll → classify → GHL push → Slack notification. If total exceeds 3 hours, increase polling frequency to every 15 min. |
| H3 | Serper.dev's 2,500 credits are sufficient for the initial Houston launch across 10 niches | Each niche × 1 city = ~10 queries. At ~50 results per query, that's 500 leads. If niches + suburbs expand, credits will need topping up. |
| H4 | The pre-warmed test campaign on restaurants will generate enough replies to validate the full system | Even a 0.5% reply rate on 100-200 test emails should yield 1-2 replies — enough to confirm the pipeline works. |
| H5 | Vercel's free tier can handle the dashboard and website without hitting limits | Free tier: 100GB bandwidth, serverless functions, edge network. Our traffic is internal (client team only) + low-volume website visitors. Well within limits. |

---

## Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R1 | Client API keys delivered late (past May 1) | **High** — card payment issues ongoing | **High** — shifts entire timeline | Bryce offered to use his card. Message Bryce tomorrow to confirm status. Build everything with mock data so only testing is blocked. |
| R2 | Instantly.ai plan doesn't include webhooks | **Medium** — depends on plan upgrade | **Low** — polling works as fallback | Build both paths: webhook receiver AND polling. Use polling as default, upgrade to webhooks if available. |
| R3 | Website design file is not web-ready (Figma/PSD instead of HTML) | **Medium** — depends on what Aleksandar "sent" | **Medium** — adds 4-8 hours for conversion | Ask Bryce to check the file format before forwarding. If not HTML, flag immediately. |
| R4 | Serper.dev Maps doesn't return owner names | **Medium** — Maps returns business info, not personal | **Medium** — adds an extra scraping/lookup step | Add a company-to-owner resolution step using the business website or LinkedIn data from AnymailFinder |
| R5 | GHL admin access never granted | **Low** — asked for multiple times | **High** — blocks all CRM integration | Escalate through Bryce if not received by May 1 |
| R6 | ICP never fully finalized | **Medium** — client hasn't locked 10 niches | **Medium** — can't run targeted sourcing | Use the examples discussed (car washes, pizzerias, laundromats, etc.) as defaults. Swap niches later via config change. |
| R7 | Upwork contract never started | **Medium** — deferred to systems validation | **Low for build** — I build regardless; payment is delayed | Bryce manages this relationship. Flag at Milestone 1 demo if still not started. |

---

## Open Questions — Need Answers By Date

| # | Question | Who answers | Needed by | Default if unanswered |
|---|----------|-------------|-----------|----------------------|
| 1 | What is the client's Instantly.ai plan? Does it include webhooks (Hyper Growth)? | Bryce | May 1 | Build polling (30-min cron) as default |
| 2 | Does Bryce build the GHL auto-reply workflow for contact form submissions, or do I? | Bryce | April 30 | Assume Bryce handles it in GHL UI |
| 3 | What format is the website design file? (HTML/Next.js vs Figma/PSD vs something else) | Bryce | April 29 | Assume HTML/static site |
| 4 | Slack or SMS for notifications? Or both? | Client (via Bryce) | May 3 | Default to Slack (free, simpler) |
| 5 | Explicit list of the 10 ICP niches? | Client | May 1 | Use discussed examples: car washes, pizzerias, laundromats, marinas, small oil companies + 5 TBD |
| 6 | First-person "I" or "We" in emails? | Client | May 3 | Default to "I" (matches Aleksandar's manual style) |
| 7 | Is the volume tier confirmed as Standard (32 inboxes)? | Client | May 1 | Assume Standard |

---

## What Is NOT Included

These items are explicitly outside the $2,500 build scope:

- Adding new niches or geographies beyond the Houston launch set
- Scaling from Standard to Scale tier (48 inboxes, 1,200/day)
- Ongoing campaign management, copy iteration, or A/B testing (Bryce handles)
- Domain rotation and hot-swapping when sending domains burn out (Bryce handles, month 3-6)
- Additional CRM integrations beyond GoHighLevel
- Content creation (blog posts, social media)
- Paid advertising
- Ongoing management beyond the first 7 days of tuning post-launch
- SMS notification setup via Twilio (only if client explicitly requests; default is Slack)

---

## Files That Will Be Created

### Directives (SOPs)
1. `directives/gtm_client_workflows/accessory_masters_gtm.md` — Master pipeline directive
2. `directives/lead_sourcing/google_maps_sourcing.md` — Serper.dev Maps scraping SOP
3. `directives/enrichment/email_find_verify.md` — AnymailFinder + Million Verifier SOP
4. `directives/personalization/cold_email_sequences.md` — AI opener generation SOP
5. `directives/infrastructure/domain_inbox_management.md` — Infrastructure management SOP

### Execution Scripts
6. `execution/lead_sourcing/serper_maps_scraper.py` — Google Maps scraper via Serper.dev
7. `execution/lead_sourcing/prospeo_leads.py` — Prospeo lead database integration
8. `execution/enrichment/anymailfinder_lookup.py` — Email finder
9. `execution/enrichment/million_verifier.py` — Email verifier
10. `execution/personalization/ai_opener_generator.py` — AI personalized first-line generator
11. `execution/gtm_client_workflows/accessory_masters_pipeline.py` — End-to-end orchestration + reply classification + GHL integration + notifications

### Web Deployments
12. Website on Vercel (client's design + contact form + Calendly)
13. Dashboard on Vercel (metrics from Instantly + GHL)
14. Backend Workers on Cloudflare (cron jobs + webhook receiver)

---

## Milestone Payment Structure

**Milestone 1 ($1,250) — Systems Validation (target: May 11)**
Payment is released when the client sees all systems working:
- Website is live on dedicated domain
- Pre-warmed test emails are sending (restaurants)
- Website contact form → GHL creates contact
- Reply detection → classification → GHL contact + opportunity
- Notification fires for positive replies
- Lead sourcing pipeline produces verified leads
- Dashboard displays data

**Milestone 2 ($1,250) — Main Launch (target: May 18)**
Payment is released when the main campaign goes live:
- 32 inboxes warmed and sending real ICP campaigns (~800/day)
- AI openers generating for real prospects
- Dashboard showing real metrics at scale
- Weekly report sending
- Full pipeline operational end-to-end
- Pre-warmed test subscription cancelled

**Upwork contract has not yet started as of April 28.** Milestone payments will be initiated once systems are validated (Aleksandar's requirement from Call 3).
