# G-Eval — captured evidence

**Run:** 2026-07-27, live URL `https://agentup-iag.pages.dev`, `--n 3`.

## Consistency (3 runs of the SAME A+ transcript through the scoring model)

Low variance across dimensions demonstrates the LLM-as-judge is stable — it is not the source of scoring noise.

```
[1/2] Score consistency (N=3 runs on A+ transcript)
  successful runs: 3 / 3
    overall          mean= 97.3  stdev= 2.31  range=  4   [ OK ]
    empathy          mean= 95.0  stdev= 5.00  range= 10   [ OK ]
    accuracy         mean= 98.3  stdev= 2.89  range=  5   [ OK ]
    resolution       mean= 98.3  stdev= 2.89  range=  5   [ OK ]
    professionalism  mean= 98.3  stdev= 2.89  range=  5   [ OK ]
```

**Reading:** with a 10-point stdev cap (looser than the mean ±5 the model actually delivered), all four rubric dimensions and the overall score pass. Empathy shows the widest range (10 points) — expected for the most subjective dimension.

## Discrimination — golden A+ vs golden fail transcripts (partial evidence)

**Ad-hoc verification via `curl`** — the fail transcript (dismissive agent, no resolution, unprofessional tone) scored:

```
{"empathyScore":10,"accuracyScore":10,"resolutionScore":5,"professionalismScore":5,
 "overallScore":7,
 "strength":"The agent was quick to respond to the customer's initial query.",
 "improvement":"The agent needs significant training in customer service fundamentals,
                including empathetic communication, accurate information, and proper
                call handling procedures.",
 "perTurnNotes":[
   {"agentTurnIndex":0,"dimension":"professionalism","sentiment":"weak",
    "note":"Informal language, abbreviations, and dismissive tone are unprofessional."},
   {"agentTurnIndex":1,"dimension":"resolution","sentiment":"weak",
    "note":"No attempt to understand or resolve the issue, or provide alternatives."},
   {"agentTurnIndex":2,"dimension":"resolution","sentiment":"weak",
    "note":"Refusal to transfer and vague instruction is unhelpful and unprofessional."}
 ]}
```

Fail overall = **7/100**. A+ overall (from consistency mean above) = **97.3/100**. Discrimination gap = **90 points**. Rubric is working.

Also: `perTurnNotes[]` are populated with the correct `agentTurnIndex` mapping, `dimension` labels, `sentiment: "weak"`, and specific, actionable notes — exactly what the rubric-anchored transcript UI needs.

## Honest gap

The `g_eval_scoring.py --n 3` **discrimination** run against the live URL did not complete this session because Gemini 2.5-flash-lite / 2.5-flash both hit their **free-tier daily quota** (250 requests / project / day) after all today's dev traffic + negative-battery + front-door × 5 + consistency × 3.

To re-run cleanly: wait for the Gemini quota to reset (~24h UTC rollover) OR add a paid billing account on Google AI Studio to lift the free-tier cap. The harness itself is correct and its consistency segment ran green.
