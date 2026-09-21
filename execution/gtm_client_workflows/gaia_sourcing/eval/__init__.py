"""
L14/L15 -- evaluation and outreach-outcome tracking (RADAR_CONTRACTS.md
section F).

`labels.py`    -- blind human ground truth (Label, cohen_kappa) against
                  which the pipeline's own grade/location extraction is
                  scored.
`scorecard.py` -- the six numbers that answer "should this pool ship, and
                  how much do we trust it" (stage `scorecard` in run.py).
`outcomes.py`  -- reply/conversation tracking per outreach template, used
                  to weight template rotation without ever rewriting a
                  template (.claude/rules/automation-boundaries.md).

No LLM call anywhere in this package (RADAR_CONTRACTS.md top rule): every
function here is deterministic Python over stage JSON, labels, and logged
outcomes.
"""
