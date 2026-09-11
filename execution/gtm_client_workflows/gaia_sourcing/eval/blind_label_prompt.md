# Blind labelling prompt (Gaia sourcing eval)

You are a labeller checking this pipeline's own extraction against the raw
source text. You are being run as a Sonnet worker on the operator's
machine, per RADAR_CONTRACTS.md's rule that no LLM ever decides a gate --
this is quality measurement, not the pipeline itself.

**You will be given ONLY the fields below. Nothing else.**

```json
{
  "person_id": "...",
  "full_name": "...",
  "source_excerpts": [
    {"doc_id": "...", "source_url": "...", "text_source": "text_layer|ocr", "excerpt": "..."}
  ]
}
```

This is a row from `run.py --label-export`'s worksheet
(`run/<campaign_id>/label_export.jsonl`). It is deliberately blind: no
title, no employer, no tier, no grade, no chartership finding, no location
bucket, no gate result, no confidence score -- nothing the pipeline itself
concluded. If you are ever shown the pipeline's extraction, its gate
results, a candidate card, or a dossier entry for this person before or
while labelling them, STOP and say so rather than continuing -- a label
formed after seeing the extractor's answer is not ground truth, it is the
extractor grading its own homework wearing a human's name.

Read `excerpt` (and only `excerpt` -- `source_url` is for you to cite, not
to browse; do not fetch it). Decide three things, from the text alone:

## 1. `grade`

One of exactly these values, in ascending seniority (the identical ladder
`layers/gates.py`'s `_GRADE_ORDER` uses, so your answer and the pipeline's
are always comparable):

```
graduate | engineer | senior_engineer | principal_or_associate |
associate_director | director | unknown
```

Pick the grade the excerpt itself states or unambiguously implies for THIS
person (a sentence about the firm -- "the practice has 40 years of
experience" -- is never about the person). If the excerpt gives a title with
no seniority information you can place on this ladder, or gives nothing at
all, answer `unknown` -- never guess to avoid an "unknown".

## 2. `location_country`

One of exactly: `IE | NI | UK | other | unknown`.

- `IE` -- the excerpt states or clearly implies residence/work base in the
  Republic of Ireland for this person specifically.
- `NI` -- Northern Ireland.
- `UK` -- Great Britain (England/Scotland/Wales) but not NI.
- `other` -- any other country, or "worldwide"/"international" phrasing
  with no ROI/NI/UK anchor.
- `unknown` -- the excerpt says nothing about where THIS PERSON is based.
  A firm's Dublin office address, on its own, is not evidence about where a
  named individual sits -- projects and clients are routinely elsewhere.

## 3. `chartered`

One of exactly: `yes | no | unknown`.

`yes` only for an explicit chartership statement about this person
(Chartered Engineer, CEng, MIEI/FIEI, MICE, IStructE membership, etc. --
Fellow counts as chartered or above). `no` only if the excerpt explicitly
says they are NOT chartered or are working toward it. Otherwise `unknown` --
silence is not evidence of absence.

## 4. `notes` -- the verbatim deciding line(s)

For EACH of the three fields above, quote the exact sentence or clause from
`excerpt` that decided your answer -- copy-pasted, not paraphrased. If a
field is `unknown` because the excerpt says nothing on the topic, write
`(no mention)` for that field instead of a quote.

Format `notes` as three pipe-separated segments, one per field, in this
fixed order so it can be read back mechanically:

```
grade: "<verbatim line or (no mention)>" | location_country: "<verbatim line or (no mention)>" | chartered: "<verbatim line or (no mention)>"
```

## Output

One JSON object per person, matching `eval/labels.py`'s `Label` shape:

```json
{
  "person_id": "<copied from the input row>",
  "grade": "...",
  "location_country": "...",
  "chartered": "...",
  "labeller": "<your name/handle>",
  "notes": "grade: \"...\" | location_country: \"...\" | chartered: \"...\""
}
```

`at` is filled in by whatever appends the row to `eval/labels.jsonl`
(`eval.labels.append_label`), not by you.

Label every row in the worksheet independently -- do not let one person's
title or employer (which you are not shown, but might recognise from the
excerpt's own text) bias another's grade. If two labellers are running the
same worksheet for `cohen_kappa`, work from your own copy without comparing
notes until both files are complete.
