# Captions — batch 1 v2

Posting notes apply to every week: personal profile, not the company page. No link anywhere in the post or the first comment. No hashtags. Reply to every saver and commenter by DM within the day. Log per post: impressions, saves, profile views at 48 h, inbound DMs. After 6 posts: kill a format under 1 save per 500 impressions or under 1% profile-view rate; scale above 2% profile views or 1 inbound DM per 2 posts.

## Week 01 — Product judgment — face

**Headline (on image):** Founders: 12 emails by hand, 4% replies.  
**Original headline:** Before you automate it, follow one real case.  
**Card fact (image only, not in caption):** A dozen emails a day, typed by hand. 4% replied. Then the tool.

**Caption** (984 chars):

Before I automated a founder's outbound, I read how he did it by hand.

The client was a US outbound consultancy. The founder had been finding sellers himself: a cold email at a time, a short blunt message, no tool. It worked: 12 emails a day, 4% replies, counted as replies per hand-sent email. It could not scale past what a single person can type in a morning.

Most automation projects start with the tool. This started with his sent folder. Reading those emails told me what the machine had to keep: the bluntness, the single question, the fact that a reply went to a person who knew the deal. It also showed where the exceptions lived. Not in the send step; after someone wrote back.

So the first thing we built was not a sender. It was a stop point: the daily run reads a kill switch before any step executes, because a system that cannot be halted should not carry a founder's reputation.

What was the last process you automated without first watching someone do it by hand?

**Alt text:** Debanjan Mazumdar, cut out on paper, beside the headline 'Founders: 12 emails by hand, 4% replies.' A note reads: read his sent folder before writing a line of code.

**Posting notes:** Format: single image (4:5 PNG). Link: none. CTA: No CTA. Measure: impressions · saves · profile views at 48 h · inbound DMs.

## Week 02 — Outbound systems — artefact

**Headline (on image):** 32 inboxes, 800 sends. Who replied?  
**Original headline:** A sent email is an activity. A useful reply is progress.  
**Card fact (image only, not in caption):** An out-of-office match returns confidence 0.99 at €0.00. No model is called.

**Caption** (973 chars):

A sent email is activity. Only a classified reply is pipeline.

The client PRD for a US outbound consultancy set the target at 800 sends a day across 32 inboxes, about 24,000 a month. Success was not written as sends. It was written as 30 to 60 positive conversations a month, booked calls tracked in the CRM, and every positive reply in front of a person fast enough to act on.

So the system that matters is the one that runs after someone answers. Each reply is sorted into a bucket: hot, positive, neutral, negative, or auto-reply. Out-of-office and unsubscribe replies are caught by plain regex before any language model sees them. Anything that looks like a buyer creates a tagged contact and an opportunity at a named pipeline stage, so a human sees it with context, not in a shared inbox.

Volume is a cost line. Replies are the product. Keep them in separate columns.

Which number does your team report on Monday: sends, or replies that someone actually acted on?

**Alt text:** Editor fragment of reply_classifier.py: regex catches out-of-office replies before any model call, the auto_reply_or_OOO line marked in brass. Headline: 32 inboxes, 800 sends. Who replied?

**Posting notes:** Format: single image (4:5 PNG). Link: none. CTA: Ask a practical question, not “agree?”. Measure: impressions · saves · profile views at 48 h · inbound DMs.

## Week 03 — AI reliability — carousel

**Headline (on image):** Your AI demo passed. 4 of 8 French CVs failed.  
**Original headline:** An AI demo works on the happy path.  
**Card fact (image only, not in caption):** An empty reply body classifies as neutral with 0.0 confidence. It is a test, not a crash.

**Caption** (958 chars):

An AI demo shows the happy path. A product has to survive everything else.

Three failure cases I now test before trusting any AI workflow, all from my own code.

Missing fields. A provider can return a null message body with a normal finish reason. The shared client used to crash on it; now an empty answer is an empty string, logged, not an exception.

Strange inputs. A reply classifier gets phone numbers, bare signatures, blank bodies. Each odd input became a named test before the classifier went live.

Wrong answers. A CV optimiser produced French bullets with English connective syntax. A per-field language check caught it across half the evaluation set and forced a model change before a single candidate saw it.

None of these appeared in the demo. Each one has a named test now, and the test file is where a buyer should look first.

Which failure would embarrass you most: a crash, a strange input handled wrongly, or a confident wrong answer?

**Alt text:** Six-slide document: your AI demo passed, 4 of 8 French CVs failed. Cases: a null provider response, a blank reply body, English grammar inside French CV bullets. Each became a test.

**Posting notes:** Format: document post (upload the PDF, 6 pages). Link: none. CTA: No CTA. Measure: impressions · saves · profile views at 48 h · inbound DMs.

## Week 04 — Operations — artefact

**Headline (on image):** Your reps retype into GoHighLevel. Still.  
**Original headline:** If a human still copies the answer into the CRM, the workflow isn’t finished.  
**Card fact (image only, not in caption):** Dedup key = provider:type:id. The watermark never goes in: identity does not change when fields do.

**Caption** (957 chars):

If a rep still pastes the reply into the CRM, the automation is not finished.

The before: an outbound tool sends, a reply lands in a shared inbox, someone copies the name and the message into GoHighLevel, picks a stage, forgets the tag. Now and then the same lead is created twice.

The after: the webhook that receives the reply writes the record itself, assigns the owner and sets the next step. The part that makes this safe is boring. Writes are idempotent, so a replayed webhook or a re-run of the sync updates the existing record instead of cloning it. Dedup entries live in a key-value store with a 60-day expiry, long enough to outlast any retry storm.

Nobody measured hours saved on this, so I will not claim them. What changed is observable: the rep opens the CRM and the next step is already there, with an owner and a tag, before anyone has typed anything.

Where in your funnel does a human still carry data from one tool to the next by hand?

**Alt text:** Editor fragment of mapping.py: dedup_key builds provider:type:id and never includes the watermark; the return line marked in brass. Headline: Your reps retype replies into GoHighLevel. Still.

**Posting notes:** Format: single image (4:5 PNG). Link: none. CTA: No CTA. Measure: impressions · saves · profile views at 48 h · inbound DMs.

## Week 05 — Founder perspective — face

**Headline (on image):** Your PM can't read code. I had to learn.  
**Original headline:** I moved closer to the code because handoffs hide too much.  
**Card fact (image only, not in caption):** cv-optimizer-agent: 15 commits, first to usable in three days.

**Caption** (984 chars):

For 15 years I wrote the requirements. Then I started reading the commits.

Engineer, then QA and release coordinator, then product owner, then AI product manager, then freelance AI product engineer. It is the slow realisation that every handoff hides something, and that the hidden thing usually decides whether the product works.

The moment it changed: a GenAI rollout where I owned the eval thresholds as a PM. Go/no-go gates, rollback plans, API contracts, all in the PRD. But the questions that mattered, what happens when the model returns nothing, when the provider rate-limits, when the answer is fluent and wrong, were only answerable by someone reading the code. So I started reading it, then writing it.

The detail only I would know: two of my public repos now have more test functions than commits, because the first thing I learned from engineers was to write the failure case down before the feature.

When did a document last hide the thing that decided your project?

**Alt text:** Debanjan Mazumdar, cut out on paper, beside the headline 'Your PM can't read code. I had to learn.' A note reads: the commit log does not flatter anyone.

**Posting notes:** Format: single image (4:5 PNG). Link: none. CTA: No CTA. Measure: impressions · saves · profile views at 48 h · inbound DMs.

## Week 06 — AI product strategy — carousel

**Headline (on image):** CEOs: that 'agent'? One regex, a 0.6 gate.  
**Original headline:** Not every AI idea deserves an agent.  
**Card fact (image only, not in caption):** Under 0.6 confidence, or on any error, the email goes to a human, never to the agent.

**Caption** (991 chars):

Not every AI idea deserves an agent. Most deserve a rule and a human.

The decision test I use, with the code behind each branch.

A rule, when the bad cases are enumerable. The humanizer strips openers like 'Certainly!' and the usual AI vocabulary with regular expressions before any token is spent.

A workflow, when the steps are known and only the judgement is fuzzy. Email triage asks a small decision model to bucket each message, and anything below the confidence floor, or any error, goes to a person rather than to the agent.

Retrieval, when the answer must cite a source you own.

An agent, only when the steps are not known in advance and the cost of a wrong step is recoverable.

Each branch closes with a human check. The client that calls the decision model retries once on a rate limit and otherwise fails open with an error field. It never raises, so the person always gets a turn.

Which branch did your last AI project actually need, and which one did the vendor sell you?

**Alt text:** Six-slide document: CEOs, that 'agent'? One regex, a 0.6 gate. Branches: a rule (regex), a workflow (confidence gate to a human), an agent; one human check closes each.

**Posting notes:** Format: document post (upload the PDF, 6 pages). Link: none. CTA: Invite thoughtful counterexamples. Measure: impressions · saves · profile views at 48 h · inbound DMs.

## Week 07 — Voice AI — carousel

**Headline (on image):** A dental phone bot says 'operator' first.  
**Original headline:** A voice assistant needs to know when to stop talking.  
**Card fact (image only, not in caption):** 'If you'd rather speak to a human, just say operator at any time' is in the greeting, before any question.

**Caption** (964 chars):

A voice agent that cannot stop talking is a liability, not a receptionist.

I built a phone assistant for a dental clinic. The hardest part was not booking; it was leaving.

The greeting discloses the AI and hands the caller an exit word before any question is asked. The prompt lists the reasons to transfer: the caller asks for a person, an emergency, a language mismatch, a hostile caller, unclear audio after repeated spell-backs, a tool failure. When any of them fires, the only allowed response is the transfer line.

The handoff carries what the human needs: who is calling, why the agent stopped, and the transcript. If the calendar reports a duplicate booking, the agent hears 'duplicate' with the reason, so the caller gets an explanation instead of silence.

Escalation is part of the experience. Designing it last is how a bot ends up arguing with a patient.

What is the exit word in your customer-facing automation, and does it work on the first try?

**Alt text:** Six-slide document: a dental phone bot says 'operator' first. The exit word in the greeting, six transfer reasons, handoff means no tools, and what the human receives.

**Posting notes:** Format: document post (upload the PDF, 6 pages). Link: none. CTA: No CTA. Measure: impressions · saves · profile views at 48 h · inbound DMs.

## Week 08 — Trust / offer — face

**Headline (on image):** Bring me one task. Keep the 40 slides.  
**Original headline:** Bring one repetitive task. Not a 40-slide AI strategy.  
**Card fact (image only, not in caption):** You leave with a written map of steps, handoffs and exceptions.

**Caption** (994 chars):

Bring one repetitive task to a 30-minute session. Leave the strategy deck at home.

What happens in a session. You describe a task your team repeats every week: the spreadsheet someone rebuilds, the replies someone sorts, the calls someone screens. We map the current steps on the call, mark where a person decides and where a person merely copies, and decide together whether automation is worth it. Sometimes it is not, and I say so.

What I will not promise before scoping: a timeline, a price, or an outcome I have not measured. My own site lists the voice demo as 'on request' because the sandbox is not live yet, and I would rather lose a lead than describe a demo that does not exist.

What you keep either way: a written map of the task, the handoffs and the exception cases, which is useful even if you build it with someone else. All code and credentials are yours from day one if we do build.

Which task would you bring: the one that annoys you most, or the one that costs you most?

**Alt text:** Debanjan Mazumdar, cut out on paper, beside the headline 'Bring me one task. Keep the 40 slides.' A note reads: bring the ugly spreadsheet, not the deck. Footer: 30-minute session.

**Posting notes:** Format: single image (4:5 PNG). Link: none. CTA: Soft invitation. On image: '30-minute session · details in the post'. Guardrail: Use this CTA only if the 30-minute session and described process are currently offered. Measure: impressions · saves · profile views at 48 h · inbound DMs.

## Week 09 — Product delivery — artefact

**Headline (on image):** Your 'add AI' line vs 3 hours to a human.  
**Original headline:** A roadmap item is not a business outcome.  
**Card fact (image only, not in caption):** Success metric as written: all positive replies surfaced to the team within 3 hours.

**Caption** (910 chars):

'Build outbound' is a roadmap item. '30 to 60 conversations a month' is an outcome.

The PRD for a US outbound consultancy did not list features. Its success section read like observations: positive conversations per month, booked calls tracked in the CRM, every positive reply surfaced to the team within 3 hours. You can check each of them on a Monday without asking an engineer.

Rewriting a vague AI roadmap item works the same way. 'Add an AI assistant' becomes 'a rep sees the next step on every positive reply without opening the inbox'.

Earlier in my career a recommendation engine was judged on iteration cycles and post-launch fit, not on whether it shipped. The cycles dropped by about a third and fit rose after launch. The roadmap item was the engine; the outcome was the team changing how it planned.

What is the last roadmap item your team shipped where nobody can say what changed afterwards?

**Alt text:** Markdown fragment of a client PRD, success metrics section: positive conversations per month, booked calls in the CRM, all positive replies surfaced within 3 hours, that line marked in brass.

**Posting notes:** Format: single image (4:5 PNG). Link: none. CTA: No CTA. Measure: impressions · saves · profile views at 48 h · inbound DMs.

## Week 10 — Operations — carousel

**Headline (on image):** Founders: API down overnight. Who acts?  
**Original headline:** A workflow without an owner is just a script.  
**Card fact (image only, not in caption):** MAX_RETRIES = 2. After that the client raises, so a person sees it.

**Caption** (989 chars):

A workflow without an owner is a script that will fail at the worst moment.

Ownership across my daily outbound run.

Trigger: before any step executes, the orchestrator reads a kill switch. If it is set, nothing runs and the log says why.

Automation: the model client retries rate limits and server errors with backoff, then raises. A retry loop that never gives up is not resilience; it is a hidden outage.

Exception: the audit loop fingerprints every finding. If the same one keeps coming back without being fixed, the loop aborts instead of oscillating.

Human: releasing the kill switch does not resume sending. A person resumes in the sending tool and checks the canary is green first. Stopping is cheap; restarting should cost a decision.

Audit trail: every step writes a structured line to a dated run log, so 'what happened on Tuesday' has an answer that is not a Slack thread.

Who in your company acts when the model is uncertain, the API fails, or a customer needs a person?

**Alt text:** Seven-slide document: founders, API down overnight, who acts? Owners: kill switch before step one, retry then raise, abort on a repeated finding, release does not resume, a dated run log.

**Posting notes:** Format: document post (upload the PDF, 7 pages). Link: none. CTA: No CTA. Measure: impressions · saves · profile views at 48 h · inbound DMs.
