# Panel lens 9 — Mira Murati (product & UX)

**Verdict: SHIP WITH TWO FIXES.** The phone journey reads as one voice. Two things break it: The newsletter dialog can pop over a visitor who is typing a registration, and Jeevana has no daily view of her registrations.

## Findings

1. **The newsletter dialog interrupts the register form (high).** `js/main.js:323` arms a 1.2 s timer as soon as the deck is active, and `:324` only blocks the dialog on the cover or when the gallery is open. No check that focus is inside `[data-reg]`, so `showModal()` (`:264`) steals focus mid-word. Fix: skip while `d.activeElement` is inside a form, and never fire once the Register tab is open.
2. **First paint is sound.** `index.html:31` preloads `sn-01` with a 563w srcset (63 KB mobile). The video waits for `hero.json` and is skipped under reduced motion, Save-Data or `?canvas=1` (`main.js:170`). The Google Fonts CSS (`index.html:30`) is render-blocking, so first paint waits on it.
3. **Autoplay on slow 4G stutters.** Frames advance every 900 ms (`main.js:107-112`). Each frame is only fetched when its turn comes (`:84-88`), and the swap waits for `onload`, so it never goes blank, but it skips. Mobile frames are 42-63 KB, too big for 900 ms at ~300 kbps. Prefetch frame n+1 while frame n is showing.
4. **iOS form is mostly right.** Inputs are 16 px (`css/styles.css:178`), so iOS does not zoom. `inputmode`, `autocapitalize` and `enterkeyhint` are correct on name, email and phone (`index.html:187-189`). Errors set `aria-invalid` and focus the first bad field (`main.js:296-297`), but no text says what is wrong. Email shows nothing until the visitor submits.
5. **After submit.** Success hides the form and focuses the `role=status` panel (`main.js:307-310`). On a network failure the button comes back and a mailto link appears (`index.html:196`). The mailto only carries a subject (`main.js:35`): everything the visitor typed is lost. Pre-fill the body with those details.
6. **Newsletter dialog: Esc works natively, the focus trap and focus restore work** (`main.js:268-276`). It fires once per browser (`:318,325`), after 35 s or 1.2 s into the deck.
7. **The FR/EN choice persists** in localStorage (`main.js:22,28`), but the URL never changes: `hreflang` en and fr both point to `/` (`index.html:9-10`).
8. **Reduced motion** turns off autoplay, video and smooth scroll (`main.js:102,170,209`) plus CSS (`styles.css:341`).
9. **404** (`404.html`) is on-voice and bilingual inline, with one way home. It ignores the visitor's saved language.
10. **Jeevana's surface is too thin (high).** Registrations go only to KV (`functions/api/register.ts:28`). `register.ts` sends no email or notification. Her only view is `/api/export?type=reg`, a Basic-auth CSV (`functions/api/export.ts:23-35`), and it returns 401 because `EXPORT_USER`/`EXPORT_PASS` are not set (`research/to_wire.md`). Today she sees nothing; the smallest surface is one email per registration.

## Honest gaps
- Code read only: no device, no throttled trace, no real iOS keyboard.
- Not audited: most of `styles.css`, `backdrop.js`, the `i18n.js` strings.
- I did not check hero video sizes against real autoplay rules (Low Power Mode blocks it; fallback untraced).
