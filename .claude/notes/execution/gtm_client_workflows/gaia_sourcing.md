# Notes

- [gates] Residence evidence: a firm-office phrase ("first joined the Cork office of", "in our London office") is not residence evidence under require_direct_evidence; a project/market mention ("experience in Ireland and the UK") never yields a place. 2026-09-11.
- [gates] Discipline exclude terms: only fire from the title or a sector claim, never from an employer/project sentence — a side "health and safety officer" duty wrongly excluded a structural Associate Director. 2026-09-11.
- [render] Client-facing reason: must be rebuilt from the gate's basis claim, with that quote on the same row; generic templates ("grade not stated", "only X missing") contradicted the evidence three times on one page. 2026-09-11.
- [render] Rule text shown to a client: generated from live params after overrides, never from spec description fields — a spec field leaked "PENDING KEITH MOLONY CALL" into client output. 2026-09-11.
- [check] Passes-with-note: shown, not silently counted as plain passes; near-miss lines read "n with a note". 2026-09-11.
- [cloud] Run cache rescue: branch gaia-run-cache-2026-09-14 holds the tarball; never merge it. 2026-09-11.
- [technical] Years-figure gates: a strict prefix ("over", "more than", "in excess of", "exceeding") reads as base+1 against a ceiling but as base (not base+1) against a floor; "at least", "15+", "upwards of" are inclusive at base; "no more than", "up to", "fewer than" never satisfy a lower bound; the reason string must quote the exact phrase matched. 2026-09-13.
- [technical] validator.normalize folds OCR-confused 1/l/I; of 154 unique dropped quotes it rescued exactly 1 (Pearse Sutton's "over 40 years"). 2026-09-13.
- [learned] The floor-vs-ceiling fix mattered in practice: an interim run credited Ronan McCrea's "over 7 years" against an 8-year floor and changed the client-facing near-miss count; after any gates.py change, always re-run gate..console and recount pool maps rather than trusting the prior numbers. 2026-09-13.
- [constraint] run.py's residence bucket map must be extended by hand whenever gates.py changes a located_ie note string, or affected rows fall into "unclassified". 2026-09-13.
- [pattern] --check evidence rendering: every gate's basis quote must surface, failing gates first, or the page states a reason no quote supports; CRM notes cap at 5 items. 2026-09-13.
- [constraint] check.csv is a client deliverable: must be written utf-8-sig and carry a formula-injection guard; input.source must be a bare filename, not a path. 2026-09-13.
- [pattern] 15-name input convention (13 August delivery + 2 delivered names) and intake.split_delivered's position rule for "delivered" rows are shared assumptions between run.py and check_page.py — change one, check the other. 2026-09-13.
- [process] Seven-lens question fan-out (Keith, Isadora, Maddie, end client, CFO, data-protection, Recruit CRM sales) produced OBJECTIONS.md; lens files live under deliverables/gaia_poc_check/lenses/. 2026-09-13.
- [technical] Fresh cloud container setup: `pip install -r requirements.txt` fails on langdetect (no wheel available) — skip it and add `pydantic[email]` separately; restore the run cache from branch gaia-run-cache-2026-09-14. 2026-09-13.
- [constraint] Sandbox-only test failures (not real regressions): test_ocr's local engine needs fitz (unavailable in sandbox) and the Chromium render test needs a browser binary the sandbox lacks. 2026-09-13.
