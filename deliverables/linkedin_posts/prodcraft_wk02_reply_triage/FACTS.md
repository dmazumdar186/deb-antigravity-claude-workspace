# Fact sheet: ProdCraft weekly notes wk 02 film ("32 inboxes, 800 sends. Who replied?")

Every word or number on screen must trace to a row here. Two kinds of source: **code** (verifiable in this repo) and **operator** (Debanjan's own post copy, about a client system whose code is not in this repo). Code beats operator when they differ.

| id | Fact | Value | Source |
|---|---|---|---|
| F01 | Inboxes | 32 | operator post wk 02 |
| F02 | Sends per day (target) | 800 | operator post wk 02 |
| F03 | Sends per month | around 24,000 | operator post wk 02 and wk 01 |
| F04 | Reply kinds named in the post | out of office · unsubscribe · no · interested, wants to speak · a question that needs a proper answer | operator post wk 02 |
| F05 | The bottleneck line | "the bottleneck has simply moved from sending to reading" | operator post wk 02 |
| F06 | Classifier classes | hot · positive · neutral · negative · auto_reply_or_OOO | code: `execution/personal_workflows/self_outbound_system/reply_classifier.py` docstring line 3 |
| F07 | Deterministic layer runs first | "Deterministic layer FIRST" | code: reply_classifier.py line 98 (comment; only these four words may be quoted) |
| F08 | OOO rule result | class `auto_reply_or_OOO`, confidence 0.99, explanation "deterministic OOO pattern matched", cost_eur_estimate 0.0 | code: reply_classifier.py lines 99–107 |
| F09 | Stop / unsubscribe rule result | class `negative`, confidence 0.99, explanation "deterministic stop/unsubscribe pattern matched", cost 0.0 | code: reply_classifier.py lines 109–117 |
| F10 | Meeting / phone rule result | class `hot`, confidence 0.90, explanation "deterministic phone / meeting-request pattern matched", cost 0.0 | code: reply_classifier.py lines 119–131 |
| F11 | Example OOO patterns (verbatim regex intent) | "out of office", "on vacation", "automatic reply", "will return", "en congés", "réponse automatique" | code: `_OOO_PATTERNS` lines 42–54 |
| F12 | Example stop patterns | "unsubscribe", "remove me", "stop emailing", "do not contact", "désinscrire" | code: `_STOP_PATTERNS` lines 56–65 |
| F13 | Example hot patterns | "call me at", "ready to start", "can we jump on a call" | code: `_HOT_PATTERNS` lines 67–73 |
| F14 | Card subhead | "An out-of-office match returns confidence 0.99 at €0.00. No model is called." | wk 02 card (operator) |
| F15 | Routing claim | the obvious replies are handled automatically; the potentially valuable ones go to the right person, with the context needed to follow up | operator post wk 02 (client system, not in repo) |
| F16 | CRM claim | the CRM gets updated, so the conversation doesn't disappear into someone's inbox | operator post wk 02 (client system, not in repo) |
| F17 | Principle | "I don't need AI to recognise one. A simple rule catches it." | operator post wk 02 |
| F18 | The real target | 30–60 positive conversations a month, with booked calls tracked in the CRM | operator post wk 02 |
| F19 | The reframe | "the target was never 800 sends a day for its own sake" | operator post wk 02 |
| F20 | Series frame | ProdCraft · weekly notes · wk 02 · page 02 | wk 02 card |
| F21 | Code snippet shown (must be byte-identical to the file) | reply_classifier.py lines 99–107 (line 98 is a comment carrying the unmeasured "~95%" and is never shown) | code |

## Hard rules

- **Illustrative replies only.** Any reply text shown on screen is invented, generic, contains no names, companies, e-mail addresses or phone numbers, and is labelled once as "illustrative replies". A phone-number-shaped string is not allowed even as an example, so the "hot" example must use the "can we jump on a call" wording.
- **No unmeasured rates.** The code docstring's "~95%" is unmeasured. It must not appear anywhere, and neither may any other share or percentage of replies.
- **No client name, no logo other than ProdCraft's own** (`deliverables/prodcraft_site_2026-10-19/site/assets/logo-prodcraft.png`).
- **The model is not shown classifying anything.** The live model path in the repo scaffold is not implemented (reply_classifier.py lines 145–151). The film may say that ambiguous replies go to judgement or to a person (F15), but must not show a model output, a model name, or a model confidence.
- **Code on screen is verbatim** (F21): same tokens and same order. Re-indentation is allowed only to fit the frame.
- **No AI-voice narration**: this is the operator's personal feed. Use music and sound design only, and keep it silent-safe: everything must read with the sound off.
- **End card**: a small "Made in code" line plus credits per `directives/video/lemo_opuscar.md`.
