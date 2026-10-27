# Round 8 critique by z-ai/glm-5.3

## Review — picky pass, P1 first

1. **[P1] js/main.js `EVENT_NAMES`** — Beacon names were silently renamed: `register_open→register_start`, `whatsapp→wa_tap`, `instagram→ig_tap`, `subscribe→newsletter_open`. The brief and handoff are explicit: send the four allowlist names verbatim (`register_open`, `whatsapp`, `instagram`, `subscribe`). If `event.ts` keeps the v3 allowlist, three of your four beacons will 400 silently (`.catch(()=>{})` hides it). → Delete the `EVENT_NAMES` map; send `JSON.stringify({name})` with `el.dataset.event` unchanged. The functional gate only checked one name — widen it to all four.

2. **[P1] index.html cover + i18n.js `heroAlt`** — The hero is the `sun` key (an AI-upscaled 600×800 source run through realesrgan ×4/×2 — the manifest says so itself). The brief: hero = `_DAV5356.jpg`, portrait 4:5, seated, gentle smile, and the DOM contract asserts FR hero alt starts with **"Jeevana assise"**. Your FR alt ("Jeevana, les yeux fermés… en robe noire") describes a different photograph — the contract check would fail, and an upscaled 600px-wide image will look soft on any 4K screen. → Use the polished `hero@800/1400/2000/2800` set (which exists and is unused), 4:5, and restore the seated alt strings.

3. **[P1] Classes section / i18n `individualBody`, `timetable`** — Prices are missing entirely. The Superprof addendum supersedes "Price on request": Classes must carry **€50/h, packages 5 h €250 / 10 h €500, €25/h in-home *after the French tax credit (crédit d'impôt)***, €50/h online. Your own gate asserts "no fee or € anywhere" — that gate is now wrong and enforces the omission. → Add a small price block per format (individual / small group on request), the tax-credit line, and keep "timetable on request" as the slot wording. Update the gate.

4. **[P1] i18n.js `registerConsent` / `subscribeConsent`** — Consent strings are paraphrased, not verbatim. Register must read *"I agree that **Jeevana stores these details to answer my registration**…"*; subscribe *"I agree to receive **Jeevana's** newsletter…"*. The API stores `CONSENT_TEXT[lang]` verbatim in KV while the visitor ticked different words — that's a legal mismatch. → Paste the two CONSENT_TEXT blocks character-for-character (EN and FR) from the handoff.

5. **[P1] index.html section order** — DOM contract: ids in order `#top, #practice, #twelve, #classes, #about, #contact`. You ship `#about` *before* `#practice` (nav order matches markup, so the gates pass) and add an unlisted `#paris` section. → Move About after Classes; fold the Paris/testimonial content into About or Contact and drop the stray id (or rename it) so the contract holds and the narrative reads practice → breaths → classes → person → contact.

6. **[P2] css/styles.css `:root`** — Palette drifts from the brief: paper `#E8D6B3` (spec `#F3EEE4`), ink `#2B1E14` (`#2A2622`), plus invented `--verm #A63A22` and `--gold #B8862B` doing accent duty everywhere (arcs, mini rings, section hairlines, ornamental "holes"). The brief's Jeevana temperature is warm paper + one ochre + one cool indigo; you have three hot accents and the indigo has nearly vanished from the system. → Reset to the spec tokens; vermilion only as a whisper (folio numerals at most). Also `.twelve .arc` should be ink at .14 with the lit arc ochre at .5 — currently everything is gold at .55.

7. **[P2] index.html `#paris` figure** — Uses `saree-eiffel@2000` (upscaled) instead of the manifest's `paris` key — the genuine Chakrāsana/Eiffel shot, max 1200, which the brief explicitly wants as the secondary Paris image. → Swap to `paris@800/1200`, never upscale, restore chip "Champ-de-Mars, Paris".

8. **[P2] css `.card` (strip)** — Brief: centred card scales 1.0 vs .96 neighbours. You only dim to opacity .88. → Add `transform:scale(.96)` on `.card:not(.is-active)` (transform/opacity only, already transitioned), and make sure `prefers-reduced-motion` keeps `.card{transform:none}` as you do.

9. **[P3] index.html hero `sizes`** — `sizes` uses `34svh`, `34.5svh` etc. — non-standard in `sizes`; browsers drop the whole value and pick the last candidate. → Replace `svh` with `vh`/`vw` in every `sizes` attribute (strip cards too).

10. **[P3] styles.css `.twelve .rays`** — A second 9 s breathing animation on the ray group plus the 5.5 s centre breath plus 240 s orbit is three concurrent motions on the backdrop; the spec allows the 240 s rotation and one 5.5 s centre breath. → Drop `rays-breathe` (keep your reduced-motion override anyway).

11. **[P3] `.section::before/::after` ornaments** — Vermilion margin rules + the "binding holes" strip on every section reads as a second, competing motif (and the holes sit behind headings on tablets — check 1024 screenshots). → Keep the fibre texture, retire or halve the holes.

12. **[P3] JSON-LD / meta** — `jobTitle` is "Hatha Yoga teacher" (spec says "Yoga teacher"), and you add an `Organization` node with `areaServed`/`email` the brief didn't ask for. Harmless, but align jobTitle and trim the Organization to name/url/logo. `og:locale` toggles to `fr_FR` — good.

## Three things that are already excellent — do not lose them

- **The strip mechanics.** Keyboard, drag with snap-recovery, 4 s autoplay with hover/focus/visibility pausing, reduced-motion disabling with an honest label, `JV_strip` exposed — 56/56 functional passes. This is the "wow" and it's solid.
- **Performance discipline.** 144 K page weight, zero layout shift, lazy below the fold, eager+`fetchpriority` hero, self-hosted fonts with `unicode-range` splits. Keep exactly this budget.
- **The frame language.** Rounded frames, mist placeholders reserving ratio, glass chips, soft long shadow, backdrop living *behind and beside* the photo — no dark plates, no pasted cut-outs. The photographs feel placed. Preserve this treatment while fixing the palette and the hero image.
