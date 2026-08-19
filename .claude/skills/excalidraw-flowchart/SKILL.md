---
name: excalidraw-flowchart
description: Generate Excalidraw flowcharts from process descriptions or Upwork job postings. Use when user asks for diagrams, flowcharts, or pastes job descriptions needing visual documentation.
allowed-tools: Read, Grep, Glob, Bash, Write
---
> **Demo Library Skill** — This skill is from a demo library. Some configuration values use placeholders (e.g. `{{USER_NAME}}`, `{{COMMUNITY_ID}}`). If something doesn't work, check for placeholder values and replace them with your own information first.

# Excalidraw Flowchart Generator

Create professional flowcharts as `.excalidraw` JSON files from natural language descriptions or job postings.

## When to Use

- User asks for a flowchart or diagram
- User pastes an Upwork job description that describes a process/workflow
- User wants to visualize decision trees, pipelines, or system architecture
- User mentions "excalidraw" or "flow diagram"

## Tool

Uses `@swiftlysingh/excalidraw-cli` via npx (no installation required):

```bash
npx @swiftlysingh/excalidraw-cli create --inline "DSL" -o output.excalidraw
```

## DSL Syntax Reference

| Syntax | Element | Use For |
|--------|---------|---------|
| `[Label]` | Rectangle | Process steps, actions |
| `{Label?}` | Diamond | Decisions, conditionals |
| `(Label)` | Ellipse | Start/End points |
| `[[Label]]` | Database | Data storage |
| `->` | Arrow | Connections |
| `-> "text" ->` | Labeled Arrow | Connections with labels |
| `-->` | Dashed Arrow | Optional/alternative paths |

### Directives

| Directive | Description | Example |
|-----------|-------------|---------|
| `@direction` | Flow direction (TB, BT, LR, RL) | `@direction LR` |
| `@spacing` | Node spacing in pixels | `@spacing 60` |

## Interpreting Job Descriptions

When given an Upwork job posting or vague process description:

### Step 1: Extract the Core Process

Look for:
- **Trigger/Input**: What starts the process? (webhook, user action, scheduled task)
- **Steps**: What actions happen in sequence?
- **Decisions**: Where are there conditionals or branches?
- **Loops**: What might repeat until a condition is met?
- **Output/End**: What's the final deliverable or state?

### Step 2: Identify Implicit Logic

Job descriptions often omit obvious steps. Infer:
- Validation steps (check if data exists, is valid)
- Error handling branches (what if X fails?)
- Retry logic (especially for API calls, scraping)
- Data transformation steps (parse, format, enrich)

### Step 3: Normalize Node Labels

Keep labels:
- Short (2-5 words)
- Action-oriented (verb + noun)
- Consistent in tense (imperative: "Fetch Data" not "Fetches Data")

### Common Patterns

**API Integration:**
```
(Start) -> [Receive Request] -> {Valid?}
{Valid?} -> "no" -> [Return Error] -> (End)
{Valid?} -> "yes" -> [Call External API] -> {Success?}
{Success?} -> "no" -> [Log Failure] -> (End)
{Success?} -> "yes" -> [Process Response] -> [Return Data] -> (End)
```

**Data Pipeline:**
```
(Trigger) -> [Fetch Raw Data] -> [Clean/Validate] -> {Quality Check?}
{Quality Check?} -> "fail" -> [Flag for Review] -> (End)
{Quality Check?} -> "pass" -> [Transform] -> [Load to Destination] -> (End)
```

**Scraping with Retry:**
```
(Start) -> [Set Filters] -> [Run Scraper] -> {Target Met?}
{Target Met?} -> "yes" -> [Export Results] -> (End)
{Target Met?} -> "no" -> [Adjust Parameters] -> [Run Scraper]
```

**Approval Workflow:**
```
(Submit) -> [Initial Review] -> {Approved?}
{Approved?} -> "no" -> [Request Changes] -> (Submit)
{Approved?} -> "yes" -> [Final Review] -> {Final Approved?}
{Final Approved?} -> "no" -> [Escalate] -> (Manual)
{Final Approved?} -> "yes" -> [Deploy] -> (Done)
```

## Execution

1. Parse the input (job description or explicit process)
2. Extract/infer the logical flow
3. Write DSL matching the structure
4. Generate file:

```bash
npx @swiftlysingh/excalidraw-cli create --inline "$(cat <<'EOF'
@direction TB
@spacing 60

(Start) -> [Step 1] -> {Decision?}
{Decision?} -> "yes" -> [Step 2] -> (End)
{Decision?} -> "no" -> [Step 3] -> [Step 1]
EOF
)" -o active/flowchart_name.excalidraw
```

5. Output goes to `active/` (intermediate file)
6. Inform user of file location and how to open (excalidraw.com)

## Output Format

Always output as `.excalidraw` JSON file. This is the native Excalidraw format and can be:
- Opened at https://excalidraw.com via File > Open
- Edited further in Excalidraw
- Exported to PNG/SVG from Excalidraw

## Reasoning Process: How to Extract Logic

When reading a job description, follow this mental model:

### 1. Identify the User Journey

Ask: "What does the user DO, step by step?" Map the happy path first.

### 2. Find Decision Points

Look for words/phrases that imply branching:
- "if", "when", "depending on", "based on"
- Multiple options (download OR email, approve OR reject)
- Validation (must be valid, check if, verify)
- Success/failure states (API calls, scraping, processing)

### 3. Find Loops

Look for:
- Retry logic ("try again", "until successful")
- Validation loops ("fix errors and resubmit")
- Iterative processes ("for each item", "batch processing")

### 4. Infer Missing Steps

Job descriptions skip "obvious" things. Always add:
- **Auth check** if roles/permissions mentioned
- **Validation** before any processing
- **Error handling** for external calls (APIs, scraping, email)
- **Storage/logging** if audit or history mentioned
- **Confirmation/completion** states

### 5. Name Nodes Consistently

| Type | Format | Examples |
|------|--------|----------|
| Start/End | Noun or state | `(User Login)`, `(Done)`, `(Error)` |
| Process | Verb + Object | `[Generate Report]`, `[Send Email]` |
| Decision | Short question | `{Valid?}`, `{Approved?}`, `{E-Sign?}` |
| Database | Data description | `[[User Records]]`, `[[Audit Log]]` |

---

## Complete Worked Example

### Input: Upwork Job Description

> **Summary:** I need a Python Developer to help me build a secure document-automation web app for my law firm that generates client-ready legal documents from structured intake data. The app should let staff (admin/paralegal/attorney roles) select a document template (Word/PDF), answer an intake questionnaire (dynamic fields), and instantly produce a correctly formatted document with our letterhead, signature blocks, and county/case captions where applicable.
>
> **Key features:**
> - Template library (upload/manage DOCX templates with merge fields)
> - Intake forms mapped to each template (conditional logic + validations)
> - One-click document generation to DOCX and/or PDF
> - Client/matter database (store inputs, reuse data across documents)
> - E-sign integration hooks (DocuSign or similar) and email delivery
> - Audit log (who generated what, when), versioning, and secure storage
> - Permissions (Admin/Attorney/Staff) and client data encryption
> - Branding controls (firm info, letterhead, footer, formatting consistency)

### Step 1: Extract User Journey (Happy Path)

Reading the description, the main user flow is:
1. Staff member logs in
2. Select or create a client/matter
3. Pick a document template
4. Fill out intake questionnaire
5. Generate document with branding
6. Deliver (download, email, or e-sign)

### Step 2: Identify Decision Points

From the description:
- **Permissions** -> need auth check (authorized or not)
- **Client/matter database** -> existing matter or new?
- **Conditional logic + validations** -> form valid or not?
- **E-sign integration hooks... and email delivery** -> multiple delivery options
- **DOCX and/or PDF** -> format choice (but can simplify to one decision)

### Step 3: Identify Loops

- **Validations** on intake form -> user must fix errors and retry

### Step 4: Infer Missing Steps

Not explicitly stated but required:
- Loading saved data when selecting existing matter
- Applying branding as a distinct step
- Saving to audit log before delivery
- Storing signed document after e-sign completes

### Step 5: Build the DSL

Map each element:

| Extracted Concept | DSL Element |
|-------------------|-------------|
| Staff logs in | `(Staff Login)` |
| Check permissions | `{Authorized?}` |
| Access denied | `[Access Denied] -> (End)` |
| Select client/matter | `[Select Client/Matter]` |
| Existing or new | `{Existing?}` |
| Create new matter | `[Create New Matter]` |
| Load saved data | `[Load Saved Data]` |
| Select template | `[Select Template]` |
| Show intake form | `[Display Intake Form]` |
| Fill questionnaire | `[Fill Questionnaire]` |
| Validation check | `{Valid?}` |
| Show errors (loop back) | `[Show Validation Errors] -> [Fill Questionnaire]` |
| Generate document | `[Generate Document]` |
| Apply branding | `[Apply Branding]` |
| Save + audit | `[Save + Audit Log]` |
| E-sign decision | `{E-Sign?}` |
| DocuSign flow | `[Send to DocuSign] -> [Await Signature] -> [[Store Signed Doc]]` |
| Delivery choice | `{Delivery?}` |
| Download | `[Download DOCX/PDF]` |
| Email | `[Email to Client]` |

### Final DSL

```
@direction TB
@spacing 60

(Staff Login) -> {Authorized?}
{Authorized?} -> "no" -> [Access Denied] -> (End)
{Authorized?} -> "yes" -> [Select Client/Matter] -> {Existing?}
{Existing?} -> "no" -> [Create New Matter] -> [Select Template]
{Existing?} -> "yes" -> [Load Saved Data] -> [Select Template]
[Select Template] -> [Display Intake Form] -> [Fill Questionnaire] -> {Valid?}
{Valid?} -> "no" -> [Show Validation Errors] -> [Fill Questionnaire]
{Valid?} -> "yes" -> [Generate Document] -> [Apply Branding] -> [Save + Audit Log] -> {E-Sign?}
{E-Sign?} -> "yes" -> [Send to DocuSign] -> [Await Signature] -> [[Store Signed Doc]] -> (Done)
{E-Sign?} -> "no" -> {Delivery?}
{Delivery?} -> "download" -> [Download DOCX/PDF] -> (Done)
{Delivery?} -> "email" -> [Email to Client] -> (Done)
```

### Execution Command

```bash
npx @swiftlysingh/excalidraw-cli create --inline "$(cat <<'EOF'
@direction TB
@spacing 60

(Staff Login) -> {Authorized?}
{Authorized?} -> "no" -> [Access Denied] -> (End)
{Authorized?} -> "yes" -> [Select Client/Matter] -> {Existing?}
{Existing?} -> "no" -> [Create New Matter] -> [Select Template]
{Existing?} -> "yes" -> [Load Saved Data] -> [Select Template]
[Select Template] -> [Display Intake Form] -> [Fill Questionnaire] -> {Valid?}
{Valid?} -> "no" -> [Show Validation Errors] -> [Fill Questionnaire]
{Valid?} -> "yes" -> [Generate Document] -> [Apply Branding] -> [Save + Audit Log] -> {E-Sign?}
{E-Sign?} -> "yes" -> [Send to DocuSign] -> [Await Signature] -> [[Store Signed Doc]] -> (Done)
{E-Sign?} -> "no" -> {Delivery?}
{Delivery?} -> "download" -> [Download DOCX/PDF] -> (Done)
{Delivery?} -> "email" -> [Email to Client] -> (Done)
EOF
)" -o active/legal_doc_automation.excalidraw
```

### Output Summary to User

After generating, tell the user:
1. File location: `active/legal_doc_automation.excalidraw`
2. How to open: https://excalidraw.com -> File -> Open
3. Brief table of extracted logic (what was interpreted from their description)

---

## Quick Example: Simple Automation

**Input:**
> "Need automation that monitors a Slack channel for new messages containing URLs. When found, scrape the URL content, summarize with GPT, and post summary back to thread."

**Reasoning:**
- Trigger: New Slack message
- Decision: Contains URL? (implied by "containing URLs")
- Process: Scrape -> Summarize -> Post
- Inferred: Error handling for failed scrapes

**DSL:**
```
@direction TB
@spacing 60

(New Slack Message) -> {Contains URL?}
{Contains URL?} -> "no" -> (Ignore)
{Contains URL?} -> "yes" -> [Scrape URL Content] -> {Scrape OK?}
{Scrape OK?} -> "no" -> [Log Error] -> (End)
{Scrape OK?} -> "yes" -> [Summarize with GPT] -> [Post to Thread] -> (Done)
```

---

## File Naming Convention

Use descriptive snake_case names based on the project:
- `legal_doc_automation.excalidraw`
- `slack_url_summarizer.excalidraw`
- `lead_scraping_pipeline.excalidraw`

All outputs go to `active/` directory.
