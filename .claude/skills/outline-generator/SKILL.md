---
name: outline-generator
description: Generate structured YouTube course outlines (title options, scripted hooks, wow moments, detailed section breakdowns) from an idea + research context. Triggers on "outline", "course outline", "plan a course", or /outline-generator.
allowed-tools: Read, Grep, Glob, Bash, Write, Edit, Task
---
> **Demo Library Skill** — This skill is from a demo library. Some configuration values use placeholders (e.g. `{{USER_NAME}}`, `{{COMMUNITY_ID}}`). If something doesn't work, check for placeholder values and replace them with your own information first.

# Outline Generator — YouTube Course Pipeline

Generate production-ready course outlines for 2-3 hour longform YouTube videos. Output matches Debanjan Mazumdar's proven course structure (see reference: `active/youtube-strategy/outlines/ai-agents-prompting-course-2026.md`).

## When to Use

- User has a course idea / keyword they want to cover
- User provides research, notes, or raw material to turn into a structured outline
- User says "outline", "course outline", "plan a course", or invokes `/outline-generator`

## Inputs

The user provides some combination of:
1. **Topic / keyword** — what the course is about (e.g., "n8n advanced automations", "Claude Code from zero")
2. **Packaging context** — target audience, angle, positioning vs competitors
3. **Raw research / notes** — bullet points, links, techniques, anything they've collected
4. **Reference outlines** — existing outlines to match in depth/style (optional)

If inputs are sparse, ask the user to provide more before proceeding. Don't generate from thin air.

## Workflow

### Step 1: X Research (if topic warrants it)

Run 3-5 targeted queries via the x-search skill to find cutting-edge discussions, real practitioner techniques, and accounts worth citing. This adds genuine value that Debanjan Mazumdar can't get from their own knowledge alone.

```bash
# Broad mode first to map the landscape
.venv/bin/python .claude/skills/outline-generator/x_search_research.py broad -q "What are the most discussed [TOPIC] techniques on X right now? Include specific accounts and posts."

# Then deep mode for actual tweets with citations
.venv/bin/python .claude/skills/outline-generator/x_search_research.py deep -q "[TOPIC] advanced techniques OR strategies" --from-date [30 days ago]
```

Compile the best findings — real techniques people are using, accounts to credit, novel approaches Debanjan Mazumdar hasn't covered yet.

### Step 2: Generate the Outline

Combine all inputs (user's idea, packaging, raw research, X research) into a structured outline. The outline MUST follow this exact structure:

---

#### Header
```markdown
# [Course Title]: [Subtitle]

Google Doc: (left blank — filled after export)
```

#### Title Options
Exactly 3 title options. Each must:
- Include the primary keyword naturally
- Include "(Full Course)" or "(Full Course 2026)" for search
- Be under 65 characters
- Be formatted for YouTube SEO (keyword-first when possible)

```markdown
## Title Options

- [Keyword]: [Value Prop] (Full Course 2026)
- [Keyword]: [Angle] (Full Course)
- [Keyword] Full Course: [Hook]
```

#### Hook (scripted)
A fully scripted 60-90 second intro Debanjan Mazumdar reads verbatim. Structure:

1. **Opening line** — what this video is about (1 sentence)
2. **Credibility** — why Debanjan Mazumdar is qualified (business results, student count, real usage)
3. **Positioning** — what level this is, what prerequisites exist
4. **Wow moment tease** — "First, I'll show you something cool in under two minutes..." + describe the wow moment
5. **Section preview** — rapid-fire list of every major technique/section (1 sentence each, make them sound compelling)
6. **Transition** — "Let's not waste any time, here we go."

The hook must name-drop specific, concrete things (not vague promises). Each technique preview should make the viewer think "I need to know how to do that."

```markdown
## Hook (scripted)

[Full scripted text here — Debanjan Mazumdar reads this verbatim on camera]
```

#### Section 0: The Wow Moment
Something visually impressive that happens in the first 2-3 minutes. Must be:
- **Visually striking** — multiple things happening at once, or a dramatic before/after
- **Fast** — complete in under 2 minutes of screen time
- **Real** — actually works, not faked or simulated
- **Relevant** — uses techniques from the course (demonstrates the ceiling)

```markdown
# 0. The wow moment — [short description]

[2-3 sentences describing what the viewer sees]

[1 sentence on why this matters / what it demonstrates]

Demo setup: [Exact steps to reproduce this demo. What to pre-configure, what tools are needed, what can go wrong.]

Links:
- [Relevant tool/doc]: [URL]
```

#### Numbered Sections (the course body)
Each section follows this template. Aim for 8-14 sections total depending on course depth.

```markdown
# [N]. [Section type]: [Title]

[1-2 sentence summary of what this section covers and why it matters]

**How it works:** [Detailed explanation. Be specific — include code snippets, configuration examples, or step-by-step breakdowns where relevant. This is Debanjan Mazumdar's reference for what to say on camera.]

**Demo:** [Exactly what to show on screen. What to set up beforehand, what the viewer sees step by step, what the expected result is. Be specific enough that Debanjan Mazumdar can reproduce this without thinking.]

**Show the prompt:** [If applicable — the exact prompt, CLAUDE.md block, or configuration. Walk through why each piece is worded the way it is.]

**When to use it:** [1-2 sentences on when this technique is valuable and when it's overkill.]

Sources: [X accounts, blog posts, original discoverers — credit where due]

Links:
- [Resource name]: [URL]
```

Not every section needs all fields. Use judgment:
- Tutorial/technique sections: all fields
- Comparison sections: use a table format instead of demo/prompt
- Strategy/business sections: skip "show the prompt", focus on real numbers and examples
- Intro/context sections: keep short (2-3 min of recording time), skip demo

#### Closing Section: What to Build Next
5 project ideas ranked by difficulty, each referencing techniques from the course. Point to {{COMMUNITY_NAME}}.

```markdown
# [N]. What to build next

[5 numbered project ideas, each with:]
1. **[Project name]** (Techniques [X] + [Y]) — [1-2 sentence description]

Point viewers to {{COMMUNITY_NAME}} for guided builds and community support.

Links:
- {{COMMUNITY_NAME}}: https://www.skool.com/{{COMMUNITY_SLUG}}
- [Other relevant links]
```

---

### Step 3: Present to User

Output the full outline in a single markdown block. Tell the user:
- Estimated recording time based on section count (~8-12 min per technique section, ~3-5 min for intro/closing sections)
- Which sections need the most demo prep
- Any gaps or sections that need more research

### Step 4: User Adjustments

The user reviews and makes changes. Incorporate feedback, add/remove sections, adjust depth.

### Step 5: Diagram Generation (separate step, after outline is finalized)

After the outline is locked, generate 1-2 diagrams per section using the diagram-generator skill. Diagrams should:
- Visualize the core concept of each section (architecture, flow, comparison)
- Use the hand-drawn whiteboard aesthetic
- Be 16:9 aspect ratio for YouTube

```bash
python3 .claude/skills/outline-generator/generate_diagram.py "[description]" --aspect 16:9
```

### Step 6: Google Doc Export (separate step)

Compile the final outline + diagrams into a Google Doc for recording reference:

```bash
python3 .claude/skills/outline-generator/md_to_gdoc.py "active/youtube-strategy/outlines/OUTLINE.md" --title "Course Title — Outline"
```

Uses `gws` CLI under the hood (no Python Google API dependencies needed).

## Quality Checks

Before presenting the outline:

- [ ] Every section has a clear demo that Debanjan Mazumdar can actually execute
- [ ] Links are real and current (not hallucinated)
- [ ] Sources credit real people / accounts (verify via X research)
- [ ] Hook previews every major section (nothing left out)
- [ ] Title options include the primary keyword
- [ ] Wow moment is genuinely impressive and takes < 2 minutes
- [ ] Total section count supports 2-3 hours of content (~10-14 sections)
- [ ] No section is too vague to record from — Debanjan Mazumdar should be able to sit down and talk through each one without additional research

## Output Location

Save outlines to: `active/youtube-strategy/outlines/[slug].md`

## Cost

- X research: ~$0.10-0.30 (3-5 queries across broad + deep)
- Diagrams: ~$0.02-0.05 each (generated separately in Step 5)
- Total per outline: ~$0.30-0.80
