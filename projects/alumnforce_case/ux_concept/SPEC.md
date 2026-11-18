# Trusted Segments: UX concept spec (follow-up for Frédéric Blanc, CEO, after the 18 Nov case presentation)

## Why this exists
After the case presentation, Frédéric asked for two things:
1. See on the UI how Trusted Segments would look: the normalised columns, and how it shows to admins.
2. He pushed back on keeping the normalised (`*_norm`) columns invisible to admins: they would help admins.

Our position (amended, not folded): **he is right, and the deck's design already needs an admin-facing surface** because it
promises "reference tables with per-tenant overrides" (deck slide 6, Annex C), and an override needs a screen. The
two new date filters do a different job (freshness, i.e. *is this still true?*) from the normalised columns
(consistency, i.e. *is this written the same way?*). So the concept makes the cleaned values visible everywhere an
admin reads or filters data, with three guard rails:
- the member's original entry is always shown next to the cleaned value and is never overwritten;
- low-confidence cleanings (for example a country inferred from the city) are marked "suggested" until an admin confirms;
- every admin change is a per-school override, logged, reversible, and never edits the member's profile.

## Deliverable
A self-contained, clickable HTML prototype at `projects/alumnforce_case/ux_concept/index.html` (one file, inline CSS/JS,
no external requests except optionally Google Fonts; must work offline from `file://`), plus `data.js` if you prefer to
keep data separate (then also local). Desktop-first at 1440×900; must not break at 1280×720.

Not AlumnForce's real brand: no logo, no copied artwork. A neutral, credible SaaS back-office look (left nav, top bar),
labelled "Concept · Trusted Segments" in the top bar. Calm, data-dense, professional. Load and follow the workspace
`impeccable` / `hallmark` design guidance if available (`.claude/skills/impeccable/SKILL.md`, `.claude/skills/hallmark/SKILL.md`).

### Language
UI strings in **French by default** with an **FR / EN toggle** in the top bar (one dictionary object). Annotations
(see below) are **English** in both modes. Label words:
- Current / To confirm / To reactivate → FR: À jour / À confirmer / À réactiver (mark in the annotation that final FR
  strings are decided with CS in week 1).
- Trusted Segments stays as the feature name. Never use the words "chat", "grade", "stale" anywhere.

### Annotation layer (key requirement)
A toggle "Annotations" (on by default). When on, numbered pins (①②③…) sit on the key UI elements, and a right-hand
panel lists each pin: **What it is** (one line), **Why** (one or two lines, plain English), and **Deck ref** (e.g.
"Slide 6, D1"). Clicking a pin or list item highlights the element. Every screen has its own pins.

### Guided tour
A "Tour" button opens a stepper (Prev / Next, step x/N) that switches screens, highlights one element with a ring,
and shows a caption card (title + 2–3 sentence explanation). 12–14 steps covering the story below. Expose
`window.tour = {go(n), next(), count}` so a script can drive it, and add `?tour=1&step=N` URL support.

## Data (ground truth: `projects/alumnforce_case/annexB_result.csv`, 49 rows)
This is the brief's own example list: "finance in London for 3+ years" after the full logic (Annex B). Columns:
`member_id, poste (job), entreprise (employer, 8 blank), finance_src (finance:declared 24 / employer 17 / title 8),
ville (8 London spellings), pays (UK 13 / Royaume-Uni 13 / United Kingdom 14 / blank 9), date_debut_poste,
date_maj_profil, derniere_connexion, cotisant (oui 14 / non 35), reliability (A=Current 1, B=To confirm 5, C=To reactivate 43)`.
Embed all 49 rows (read the CSV and convert; do not invent rows). There are **no names** in the file: display
"Member M0502" etc. and say in an annotation that names are hidden in this concept (privacy) and the real product shows
the member's name as today.

Derived cleaned values (deterministic, compute in the build script or hardcode from the CSV):
- `ville_norm`: all 8 spellings → "London". Exact counts in this list: Londres (Royaume-Uni) 10, london 9, London, UK 6,
  LONDON 6, Greater London 6, Londres 5, London - Canary Wharf 4, London 3.
- `pays_norm`: UK / Royaume-Uni / United Kingdom → "United Kingdom" (status *auto*); blank → "United Kingdom"
  with status **suggested · inferred from city** (needs confirmation).
- Finance signal shown as a chip: Declared / From employer / From job title.
- Reliability label from A/B/C. Reference date for "x years ago": **12 Oct 2026** (the case's reference date).
  Rule (shown in an annotation): Current = profile updated < 2 years ago or login < 1 year; To confirm = updated
  2–4 years ago; To reactivate = older or no date; future dates ignored. Thresholds are per-school settings.
Do not fabricate any other statistic. Any illustrative number not from the CSV must be labelled "illustrative".

## Screens (left nav items)

### 1. Lists → New list (the segmenter, flags ON)
- **Sentence box** at the top (feature `nl_targeting`): placeholder "Décrivez votre cible…". Pre-typed example
  available: "Diplômés qui travaillent dans la finance à Londres depuis plus de 3 ans". Pressing "Fill in filters"
  shows a short simulated pre-flight → "AI translated" → "Checked" sequence (no real AI), then pre-fills the filters,
  with the admin's sentence shown next to the filters (diff view) and an "unmapped part" line (empty here).
  Annotation: only the sentence and filter names go to the model, never a member.
- **Filters panel** (existing segmenter look, AND between filters):
  - City (workplace): value "London" with a badge "cleaned · groups 8 spellings" and an expander listing the 8
    original spellings with their counts. This is the key answer to Frédéric.
  - Sector (current job): Finance, with a note "also matched from employer (17) and job title (8)".
  - Job start date: before 12 Oct 2023 (3+ years).
  - New group "Reliability" with the two **new date filters**: "Last profile update" and "Last login" (empty by default),
    tagged NEW. Annotation: recorded automatically by the platform, never typed by anyone; reuse the existing date filter.
- **Results header**: "49 members" and three clickable label chips: À jour 1 · À confirmer 5 · À réactiver 43; clicking
  filters the table.
- **Results table** columns: Member · Job · Employer · City (cleaned, with original in small grey under it: "as typed:
  Londres (Royaume-Uni)") · Country (cleaned; "suggested" badge for the 9 inferred) · Finance signal chip · Last profile
  update ("4 y ago" + date) · Last login · Label · Dues member (yes/no).
  A switch above the table: "Show original values" (on by default). Off = cleaned only.
- **Actions bar**: "Send to À jour + À confirmer (6)", "Reactivate 43 members" (opens a modal preview of the existing
  Profile Update Campaign, pre-filled, school-written text, two variants A/B), "Save list" (saved name
  "Finance · London · 3+ yrs", description = the sentence, "Computed on 12/10/2026 · relative dates recalculated when
  opened or sent"), "Export" (modal: columns cleaned / original / both).

### 2. Data quality → Cleaned values (the admin-visible normalised columns)
Tabs: City · Country · Sector from employer.
- City tab table: Original value | Cleaned value | Members (in this list) | Source (Global table / Your override) |
  Status (Auto / Confirmed by you / Suggested) | Action (Confirm · Change · Not this place).
  Rows = the 8 London spellings with counts. "Change" opens an inline edit that creates a school override
  (show a toast "Override saved for your school. The member's entry is unchanged.").
- Country tab: UK 13, Royaume-Uni 13, United Kingdom 14 → United Kingdom (Auto); (blank) 9 → United Kingdom
  (Suggested · inferred from city) with a bulk "Confirm 9".
- Sector-from-employer tab: employers in the list mapped to Finance with member counts (Amundi 5, Morgan Stanley 4,
  Barclays 4, Rothschild & Co 3, Crédit Agricole CIB 3, Société Générale 3, Goldman Sachs 3, … compute all from the
  CSV; "(no employer) 8" shown as "not mapped").
- A banner: "Cleaned values are used for lists and counts. What members typed is never changed."
- A small summary card: "8 spellings → 1 city · 3 country spellings + 9 blanks → 1 country".

### 3. Member record (admin view)
Pick a member from the table (default M0495). Two columns: "As entered by the member" vs "Cleaned (used for lists)"
for City, Country, Sector, Employer. A Reliability card: last profile update, last login, label, the reason in words
("Profile updated 20 May 2023, 3 years ago → À confirmer"). A preview box "What the member sees on their profile":
"Profile last updated 3 years ago · Confirm / Correct" (no label word shown to members).

### 4. Settings → Features (flags)
Two switches per school: `reliability` and `nl_targeting`, both described in plain words with a list of what
appears/disappears. Toggling them live hides/shows the corresponding elements across the prototype (sentence box,
label chips, the two new filters, label column, Data quality page). With both off, the segmenter looks like today:
annotate "flag off = today's segmenter, unchanged".

### 5. "Why visible" panel (reachable from the top bar, and the last tour step)
A short design-decision card, plain English:
- Your point: cleaned values help admins. **Adopted.** Admins filter by one clean city, see what was grouped, fix it.
- What the two new date filters do: freshness (is this still true?). Cleaned columns do consistency (is it written the
  same way?). Both are needed; neither replaces the other.
- Guard rails: original always visible; suggestions need confirmation; overrides per school, logged, reversible;
  the member's profile is never edited.
- Cost: no extra build. The override screen was already in D1's "reference tables with per-tenant overrides"; this
  makes it the admin's view. (Do not state dev-week numbers.)

## Quality bar
- No console errors; every button does something or shows a "concept" tooltip.
- Text contrast WCAG AA; tables readable; nothing overflows at 1280×720.
- No real AlumnForce logo or brand assets. No names. No claims about AlumnForce internals beyond the deck.
- `<meta name="robots" content="noindex">`.
