# Panel lens 5 — Hormozi (offer & unit economics)

**Verdict: honest, low-friction path; weak offer.** Likelihood and effort terms are handled; dream outcome is unnamed and time delay is undefined (no timetable, no price). Nothing scarce or invented is claimed.

## Findings
1. **No dream outcome for a Paris beginner.** Cover sells the tradition (`i18n.js:25-26` sūtra lines; `:51` "taught from the tradition"). The nearest outcome is "the class settles" (`:43`). Missing: what a beginner gets after a month (calmer mind, steadier body). Write it from the operator's own words, not invented copy.
2. **Likelihood lever exists but is buried.** "Beginners are welcome. Every posture has an adaptation" (`i18n.js:54`) is the strongest conversion line and sits in tab 02. The cover should carry it.
3. **No risk reversal.** "Price on request" (`i18n.js:66`) plus no first-class terms means uncertainty on both cost and commitment. *Suggestion to the operator only:* a trial/first-class offer. Do not add copy now.
4. **Time delay is open.** Empty timetable -> "opens soon" (`i18n.js:61`, `index.html:163`) with no date; "reply by email" (`i18n.js:68,73`) has no response window.
5. **Path is ≤ 3 steps.** Cover CTA -> Register (`index.html:78`, also header `:47`, mobile bar `:236`) -> submit (`:195`). Pass.
6. **Form is close to minimal.** 3 required (name, email, consent) + 4 optional/defaulted (`index.html:187-194`). Level defaults to "New to yoga" (`:191`), which is right. Could hide Phone/Message behind one optional field; minor.
7. **Newsletter is an empty ask.** "A few letters a year: workshops, new classes, a sūtra" (`i18n.js:76`) offers no lead magnet, and nothing is sent yet (`to_wire.md`: KV only). Fine as a soft ask; not a capture engine.
8. **No false scarcity.** "Small group" (`i18n.js:64`) is descriptive, no counts or deadlines. Pass.
9. **Contact panel is a strong escape hatch** (phone/WhatsApp, `index.html:207-208`), which suits Paris beginners who prefer messaging.

## Supply first (by expected conversion impact)
1. **Timetable** (`js/schedule.json`): turns "interest" into a bookable slot; fixes time delay.
2. **Price**: takes away the biggest unknown.
3. **First-class / trial terms**: risk reversal (operator decides).
4. **One real testimonial** (name + consent): raises perceived likelihood.
5. Studio address / arrondissement; reply-time promise.

## Honest gaps
- Read the EN strings and the HTML only. FR parity was not checked line by line.
- No traffic or form data exists, so the ranking is judgement, not measured.
- Did not test the JS flow (tab switching, when the dialog fires).
