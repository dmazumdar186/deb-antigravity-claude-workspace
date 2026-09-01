# Fuzzy Variables — LLM-woven personalization fields

Source: Nick Saraev, Claude Code Marketing course [3:11:12–4:06:22]; library
doc `docs/courses/claude_code_marketing_nick_saraev_2026-08.md` §1.7, §3–4.

## Goal

Upgrade mail-merge personalization from **hard variables** (raw data pasted
verbatim: first name, city) to **fuzzy variables**: an LLM turns the raw datum
into a short natural-language phrase woven into a human-written template, so
the email reads as originally written for that person.

## Inputs

- A **human-written** email template that already works. AI never authors the
  whole email — only the fuzzy slots.
- Slot markers: `{{longDescriptiveCamelCaseName}}`. The variable NAME is the
  generation instruction (e.g. `{{shortPlausibleReasonWhyTheySignedUp}}`,
  `{{thingInCommon}}`, `{{qualified<ICP>}}`), not a label for humans.
- Lead/subscriber data by **path** (CSV/Sheet — never attach large files, per
  `~/.claude/rules/no-large-file-attachments.md`).

## Tools / Scripts

This is a methodology directive — no paired `fuzzy_variables.py` by design;
runs compose existing rails per the model-tier rule (bulk pass =
`claude-sonnet-5`, rubric/template design = `claude-fable-5-1`).

- Per-row generation rails: `execution/personalization/ai_opener_generator.py`
  and `execution/personalization/variant_generator.py`.
  (`execution/modules/personalizers/` is currently empty — owed.)
- Output to Instantly (cold) via `execution/modules/outputs/`; warm sends via
  Gmail SMTP. (Course used Kit; we hold no Kit account.)

## Outputs

A NEW enriched file/sheet — never modify the source in place — containing all
original columns plus one column per fuzzy variable, appended in template
order, validated before delivery.

## Steps

1. Write/confirm the human template; mark fuzzy slots. Remove em dashes and
   AI-tells from the template (see `/humanizer`).
2. Spec the generation prompt with ALL of: read every row (no sampling); one
   value per slot per row; length caps (~10 words for reason-type, ~5 for
   paraphrase-type); row-to-row distinctness (vary sentence structure and word
   choice even when source data repeats — no shared lookup phrases); tone
   (casual, direct, first-person, slightly imperfect); create a new artifact.
3. Test on ≤5 sample rows first. If demo/hypothetical leads, say so explicitly
   so the model does not live-research them.
4. Review generated values for length/naturalness; iterate the caps.
5. Run the full pass (execution tier), validate (see gate below), deliver.
6. Preview merge rendering in the sending platform on ≥2 real records before
   any send.

## Edge Cases

- **Compliance**: numeric performance claims in cold templates must be backed
  by real case studies — unsubstantiated numbers risk sending-account
  suspension and deceptive-claims exposure. Treat a model's compliance flag as
  a blocker, not noise.
- **Proportion rule**: the fewer AI-generated words as a share of the email,
  the less it reads as AI. If a fuzzy value keeps growing, shrink the slot.
- **Never test with fake data against real subscriber addresses** —
  deliverability damage. Use isolated test inboxes.
- **Output-acceptance gate** (per `~/.claude/rules/output-acceptance-gate.md`):
  hard-fail on empty/placeholder slot values, language mismatch, length-cap
  violations, and duplicate phrasing across rows (n-gram overlap check).
- Data used for personalization goes into the send itself only — do not
  publish scraped personal detail anywhere else.
