# Claims gate for client-facing text (operator order, 2026-11-03)

Trigger: a factual claim about a client's brief was made from memory one prompt after a self-audit, and was wrong. Never again.

Rule: before any email, page, proposal or reply text is shown to the operator, every factual sentence in it gets a row in a claims file next to it (`<text>.claims.md`): claim → exact source (file:line, or URL + date checked, or "what we said on <date> in <file>"). No source → the sentence is rewritten as an open question or removed. An independent worker (not the author) verifies every row against its source and returns PASS/FAIL; only PASS text reaches the operator. Judgement calls (price, tone) are marked as such, not sourced.
Applies to: everything addressed to a client or prospect, and to any statement about what a client wrote.
