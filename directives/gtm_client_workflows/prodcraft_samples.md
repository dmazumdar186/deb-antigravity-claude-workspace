# ProdCraft Sample Proposals (send on "yes")

## Goal

Keep one ready-to-send sample proposal per campaign niche, so a prospect who answers the cold email's "want me to send over an example?" gets a PDF within minutes. Each sample shows a one-paragraph client brief turned into a client-ready proposal in one working day (the Proposal Engine offer, `directives/lead_sourcing/prodcraft_campaign.md` v2).

## Inputs

- Content modules (fictional clients only, all figures illustrative):
  - `sample_event.py`: EVENT/AV pitch deck, SKO 2027, Las Vegas, 600 pax (16:9, 11 slides, USD)
  - `sample_fitout_us.py`: US fit-out bid proposal, Chicago, 14,000 sq ft (Letter, 7 pages, USD)
  - `sample_fitout_uk.py`: UK Cat B tender submission, London, 1,300 m² (A4, 7 pages, GBP)
  - `sample_dmc.py`: DMC incentive trip proposal, Lisbon, 120 pax, 4 nights (A4, 8 pages, EUR)
- Shared look: `render.py` (Inter, neutral bone/ink palette, one accent per document).

## Tools/Scripts

- `execution/gtm_client_workflows/prodcraft_samples/build_samples.py` builds HTML, then PDF, then PNG previews.
- `render_pdf.js` uses Node Playwright Chromium and flags any page whose content overflows its box (exit 2).
- `pdftoppm` (poppler) renders the PDF pages to PNG for the visual check.

## Outputs

- `deliverables/prodcraft_samples/{event_av_pitch_deck,fitout_us_bid_proposal,fitout_uk_tender_submission,dmc_trip_proposal}.{html,pdf}` (committed; fictional, no PII).
- PNG previews in `.tmp/prodcraft_samples/png/` (not committed).
- Google Drive: private folder "ProdCraft samples (send on yes)" with the 4 PDFs (not shared).

## Steps

1. Edit content in the matching `sample_*.py`. Every total is computed in code from its lines, so it adds up. Never type a total by hand.
2. `python3 execution/gtm_client_workflows/prodcraft_samples/build_samples.py [--only <slug>]`. It must print `overflow=none` for every doc.
3. Look at every PNG in `.tmp/prodcraft_samples/png/` (use a worker; images stay out of the main context). Check for cut-off tables, overlapping text, wrapped labels, and empty pages. Fix and rebuild until clean.
4. Re-upload changed PDFs to the Drive folder. Do not share the folder; it is sent as an attachment.

## Rules (contract)

- Footer on every page: "Sample — fictional client, illustrative figures. Prepared by ProdCraft."
- Page 1 carries the "Built from: [brief] → this proposal in one working day" box.
- Client and firm names are invented words, checked by web search (2026-11-03: Velloran, Merrow Lane, Brannick Hale, Ashcombe Rook, Tandrevo, Pellwyn Harcourt, Saltmarrow, Draxmere). No real hotels: use "e.g." category descriptions. No claims of past clients or results.
- Plain industry language (GMP, alternates, preliminaries, provisional sums, IMAG, run of show, flight banks). Never "AI-powered" or software jargon.

## Edge Cases

- Python Playwright is not installed in cloud sessions; Node `playwright` is, so PDF rendering runs through `node`.
- `font-feature-settings: tnum` makes digits look spaced out in low-DPI previews. To check this, render one crop at 150 dpi before treating it as a defect.
- Dates are relative to the proposal date (3 Nov 2026). If a sample is reissued later, move the timeline and validity dates forward so no milestone is in the past.
- Deck CSS sizes (`.deck ...`) override the document sizes. After you change base type sizes, check both formats.

## Changelog

- 2026-11-03: created. Four samples built and visually checked page by page. PDFs uploaded to Drive.
