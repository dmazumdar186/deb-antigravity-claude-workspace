# Gaia Talent — redesign concept

A static, framework-free redesign concept for gaiatalent.com. Five pages, one
stylesheet, four small scripts, no third-party runtime dependencies. This folder
(`src/`) holds the **templates**; the deployable output is built into `../site/`.

Every fact on the public pages comes either from gaiatalent.com itself or from
`data/jobs.json`, which was read from the live role pages on 15 September 2026.
Nothing is invented. Salaries and per-role posting dates are deliberately not
shown (see `for-keith/index.html`, "Where the data came from").

---

## 1. Running the build

```bash
python3 execution/gtm_client_workflows/gaia_redesign/build_site.py \
    --src  deliverables/gaia_redesign_2026-09-17/src \
    --out  deliverables/gaia_redesign_2026-09-17/site

# reuse the stored link-check instead of re-hitting gaiatalent.com:
#   ... --skip-links
```

The build:

1. checks every live role URL with a HEAD request (6 threads, 20s timeout) and
   writes `data/link_check.json`; a blocked network is recorded honestly rather
   than being reported as broken links;
2. copies `src/` to `site/`, stripping block comments from the CSS and JS on the
   way out (the sources stay documented, the shipped files stay inside the
   45&nbsp;KB CSS / 30&nbsp;KB JS budgets);
3. renders the template markers listed in §3;
4. measures the real byte weight of the built files and writes it into the
   evidence table on `for-keith/index.html`;
5. validates the result and **exits non-zero** on any failure.

Validation covers: relative paths only, every local `href`/`src` resolves, every
image has `alt` + `width` + `height`, every form control has a `<label for>`,
every JSON-LD block parses, the rendered role count equals the dataset, exactly
one `<h1>` per rendering path, `robots` noindex present, no unrendered markers,
no forbidden vocabulary on the public pages, and the CSS/JS weight budgets.

Unit tests for the scroll and scene maths:

```bash
cd deliverables/gaia_redesign_2026-09-17/src && node --test js/motion.test.js
```

Screenshots at 390 / 768 / 1440, plus tall captures, the seven hero scene states
and a reduced-motion set:

```bash
bash execution/gtm_client_workflows/gaia_redesign/screenshot.sh
```

## 2. Configuration

`config.json` is read at build time and never shipped.

| Key | Effect |
|---|---|
| `contact_email` | Written to `<body data-contact-email>`. While it is empty the contact forms compose the message on the page with a copy button and the two phone numbers, and the "Open in email" link stays hidden. Set it to a real Gaia address and the mailto link appears. |
| `as_of` | The "Live roles as of …" date shown on the roles sections. |
| `site_base` | Absolute base used to render `sitemap.xml`. |

## 3. Template markers

`build_site.py` replaces these HTML comments. Leaving one unrendered fails the
build.

| Marker | Page | Renders |
|---|---|---|
| `<!-- @org:jsonld -->` | index | Organization + two LocalBusiness blocks |
| `<!-- @jobs:ticker -->` | index | marquee rail of live roles (duplicated group is `aria-hidden`) |
| `<!-- @jobs:chips -->` | index | top six sectors, linked into the filtered board |
| `<!-- @jobs:featured -->` | index | eight featured role rows |
| `<!-- @sectors:map -->` | index | the 23 sectors, sized by live-role count |
| `<!-- @team:roster -->` | index | five-person roster with a staggered reveal |
| `<!-- @flow:role:1…6 -->` | index | one live role card per hero state |
| `<!-- @art:0…6 -->` | index | inline SVG for the no-motion hero fallback |
| `<!-- @jobs:jsonld -->` | jobs | JobPosting for every role |
| `<!-- @jobs:filters -->` | jobs | Location / Sector / Type selects, built from the data |
| `<!-- @jobs:all -->` | jobs | the full board |
| `<!-- @jobs:count -->`, `<!-- @jobs:consultant-line -->` | jobs | counts and the consultant line |
| `<!-- @team:full -->` | team | the full roster |
| `<!-- @evidence:table -->`, `<!-- @links:verified -->` | for-keith | measured bytes, live-link result |
| `<!-- @sitemap:urls -->` | sitemap.xml | page URLs from `site_base` |

## 4. Regenerating `jobs.json` from Vincere (or anywhere else)

The build only cares about the contract below. Point any exporter at it —
Vincere's API, a CSV, a WordPress feed — and the whole site re-renders.

```jsonc
[
  {
    "slug":       "senior-ecologist-ornithology",   // required, unique, URL-safe
    "title":      "Senior Ecologist – Ornithology", // required
    "url":        "https://gaiatalent.com/jobs/senior-ecologist-ornithology/", // required, absolute
    "location":   "Cork",                           // required; feeds the Location filter
    "sectors":    ["Ecological Jobs"],              // required, ≥1; first one drives the Sector filter
    "type":       "Permanent",                      // required; "Permanent" | "Contract"
    "salary":     null,                             // optional, never displayed
    "consultant": "Isadora",                        // optional; shown per row on the board
    "consultant_title": "Senior Recruitment Specialist",
    "summary":    "One or two sentences.",          // optional; becomes the JSON-LD description
    "posted":     "2026-09-14"                      // optional, never displayed
  }
]
```

Notes for whoever wires this up:

- **Counts are computed, never typed.** "63 roles open right now" and the
  superscripts on the sector map are derived from this file. Change the file and
  every number on the site follows.
- **The hero picks its own roles.** `FLOW_PICKS` in `build_site.py` matches title
  keywords in order and never reuses a role; if a keyword list matches nothing
  the build fails loudly rather than shipping an empty card.
- **`sectors` is free text.** The board shows the values as they come; the home
  page maps them onto Gaia's own 23 sectors with the keyword table in
  `build_site.py` (`SECTORS`).
- **Salary is intentionally ignored** everywhere, because only a minority of the
  roles disclose one and a partial display misleads candidates.

## 5. Porting it to gaiatalent.com

Three routes, in increasing order of commitment.

1. **Point a subdomain at the static files.** `site/` is plain HTML, CSS, JS and
   images — no database, no PHP. Upload it to Cloudflare Pages, Netlify or
   GitHub Pages and point `new.gaiatalent.com` at it. Remove
   `<meta name="robots" content="noindex,nofollow">` from each page only when it
   is genuinely meant to be indexed. Nothing on the live site is touched.
2. **Hand it to a web team as a theme.** The markup is semantic and the CSS is
   one file with all tokens at the top of `css/styles.css`. The header and footer
   are duplicated per page on purpose (no build-time templating for the shell),
   so converting a page to a WordPress template is a copy-and-paste job. The
   roles board is already generated from a JSON feed, so pointing it at Vincere
   is a data-mapping task, not a rebuild.
3. **Keep WordPress for the blog, use these pages for the front.** Serve
   `index.html`, `jobs/` and `team/` statically and leave the existing WordPress
   at `/blog/`. Lowest-risk option; nothing already owned is discarded.

All paths are relative with no leading slash, so the site runs unchanged from
`file://`, from a domain root, or from a subfolder such as
`https://example.github.io/repo/gaia/`.

## 6. How the page is put together

- `css/styles.css` — one sheet. Tokens (OKLCH with hex fallbacks) at the top,
  then reset, type, shell, and one block per section. Colour strategy is
  "committed": navy carries the hero, roles, proof and footer; cool mist bands
  carry the reading sections.
- `js/motion.js` — pure maths, no DOM. Scroll progress, the hero state machine,
  the scene's presence windows, the card-stack transforms. Unit-tested.
- `js/flow.js` — the hero. One canvas landscape that rearranges itself across
  seven states: the horizon is a 32-vertex polyline lerped between y-profiles,
  and each element (turbines, dam, solar rows, water plane, barrage, greenway,
  bridge, tree line, birds) fades in on a triangular window around its own
  state. DPR-aware; time-based motion is capped at ~30fps and only runs while
  the stage is on screen and the tab is visible.
- `js/main.js` — header, mobile menu, reveals, the pinned card stack, the
  contact forms.
- `js/jobs.js` — progressive enhancement over the server-rendered board. Every
  row is already in the HTML; the script only hides non-matching rows and keeps
  the query string in sync, so `?sector=Ecology` works as a shareable link.

**Degrade ladder**, on every animated section: below 800px, under
`prefers-reduced-motion: reduce`, and with JavaScript off, the pinned hero
becomes seven stacked blocks with inline SVG artwork, the card stack becomes a
plain list, and the ticker becomes a wrapped list of links. Nothing is hidden
behind an animation that might not run.

**Review hooks** (they change nothing in normal use):
`index.html#state-3` scrolls straight to the fourth leg of the hero sequence;
`index.html?scene=3` freezes the stage on that leg, which is how the scene
screenshots are taken (a headless renderer always captures from the top of the
document).

## 7. Known gaps — for Gaia to fill

Listed in full on `for-keith/index.html`: team bios, client logos or
testimonials, placement numbers, a contact email for the form, the CRO number
and registered address, and which sectors to lead with.
