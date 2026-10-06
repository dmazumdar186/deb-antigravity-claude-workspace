/* GTM People — v3 "Brief it". One IIFE, zero dependencies, no globals.
   Concept by ProdCraft — all copy below is the live gtm-people.com text, held as data. */
(function () {
  'use strict';
  var doc = document, root = doc.documentElement;
  root.classList.add('has-js');
  window.addEventListener('error', function () { root.classList.remove('has-js'); });
  var $ = function (s, c) { return (c || doc).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || doc).querySelectorAll(s)); };
  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var h = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (ch) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]; }); };

  /* ---------------- Knowledge base (live copy as data) ---------------- */
  var KB = {"specialisms":[{"name":"Founding Sales","text":"Your first AE, SDR or sales leader. The hire that defines your revenue trajectory — we've done this over 50 times."},{"name":"Account Executives","text":"Closers who thrive in ambiguity. Mid-market and enterprise AEs at every stage, from first quota-carrier to senior enterprise."},{"name":"Customer Success","text":"Retention-obsessed CSMs and AMs who turn customers into advocates. Net revenue retention starts with the right people."},{"name":"Sales Development","text":"Pipeline machines. SDRs and BDRs who create qualified opportunities from scratch — outbound, inbound, and hybrid."},{"name":"GTM Leadership","text":"CROs, VPs of Sales, and Heads of Revenue who've scaled a function before and know what good looks like at your stage."},{"name":"Revenue Operations","text":"The system thinkers who wire your GTM engine for scale. RevOps, SalesOps, and Marketing Ops specialists."},{"name":"Marketing","text":"Demand gen, product marketing and growth hires who build pipeline and position you to win."},{"name":"GTM Engineering","text":"The new breed wiring Clay, outbound and AI into pipeline systems — rare, and easy to hire wrong."},{"name":"Pre-Sales & Solutions","text":"Sales engineers and solutions consultants who win the technical sale and de-risk the deal."}],"clientSteps":[{"n":"01","name":"Deep Brief","text":"A 60-minute onboarding call. We go beyond the job spec — your stage, culture, ICP, what the last hire got wrong, what great actually looks like in this role at your size of business."},{"n":"02","name":"Market Map","text":"We build a targeted longlist from our active GTM network and run a structured headhunt. No job board blasts. No CV farming. Every candidate is approached specifically for your role."},{"n":"03","name":"Screen & Qualify","text":"We screen candidates against your brief, verify track record, check motivations are genuine, and prepare a written summary on each. You only see people who are truly in play."},{"n":"04","name":"Curated Shortlist","text":"You receive 3–5 fully briefed, motivated candidates — typically within 5 working days. Each comes with a summary, salary expectations, and our assessment of fit."},{"n":"05","name":"Interview Support","text":"We manage scheduling, prep both sides, gather structured feedback after each stage, and keep candidates warm so you don't lose them to a competitor offer while you deliberate."},{"n":"06","name":"Offer & Close","text":"We handle the offer, negotiate on your behalf, and manage the counter-offer risk. 7 in 10 candidates who accept a counter-offer leave within 9 months — we coach through this carefully."}],"checkins":{"title":"30 / 60 / 90 Day Check-ins","text":"After every placement we check in with both the client and the candidate at 30, 60, and 90 days. If something isn't working, we want to know — and fix it — before it becomes a problem. Every placement carries our 3-month replacement guarantee."},"taasReview":{"title":"TaaS Clients: Ongoing Partnership","text":"For Scaleup and Unicorn tier clients, we run a monthly hiring review — pipeline updates, market intelligence, upcoming role planning. Your talent partner stays embedded so you're never starting from scratch on the next hire."},"candidateSteps":[{"n":"01","name":"Register","text":"Apply for a specific role or register your interest in being considered for future opportunities. We review every submission personally — no black hole."},{"n":"02","name":"Intro Call","text":"A consultant calls within 48 hours. We want to understand your motivations, not just your CV — what stage you want to join, what kind of mission matters, what you're actually looking for next."},{"n":"03","name":"Matched to Roles","text":"We match you to live roles that fit your profile. We'll only put you forward for roles where we genuinely believe you're a strong fit — not to fill a quota."},{"n":"04","name":"Supported Process","text":"We brief you fully on the company, coach you through the interview stages, manage feedback in real time, and handle offer negotiation so you go in with full information."}],"salary":[{"role":"SDR / BDR","base":"£28k – £45k","ote":"OTE £45k – £75k","note":"Seed → Series B · 60/40 base:variable"},{"role":"Account Executive","base":"£55k – £90k","ote":"OTE £110k – £180k","note":"Series A → Series C · 50/50 split"},{"role":"Customer Success Manager","base":"£45k – £70k","ote":"OTE £60k – £95k","note":"Seed → Series B · expansion-based variable"},{"role":"RevOps Manager","base":"£55k – £80k","ote":"OTE £65k – £95k","note":"Series A → Series C · system-bonus weighted"},{"role":"Head of Sales","base":"£80k – £120k","ote":"OTE £150k – £220k","note":"Series A → Series B · team quota-carry"},{"role":"VP Sales / CRO","base":"£120k – £180k","ote":"OTE £220k – £320k+","note":"Series B → Series C · equity + LTIP"}],"salaryIntro":"UK market rates for B2B SaaS go-to-market roles. Ranges reflect Seed to Series C benchmarks — London-weighted, based on live placement data.","salaryCta":["Need a detailed benchmark for your specific role, stage, and geography? We'll send you a custom comp report.","Request a Salary Benchmark →"],"faqs":[{"q":"What is GTM recruitment?","a":"GTM (go-to-market) recruitment is the specialist hiring of sales, marketing, customer success, and RevOps professionals for B2B SaaS companies. It covers Account Executives, SDRs, BDRs, Customer Success Managers, RevOps specialists, and GTM leaders from Head of Sales to CRO."},{"q":"When should a SaaS startup hire their first salesperson?","a":"Most early-stage SaaS companies should hire their first dedicated salesperson once they have 5–10 paying customers and repeatable product-market fit signals. At Seed stage, founders typically carry the first sales motion before making a first commercial hire between £1M–£3M ARR. Hiring too early — before PMF — is the most common costly mistake."},{"q":"What's the difference between an SDR and a BDR?","a":"An SDR (Sales Development Representative) typically handles inbound lead qualification — responding to people who've raised their hand. A BDR (Business Development Representative) focuses on outbound prospecting to target accounts. At early-stage SaaS startups, the roles are often combined, with the hire focused on building pipeline from scratch using both motions."},{"q":"What does a SaaS GTM recruitment agency charge?","a":"GTM People operates on a Talent as a Service (TaaS) model — a monthly or annual subscription giving you a dedicated talent partner without per-placement fees. For lower-volume hiring we also offer retained search, structured in thirds: on instruction, shortlist, and placement. TaaS clients making 3+ hires per year typically save 40–60% compared to traditional per-hire agency costs."},{"q":"How long does it take to hire an Account Executive?","a":"Working with GTM People, we typically deliver a first shortlist within five days. Without specialist support, most in-house teams take 60–90 days to hire. The biggest factors are comp-package competitiveness and clarity on the ideal candidate profile."},{"q":"What should I pay a Series A SaaS Account Executive?","a":"UK: a mid-market AE at Series A typically earns £55,000–£75,000 base with 50/50 OTE (£110,000–£150,000 total); London and enterprise sit at the higher end (£80,000–£100,000 base, OTE to £180,000+). US: expect roughly $120,000–$150,000 base with $240,000–$300,000 OTE for a comparable mid-market AE, higher in the Bay Area / New York and for enterprise. Under-paying by more than ~10% vs. market means you'll lose candidates at offer stage."},{"q":"Do you work with companies outside the UK?","a":"Yes — while GTM People is based in London, we place GTM talent globally. We regularly support SaaS companies hiring across EMEA (Germany, Netherlands, France), as well as US-based companies expanding into the UK and Europe. We can also help with US-based GTM hires for companies in the Americas."},{"q":"What if the hire doesn't work out?","a":"All GTM People placements come with a 3-month replacement guarantee as standard — if the hire doesn't work out within the first 3 months, we'll rerun the search at no additional fee. Scaleup and Unicorn TaaS clients benefit from extended 6–12 month guarantee periods. The guarantee does not apply if fees are unpaid."}],"partners":[{"name":"RemoFirst","tag":"Global hiring & EOR","text":"Compliant international hiring in 185+ countries, at partner rates."},{"name":"Pocket","tag":"AI meeting & call notes","text":"An AI device that captures your meetings and calls and turns them into instant transcripts, summaries and action items — ideal for sales teams and founders."},{"name":"Apollo.io","tag":"Sales intelligence & engagement","text":"All-in-one sales intelligence & engagement — verified B2B contact data, email sequences and a dialler in one place."},{"name":"Amplemarket","tag":"AI outbound platform","text":"AI-powered outbound for B2B sales teams — prospect data, multichannel sequences and AI copilots to book more meetings."},{"name":"Claap","tag":"AI call recording & coaching","text":"AI call recorder and sales-coaching tool — captures meetings without a bot, summarises calls and helps managers coach reps."},{"name":"AI Accounts","tag":"Accounting & finance for founders","text":"Startup-savvy, AI-led accountants who genuinely get early-stage SaaS — cash visibility, forecasting and finance support for founders and their new hires."},{"name":"Close","tag":"Sales CRM for startups & SMBs","text":"A CRM built for startup and SMB sales teams — calling, email, SMS and pipeline in one place so reps sell instead of doing admin."},{"name":"Tellent","tag":"HR & recruiting (Recruitee ATS)","text":"People platform for growing teams — Recruitee applicant tracking plus HR, performance and learning tools in one suite."},{"name":"Rippling","tag":"HR, payroll & IT platform","text":"All-in-one workforce platform — payroll, HR, benefits, devices and app access running off one employee record."},{"name":"Navan","tag":"Business travel & expense","text":"Business travel and expense management in one app — book trips, control policy and automate expense reports."},{"name":"Pipedrive","tag":"Sales CRM & pipeline","text":"Simple, visual sales CRM and pipeline management for growing teams — set up a founder-led pipeline in an afternoon. Extended 30-day free trial via our link."},{"name":"Gamma","tag":"AI decks & documents","text":"AI-powered presentations, documents and web pages created in minutes — build an interview case-study or board deck fast."},{"name":"lemlist","tag":"Multichannel outreach","text":"Multichannel outreach for personalised email and LinkedIn prospecting — personalisation at scale for a lean SDR team."},{"name":"KrispCall","tag":"Cloud phone & dialler","text":"AI-powered cloud phone system with virtual numbers, a power dialler and CRM integrations — give a new SDR a dialler and local numbers on day one."},{"name":"Capsule CRM","tag":"Simple CRM for small teams","text":"Simple, affordable CRM built for small teams, with Transpond for email marketing — a UK-built first CRM for founder-led sales."},{"name":"Surfer","tag":"SEO content optimisation","text":"Write content that ranks — Surfer scores and guides your pages against what's already winning in search, for marketing teams and candidates building a personal brand."},{"name":"Dropbox DocSend","tag":"Document sharing & analytics","text":"Secure document sharing with analytics — see who opened your pitch deck or proposal and for how long. Ideal for founders sending decks to investors."},{"name":"Trainual","tag":"Onboarding & SOPs","text":"Turns your playbook, processes and onboarding into one place new hires can follow from day one — so a new SDR or AE ramps on your process, not tribal knowledge."},{"name":"Datarails","tag":"FP&A for finance teams","text":"FP&A platform that automates budgeting, forecasting and board reporting while keeping Excel at the core — finance firepower before your first FP&A hire."},{"name":"Lusha","tag":"Sales intelligence & contact data","text":"Verified emails and direct dials for sales teams, with a free plan to start — useful for reps prospecting and for candidates researching target employers."},{"name":"folk","tag":"AI-assisted CRM for small teams","text":"A simple, AI-assisted CRM for small teams and founder-led sales — contacts, pipelines and follow-ups in one lightweight workspace."},{"name":"doola","tag":"US company formation & compliance","text":"US company formation, bookkeeping, tax and compliance for founders outside the US — Delaware C-corp or LLC, EIN and registered agent, handled online."},{"name":"Signable","tag":"UK eSignature","text":"UK-built eSignature for getting contracts, offer letters and onboarding documents signed quickly and securely."},{"name":"MeetGeek","tag":"AI note-taker","text":"AI meeting assistant that records, transcribes and summarises your Zoom, Google Meet and Teams calls, then sends notes and action items to your CRM and team tools — so founders and new reps never lose what was agreed on a call."},{"name":"Aircall","tag":"Cloud phone system","text":"Cloud phone system for sales and support teams: local numbers in 100+ countries, call recording, a power dialler and native HubSpot, Salesforce and Pipedrive integrations — so every call is logged without admin."},{"name":"Blinq","tag":"Digital business cards","text":"Digital business cards for the whole team — share contact details by QR code or tap, keep branding consistent, and capture leads met at events straight into your CRM. 50% off the first 3 months of Blinq for Business through our link."},{"name":"Livestorm","tag":"Webinars & virtual events","text":"Browser-based webinars and virtual events for SaaS teams — product demos, customer onboarding and live Q&As with registration pages, follow-up emails and CRM sync built in. Nothing for attendees to download."},{"name":"Vista Social","tag":"Social media · sales & marketing","text":"All-in-one social media management: schedule and publish across every channel, engage from one inbox, and report on performance — managing multiple brands or clients from a single workspace."}],"about":["GTM People was founded by Ian Harwood — a specialist GTM recruiter with over 20 years of experience placing sales, marketing, RevOps, and CS leaders across the UK and Europe.","After over two decades placing GTM talent — first at generalist agencies, then building a specialist SaaS-focused recruitment desk — Ian saw the same problem repeated with every early-stage client: they were getting a generalist recruitment process applied to a highly specialist hiring challenge.","Early-stage SaaS hiring is different. The profile that succeeds at a 30-person Series A looks nothing like the person who thrives at a 300-person Series C. The motivation, the risk appetite, the skills that matter — completely different. Most recruiters don't know the difference. We do, because we've spent over 20 years in it.","GTM People was built to solve that. Specialist knowledge, a warm active network, and a subscription model that aligns our incentives with yours — not just with the next placement fee."],"pillars":[{"name":"Stage Specialists","text":"We understand what great looks like at Seed vs Series A vs Series C — and hire the right person for the right stage, not just the best CV."},{"name":"Network First","text":"Our candidates are warm, vetted, and motivated. We know who's actually open to a move before we ever pick up the phone."},{"name":"Speed Without Compromise","text":"Day-one feasibility report. Five-day shortlist. Because your pipeline won’t wait."},{"name":"3-Month Guarantee","text":"Every placement carries a 3-month replacement guarantee. We back every hire we make — no small print, no excuses."}],"jobs":[{"id":"fa483ec1-a26b-4e65-b9fa-2c8ec32cf483","t":"Strategic Account Manager / Engagement Manager","l":"New York, NY (Hybrid)","w":"hybrid","rt":"Other","s":"Seed","b":[110000,150000],"o":[140000,190000],"c":"USD","e":"Competitive equity","d":"Own and grow a portfolio of Fortune 500 accounts at an AI-native consumer intelligence platform. You will be the glue between clients and the product and engineering teams - translating complex business needs into deployments that stick, and helping build the customer-experience function from scratch. A product-oriented CS/engagement role for someone who thinks like a PM but owns enterprise accounts. Hiring 1-2 people, tied to upcoming enterprise deals."},{"id":"80034cf0-2bdf-4dfa-ab8a-d41a14228805","t":"Full-Stack Software Engineer","l":"New York, NY (On-site)","w":"onsite","rt":"Other","s":"Seed","b":[120000,160000],"o":[null,null],"c":"USD","e":"Competitive equity","d":"Work across every layer of an AI-native platform for enterprise retail and consumer brands - from the backend services that process enterprise data at scale to the frontend interfaces that make that intelligence usable. In a small team, full-stack means full ownership: take features from idea to production and iterate directly with enterprise clients. Recently seed-funded by leading investors and already proven with Fortune 500 clients. On-site in New York."},{"id":"ca7c6529-b4c5-4b21-81d0-cab0d0445766","t":"Senior DevOps Engineer","l":"New York, NY (On-site)","w":"onsite","rt":"Other","s":"Seed","b":[160000,200000],"o":[null,null],"c":"USD","e":"Meaningful equity","d":"Own the infrastructure that keeps an AI-native platform running at enterprise scale - the cloud systems Fortune 500 retailers trust with their most critical data and decision-making. A hands-on, high-ownership role working closely with backend and ML engineers to keep the platform secure, scalable and relentlessly reliable, built on GitOps and infrastructure-as-code. Recently seed-funded by leading investors. On-site in New York (some remote Fridays)."},{"id":"c60241be-d9c2-4f25-8dee-32b339d81607","t":"Sales Executive","l":"London","w":"hybrid","rt":"Sales","s":null,"b":[60000,75000],"o":[35000,40000],"c":"GBP","e":null,"d":"A leading provider of business information services for legal, tax, accounting and compliance professionals, is hiring a Sales Executive to sell new technology solutions and drive cross-sell and up-sell opportunities across their suite of online, software and AI solutions. The role involves building pipelines, conducting consultative sales conversations, and managing the end-to-end sales process within assigned UK & Ireland territories."},{"id":"4def4848-c1e7-4d3f-9c9d-81921df652e1","t":"Account Executive","l":"New York, NY (On-site)","w":null,"rt":"Sales","s":"Seed","b":[110000,135000],"o":[250000,250000],"c":"USD","e":"Competitive equity","d":"Become the founder of a vertical at an AI-native consumer intelligence platform. This is a role for an industry insider with a genuine passion for a specific consumer category (food & beverage, CPG or retail): own the full commercial motion in your vertical, leverage the platform to become the authority in your space, and build a book of business that grows with you. Seed-funded and already live with Fortune 500 brands. On-site in New York."},{"id":"fbfe53a7-6862-4892-898c-c03cabc497ab","t":"Enterprise Account Executive (Founding Hire)","l":"New York, NY (Hybrid)","w":"hybrid","rt":"Sales","s":"Seed","b":[140000,180000],"o":[280000,300000],"c":"USD","e":"Meaningful early equity","d":"A genuine ground-floor GTM opportunity: become the first dedicated Enterprise AE at an AI-native consumer intelligence platform, selling to Fortune 500 companies with USD 10B+ in revenue. Seed-funded and already live with household-name brands across CPG, beauty, retail and travel. Own the full Fortune 500 sales cycle, write the playbook future AEs inherit, and step onto a clear path to Head of Sales."},{"id":"b29af814-d987-4b20-a117-5fc67e93eaa2","t":"Partner Implementation Manager","l":"London","w":"hybrid","rt":"CSM","s":"Series C","b":[70000,85000],"o":[null,null],"c":"GBP","e":"Competitive equity","d":"Uncountable is an R&D platform used by enterprise chemists and material scientists to accelerate product discovery and development. This Partner Implementation Manager role bridges Uncountable's implementation team and partner ecosystem, starting as a hands-on IC before transitioning to oversee 3-5 partner-led implementations across enterprise accounts."},{"id":"17d86181-e0e5-4642-9edb-e666bbee3591","t":"GTM Associate (SDR)","l":"London, UK","w":"office","rt":"SDR/BDR","s":"Bootstrapped","b":[30000,50000],"o":[50000,65000],"c":"GBP","e":null,"d":"Our client is a profitable, rapidly expanding real-time data and intelligence platform serving 300+ investment firms in private markets. The GTM Associate will run outbound campaigns end-to-end, research institutional buyers (VCs and PE investors), and work directly with founders to build and refine the outbound engine."},{"id":"63b3eff8-58c4-437e-a33c-ee512589f003","t":"Partner Implementation Manager","l":"New York","w":"hybrid","rt":"CSM","s":"Series C","b":[90000,120000],"o":[null,null],"c":"USD","e":"Competitive equity","d":"Uncountable is an R&D platform used by enterprise chemists and material scientists to accelerate product discovery and development. This Partner Implementation Manager role bridges Uncountable's implementation team and partner ecosystem, starting as a hands-on IC before transitioning to oversee 3-5 partner-led implementations across enterprise accounts."},{"id":"b09275b0-d877-40eb-969e-e752b2dd5dfc","t":"Partner Account Manager","l":"London, UK","w":"hybrid","rt":"Other","s":"Series C","b":[100000,170000],"o":[null,null],"c":"GBP","e":"Competitive equity","d":"Partner Account Manager for a rapidly expanding technology provider (Series C) in the networking space. Own the UK installation-partner network - relationships, KPI performance management, programme-building. Hybrid London, 30-40% field travel."},{"id":"d24b0f42-bc0e-4880-ade8-4dcbe86cd165","t":"Account Manager","l":"London","w":"hybrid","rt":"Sales","s":null,"b":[65000,75000],"o":[35000,40000],"c":"GBP","e":"pension, gym membership,","d":""},{"id":"19771894-16fe-4e93-95d8-80c7487a7aec","t":"Founding GTM","l":"London","w":"onsite","rt":"Sales","s":"Pre-Seed","b":[70000,140000],"o":[100000,170000],"c":"GBP","e":"Meaningful / competitive equity + relocation","d":"First commercial hire at a stealth-stage AI company transforming the $3T commercial insurance market. Own outbound prospecting and closing for the world's largest insurance brokers, working directly with the founders to build the GTM engine from scratch: cold outreach + personalised LinkedIn + targeted prospecting into the top 20 global brokers; full sales cycle from first touch to pilot close; conferences and in-person meetings; manage/improve GTM tooling (CRM, Clay, automated outreach); help kick off pilots with 12 of the top 20 brokers by year end.\r\n \r\n5 days in-office in London. Relocation available; visa sponsorship / transfers on the table (OPT, H1B, TN). Looking to hire 1-2. Reports to Jedrzej Brozyna (Founders Associate).\r\n \r\nInterview process: Initial behavioural screen with Jed (30m) -> Behavioural deep-dive with Gagan, CEO (45m) -> Half-day on-site case study & working trial (GTM case + consulting-style pricing case + build a working AI demo and role-play the deal)."},{"id":"5120ec95-70f7-4990-9b94-40728d13cc71","t":"Sales Manager","l":"London","w":"office","rt":"Sales","s":null,"b":[35000,45000],"o":[40000,50000],"c":"GBP","e":null,"d":"Expanding retail technology company seeks a driven Sales Manager to source and secure new sales opportunities for their specialised retail software solutions serving the Apparel, Footwear and General Merchandise sectors. The role involves managing the full sales pipeline from cold-calling to contract closure, with comprehensive team support and potential for future leadership responsibilities."},{"id":"1395f83a-9f2c-4efa-b8a6-9b6af9312a20","t":"SDR Manager","l":"London (Hybrid)","w":"hybrid","rt":"Sales","s":"Series A","b":[75000,85000],"o":[85000,95000],"c":"GBP","e":null,"d":"AI-native employee-benefits (HR Tech) B2B SaaS, ~20 people, fresh off a multi-million-pound Series A and named among the UK's leading startups. First SDR Manager hire to build and own the outbound engine from scratch and scale a growing SDR/BDR team. London, hybrid (3+ days)."},{"id":"d03d1ce2-affd-46d5-999d-120a6140b575","t":"Senior Account Manager – Financial Data & Intelligence – London","l":"London","w":"office","rt":"Sales","s":"Bootstrapped","b":[80000,100000],"o":[120000,150000],"c":"GBP","e":null,"d":"Our client is a profitable, rapidly expanding real-time data and intelligence platform serving 300+ investment firms in private markets. The founding senior account manager will run end-to-end account management function including building out the playbook and dealing with growth, renewals and all other aspects of account management in the institutional buyers (VCs and PE investors) market place,"},{"id":"0655d5f7-fb2f-4ee8-af57-b695290e7798","t":"Senior ML/AI Engineer","l":"New York, NY (On-site)","w":"onsite","rt":"Other","s":"Seed","b":[170000,230000],"o":[null,null],"c":"USD","e":"Competitive equity","d":"Build and deploy the intelligent systems at the core of an AI-native platform for enterprise retail and consumer brands - models and agentic architectures that power demand forecasting, consumer intelligence, competitive analysis and autonomous decision-making for some of the world's largest retailers. This is applied AI at real enterprise scale, generating meaningful value for Fortune 500 clients. Recently seed-funded by leading investors, with a small, engineering-heavy team. On-site in New York."},{"id":"ae155335-4d92-44ee-8efb-ce62188a078e","t":"Channel Co-Sell Director","l":"Remote, United States","w":"remote","rt":"Partnerships","s":"Series C","b":[200000,275000],"o":[null,null],"c":"USD","e":"Discussed at offer stage","d":"Own and accelerate Netomi's co-sell status and marketplace strategy across AWS, Azure and GCP - unlocking committed cloud spend and co-sell motions. Analyse cloud-spend architecture (hundreds of thousands/month on AWS) to optimise routing and marketplace credit; build the hyperscaler co-sell playbook; create enablement assets (playbooks, transaction guides, pitch decks, certification); work with the VP of Alliances and cross-functional GTM/Product/SE teams; support marketplace transactions and private offers; track partner activation, marketplace pipeline and sourced/influenced revenue.\r\n \r\nFully remote (US-based). Travel 30-40%; proximity to a major airport important. Not open to visa sponsorship (US citizen / Green Card only).\r\n \r\nInterview process: GTM Team Screen (30m) -> Head of Product (Brian McDonald, 45m) -> Chief of Staff (David Herrera, 45m) -> Take-home project -> President 1:1 (Justin Wexler, 30m) -> Panel presentation (1h)."},{"id":"04334d6d-4c15-4a73-ad1c-f83e83e1a83d","t":"GTM Engineer","l":"US / UK Remote (Austin, TX & London hubs)","w":"remote","rt":"Sales","s":"Seed","b":[120000,180000],"o":[null,null],"c":"USD","e":"0.2-0.6% equity","d":"First commercial hire (GTM Engineer) a leading VC backed AI voice-agent QA platform. Full-cycle high-agency IC, AI-native tooling essential. Remote US/UK."},{"id":"2ea90031-9791-468e-8cd3-5ae8e78ede12","t":"Senior Account Executive - UK & Ireland","l":"Remote (UK)","w":"remote","rt":"Sales","s":"Seed","b":[90000,120000],"o":[180000,240000],"c":"GBP","e":"Equity included at seed stage","d":"A rare first-AE opportunity to own the entire UK & Ireland patch for an AI-native automation platform for retail and FMCG enterprises, backed by a top-tier investor and approaching Series A. You will sell into enterprise operations teams, build territory from scratch, and shape the go-to-market motion alongside the founders. Fully remote in the UK, with uncapped commission and seed-stage equity."},{"id":"1ffdfdfc-5eee-45e0-b0e1-0ec6fd21e204","t":"Founding Client Partner","l":"London, UK","w":"hybrid","rt":"Sales","s":"Seed","b":[90000,110000],"o":[185000,220000],"c":"GBP","e":"Meaningful equity (early-stage)","d":"Founding UK Client Partner for a Seed-stage, backed by a leading US venture capital player in agentic-AI performance-marketing platform. Player-coach role owning the full UK sales cycle."},{"id":"2494380e-3361-48cf-a83f-1b3f9bb86c7c","t":"Forward Deployed Engineer - AI Agents (Retail & Consumer Goods)","l":"Remote (UK/EU)","w":"remote","rt":"Other","s":"Seed","b":[110000,200000],"o":[null,null],"c":"EUR","e":"Meaningful equity, with the option to trade cash for additional equity","d":"A rare Forward Deployed Engineer role with one of Europe's most exciting AI companies - embedding directly with enterprise retail and consumer-goods customers to ship agentic AI and automation into live operations. Our client is a fast-growing, venture-backed platform (world-class European investors) already trusted by some of Europe's largest retailers and brands. Fully remote across the UK/EU, with real ownership and equity upside at a genuinely early-stage business."},{"id":"b4c6d4f4-ff32-45aa-a882-d912b6779afe","t":"Customer Account Manager","l":"London, UK","w":"hybrid","rt":"Sales","s":null,"b":[60000,80000],"o":[120000,130000],"c":"GBP","e":null,"d":"Customer Account Manager  - cross-sell/upsell tax-tech SaaS to existing EMEA accounts. Hybrid London 1-2 times a month."},{"id":"cab650c5-04bc-4b59-9bda-dc47d3d39d79","t":"Commercial Account Executive","l":"Paris, France","w":"hybrid","rt":"Sales","s":null,"b":[60000,60000],"o":[100000,100000],"c":"EUR","e":null,"d":"New-business Commercial AE selling e-invoicing & indirect-tax SaaS across France. Hybrid Paris, 3 days/week."},{"id":"40c8cb32-d9de-4cfb-9624-93240f5916c2","t":"Account Executive","l":"San Francisco","w":"remote","rt":"Sales","s":"Series A","b":[125000,150000],"o":[250000,300000],"c":"USD","e":"0.10% - 0.20%","d":"Series B company (funded $20M) that uses AI to remake consumer underwriting for residential real estate, targeting institutional property managers and real estate investors. The Account Executive role is full-cycle sales of enterprise deals ($50K-$300K+ ARR), running prospecting through close over 2-5 month cycles."},{"id":"2278857a-ebc6-4786-af74-01330b06a468","t":"Product Marketing Manager (First PMM Hire)","l":"New York, NY (On-site)","w":"onsite","rt":"Marketing","s":"Seed","b":[125000,175000],"o":[null,null],"c":"USD","e":"Competitive early equity","d":"The first dedicated Product Marketing hire at an AI-native consumer intelligence platform - build the PMM function from scratch with real budget and executive support. Own mid-to-bottom-funnel conversion from positioning and messaging through to sales enablement and launch execution, with measurable impact on win rates, conversion and influenced pipeline. Seed-funded, revenue-generating, and live with Fortune 500 brands."}]};
  KB.tiers = [
    { id: 'Launchpad', sub: 'Per Hire', mo: 500, yr: '£5,000 / year', rate: 0.20, included: 'No included placements · 20% per hire', guarantee: '3-month replacement guarantee', gMonths: 3, cta: 'Get started',
      bullets: ['Dedicated search & active headhunt', '3–5 curated candidates per role', 'Quarterly talent report + competitor watchlist', 'No included placements · 20% per hire', '3-month replacement guarantee'] },
    { id: 'Scaleup', sub: 'Monthly Retainer', mo: 1000, yr: '£10,000 / year', rate: 0.175, included: '1 included placement / year (up to £75k base)', guarantee: 'Then 17.5% · 6-month guarantee', gMonths: 6, cta: 'Talk to Us →', popular: true,
      bullets: ['Dedicated talent partner embedded with your team', 'Competitor watchlist + compensation benchmarking', 'Priority sourcing & market mapping', '1 included placement / year (up to £75k base)', 'Then 17.5% · 6-month guarantee'] },
    { id: 'Unicorn', sub: 'Strategic Partner', mo: 2500, yr: '£30,000 / year', rate: 0.15, included: '2 included placements / year (up to £100k base) — or 3 up to £75k', guarantee: 'Then 15% · 12-month rolling guarantee', gMonths: 12, cta: "Let's Talk",
      bullets: ['Full GTM talent partnership + executive search', 'Salary benchmarking & market data', '2 included placements / year (up to £100k base) — or 3 up to £75k', 'Then 15% · 12-month rolling guarantee', 'On-market talent alerts across up to 10 target companies (competitors, similar sales motions)'] },
    { id: 'Partner', sub: 'Embedded', mo: 8500, yr: 'Monthly · min 3 months', rate: null, included: 'Unlimited hiring within capacity', guarantee: 'Same flat price whatever tier you\'re on', gMonths: 3, cta: 'Enquire', flat: true,
      bullets: ['A GTM recruiter embedded in your team, full-time', 'Unlimited hiring within capacity', 'Same flat price whatever tier you\'re on', 'Fractional option: £4,500/mo, 2 days a week'] }
  ];
  KB.feeNotes = {
    intro: 'Choose a model that fits your hiring volume and budget — from a single founding hire to an ongoing talent partnership.',
    intel: 'Intelligence adds competitor watchlists, comp benchmarking & market reports — a flat +50% at every tier.',
    how: 'How our fees work: we charge on base salary + guaranteed earnings only — never OTE or commission (most agencies charge on OTE, inflating a sales-hire fee by 40–100%). Every placement beyond your included ones carries a £2,500 engagement retainer, credited in full against the fee — never a cost on top.',
    beyond: 'Every hire beyond your included placements is 15% — not our standard rate.',
    example: 'On a £100,000 role that\'s £15,000 rather than £30,000 — a 50% saving, for as long as you subscribe.'
  };
  KB.whyTaas = {
    intro: 'A traditional agency gets paid once — when you make the hire. That means their interest ends the moment the contract is signed. TaaS flips the model.',
    bad: ['Per-hire fee creates pressure to fill fast, not well', 'No incentive to care what happens after placement', 'Candidates often oversold to get the fee', 'Every search starts from scratch', "You're a transaction, not a relationship"],
    good: ['Monthly retainer means we care about long-term quality', 'Your talent partner stays embedded in your team', 'Candidates are briefed fully — no surprises after joining', 'Pipeline always warm — next hire is faster than the last', '3-month guarantee on every placement']
  };
  KB.stats = [['20+', 'Years specialist GTM recruitment'], ['5', 'Days to first shortlist'], ['7/10', 'Counter-offer hires leave in 9 months'], ['Seed–C', 'Our focus. 100% SaaS GTM.'], ['3mo', 'Replacement guarantee on every placement'], ['UK·US·EU', 'London-based, placing globally']];
  KB.faqTags = [['general'], ['seed', 'preseed', 'bootstrapped', 'founding', 'AE', 'SDR'], ['SDR'], ['fee', 'volume'], ['AE', 'speed'], ['AE', 'seriesa', 'us'], ['us', 'eu', 'abroad'], ['guarantee', 'seriesb', 'seriesc']];
  KB.pillarTags = [['seed', 'preseed', 'seriesa', 'seriesb', 'seriesc', 'bootstrapped', 'pe'], ['seed', 'preseed', 'seriesa', 'bootstrapped'], ['seed', 'preseed', 'seriesa', 'bootstrapped'], ['seriesb', 'seriesc', 'pe', 'seriesa']];
  KB.jsb = { title: 'JobSearchBud — your job search, supercharged', text: 'Our own AI-powered CV and job-search tool. It sharpens your CV, tailors it to each role and helps you stand out and land faster — free for GTM People candidates.', cta: 'Visit JobSearchBud →', badge: '★ FOUNDING PARTNER · FOR CANDIDATES' };
  KB.candidateAudience = /^(Surfer|Lusha)$/;

  /* ---------------- Intent engine ---------------- */
  var STAGES = [['preseed', /pre[\s-]?seed/i, 'Pre-Seed'], ['seriesa', /series\s*a\b/i, 'Series A'], ['seriesb', /series\s*b\b/i, 'Series B'], ['seriesc', /series\s*c\b/i, 'Series C'], ['seriesd', /series\s*d\b/i, 'Series D+'], ['seed', /\bseed\b/i, 'Seed'], ['bootstrapped', /bootstrap/i, 'Bootstrapped'], ['pe', /\bpe[\s-]?backed\b|private equity|\bpe\b/i, 'PE Backed']];
  var FAMILIES = [
    ['SDR', /\b(sdr|bdr|sales development|business development rep|outbound rep|outbound)\b/i, 'SDR / BDR'],
    ['RevOps', /rev\s?ops|revenue operations|sales ops|marketing ops/i, 'RevOps'],
    ['GTM Eng', /gtm engineer|gtm eng|\bclay\b/i, 'GTM Engineering'],
    ['Pre-Sales', /sales engineer|solutions? (consultant|engineer)|pre-?sales|forward deployed/i, 'Pre-Sales & Solutions'],
    ['Leadership', /head of sales|vp sales|vp of sales|\bvp\b|\bcro\b|chief revenue|sales leader|sales director|head of revenue/i, 'GTM Leadership'],
    ['Marketing', /\b(marketing|pmm|demand gen|growth marketer)\b/i, 'Marketing'],
    ['CS', /\b(cs|csm|customer success|account manager|\bam\b)\b/i, 'Customer Success'],
    ['AE', /\b(ae|aes|account exec\w*|closer|sales exec\w*|client partner|sales rep|salesperson|sales hire|gtm hire)\b/i, 'Account Executives']
  ];
  var LOCS = [['london', /london/i, 'London'], ['manchester', /manchester/i, 'Manchester'], ['newyork', /new york|\bnyc?\b/i, 'New York'], ['sf', /san francisco|\bsf\b|bay area/i, 'San Francisco'], ['paris', /paris|france/i, 'Paris'], ['remote', /remote/i, 'Remote'], ['hybrid', /hybrid/i, 'Hybrid'], ['uk', /\buk\b|united kingdom|britain/i, 'UK'], ['us', /\bus\b|\busa\b|united states|america/i, 'US'], ['eu', /\beu\b|europe|emea|germany|netherlands/i, 'EU']];
  var SENIORITY = [['founding', /founding|first (sales|commercial|gtm|ae|sdr|hire)/i], ['clevel', /\bcro\b|chief|c-level/i], ['vp', /\bvp\b/i], ['head', /head of/i], ['senior', /senior|enterprise/i]];

  function parseBrief(text) {
    var t = ' ' + (text || '') + ' ';
    var p = { mode: /looking|candidate|my next role|i am an? |i'm an? |job for me/i.test(t) ? 'looking' : null, stage: null, stageLabel: null, family: null, familyLabel: null, location: null, locationLabel: null, seniority: null, volume: 1, founding: false };
    for (var i = 0; i < STAGES.length; i++) if (STAGES[i][1].test(t)) { p.stage = STAGES[i][0]; p.stageLabel = STAGES[i][2]; break; }
    for (i = 0; i < FAMILIES.length; i++) if (FAMILIES[i][1].test(t)) { p.family = FAMILIES[i][0]; p.familyLabel = FAMILIES[i][2]; break; }
    for (i = 0; i < LOCS.length; i++) if (LOCS[i][1].test(t)) { p.location = LOCS[i][0]; p.locationLabel = LOCS[i][2]; break; }
    for (i = 0; i < SENIORITY.length; i++) if (SENIORITY[i][1].test(t)) { p.seniority = SENIORITY[i][0]; break; }
    p.founding = /founding|first/i.test(t);
    if (!p.family && p.founding) { p.family = 'AE'; p.familyLabel = 'Founding Sales'; }
    if (p.seniority === 'vp' || p.seniority === 'clevel' || p.seniority === 'head') { if (!p.family || p.family === 'AE') { p.family = 'Leadership'; p.familyLabel = 'GTM Leadership'; } }
    var m = t.match(/(\d+)\s*(hires|roles|people|heads)/i);
    if (m) p.volume = +m[1]; else if (/team of|several|multiple|a team|build (a|the) team|whole team/i.test(t)) p.volume = 3;
    return p;
  }

  /* ---------------- Role matching ---------------- */
  var FAM_TITLE = { AE: /account executive|sales executive|client partner|founding gtm|\bae\b/i, SDR: /\bsdr\b|\bbdr\b|sales development|gtm associate/i, CS: /customer success|\bcsm\b|account manager|implementation|customer account/i, RevOps: /rev\s?ops|revenue operations|sales ops/i, Leadership: /head of|\bvp\b|\bcro\b|director|sales manager|sdr manager/i, Marketing: /marketing/i, 'GTM Eng': /gtm engineer/i, 'Pre-Sales': /sales engineer|solutions|forward deployed|pre-sales/i };
  var LOC_TEST = { london: /london/i, manchester: /manchester/i, newyork: /new york|\bny\b/i, sf: /san francisco/i, paris: /paris/i, remote: /remote/i, hybrid: /hybrid/i, uk: /london|\buk\b|manchester/i, us: /new york|\bny\b|san francisco|united states|\bus\b|austin/i, eu: /paris|france|\beu\b|europe/i };
  var STAGE_LABEL = { preseed: 'Pre-Seed', seed: 'Seed', seriesa: 'Series A', seriesb: 'Series B', seriesc: 'Series C', seriesd: 'Series D+', bootstrapped: 'Bootstrapped', pe: 'PE Backed' };
  function jobFamilyOk(j, fam) { return !!fam && (FAM_TITLE[fam] ? FAM_TITLE[fam].test(j.t) : false) || (fam === 'SDR' && j.rt === 'SDR/BDR') || (fam === 'CS' && j.rt === 'CSM') || (fam === 'Marketing' && j.rt === 'Marketing'); }
  function jobLocOk(j, loc) { if (!loc) return false; var hay = j.l + ' ' + (j.w || ''); return LOC_TEST[loc].test(hay); }
  function matchJobs(p) {
    var scored = KB.jobs.map(function (j) {
      var s = 0, fam = p.family ? jobFamilyOk(j, p.family) : true, loc = p.location ? jobLocOk(j, p.location) : true, stg = p.stage ? j.s === STAGE_LABEL[p.stage] : true;
      if (p.family && fam) s += 3; if (p.location && loc) s += 2; if (p.stage && stg) s += 1;
      if (j.rt === 'Sales' && !p.family) s += 0.5;
      return { j: j, s: s, exact: fam && loc };
    });
    var exact = scored.filter(function (x) { return x.exact && (p.family || p.location); });
    exact.sort(function (a, b) { return b.s - a.s; });
    if (!p.family && !p.location) { scored.sort(function (a, b) { return (b.j.rt === 'Sales') - (a.j.rt === 'Sales') || b.s - a.s; }); return { jobs: scored.map(function (x) { return x.j; }), exact: true, all: true }; }
    if (exact.length) return { jobs: exact.map(function (x) { return x.j; }), exact: true };
    scored.sort(function (a, b) { return b.s - a.s; });
    return { jobs: scored.slice(0, 3).map(function (x) { return x.j; }), exact: false };
  }
  var SYM = { GBP: '£', USD: '$', EUR: '€' };
  function k(n, c) { return n == null ? '' : SYM[c] + (n >= 1000 ? Math.round(n / 1000) + 'k' : n); }
  function range(a, c) { if (a[0] == null && a[1] == null) return ''; if (a[0] === a[1] || a[1] == null) return k(a[0], c); if (a[0] == null) return k(a[1], c); return k(a[0], c) + '–' + k(a[1], c); }
  function comp(j) { var b = range(j.b, j.c), o = range(j.o, j.c); return (b ? 'base ' + b : 'comp on request') + (o ? ' · OTE ' + o : ''); }
  function equityDot(j) { var has = j.e && !/^none$/i.test(j.e) && !/pension/i.test(j.e); return '<span class="eq' + (has ? ' eq-on' : '') + '" title="' + h(has ? j.e : 'No equity listed') + '" aria-label="' + (has ? 'Equity: ' + h(j.e) : 'No equity listed') + '"></span>'; }

  /* ---------------- Answer builder ---------------- */
  function salaryRowFor(p) {
    var map = { AE: 1, SDR: 0, CS: 2, RevOps: 3, Leadership: (p.seniority === 'vp' || p.seniority === 'clevel') ? 5 : 4 };
    var i = p.family ? map[p.family] : 1;
    if (i == null) return { row: KB.salary[1], proxy: true };
    return { row: KB.salary[i], proxy: false };
  }
  function tierFor(p) {
    if (p.volume >= 3) return KB.tiers[3];
    if (!p.stage) return KB.tiers[1];
    if (/preseed|seed|bootstrapped/.test(p.stage)) return KB.tiers[0];
    if (p.stage === 'seriesa') return KB.tiers[1];
    return KB.tiers[2];
  }
  function midBase(row) { var m = row.base.match(/£(\d+)k\s*–\s*£(\d+)k/); return m ? Math.round((+m[1] + +m[2]) / 2) * 1000 : 75000; }
  function pickFaqs(p) {
    var want = ['general'];
    if (p.stage) want.push(p.stage); if (p.family) want.push(p.family); if (p.location === 'us' || p.location === 'newyork' || p.location === 'sf') want.push('us'); if (p.location === 'eu' || p.location === 'paris') want.push('eu'); if (p.founding) want.push('founding'); if (p.volume >= 3) want.push('volume');
    var scored = KB.faqs.map(function (f, i) { var s = 0; KB.faqTags[i].forEach(function (t) { if (want.indexOf(t) > -1) s += (t === 'general' ? 0.5 : 1); }); return { f: f, i: i, s: s }; });
    scored.sort(function (a, b) { return b.s - a.s || a.i - b.i; });
    return scored.slice(0, 2);
  }
  function pickPillars(p) {
    var st = p.stage || 'seriesa';
    var out = KB.pillars.map(function (pl, i) { return { pl: pl, i: i, on: KB.pillarTags[i].indexOf(st) > -1 }; }).filter(function (x) { return x.on; }).slice(0, 2);
    return out.length ? out : KB.pillars.slice(0, 2).map(function (pl, i) { return { pl: pl, i: i }; });
  }
  var DAY = 86400000;
  function fmtDate(d) { return d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' }); }
  function plan(tier, now) {
    var d = function (n) { return fmtDate(new Date(now.getTime() + n * DAY)); };
    return [
      ['Day 0 · ' + d(0), 'Deep brief (60 min)'], ['Day 1 · ' + d(1), 'Day-one feasibility report'], ['Days 1–3', 'Market map'], ['Day 5 · ' + d(5), 'Shortlist of 3–5'],
      ['Then', 'Interview support · Offer & close — we manage the counter-offer risk'], ['30 / 60 / 90', 'Check-ins with client and candidate'], ['Guarantee', tier.gMonths + '-month' + (tier.id === 'Unicorn' ? ' rolling' : '') + ' guarantee (' + tier.id + ')']
    ];
  }

  /* ---------------- Rendering ---------------- */
  var board = $('[data-board]'), tilesEl = $('[data-tiles]'), stripsEl = $('[data-strips]'), input = $('[data-brief]'), summaryEl = $('[data-summary]');
  var state = { mode: 'hiring', brief: '', parsed: parseBrief(''), open: null, intel: false, tierOverride: null, base: 100000, agency: false, filt: { loc: '', type: '', stage: '' } };
  var LOCGROUP = function (j) { var l = j.l; return /remote/i.test(l) ? 'Remote' : /london/i.test(l) ? 'London' : /new york/i.test(l) ? 'New York' : /san francisco/i.test(l) ? 'San Francisco' : /paris/i.test(l) ? 'Paris' : l; };

  function roleRow(j) { return '<li class="role"><strong>' + h(j.t) + '</strong><span class="role-meta">' + h(LOCGROUP(j)) + (j.s ? ' · ' + h(j.s) : '') + '</span><span class="role-comp">' + h(range(j.b, j.c) || 'comp on request') + ' base</span></li>'; }
  function roleFull(j) { return '<li class="role role-full" data-row tabindex="0" role="button" aria-expanded="false"><div><strong>' + h(j.t) + '</strong><span class="role-meta">' + h(j.l) + (j.s ? ' · ' + h(j.s) : '') + ' · ' + h(j.rt) + (j.w ? ' · ' + h(j.w) : '') + '</span></div><div class="role-comp">' + h(comp(j)) + ' ' + equityDot(j) + (j.e && !/^none$/i.test(j.e) ? ' <em>' + h(j.e) + '</em>' : '') + '</div>' + (j.d ? '<p class="role-d">' + h(j.d) + '</p>' : '') + '</li>'; }
  function chipRow(name, key, opts) { return '<div class="chips chips-f" role="group" aria-label="' + name + '">' + opts.map(function (o) { var on = state.filt[key] === o[0]; return '<button type="button" class="chip' + (on ? ' is-on' : '') + '" data-f="' + key + '" data-v="' + h(o[0]) + '" aria-pressed="' + on + '">' + h(o[1]) + '</button>'; }).join('') + '</div>'; }
  function rolesDrawer(matchList) {
    var f = state.filt, pool = KB.jobs.filter(function (j) { return (!f.loc || LOCGROUP(j) === f.loc) && (!f.type || j.rt === f.type) && (!f.stage || j.s === f.stage); });
    var groups = {}; pool.forEach(function (j) { var g = LOCGROUP(j); (groups[g] = groups[g] || []).push(j); });
    var locs = [['', 'All locations']].concat(['London', 'New York', 'Remote', 'San Francisco', 'Paris'].map(function (l) { return [l, l]; }));
    var types = [['', 'All role types']].concat(['Sales', 'SDR/BDR', 'CSM', 'Marketing', 'Partnerships', 'Other'].map(function (t) { return [t, t]; }));
    var stages = [['', 'All stages']].concat(['Bootstrapped', 'Pre-Seed', 'Seed', 'Series A', 'Series C'].map(function (t) { return [t, t]; }));
    return '<p class="lead">All roles are confidential — company names are disclosed at shortlist stage. Apply once and we\'ll match you to relevant opportunities as they come in.</p>' + chipRow('Location', 'loc', locs) + chipRow('Role type', 'type', types) + chipRow('Stage', 'stage', stages) + '<p class="note"><b>' + pool.length + ' of ' + KB.jobs.length + '</b> live roles' + (f.loc || f.type || f.stage ? ' · <button type="button" class="link" data-all-roles>All 25</button>' : '') + ' · <a href="https://gtm-people.com/jobs" target="_blank" rel="noopener">Not seeing the right role? Register your interest →</a></p>' + Object.keys(groups).map(function (g) { return '<h4>' + h(g) + ' <small>' + groups[g].length + '</small></h4><ul class="roles roles-exp">' + groups[g].map(roleFull).join('') + '</ul>'; }).join('');
  }
  function tileRoles(p, looking) {
    var m = matchJobs(p), list = m.jobs, N = KB.jobs.length, n = m.all ? N : list.length;
    var crit = [p.locationLabel, p.familyLabel ? p.familyLabel.replace('Account Executives', 'AE').replace('Customer Success', 'CS').replace('GTM Leadership', 'leadership') : ''].filter(Boolean).join(' ');
    var line = m.all ? 'live roles across UK · US · EU' : (m.exact ? crit + ' roles live' + (p.stageLabel ? ' · ' + p.stageLabel + ' and nearby' : '') : 'closest roles — no exact ' + crit + ' match yet');
    return { id: 'roles', eyebrow: 'Roles in play', num: String(n), line: line, badge: m.all || m.exact ? n + ' of ' + N : 'closest 3',
      body: '<ul class="roles">' + list.slice(0, 3).map(roleRow).join('') + '</ul>' + (looking ? '<a class="btn btn-sm tile-cta" href="https://gtm-people.com/jobs" target="_blank" rel="noopener">Register interest →</a>' : ''),
      more: rolesDrawer(list), src: 'Source: live Jobs board (25 public roles, snapshot 2026-10-06) filtered by role family, location and stage parsed from your brief · company names disclosed at shortlist stage.' };
  }
  function bars() { return '<ul class="bars">' + KB.salary.map(function (r) { var m = r.base.match(/£(\d+)k\s*–\s*£(\d+)k/); var lo = m ? +m[1] : 0, hi = m ? +m[2] : 0; return '<li><div class="bar-head"><strong>' + h(r.role) + '</strong><span>' + h(r.base) + ' · ' + h(r.ote) + '</span></div><div class="bar"><span style="left:' + (lo / 180 * 100) + '%;width:' + ((hi - lo) / 180 * 100) + '%"></span></div><small>' + h(r.note) + '</small></li>'; }).join('') + '</ul>'; }
  function tileRate(p) {
    var sr = salaryRowFor(p), r = sr.row, us = (p.location === 'us' || p.location === 'newyork' || p.location === 'sf');
    var usFull = KB.faqs[5].a.split('US:')[1].trim();
    return { id: 'rate', eyebrow: 'Market rate · ' + r.role, num: r.base.replace(/\s/g, ''), line: 'base · ' + r.ote + ' · ' + r.note.split(' · ')[1], badge: '2026 Salary Guide',
      body: '<p class="note fact"><b>' + h(r.note.split(' · ')[0]) + '</b><br>' + (sr.proxy ? 'closest guide row to ' + h(p.familyLabel) : 'stage range for this row · ' + h(r.note.split(' · ')[1] || '')) + '</p>' + (us ? '<p class="note">US mid-market AE: ~$120–150k base, $240–300k OTE</p>' : ''),
      more: '<p class="lead">' + h(KB.salaryIntro) + '</p>' + (us ? '<p><b>US:</b> ' + h(usFull) + '</p>' : '') + bars() + '<p>' + h(KB.salaryCta[0]) + ' <a href="#contact" data-open="contact">' + h(KB.salaryCta[1]) + '</a></p>',
      src: 'Source: 2026 Salary Guide row "' + r.role + '"' + (us ? ' + FAQ "What should I pay a Series A SaaS Account Executive?" (US sentence)' : '') + '.' };
  }
  function money(n) { return '£' + Math.round(n).toLocaleString('en-GB'); }
  function tierNow(p) { var rec = tierFor(p); return { rec: rec, tier: state.tierOverride ? KB.tiers.filter(function (t) { return t.id === state.tierOverride; })[0] : rec }; }
  function calcLine(tier, base) { var agency = base * 0.30, k = money(base).replace(',000', 'k'); return tier.flat ? '<b>' + money(tier.mo) + '/mo flat</b>, unlimited hires vs <b>' + money(agency) + '</b> per hire at a 30%-of-OTE agency (' + k + ' base)' : '<b>' + money(base * tier.rate) + '</b> with us vs <b>' + money(agency) + '</b> at a 30%-of-OTE agency (' + k + ' base)'; }
  function tileFee(p) {
    var tn = tierNow(p), tier = tn.tier, rec = tn.rec, mult = state.intel ? 1.5 : 1;
    var inc = tier.id === 'Launchpad' ? 'no included placements · then 20%' : tier.id === 'Scaleup' ? '1 placement included · then 17.5%' : tier.id === 'Unicorn' ? '2 placements included · then 15%' : 'unlimited hiring within capacity';
    return { id: 'fee', eyebrow: 'Your fee', num: money(tier.mo * mult) + '/mo', line: tier.id + ' · ' + inc, badge: 'Recommended: ' + rec.id,
      body: '<p class="note calc-line" data-calc>' + calcLine(tier, state.base) + '</p><p class="note fact"><b>' + h(tier.flat ? 'Monthly · min 3 months' : tier.guarantee.replace(/^Then [\d.]+% · /, '')) + '</b><br>' + (tier.flat ? 'A GTM recruiter embedded in your team, full-time' : 'replacement guarantee on every placement at this tier') + '</p>',
      more: '<div class="fee-ctl"><div class="tier-pick" role="group" aria-label="Tier">' + KB.tiers.map(function (t) { return '<button type="button" class="chip' + (t.id === tier.id ? ' is-on' : '') + '" data-tier="' + t.id + '" aria-pressed="' + (t.id === tier.id) + '">' + t.id + (t.id === rec.id ? ' ★' : '') + '</button>'; }).join('') + '</div><label class="calc"><span>Base salary <output data-base-out>' + money(state.base) + '</output></span><input type="range" min="30000" max="200000" step="5000" value="' + state.base + '" data-base aria-label="Base salary"></label><label class="switch"><input type="checkbox" data-intel' + (state.intel ? ' checked' : '') + '> <span>Recruitment + Intelligence (+50%)</span></label></div><p class="note">' + h(KB.feeNotes.intro) + ' ' + h(KB.feeNotes.intel) + '</p><div class="tiers">' + KB.tiers.map(function (t) { return '<div class="tier' + (t.id === rec.id ? ' is-rec' : '') + '">' + (t.popular ? '<span class="tag">Most Popular</span>' : '') + '<h4>' + h(t.id) + ' <small>' + h(t.sub) + '</small></h4><p class="price"><b>' + money(t.mo * mult) + '</b>/mo <small>' + h(t.yr) + '</small></p><ul>' + t.bullets.slice(0, 3).map(function (b) { return '<li>' + h(b) + '</li>'; }).join('') + '</ul><p class="tier-inc">' + h(t.included) + (t.flat ? '' : ' · ' + h(t.guarantee)) + '</p><a class="btn btn-sm" href="#contact" data-open="contact">' + h(t.cta) + '</a></div>'; }).join('') + '</div><p class="fine">' + h(KB.feeNotes.how) + '</p><p class="fine"><b>' + h(KB.feeNotes.beyond) + '</b> ' + h(KB.feeNotes.example) + '</p>',
      src: 'Source: Talent as a Service tiers (' + rec.id + ' = ' + (p.volume >= 3 ? '3+ hires → Partner' : (p.stageLabel || 'stage not given → Scaleup, Most Popular')) + ') + "How our fees work" fine print; agency comparison uses the live £15,000-vs-£30,000 example rate.' };
  }
  var DAY = 86400000;
  function fmtDate(d) { return d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' }); }
  function plan(tier, now) { var d = function (n) { return fmtDate(new Date(now.getTime() + n * DAY)); }; return [['Day 0 · ' + d(0), 'Deep brief (60 min)'], ['Day 1 · ' + d(1), 'Day-one feasibility report'], ['Days 1–3', 'Market map'], ['Day 5 · ' + d(5), 'Shortlist of 3–5'], ['Then', 'Interview support · Offer & close — we manage the counter-offer risk'], ['30 / 60 / 90', 'Check-ins with client and candidate'], ['Guarantee', tier.gMonths + '-month' + (tier.id === 'Unicorn' ? ' rolling' : '') + ' guarantee (' + tier.id + ')']]; }
  function stripPlan(p) {
    var tier = tierFor(p), rows = plan(tier, new Date());
    return { id: 'plan', eyebrow: 'How we\'d run your search', line: 'Brief ' + fmtDate(new Date()) + ' → shortlist of 3–5 by ' + fmtDate(new Date(Date.now() + 5 * DAY)), badge: tier.gMonths + '-month guarantee',
      more: '<div class="cols"><div><ol class="plan">' + rows.map(function (r) { return '<li><span>' + h(r[0]) + '</span><b>' + h(r[1]) + '</b></li>'; }).join('') + '</ol><h4>' + h(KB.checkins.title) + '</h4><p>' + h(KB.checkins.text) + '</p><h4>' + h(KB.taasReview.title) + '</h4><p>' + h(KB.taasReview.text) + '</p></div><div><p class="lead">At Seed to Series C, every week without the right person costs revenue. Our process is built for speed without cutting corners on quality.</p><ol class="steps">' + KB.clientSteps.map(function (s) { return '<li><b>' + h(s.n) + ' ' + h(s.name) + '</b><p>' + h(s.text) + '</p></li>'; }).join('') + '</ol></div></div>',
      src: 'Source: How It Works (six client steps), 30/60/90 check-ins, tier guarantee length; dates computed from today.' };
  }
  function stripWhy(p) {
    var ps = pickPillars(p), first = ps[0].pl;
    return { id: 'why', eyebrow: 'Why this works at ' + (p.stageLabel || 'your stage'), line: first.text.split(/ — |\. /)[0].replace(/[.,]$/, '') + '.', badge: ps.map(function (x) { return x.pl.name; }).join(' · '),
      more: '<div class="cols"><div><h4>Built by someone who\'s been in the seat.</h4>' + KB.about.map(function (a) { return '<p>' + h(a) + '</p>'; }).join('') + '<ul class="pillars">' + KB.pillars.map(function (x) { return '<li><b>' + h(x.name) + '</b> ' + h(x.text) + '</li>'; }).join('') + '</ul></div><div><ul class="stats">' + KB.stats.map(function (s) { return '<li><b>' + h(s[0]) + '</b><span>' + h(s[1]) + '</span></li>'; }).join('') + '</ul><h4>Why TaaS? Traditional recruitment has the wrong incentives.</h4><p>' + h(KB.whyTaas.intro) + '</p><div class="vs"><ul class="bad"><li class="vs-h">Traditional Agency</li>' + KB.whyTaas.bad.map(function (b) { return '<li>' + h(b) + '</li>'; }).join('') + '</ul><ul class="good"><li class="vs-h">GTM People TaaS</li>' + KB.whyTaas.good.map(function (b) { return '<li>' + h(b) + '</li>'; }).join('') + '</ul></div></div></div>',
      src: 'Source: About GTM People (pillars tagged by stage) + Why TaaS table.' };
  }
  function stripFaq(p) {
    var two = pickFaqs(p);
    return { id: 'faq', eyebrow: 'Questions founders at ' + (p.stageLabel || 'your stage') + ' ask', line: two[0].f.q, badge: '2 of 8',
      more: '<p class="lead">Answers to the questions we get asked most often by founders and hiring managers at early-stage SaaS companies.</p><div class="cols">' + [KB.faqs.slice(0, 4), KB.faqs.slice(4)].map(function (half) { return '<div>' + half.map(function (f) { var i = KB.faqs.indexOf(f); return '<details class="qa"' + (i === two[0].i || i === two[1].i ? ' open' : '') + '><summary>' + h(f.q) + '</summary><p>' + h(f.a) + '</p></details>'; }).join('') + '</div>'; }).join('') + '</div>',
      src: 'Source: Common Questions (8 FAQs), ranked by stage, role family and location tags.' };
  }
  function contactForm(p, looking) {
    var stages = ['Pre-Seed', 'Seed', 'Series A', 'Series B', 'Series C', 'Series D+', 'Bootstrapped', 'PE Backed'];
    return '<form class="form" data-form novalidate><div class="row2"><label>First Name *<input name="first" required autocomplete="given-name"></label><label>Last Name *<input name="last" required autocomplete="family-name"></label></div><div class="row2"><label>' + (looking ? 'Current company' : 'Company *') + '<input name="company" autocomplete="organization"></label><label>Email *<input type="email" name="email" required inputmode="email" autocomplete="email"></label></div>' + (looking ? '' : '<label>Funding Stage<select name="stage"><option value="">Select…</option>' + stages.map(function (s) { return '<option' + (s === p.stageLabel ? ' selected' : '') + '>' + s + '</option>'; }).join('') + '</select></label>') + '<label>' + (looking ? 'What are you looking for?' : 'What are you hiring?') + '<textarea name="brief" rows="2">' + h(state.brief) + '</textarea></label><button class="btn" type="submit">' + (looking ? 'Register interest →' : 'Send Message →') + '</button><p class="form-note" data-form-note aria-live="polite">We respond within one working day. No hard sell — just a conversation.</p></form>';
  }
  function contactLinks() { return '<ul class="contacts"><li><a href="tel:+447803236717">+44 7803 236717</a></li><li><a href="mailto:hello@gtm-people.com">hello@gtm-people.com</a></li><li><a href="https://linkedin.com/company/gtm-people-com" target="_blank" rel="noopener">linkedin.com/company/gtm-people-com</a></li><li>Based In: London, UK — placing globally</li></ul>'; }
  function stripContact(p, looking) {
    return { id: 'contact', eyebrow: looking ? 'Register' : 'Next step', line: looking ? 'Register once — we match you as roles come in. No spam.' : 'Tell us what you\'re building — we reply within one working day.', badge: looking ? 'No black hole' : 'One working day',
      more: '<div class="cols"><div><p class="lead">' + (looking ? 'Register' : 'Tell us about your hiring need') + '</p>' + contactForm(p, looking) + '</div><div><p class="lead">' + (looking ? 'Looking for a role?' : 'Ready to build your GTM team?') + '</p>' + contactLinks() + '</div></div>',
      src: 'Source: Get In Touch (form fields verbatim; stage and brief pre-filled from your brief).' };
  }
  function tileHowYou() { return { id: 'howyou', eyebrow: 'How it works for you', num: '48h', line: 'A consultant calls within 48 hours · ' + KB.candidateSteps.map(function (s) { return s.name; }).join(' → '), badge: '4 steps', body: '', more: '<ol class="steps cols">' + KB.candidateSteps.map(function (s) { return '<li><b>' + h(s.n) + ' ' + h(s.name) + '</b><p>' + h(s.text) + '</p></li>'; }).join('') + '</ol>', src: 'Source: How It Works — For Candidates (four steps, verbatim).' }; }
  function stripJsb() { return { id: 'jsb', eyebrow: 'JobSearchBud', line: 'Our own AI-powered CV and job-search tool — free for GTM People candidates.', badge: 'Founding partner', more: '<p class="eyebrow">' + h(KB.jsb.badge) + '</p><p class="lead">' + h(KB.jsb.title) + '</p><p>' + h(KB.jsb.text) + '</p><a class="btn btn-sm" href="https://gtm-people.com/partners" target="_blank" rel="noopener">' + h(KB.jsb.cta) + '</a>', src: 'Source: Partners & Perks — founding partner panel, verbatim.' }; }
  function stripPartnersCand() {
    var list = KB.partners.filter(function (p) { return KB.candidateAudience.test(p.name); });
    return { id: 'pcand', eyebrow: 'Partners for candidates', line: list.map(function (p) { return p.name + ' (' + p.tag + ')'; }).join(' · '), badge: list.length + ' perks', more: '<p class="lead">We partner with best-in-class providers so our clients and candidates get preferential access, discounts and support — well beyond the placement itself.</p><ul class="plist cols">' + list.map(function (p) { return '<li><b>' + h(p.name) + '</b> <span>' + h(p.tag) + '</span><p>' + h(p.text) + '</p></li>'; }).join('') + '</ul>', src: 'Source: Partners & Perks, filtered to "For candidates".' };
  }

  function answer(p) {
    var looking = state.mode === 'looking';
    var tiles = looking ? [tileRoles(p, true), tileRate(p), tileHowYou()] : [tileRoles(p, false), tileRate(p), tileFee(p)];
    var strips = looking ? [stripJsb(), stripPartnersCand(), stripContact(p, true)] : [stripPlan(p), stripWhy(p), stripFaq(p), stripContact(p, false)];
    var m = matchJobs(p), sr = salaryRowFor(p).row, tier = tierFor(p);
    var who = [p.stageLabel, p.locationLabel, p.family ? sr.role : null].filter(Boolean).join(' · ');
    var sum = (who ? who + ' — ' : 'Any stage, any role — ') + (m.all ? '25' : m.jobs.length) + ' live role' + ((m.all ? 25 : m.jobs.length) === 1 ? '' : 's') + (m.exact ? '' : ' nearby') + ', ' + sr.base.replace(/\s/g, '').replace('–', '–') + ' base' + (looking ? ', intro call within 48 hours.' : ', ' + tier.id + ' tier from ' + money(tier.mo) + '/mo.');
    return { summary: sum, tiles: tiles, strips: strips };
  }

  function renderBoard() {
    if (!tilesEl) return;
    var p = state.parsed, a = answer(p);
    if (summaryEl) { summaryEl.textContent = a.summary; summaryEl.title = a.summary; }
    tilesEl.innerHTML = a.tiles.map(function (t, i) {
      var open = state.open === t.id;
      return '<article class="tile' + (open ? ' is-open' : '') + '" id="t-' + t.id + '" data-tile="' + t.id + '" style="--i:' + i + '"><header class="tile-h"><h2 class="eyebrow">' + h(t.eyebrow) + '</h2><span class="badge">' + h(t.badge) + '</span></header><p class="num">' + h(t.num) + '</p><p class="line">' + h(t.line) + '</p><div class="tile-b">' + t.body + '</div><button type="button" class="open" data-toggle="' + t.id + '" aria-expanded="' + open + '" aria-controls="more-' + t.id + '">' + (open ? 'Close ↑' : 'Open ↓') + '</button><div class="tile-more" id="more-' + t.id + '" role="region" aria-label="' + h(t.eyebrow) + ' — full content"' + (open ? '' : ' hidden') + '>' + t.more + '</div><p class="tile-src">' + h(t.src) + '</p></article>';
    }).join('');
    if (stripsEl) stripsEl.innerHTML = a.strips.map(function (t, i) {
      var open = state.open === t.id;
      return '<article class="strip' + (open ? ' is-open' : '') + '" id="t-' + t.id + '" data-tile="' + t.id + '" style="--i:' + (i + 3) + '"><button type="button" class="strip-h" data-toggle="' + t.id + '" aria-expanded="' + open + '" aria-controls="more-' + t.id + '"><span class="eyebrow">' + h(t.eyebrow) + '</span><span class="strip-line">' + h(t.line) + '</span><span class="badge">' + h(t.badge) + '</span><svg class="chev" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></button><div class="tile-more" id="more-' + t.id + '" role="region" aria-label="' + h(t.eyebrow) + ' — full content"' + (open ? '' : ' hidden') + '>' + t.more + '<p class="tile-src">' + h(t.src) + '</p></div></article>';
    }).join('');
    board.classList.toggle('is-looking', state.mode === 'looking');
    board.classList.toggle('agency', state.agency);
    layoutDots(p);
    askRemote(p);
  }

  /* ---------------- Remote ask (optional Worker) ---------------- */
  var askSeq = 0;
  function askRemote(p) {
    var url = root.dataset.askUrl; if (!url || !state.brief || !window.fetch) return;
    var seq = ++askSeq;
    fetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ brief: state.brief, parsed: p }) })
      .then(function (r) { return r.json(); })
      .then(function (j) { if (seq !== askSeq || !j || j.error) return; if (j.summary && summaryEl) summaryEl.textContent = j.summary; (j.tiles || []).forEach(function (t) { var el = $('#t-' + t.id + ' .tile-b', tilesEl); if (el && t.answer) el.innerHTML = t.answer; }); })
      .catch(function () { /* local answer stands */ });
  }

  /* ---------------- Dots (quiet field behind the input) ---------------- */
  var dotsEl = $('[data-dots]'), dots = [], NDOTS = 12;
  function seedDots() { if (!dotsEl) return; var s = ''; for (var i = 0; i < NDOTS; i++) s += '<i class="dot"></i>'; dotsEl.innerHTML = s; dots = $$('.dot', dotsEl); layoutDots(state.parsed); }
  function layoutDots(p) {
    if (!dots.length) return;
    var m = matchJobs(p), hits = m.all ? 0 : Math.max(1, Math.round(NDOTS * m.jobs.length / KB.jobs.length));
    var W = dotsEl.clientWidth || 800, H = dotsEl.clientHeight || 80;
    dots.forEach(function (d, i) {
      var hit = i < hits, x, y;
      if (m.all) { x = W * (0.08 + 0.84 * i / (NDOTS - 1)); y = H * (0.3 + 0.4 * ((i * 7) % 3) / 2); }
      else if (hit) { x = W * 0.9 - (hits - 1 - i) * 10; y = H * 0.5; }
      else { x = W * (0.04 + 0.5 * ((i * 5) % NDOTS) / NDOTS); y = H * (0.2 + 0.6 * ((i * 3) % 4) / 3); }
      d.style.transform = 'translate(' + Math.round(x) + 'px,' + Math.round(y) + 'px)';
      d.classList.toggle('is-hit', hit);
    });
  }

  /* ---------------- Brief input, chips, stage, typewriter ---------------- */
  var typing = { timer: null, active: false };
  var EXAMPLES = ['Series A, London, founding AE', 'SDR in New York, Seed', 'VP Sales, Series B, remote UK'];
  var PLACEHOLDER = 'Describe the hire… e.g. Series A, London, founding AE';
  function setBrief(text, fromUser) {
    state.brief = text; state.parsed = parseBrief(text);
    if (state.parsed.mode === 'looking' && fromUser) state.mode = 'looking';
    state.tierOverride = null; state.filt = { loc: '', type: '', stage: '' };
    if (input && input.value !== text) input.value = text;
    syncStage(); syncModeChips();
    renderBoard();
  }
  var debounce;
  function onInput() { clearTimeout(debounce); var v = input.value; debounce = setTimeout(function () { setBrief(v, true); }, 120); }
  function stopTyping() { typing.active = false; clearTimeout(typing.timer); if (input) { input.classList.remove('is-typing'); input.placeholder = PLACEHOLDER; } }
  function typewriter() {
    if (!input) return;
    if (reduced) { input.placeholder = 'e.g. ' + EXAMPLES[0]; return; }
    typing.active = true; input.classList.add('is-typing');
    var ex = 0, ch = 0;
    var step = function () {
      if (!typing.active) return;
      var text = EXAMPLES[ex]; ch++;
      input.placeholder = text.slice(0, ch) + (ch < text.length ? '|' : '');
      if (ch < text.length) typing.timer = setTimeout(step, 40 + Math.random() * 40);
      else if (ex < EXAMPLES.length - 1) typing.timer = setTimeout(function () { ex++; ch = 0; if (typing.active) step(); }, 1600);
      else typing.timer = setTimeout(function () { stopTyping(); input.placeholder = 'e.g. ' + EXAMPLES[0]; }, 1600);
    };
    step();
  }
  var stageSel = $('[data-stage-select]');
  function syncStage() { if (stageSel) { stageSel.value = state.parsed.stageLabel || ''; stageSel.classList.toggle('is-on', !!state.parsed.stageLabel); $$('option', stageSel).forEach(function (o) { if (o.value) o.textContent = (o.selected ? 'Stage: ' : '') + o.value; }); } }
  function syncModeChips() { $$('[data-mode]').forEach(function (b) { var on = b.dataset.mode === state.mode; b.classList.toggle('is-on', on); b.setAttribute('aria-pressed', on ? 'true' : 'false'); }); $$('[data-nav-mode]').forEach(function (a) { a.classList.toggle('is-on', a.dataset.navMode === state.mode); }); }
  function setMode(m) { state.mode = m; state.open = null; syncModeChips(); renderBoard(); }
  function setStage(label) {
    var stripped = state.brief.replace(/pre[\s-]?seed|series\s*[abcd]\+?|\bseed\b|bootstrapped|pe[\s-]?backed/ig, '').replace(/\s*[,·]\s*[,·]\s*/g, ', ').replace(/^[\s,·]+|[\s,·]+$/g, '').trim();
    setBrief(label ? (stripped ? stripped + ', ' + label : label) : stripped, true);
  }

  /* ---------------- Board events ---------------- */
  function openTile(id, scroll) {
    state.open = state.open === id ? null : id;
    renderBoard();
    var el = $('#t-' + id); if (el && scroll !== false && state.open) el.scrollIntoView({ block: 'nearest', behavior: reduced ? 'auto' : 'smooth' });
  }
  function onBoardClick(e) {
    var t = e.target.closest('[data-toggle]'); if (t) { openTile(t.dataset.toggle); return; }
    var tier = e.target.closest('[data-tier]'); if (tier) { state.tierOverride = tier.dataset.tier; renderBoard(); return; }
    var f = e.target.closest('[data-f]'); if (f) { state.filt[f.dataset.f] = state.filt[f.dataset.f] === f.dataset.v ? '' : f.dataset.v; renderBoard(); return; }
    var all = e.target.closest('[data-all-roles]'); if (all) { state.filt = { loc: '', type: '', stage: '' }; renderBoard(); return; }
    var row = e.target.closest('[data-row]'); if (row && !e.target.closest('a')) { var ex = row.getAttribute('aria-expanded') === 'true'; row.setAttribute('aria-expanded', String(!ex)); return; }
    var op = e.target.closest('[data-open]'); if (op) { e.preventDefault(); state.open = op.dataset.open; renderBoard(); var el = $('#t-' + op.dataset.open); if (el) el.scrollIntoView({ block: 'start' }); }
  }
  function onBoardInput(e) {
    var r = e.target.closest('[data-base]'); if (r) { state.base = +r.value; var out = $('[data-base-out]', board), calc = $('[data-calc]', board); if (out) out.textContent = money(state.base); if (calc) calc.innerHTML = calcLine(tierNow(state.parsed).tier, state.base); return; }
    var c = e.target.closest('[data-intel]'); if (c) { state.intel = c.checked; renderBoard(); }
  }
  function onBoardSubmit(e) { var f = e.target.closest('[data-form]'); if (!f) return; e.preventDefault(); var note = $('[data-form-note]', f); if (note) { note.textContent = 'Concept — not wired. On the live site this reaches Ian within one working day.'; note.classList.add('is-concept'); } }
  if (board) { board.addEventListener('keydown', function (e) { if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('[data-row]')) { e.preventDefault(); e.target.click(); } }); board.addEventListener('click', onBoardClick); board.addEventListener('input', onBoardInput); board.addEventListener('submit', onBoardSubmit); }
  var briefChips = $('[data-quick]');
  if (briefChips) briefChips.addEventListener('click', function (e) { var b = e.target.closest('[data-brief-text]'); if (!b) return; stopTyping(); setBrief(b.dataset.briefText, true); });
  $$('[data-mode]').forEach(function (b) { b.addEventListener('click', function () { stopTyping(); setMode(b.dataset.mode); }); });
  $$('[data-nav-mode]').forEach(function (a) { a.addEventListener('click', function (e) { e.preventDefault(); stopTyping(); setMode(a.dataset.navMode); if (board) board.scrollIntoView({ block: 'start' }); }); });
  if (stageSel) stageSel.addEventListener('change', function () { stopTyping(); setStage(stageSel.value); });
  if (input) {
    input.addEventListener('focus', function () { if (typing.active) stopTyping(); });
    input.addEventListener('input', function () { stopTyping(); onInput(); });
    input.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); stopTyping(); setBrief(input.value, true); if (board) board.scrollIntoView({ block: 'start', behavior: reduced ? 'auto' : 'smooth' }); } });
  }
  var agencyBtn = $('[data-agency]');
  if (agencyBtn) agencyBtn.addEventListener('click', function () { state.agency = !state.agency; agencyBtn.setAttribute('aria-pressed', String(state.agency)); agencyBtn.textContent = state.agency ? 'Agency view: on' : 'Agency view'; board.classList.toggle('agency', state.agency); });
  var shareBtn = $('[data-share]');
  if (shareBtn) shareBtn.addEventListener('click', function () {
    var hash = '#b=' + encodeURIComponent(state.brief) + '&m=' + state.mode, url = location.origin + location.pathname + hash;
    history.replaceState(null, '', hash);
    var done = function () { shareBtn.textContent = 'Link copied'; setTimeout(function () { shareBtn.textContent = 'Copy link to this brief'; }, 1800); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(done, done); else done();
  });

  /* ---------------- Hash routing ---------------- */
  var DEEP = { pricing: 'fee', salary: 'rate', roles: 'roles', contact: 'contact' };
  function fromHash() {
    var hsh = location.hash.replace(/^#/, ''); if (!hsh) return false;
    if (/^b=/.test(hsh)) { var q = {}; hsh.split('&').forEach(function (kv) { var i = kv.indexOf('='); q[kv.slice(0, i)] = decodeURIComponent(kv.slice(i + 1).replace(/\+/g, ' ')); }); stopTyping(); if (q.m === 'looking' || q.m === 'hiring') state.mode = q.m; setBrief(q.b || '', false); return true; }
    if (DEEP[hsh]) { stopTyping(); if (hsh === 'pricing' || hsh === 'salary') state.mode = 'hiring'; state.open = DEEP[hsh]; syncModeChips(); renderBoard(); var el = $('#t-' + DEEP[hsh]); if (el) el.scrollIntoView({ block: 'start' }); return true; }
    return false;
  }
  window.addEventListener('hashchange', fromHash);
  $$('a[href^="#"]').forEach(function (a) { a.addEventListener('click', function (e) { var id = a.getAttribute('href').slice(1); if (DEEP[id]) { e.preventDefault(); history.replaceState(null, '', '#' + id); fromHash(); } }); });

  /* ---------------- Everything index (verbatim drawers from the KB) ---------------- */
  var cnt = $('[data-count-partners]'); if (cnt) cnt.textContent = '×' + (KB.partners.length + 1);
  var pl = $('[data-partner-list]'); if (pl) pl.innerHTML = KB.partners.map(function (p) { return '<li><b>' + h(p.name) + '</b> <span>' + h(p.tag) + '</span><p>' + h(p.text) + '</p></li>'; }).join('') + '<li><b>Your logo here?</b><p>We\'re building our partner ecosystem. If you offer tools, training or services for GTM teams, let\'s talk.</p><a href="https://gtm-people.com/partners" target="_blank" rel="noopener">Apply to partner →</a></li>';
  var sl = $('[data-spec-list]'); if (sl) sl.innerHTML = KB.specialisms.map(function (s) { return '<li><b>' + h(s.name) + '</b><p>' + h(s.text) + '</p></li>'; }).join('');
  var hl = $('[data-how-list]'); if (hl) hl.innerHTML = '<p class="lead">For clients</p><ol class="steps">' + KB.clientSteps.map(function (s) { return '<li><b>' + h(s.n) + ' ' + h(s.name) + '</b><p>' + h(s.text) + '</p></li>'; }).join('') + '</ol><p><b>' + h(KB.checkins.title) + '</b> ' + h(KB.checkins.text) + '</p><p><b>' + h(KB.taasReview.title) + '</b> ' + h(KB.taasReview.text) + '</p><p class="lead">For candidates</p><ol class="steps">' + KB.candidateSteps.map(function (s) { return '<li><b>' + h(s.n) + ' ' + h(s.name) + '</b><p>' + h(s.text) + '</p></li>'; }).join('') + '</ol>';
  var al = $('[data-about-list]'); if (al) al.innerHTML = KB.about.map(function (a) { return '<p>' + h(a) + '</p>'; }).join('') + '<ul class="pillars">' + KB.pillars.map(function (x) { return '<li><b>' + h(x.name) + '</b> ' + h(x.text) + '</li>'; }).join('') + '</ul><ul class="stats">' + KB.stats.map(function (s) { return '<li><b>' + h(s[0]) + '</b><span>' + h(s[1]) + '</span></li>'; }).join('') + '</ul>';
  var wl = $('[data-why-list]'); if (wl) wl.innerHTML = '<p>' + h(KB.whyTaas.intro) + '</p><div class="vs"><ul class="bad"><li class="vs-h">Traditional Agency</li>' + KB.whyTaas.bad.map(function (b) { return '<li>' + h(b) + '</li>'; }).join('') + '</ul><ul class="good"><li class="vs-h">GTM People TaaS</li>' + KB.whyTaas.good.map(function (b) { return '<li>' + h(b) + '</li>'; }).join('') + '</ul></div>';
  var tl = $('[data-tier-list]'); if (tl) tl.innerHTML = '<div class="tiers">' + KB.tiers.map(function (t) { return '<div class="tier">' + (t.popular ? '<span class="tag">Most Popular</span>' : '') + '<h4>' + h(t.id) + ' <small>' + h(t.sub) + '</small></h4><p class="price"><b>' + money(t.mo) + '</b>/mo <small>' + h(t.yr) + '</small></p><ul>' + t.bullets.map(function (b) { return '<li>' + h(b) + '</li>'; }).join('') + '</ul><span class="chip">' + h(t.cta) + '</span></div>'; }).join('') + '</div><p class="fine">' + h(KB.feeNotes.how) + '</p><p class="fine"><b>' + h(KB.feeNotes.beyond) + '</b> ' + h(KB.feeNotes.example) + '</p>';
  var sal = $('[data-salary-list]'); if (sal) sal.innerHTML = KB.salary.map(function (r) { return '<li><b>' + h(r.role) + '</b> ' + h(r.base) + ' · ' + h(r.ote) + '<p>' + h(r.note) + '</p></li>'; }).join('');
  var fl = $('[data-faq-list]'); if (fl) fl.innerHTML = KB.faqs.map(function (f) { return '<li><b>' + h(f.q) + '</b><p>' + h(f.a) + '</p></li>'; }).join('');
  var jl = $('[data-job-list]'); if (jl) jl.innerHTML = KB.jobs.map(roleFull).join('');

  /* ---------------- Reveal (desktop only; always painted under 800px) ---------------- */
  var reveals = $$('.reveal');
  if (reveals.length && 'IntersectionObserver' in window && window.innerWidth >= 800 && !reduced) {
    var io = new IntersectionObserver(function (es) { es.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('is-in'); io.unobserve(en.target); } }); }, { threshold: 0.01, rootMargin: '0px 0px 8% 0px' });
    reveals.forEach(function (r) { io.observe(r); });
    setTimeout(function () { reveals.forEach(function (r) { r.classList.add('is-in'); }); }, 2500);
  } else reveals.forEach(function (r) { r.classList.add('is-in'); });

  /* ---------------- Quick-brief strip: arrows + wheel ---------------- */
  (function () {
    var wrap = $('.strip-wrap'), track = wrap && wrap.querySelector('[data-quick]'); if (!wrap || !track) return;
    var prev = wrap.querySelector('[data-arr="-1"]'), next = wrap.querySelector('[data-arr="1"]');
    function sync() { var max = track.scrollWidth - track.clientWidth - 1; if (prev) prev.disabled = track.scrollLeft <= 30; if (next) next.disabled = track.scrollLeft >= max; wrap.classList.toggle('is-static', max <= 0); }
    function step(dir) { track.scrollBy({ left: dir * Math.max(160, track.clientWidth * 0.6), behavior: reduced ? 'auto' : 'smooth' }); }
    if (prev) prev.addEventListener('click', function () { step(-1); });
    if (next) next.addEventListener('click', function () { step(1); });
    track.addEventListener('wheel', function (e) { if (Math.abs(e.deltaY) > Math.abs(e.deltaX) && track.scrollWidth > track.clientWidth) { e.preventDefault(); track.scrollBy({ left: e.deltaY, behavior: 'auto' }); } }, { passive: false });
    track.addEventListener('scroll', sync, { passive: true }); window.addEventListener('resize', sync); sync(); setTimeout(sync, 600);
  })();

  /* ---------------- Boot ---------------- */
  seedDots();
  window.addEventListener('resize', function () { layoutDots(state.parsed); });
  syncModeChips(); syncStage();
  if (!fromHash()) { renderBoard(); typewriter(); }
})();

/* v4 opening (2nd IIFE). Stage = canvas (particles, dot-matrix world) + HTML cards/counters + SVG timeline.
   Footage: assets/hero.json "ready":true => the stage plays assets/hero.mp4 (recorded from this very canvas by
   research/render_hero_video.mjs) and the canvas never starts; poster only under reduced motion; canvas fallback on error.
   ?record=1 => deterministic (seeded, no autoplay) and window.__tick(frame) steps the sequence at 30 fps. */
(function () {
  var sec = document.querySelector('[data-opening]'); if (!sec) return;
  var $ = function (s, c) { return (c || sec).querySelector(s); }, $$ = function (s, c) { return Array.prototype.slice.call((c || sec).querySelectorAll(s)); };
  var mq = function (q) { return !!(window.matchMedia && window.matchMedia(q).matches); };
  var REC = /[?&]record=1/.test(location.search), reduced = !REC && mq('(prefers-reduced-motion: reduce)'), TAU = Math.PI * 2;
  var DUR = REC ? [4100, 2700, 2600, 2600] : [6500, 4200, 4200, 4200], VDUR = [4100, 2700, 2600, 2600];
  var beats = $$('[data-beat]'), pills = $$('[data-pill]'), stage = $('[data-stage]'), cardsBox = $('[data-cards]'), cards = $$('[data-card]'); if (!beats.length || !stage) return;
  var cur = 0, acc = 0, last = 0, raf = 0, paused = false, onScreen = true, busy = 0, videoMode = false;
  var seed = 1234567, rnd = REC ? function () { seed |= 0; seed = seed + 0x6D2B79F5 | 0; var t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; } : Math.random;
  var ease = function (k) { return k < 0 ? 0 : k > 1 ? 1 : 1 - Math.pow(1 - k, 3); }, lerp = function (a, b, k) { return a + (b - a) * k; };

  var fmt = function (n, suf) { return (n >= 1000 ? n.toLocaleString('en-GB') : String(n)) + suf; };
  function setCounters(k) { $$('[data-count]').forEach(function (el) { var to = +el.dataset.count; el.textContent = fmt(Math.round(to * ease(k)), el.dataset.suffix || ''); }); }
  function counters() {
    if (reduced) { setCounters(1); return; }
    var t0 = 0; setCounters(0);
    (function step(now) { if (!t0) t0 = now; var k = (now - t0) / 1400; setCounters(k); if (k < 1 && cur === 1) requestAnimationFrame(step); })(performance.now());
  }
  function setCards(lit, up) { cards.forEach(function (c, k) { c.classList.toggle('is-lit', k < lit); c.classList.toggle('is-up', up && k === 2); }); if (cardsBox) cardsBox.classList.toggle('is-placed', !!up); }
  function show(n) { beats[n].classList.add('is-on'); sec.dataset.cur = n; if (n === 1) { setCards(5, false); if (!REC) setTimeout(function () { if (cur === 1) counters(); }, 450); } if (n === 0) setCards(0, false); }
  function go(i) {
    var n = (i + beats.length) % beats.length, tok = ++busy, out = beats[cur]; cur = n; acc = 0;
    pills.forEach(function (p, k) { p.setAttribute('aria-current', k === n ? 'true' : 'false'); p.style.setProperty('--p', k < n ? '1' : '0'); });
    beats.forEach(function (b) { if (b !== out) b.classList.remove('is-on', 'is-out'); });
    out.classList.add('is-out');
    setTimeout(function () { out.classList.remove('is-on', 'is-out'); if (tok !== busy) return; setTimeout(function () { if (tok === busy) show(n); }, reduced ? 0 : 120); }, reduced ? 0 : 260);
  }
  pills.forEach(function (p, k) {
    p.addEventListener('click', function () { if (k !== cur && !videoMode) go(k); });
    p.addEventListener('keydown', function (e) { var d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0; if (!d || videoMode) return; e.preventDefault(); go(cur + d); pills[cur].focus(); });
  });
  sec._go = go; /* QA hook (no pager in the UI; beats auto-advance) */
  var hov = false, foc = false, upd = function () { paused = hov || foc; };
  sec.addEventListener('mouseenter', function () { hov = true; upd(); }); sec.addEventListener('mouseleave', function () { hov = false; upd(); });
  sec.addEventListener('focusin', function () { foc = true; upd(); }); sec.addEventListener('focusout', function () { foc = false; upd(); });

  /* ---- canvas ---- */
  var cv = $('[data-pipe]'), ctx = cv && cv.getContext ? cv.getContext('2d') : null, W = 0, H = 0, P = [], m = false, spr = null;
  function sprite(col) { var c = document.createElement('canvas'); c.width = c.height = 24; var g = c.getContext('2d'), gr = g.createRadialGradient(12, 12, 0, 12, 12, 12); gr.addColorStop(0, col + '.6)'); gr.addColorStop(1, col + '0)'); g.fillStyle = gr; g.fillRect(0, 0, 24, 24); return c; }
  var sprM = null;
  function seedP() {
    m = window.innerWidth < 800; var N = m ? 300 : 800; P = []; seed = 1234567;
    for (var i = 0; i < N; i++) { var a = rnd() * TAU, r = Math.sqrt(rnd()); P.push({ x: .5 + Math.cos(a) * r * .44, y: .3 + Math.sin(a) * r * .19, s: .25 + rnd() * .5, ph: rnd() * TAU, d: rnd(), c: i % 5, r: 1.6 + rnd(), al: .75 + rnd() * .2 }); }
  }
  function size() { if (!ctx) return; var d = Math.min(m ? 1.25 : 1.5, window.devicePixelRatio || 1); W = stage.clientWidth; H = stage.clientHeight; m = window.innerWidth < 800; cv.width = W * d; cv.height = H * d; ctx.setTransform(d, 0, 0, d, 0, 0); seedP(); if (!spr) { spr = sprite('rgba(167,139,250,'); sprM = sprite('rgba(6,214,160,'); } mapLayout(); }
  function cardX(k) { var cw = m ? 40 : 56; return W / 2 + (k - 2) * (cw + 8); }
  function drawPipe(now, p) {
    var t = now / 1000, i, d, x, y, k, al, ch = m ? 40 : 56, nx = W / 2, top = H * .89 - ch, ny = top - 38, cy = top + ch / 2, dim = cur === 1 ? .1 : 1, lit = 0, glow = [0, 0, 0, 0, 0];
    for (i = 0; i < P.length; i++) {
      d = P[i]; al = d.al * dim; var sp = cur === 0 ? 1 : .35;
      var cx = W * d.x + Math.sin(t * d.s * sp + d.ph) * 9, cyy = H * d.y + Math.cos(t * d.s * .8 * sp + d.ph) * 7;
      x = cx; y = cyy;
      if (cur === 0 && p > .26 && d.d < .74) {
        if (p > .64) continue;
        k = ease((p - .26 - d.d * .26) / .22);
        if (k > 0) {
          if (k < .55) { var q = k / .55; x = lerp(cx, nx + (d.d - .5) * 24, q); y = lerp(cyy, ny, q); }
          else { var q2 = (k - .55) / .45; x = lerp(nx + (d.d - .5) * 24, cardX(d.c), q2); y = lerp(ny, cy, q2); if (y >= top - 2) { if (d.c + 1 > lit) lit = d.c + 1; if (q2 < 1.06) glow[d.c] += .12; continue; } }
        }
      }
      ctx.globalAlpha = al * .9; ctx.drawImage(spr, x - 7, y - 7, 14, 14);
      ctx.globalAlpha = al; ctx.fillStyle = '#C4B5FD'; ctx.beginPath(); ctx.arc(x, y, d.r, 0, TAU); ctx.fill();
    }
    if (cur === 0) for (i = 0; i < 5; i++) { var gl = p > .64 ? Math.max(0, 1 - (p - .64) / .1) * .5 : Math.min(1, glow[i]); if (gl > 0) { ctx.globalAlpha = gl; ctx.drawImage(sprM, cardX(i) - 30, top - 30, 60, 60); } }
    ctx.globalAlpha = 1;
    if (cur === 0) { var litN = p < .26 ? 0 : p < .62 ? Math.min(5, Math.max(lit, Math.floor((p - .3) / .064))) : 5; setCards(litN, p > .72); }
  }

  /* ---- dot-matrix world: Natural Earth 110m land rasterised by research/build_dotmap.py (equirectangular, lat +-60) ---- */
  var DOTMAP = { cols: 164, rows: 53, step: 2.2, lat: 58.3, b64: 'ACAH//+B/AAAAYGf////////gHAAEAA///8/8AAAKAH////////gBgAAAAH///v/AAAC7//////////gQAAAAA/////gAAAT//////////4AAAAAAH///9HAAAD//////////6AAAAAAB////6AAAAf/9fP/////8AAAAAAAf///wAAAAHt+Dn/////+MAAAAAAH///8AAAAPhnsc/////+AAAAAAAA///8AAAADwFP/P////xBAAAAAAAP//+AAAAA4CD/7////+YwAAAAAAB///gAAAAH+AD//////E4AAAAAAAH//gAAAAD/xA//////4QAAAAAAAB//4AAAAB//f//////+AAAAAAAAAH8CAAAAAf//79/////gAAAAAAAAA/AAAAAAf//+/j////wAAAAAAAAAXgCAAAAH///3/B///4AAAAAAAAAA4AgAAAD///+/4f8/4AAAAAAAAAAPEBAAAA////v8B+P0AAAAAAAAAAA/AAAAAP///5+AeB8AAAAAAAAAAAA8AAAAD////eADAPggAAAAAAAAAADAAAAA////4AAwA4AAAAAAAAAAAAQ5AAAH////YAMAGBAAAAAAAAAAAD/4AAA////+AAgIAIAAAAAAAAAAAH/AAAH////AAIBACAAAAAAAAAAAB/+AAAAP//gAAAoIAAAAAAAAAAAA//gAAAD//wAAAGOAAAAAAAAAAAAf/8AAAA//4AAABngAAAAAAAAAAAD//wAAAP/8AAAAM6CwAAAAAAAAAB///gAAB//AAAABAgPAAAAAAAAAAf//8AAAP/wAAAAOAB4AAAAAAAAAD///AAAD/8AAAAAAgJAAAAAAAAAAf//gAAA//AAAAAAACAAAAAAAAAAH//wAAAP/wgAAAAAcgAAAAAAAAAA//8AAAH/8QAAAAA/MAAAAAAAAAAH//AAAB/+MAAAAAf/AAIAAAAAAAA//wAAAP/DAAAAAP/4AAAAAAAAAAP/4AAAD/xwAAAAP//AAAAAAAAAAD/wAAAA/8IAAAAH//4AAAAAAAAAA/8AAAAH+AAAAAB//+AAAAAAAAAAf+AAAAB/AAAAAAP//wAAAAAAAAAH/gAAAAPgAAAAAD//4AAAAAAAAAB/wAAAADwAAAAAA8H+AAAAAAAAAAfwAAAAAAAAAAAAAAfAAAAAAAAAAP8AAAAAAAAAAAAAADwAQAAAAAAAD8AAAAAAAAAAAAAAAAAEAAAAAAAA8AAAAAAAAAAAAAAACACAAAAAAAAHAAAAAAAAAAAAAAAAADAAAAAAAADgAAAAAAAAAAAAAAAAAgAAAAAAAB4AAAAAAAAAAAAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAAAAAAAABgAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==' };
  var BITS = null, DOTS = [], MAP = {}, CITIES = [['London', -0.13, 51.5], ['Manchester', -2.2, 53.5], ['Paris', 2.35, 48.85], ['New York', -74, 40.7], ['San Francisco', -122.4, 37.8]];
  function bits() { if (BITS) return BITS; var bin = atob(DOTMAP.b64); BITS = new Uint8Array(bin.length); for (var i = 0; i < bin.length; i++) BITS[i] = bin.charCodeAt(i); return BITS; }
  function land(lon, lat) { var c = Math.floor((lon + 180) / DOTMAP.step), r = Math.floor((DOTMAP.lat - lat) / DOTMAP.step); if (r < 0 || r >= DOTMAP.rows || c < 0 || c >= DOTMAP.cols) return 0; var i = r * DOTMAP.cols + c; return bits()[i >> 3] >> (7 - (i & 7)) & 1; }
  var LON0 = -135, LON1 = 40, YS = 1.25; /* lon crop (the five cities + Europe/Africa/Americas) and a mild vertical stretch so the band fills the square stage */
  function proj(lon, lat) { return [MAP.x + (lon - LON0) / (LON1 - LON0) * MAP.w, MAP.y + (DOTMAP.lat - lat) / (2 * DOTMAP.lat) * MAP.h]; }
  function mapLayout() {
    if (!DOTMAP.b64) return; var inset = 16; MAP.w = W - inset * 2; MAP.h = Math.min(H * .9, MAP.w * (2 * DOTMAP.lat) / (LON1 - LON0) * YS); MAP.x = inset; MAP.y = (H - MAP.h) / 2; MAP.lon0 = LON0; MAP.lon1 = LON1; MAP.lat = DOTMAP.lat;
    DOTS = []; var b = bits(), pins = CITIES.map(function (c) { return proj(c[1], c[2]); }), c0 = Math.floor((LON0 + 180) / DOTMAP.step), c1 = Math.ceil((LON1 + 180) / DOTMAP.step);
    for (var r = 0; r < DOTMAP.rows; r++) for (var c = c0; c < c1; c++) { var i = r * DOTMAP.cols + c; if (b[i >> 3] >> (7 - (i & 7)) & 1) { var q = proj(-180 + (c + .5) * DOTMAP.step, DOTMAP.lat - (r + .5) * DOTMAP.step), near = pins.some(function (pp) { return (pp[0] - q[0]) * (pp[0] - q[0]) + (pp[1] - q[1]) * (pp[1] - q[1]) < (m ? 60 : 200); }); if (q[0] >= MAP.x && q[0] <= MAP.x + MAP.w) DOTS.push([q[0], q[1], near]); } }
    sec._pins = {}; CITIES.forEach(function (c, i) { sec._pins[c[0]] = pins[i]; }); sec._land = land; sec._map = MAP;
  }
  function drawMap(now, p) {
    if (!DOTS.length) return; var i, dr = m ? 1 : 1.25, t = now / 1000;
    var edge = MAP.x + MAP.w - 48; ctx.fillStyle = 'rgba(255,255,255,.55)'; ctx.beginPath(); for (i = 0; i < DOTS.length; i++) if (!DOTS[i][2] && DOTS[i][0] <= edge) { ctx.moveTo(DOTS[i][0] + dr, DOTS[i][1]); ctx.arc(DOTS[i][0], DOTS[i][1], dr, 0, TAU); } ctx.fill();
    for (i = 0; i < DOTS.length; i++) if (!DOTS[i][2] && DOTS[i][0] > edge) { ctx.globalAlpha = Math.max(0, 1 - (DOTS[i][0] - edge) / 48); ctx.beginPath(); ctx.arc(DOTS[i][0], DOTS[i][1], dr, 0, TAU); ctx.fill(); } ctx.globalAlpha = 1; /* soft right edge: dots fade over the last 48 px */
    ctx.fillStyle = '#06D6A0'; ctx.beginPath(); for (i = 0; i < DOTS.length; i++) if (DOTS[i][2]) { ctx.moveTo(DOTS[i][0] + dr, DOTS[i][1]); ctx.arc(DOTS[i][0], DOTS[i][1], dr, 0, TAU); } ctx.fill();
    var L = sec._pins.London, fs = m ? 10 : 13, sc = m ? .6 : 1; ctx.font = '600 ' + fs + 'px ' + getComputedStyle(sec).fontFamily; ctx.lineWidth = 1.6; ctx.strokeStyle = 'rgba(6,214,160,.9)';
    /* arcs: every arc starts at London; short hops get a small bulge */
    CITIES.forEach(function (c, k) {
      if (!k) return; var q = sec._pins[c[0]], g = ease((p - .08 - (k - 1) * .09) / .35); if (g <= 0) return;
      var dx = Math.abs(L[0] - q[0]), mx = (L[0] + q[0]) / 2, my = Math.min(L[1], q[1]) - Math.min(dx * .3, 60) - 4;
      ctx.beginPath(); ctx.moveTo(L[0], L[1]); for (var s = 1; s <= 24; s++) { var u = s / 24 * g, a = 1 - u; ctx.lineTo(a * a * L[0] + 2 * a * u * mx + u * u * q[0], a * a * L[1] + 2 * a * u * my + u * u * q[1]); } ctx.stroke();
    });
    /* pins: UK pair small (6 px) with a dark separator ring; London pulses */
    var OFF = [[28, 0], [-40, -40], [36, 36], [0, 22], [0, 22]], boxes = [];
    CITIES.forEach(function (c, k) {
      var q = sec._pins[c[0]], pr = k < 2 ? 3 : 4;
      ctx.fillStyle = '#1B0838'; ctx.beginPath(); ctx.arc(q[0], q[1], pr + 1.5, 0, TAU); ctx.fill();
      ctx.fillStyle = k ? '#F5F3FF' : '#06D6A0'; ctx.beginPath(); ctx.arc(q[0], q[1], pr, 0, TAU); ctx.fill();
      if (!k) { var pu = (t % 2) / 2; ctx.globalAlpha = 1 - pu; ctx.beginPath(); ctx.arc(q[0], q[1], pr + 3 + pu * 14, 0, TAU); ctx.stroke(); ctx.globalAlpha = 1; }
    });
    /* labels: offset + leader line, nudged 16 px along their own direction until boxes no longer intersect */
    CITIES.forEach(function (c, k) {
      var q = sec._pins[c[0]], ox = OFF[k][0] * sc, oy = OFF[k][1] * sc, w = ctx.measureText(c[0]).width, h = fs, bx, by, tries = 0, hit;
      var place = function () { var lx = q[0] + ox, ly = q[1] + oy; bx = ox > 0 ? lx : ox < 0 ? lx - w : lx - w / 2; by = ly - h / 2; };
      place();
      do { hit = boxes.some(function (b) { return bx < b[0] + b[2] + 4 && bx + w + 4 > b[0] && by < b[1] + b[3] + 2 && by + h + 2 > b[1]; }); if (hit) { oy += (oy < 0 ? -16 : 16) * sc; place(); } } while (hit && ++tries < 6);
      boxes.push([bx, by, w, h]);
      if (ox || oy) { var ex = ox > 0 ? bx - 3 : ox < 0 ? bx + w + 3 : q[0], ey = ox ? by + h / 2 : (oy > 0 ? by - 2 : by + h + 2); ctx.strokeStyle = 'rgba(255,255,255,.5)'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(q[0], q[1]); ctx.lineTo(ex, ey); ctx.stroke(); ctx.strokeStyle = 'rgba(6,214,160,.9)'; ctx.lineWidth = 1.6; }
      ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.fillStyle = '#F5F3FF'; ctx.fillText(c[0], bx, by + h / 2); ctx.textBaseline = 'alphabetic';
    });
  }
  function draw(now) { ctx.clearRect(0, 0, W, H); if (cur < 2) drawPipe(now, acc / DUR[0]); else if (cur === 3) drawMap(now, acc / DUR[3]); }
  function frame(now) {
    raf = 0; if (!last) last = now; var dt = Math.min(100, now - last); last = now;
    if (!paused && !reduced) { acc += dt; if (acc >= DUR[cur]) go(cur + 1); if (pills[cur]) pills[cur].style.setProperty('--p', (acc / DUR[cur]).toFixed(3)); }
    if (ctx) draw(now);
    if (onScreen && !document.hidden && !reduced && !videoMode) raf = requestAnimationFrame(frame); else last = 0;
  }
  function start() { if (!raf && onScreen && !document.hidden && !videoMode && !REC) raf = requestAnimationFrame(frame); }
  size(); window.addEventListener('resize', size);
  document.addEventListener('visibilitychange', function () { start(); syncVideo(); });
  var hdr = document.querySelector('.hdr');
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(function (es) { onScreen = es[0].intersectionRatio >= .15; start(); syncVideo(); }, { threshold: [0, .15, .3] }).observe(sec);
    if (hdr) new IntersectionObserver(function (es) { hdr.classList.toggle('over', es[0].isIntersecting); }, { rootMargin: '-64px 0px 0px 0px', threshold: 0 }).observe(sec);
  }
  if (REC) {
    sec.classList.add('rec'); var qs = /[?&]size=(\d+)/.exec(location.search); if (qs) { stage.style.width = stage.style.height = qs[1] + 'px'; size(); }
    window.__tick = function (f) {
      var t = f / 30 * 1000, tot = DUR.reduce(function (a, b) { return a + b; }, 0), u = t % tot, n = 0; while (u >= DUR[n]) { u -= DUR[n]; n++; }
      if (n !== cur) { beats.forEach(function (b, k) { b.classList.toggle('is-on', k === n); b.classList.remove('is-out'); }); cur = n; sec.dataset.cur = n; pills.forEach(function (p, k) { p.setAttribute('aria-current', k === n ? 'true' : 'false'); p.style.setProperty('--p', k < n ? '1' : '0'); }); if (n === 0) setCards(0, false); if (n === 1) setCards(5, false); }
      acc = u; if (n === 1) setCounters((u - 450) / 1400); if (ctx) draw(t); return n;
    };
    window.__tick(0);
  } else if (reduced && ctx) { draw(0); setCards(5, true); } else start();

  /* ---- CTAs ---- */
  var brief = document.getElementById('brief'), input = document.querySelector('[data-brief]');
  function toBrief(e) { e.preventDefault(); if (!brief) return; brief.scrollIntoView({ block: 'start', behavior: reduced ? 'auto' : 'smooth' }); if (input) input.focus({ preventScroll: true }); }
  var sb = $('[data-start-brief]'); if (sb) sb.addEventListener('click', toBrief);
  var br = $('[data-browse-roles]'); if (br) br.addEventListener('click', function (e) { var look = document.querySelector('[data-nav-mode="looking"]'); if (look) look.click(); toBrief(e); if (input) input.blur(); });

  /* ---- footage (see header) ---- */
  var vid = $('[data-hero-video]'), vtimer = 0;
  function syncVideo() { if (!vid || !videoMode) return; if (onScreen && !document.hidden) { if (vid.paused && vid.currentSrc) vid.play().catch(function () {}); } else if (!vid.paused) vid.pause(); }
  function videoBeats() { if (vtimer) return; vtimer = setInterval(function () { if (!videoMode || vid.paused) return; var u = (vid.currentTime * 1000) % 12000, n = 0; while (u >= VDUR[n]) { u -= VDUR[n]; n++; } if (n !== cur) go(n); if (pills[n]) pills[n].style.setProperty('--p', (u / VDUR[n]).toFixed(2)); }, 120); }
  function enterVideo() { videoMode = true; if (raf) { cancelAnimationFrame(raf); raf = 0; } sec.classList.add('has-video'); videoBeats(); }
  function leaveVideo() { videoMode = false; clearInterval(vtimer); vtimer = 0; sec.classList.remove('has-video'); vid.innerHTML = ''; start(); }
  var con = navigator.connection, saveData = !!(con && con.saveData);
  if (vid && !REC && !/[?&]canvas=1/.test(location.search) && window.fetch && /^https?:/.test(location.protocol)) { // ?canvas=1 forces the live canvas (QA)
    try {
      fetch('assets/hero.json').then(function (r) { return r.ok ? r.json() : null; }).then(function (mf) {
        if (!mf || !mf.ready) return;
        if (mf.poster) vid.poster = 'assets/' + mf.poster;
        if (reduced || saveData) { if (mf.poster) sec.classList.add('has-video'); return; }
        vid.addEventListener('playing', enterVideo, { once: true }); vid.addEventListener('error', leaveVideo, { once: true });
        var f = (m && mf.portrait) || mf.landscape || 'hero.mp4'; vid.innerHTML = '<source src="assets/' + f + '" type="video/mp4"><source src="assets/' + f.replace(/\.mp4$/, '.webm') + '" type="video/webm">'; vid.load(); var pl = vid.play(); if (pl && pl.catch) pl.catch(function () {});
      }).catch(function () {});
    } catch (err) { /* no footage */ }
  }
})();
