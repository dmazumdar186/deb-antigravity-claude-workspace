# GreenJobs demo, fourth-pass design review (2026-09-25)

Reviewer stance: the head of design at a company that ships one object at a time and sweats
the corner radius. Every note below is a direction, not a description.

## What the operator saw
"Buttons look simple. Logo is yellow, favicon is green. Inner pages too dense. Mid."
They are right on all four counts.

## 1. One brand, not three
- Header leaf is honey `#d99a1c`; favicon is a dark-green tile with a lime leaf; buttons are pale
  mint `#a9d18e`; the footer wordmark is honey again. Three products are wearing one name.
- Direction: one mark. Deep green leaf on an ink tile, at every size (favicon, header, footer,
  menu, manifest, OG). Wordmark "Green**Jobs**" with "Jobs" in the same deep green. Honey is retired
  from the brand and survives only as the sun in the landscape.
- The action colour becomes a real green with white text (forest `#1f7a3d` range, AA on white),
  so "Post a job" reads as the one thing to press on the page, not a mint pill among beige.

## 2. Buttons that feel pressed, not printed
- Today: flat fill, 1.5 px outline, translateY(-1px). No depth, no state, no reward.
- Direction: primary = green gradient (lighter top edge, darker base), inner top highlight, soft
  coloured shadow, hover lifts and brightens, active compresses, focus ring in the same green.
  Secondary = ink outline that fills to ink on hover. Ghost = surface that tints on hover.
  Icon buttons get a real surface. Arrows slide. Transitions 180 to 260 ms, one easing.

## 3. Density: reveal, don't dump
- Jobs: every row shows sector chip + salary + type + age + save icon; 88 rows of that is a
  spreadsheet. Direction: rest state shows title, employer, place, salary. Hover or focus lifts
  the card and unfolds a summary line, the sector chip, and Apply / Save actions. On touch, the
  row expands on tap; the title link still goes to the job.
- Salary explorer: four full charts at once. Direction: headline numbers first, then one chart
  in view at a time behind a segmented control; bars reveal their value on hover.
- Employers: four text columns. Direction: four cards, closed by default with a one-line
  promise each; hover or click unfolds the detail. "Post a job" inside the reveal.
- Sectors: treemap, then a long list. Direction: the list is an accordion; a sector row opens
  to its roles on click and previews the count on hover.
- Job page: the description is a wall. Direction: the first paragraph shows; "Read the full
  description" unfolds the rest. The facts rail stays.

## 4. Surface and rhythm
- Cards get a hairline border plus a two-layer shadow and lift on hover; page heads get more air.
- Motion respects `prefers-reduced-motion`; everything works without JS (details/summary).

## Not done this pass
- No Higgsfield or GLM calls: the cloud session holds no API keys (`HF_API_TOKEN`, GLM) and the
  Higgsfield console balance was below the estimate on 2026-09-24. The hero footage already shipped stays.
