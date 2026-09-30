# Human-eye run r3 — final fix list (2026-09-30). Both editions. Everything else from r3 is accepted as P3 polish and listed in the verdict.
P1  1. Package table at 1024 (and 1440 in some captures): sticky thead covers the first row — the offset must equal the site header height at every width (measure --hdr-h at 1024) or drop sticky thead below 1200px.
P2  2. Post-a-job form: salary inputs need visible "Minimum"/"Maximum" labels and a currency prefix (€/£ per edition); description label → "Job description" with help text "Shown to candidates as plain text; paragraphs and bullet lines are kept." under the field; board-card meta double space before "·"; same chip order on the board card and job-page mock (salary last on both).
P2  3. Dashboard: "Agency share" description → one sentence ("Roles posted by recruitment agencies rather than the employer directly."); "Salary disclosure" description → one sentence; lede: delete "Reported once analytics is switched on."; tiles in a row must share height (align-items stretch, descriptions clamped to 2 lines with title attr).
P2  4. UK job cards at 390: "Dacorum Borough Council" / "· Hertfordshire" — the separator STILL starts the line; render meta as "<span class=row__pair>· Hertfordshire</span>" where the pair is nowrap and the separator is inside the pair (verify on uk/jobs/ at 390 by screenshot).
P2  5. Job page sidebar: merge "Location" and "Where" into one row "Location: London (UK)" / "Ireland & UK (nationwide)"; drop the duplicate country chip when the city already implies it (keep the loc badge).
P2  6. Jobs toolbar dark theme: List/Map/Saved segmented control needs its track background in dark; at 390 put "Quick job match" on the same row as the toggle.
P2  7. Sectors treemap: no truncated labels ("Sustainabi…", "econ…") — wrap to two lines or shorten to the sector's short name when the tile is < 150px; ONE ink colour rule (luminance-based) applied to every tile; "Tap a block" → "Choose a block".
P2  8. Map: Northern Ireland outline on the IE map must use the same muted fill as other zero regions in dark; at 390 show county counts (font 10px) on regions with ≥1 role.
P2  9. Subscribe dialog note → "You can also set up job alerts by email on greenjobs.ie." (edition domain), quieter style.
P2 10. Quick job match result cards: title in the same serif as listing cards.
P3 11. Insights at 390: x-axis labels one row, shortened ("20–30k"), max 5 ticks.
P3 12. 404 light: footer wordmark colour consistent with the site header.
P3 13. Employers page: merge the two note boxes under the CTAs into one; "Or send your details" → "Send your details"; "Audience and reach" card headings same height.
Note: the "longjd" screenshots use the test harness's hostile fixture text (lorem ipsum, <b>, Senior Ecologist) — that is the test input, never shown to the client; no change.
