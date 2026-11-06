# Pre-mortem: what could make a non-technical reader stop and frown (6 Nov 2026)

Method: imagine Veena or her manager writes back, "Why does this page say X?" and work backwards. Each item below is a question we would hate to be asked. Each becomes an automated check (`qa/client_eye/`) or a human-eye check, run on every page and state of **the hub, Option A (hosted and local), Option B and the extra**, at 1440 and 390, in a French browser (fr-FR, Europe/Paris) and in an English one (en-GB). Release rule: **zero findings** on every automated check, and an eye reviewer verdict of SHIP. Exceptions are allowed only with a written reason in `25_Test_Register.md`.

## A. First contact (the email and the hub)
| # | "Why …?" | Check |
|---|---|---|
| A1 | … does the link in the email not open / look broken / wrap oddly in Outlook? | Email draft contains one short link only; every URL is https and returns 200; no Playground URL in the email (those live on the hub). |
| A2 | … did nothing happen for 20 seconds after I clicked WordPress? | The hub says, next to each Option A button, that it takes about 15–25 s to start. The Playground boot screen is shown, never a blank page (hosted smoke measures the boot). |
| A3 | … does the page say "will appear here", "REPLACE", "TODO", "lorem", "undefined", "NaN", "null", "[object Object]", "{{", "%s", "XXX"? | Text-blacklist crawl of every page and state, visible text and attributes (alt, title, aria-label, placeholder). |
| A4 | … is a link or image broken? | Link checker: every anchor, `src`, `href`, `poster` and video source returns 200, or 30x to a page that returns 200. No mixed content. |
| A5 | … does the video not play / play without the thumbnail / play too big on my phone? | Each video has `poster`, `controls`, `playsinline` and `preload="metadata"`, a size under 25 MB, `faststart`, and plays in Chromium (decoded frame count > 0). |
| A6 | … does the browser tab say something odd, or show no icon? | Every page has a meaningful `<title>` (no "Document", "Vite", "WordPress › Error") and a favicon that returns 200. |
| A7 | … does the address bar say "debanjan186"? | Known and accepted unless the operator asks for a custom domain. Listed in the morning summary as a decision for the operator. |

## B. Language, typography, numbers
| # | "Why …?" | Check |
|---|---|---|
| B1 | … is there English in the French screens (Option A/B UI), or French left in an English sentence on the hub (outside quoted labels)? | A language check per text node: French UI must have no English stop-word runs (« the », « and », « Submit », « Save », « Loading », « Error », WordPress strings such as « Howdy », « Dashboard », « Posts »). Hub: French only inside « ». |
| B2 | … is a date in US or ISO format, or a day off near midnight? | Regex sweep for `\d{4}-\d{2}-\d{2}` and `\d{2}/\d{2}/\d{4}` (must be a valid jj/mm/aaaa date); a clock-at-00:05-Paris run; time shown in Paris time. |
| B3 | … does « 1 réponses », « 0 congrès trouvés », « 12 publié » read wrong? | Plural sweep across all counters at 0, 1, 2 and many. |
| B4 | … is a word cut in the middle, or a « » on its own line, or « — exemple » alone on a line? | Layout probe: no text node wraps inside a word (a hyphen-less break detected via range rects); no line starts with » ; : ! ? or ends with «; at 320, 390, 768, 1280, 1440 and 1920. |
| B5 | … is there a typo? | Spell check of every visible French and English string (`aspell` fr and en-GB, or a hunspell wordlist) with a project allowlist; zero unknown words unless allowlisted with a reason. |
| B6 | … are the same things called different names (Équipe / equipe / team; Demandes / Enquiries)? | A glossary of the 20 key labels; each must appear the same way in the hub instructions and in both UIs (the hub quotes the exact UI label). |
| B7 | … does a capital or an accent look wrong (« Equipe », « Acces »)? | A missing-accent sweep for known words (Équipe, Accès, Congrès, Réinitialiser, Vérifié, Qualifiée, …). |

## C. Things that look broken even when they are not
| # | "Why …?" | Check |
|---|---|---|
| C1 | … did I see a red error, a 404 or a white page? | Every route returns 2xx/3xx in normal use; styled French 404/410/429 pages exist and are reachable only by bad URLs; zero console errors and page errors in every journey. |
| C2 | … did a button do nothing, or need two clicks? | Click every visible button and link in each role: each causes a navigation, a visible state change or a visible message within 2 s. |
| C3 | … is a box empty, or a dashboard panel blank? | Empty-state sweep: every list, table and widget with 0 items shows a sentence, never a blank box. |
| C4 | … did something move while I was clicking (layout jump)? | CLS ≤ 0.02 per page; no element shift after load. |
| C5 | … does it look different from one page to the next (fonts, buttons)? | Computed-style sampling: one family each for body and display, one button style family, one accent colour. |
| C6 | … is something hidden behind the header or cut off on the right on my phone? | Overflow probe: `scrollWidth ≤ innerWidth` on every page at 320/390; anchor targets not under the sticky header. |
| C7 | … did I get logged out or lose my changes (overnight reset, session expiry)? | A session older than its expiry shows a French « Session expirée » message and a login link; the 03:00 UTC purge only touches sandboxes idle for more than 24 h; the hub states that each trial is private and is reset after 24 h. |
| C8 | … did I see technical stuff (IDs, hashes, JSON, stack traces, "Fatal error", SQL, "Worker threw", headers)? | Blacklist: `Error:`, `at `, `stack`, `Exception`, `Fatal`, `Warning:`, `Notice:`, `Deprecated`, `SQLITE`, `D1_`, `TypeError`, `undefined`, JSON braces in visible text, raw `<!-- wp:` markup, hex runs of 16 or more characters. |
| C9 | … can I see testing junk (`=cmd`, `<script>`, "AUDIT-PROBE", "test", Lorem) in the sample data? | Seed audit: every visible seed string is reviewed fictional data; a fresh-browser crawl finds no test residue. |
| C10 | … do the instructions on the hub not match what I see? | Instruction replay: an agent follows each hub step literally, only by visible labels, in each option, and every step must succeed in the stated number of clicks. |

## D. Trust and honesty
| # | "Why …?" | Check |
|---|---|---|
| D1 | … does it claim something that is not true (a feature "works" but does not)? | Every "Works in the demo" cell on the hub is backed by a passing test ID; every "Built during the project" cell has no working UI pretending otherwise. |
| D2 | … is there a real-looking person, company, phone number or e-mail? | All names fictional, e-mails @example.com, phones in a reserved fictional range (e.g. +33 1 99 00 xx xx) or masked; no real congress names. |
| D3 | … does it mention a price, a percentage, a client or a statistic you never sourced? | Number sweep: every number on the hub is a week number, a date, a count of our own demo data, or traced to a source line in `/redteam`. |
| D4 | … is a GM&E code visible anywhere without approval? | Leak crawl (existing) plus a DOM and attribute sweep in every role, including input values and title attributes. |

## E. Process gaps (how a defect could slip past us)
| # | Gap | Guard |
|---|---|---|
| E1 | A test passed against the wrong URL or an old build. | Every report names the commit and deployed version; the hub's links are checked against the live versions on the day. |
| E2 | A fix broke an earlier fix. | The full suites run twice green after every change; the client-eye gate runs last, on the deployed versions. |
| E3 | Screenshots reviewed were stale or from a dirty seed. | The final eye review uses shots taken by the gate itself from fresh contexts on the deployed sites, in this run. |
| E4 | Only Chromium was tested. | The client-eye gate also runs in WebKit and Firefox (Playwright ships them if available; if not installed, record N/A, never PASS). |
| E5 | Only the happy path at one width. | Every check runs at 390 and 1440 minimum, and B4 and C6 at six widths. |
