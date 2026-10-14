# yogaavecjitendra.fr — how to change your website yourself

This is your website. You own it completely. No developer is needed for everyday changes.

## The 3 things you log in to (all free)

| What | Where | What it is for |
|---|---|---|
| **The editor** | https://app.pagescms.org | Change photos, videos and text. This is the only one you use day to day. |
| GitHub | https://github.com | Stores the website files. You log in to the editor with this account. |
| Cloudflare | https://dash.cloudflare.com | Publishes the website and manages the domain. You rarely need it. |

## Change a photo (2 minutes)

1. Go to https://app.pagescms.org and click **Sign in with GitHub**.
2. Open the **yogaavecjitendra** project.
3. In the left menu click **Media** → folder **images** → **Upload** your new photo.
   Use JPG files, ideally under 1 MB (resize on your phone first if it is huge).
4. Click the page you want to change in the left menu (for example **Home (French)**).
5. Click the photo field (for example *Hero image*) → **Select** → pick your new photo.
6. Click **Save** at the top.
7. Wait 2 to 3 minutes. Refresh https://yogaavecjitendra.fr. Done.

Each page exists twice: **(French)** and **(English)**. Change both if the photo should change in both languages.

## Change a video

Same as a photo: **Media** → **videos** → upload an MP4 (keep it under 50 MB), then pick it in the **Video** field of the page. The **Video poster** field is the still image shown before the video plays.

## Change text, prices, schedule, phone number

Click the page in the left menu, edit the text boxes, **Save**. The schedule, offers, contact details, press mentions and recommendations each have their own page in the menu.

## Where each photo lives

| Photo on the site | Page in the editor | Field |
|---|---|---|
| Big photo at the top | Home (French) / Home (English) | Hero image |
| Your portrait | Home | Portrait image |
| One photo per offer (studio, home, online, corporate) | Offerings | Images → Image |
| The sliding photo gallery | Schedule | Gallery |
| Logos of companies | Clients (logos) | Logo |

## Add or remove photos in the gallery

1. Editor → **Schedule (French)** → scroll to **Gallery**.
2. **Add a photo:** click **+ Add** at the bottom of the list → in the new row click **Src** → **Select** → choose a photo you uploaded in Media → type a short description in **Alt** (what the photo shows; this is read by Google and by blind visitors).
3. **Remove a photo:** hover the row → click the trash icon.
4. **Reorder:** drag the row by its handle.
5. **Save.** Repeat in **Schedule (English)** so both languages match.

There is no limit on the number of photos. 6 to 12 looks best.

## Change the background music

1. To use a different track: **Media** → folder **audio** → **Upload** an MP3 (keep it under 5 MB; use royalty-free music, for example from pixabay.com/music, otherwise the site can be taken down for copyright).
2. Editor → **Ambient sound (site settings)**:
   - **Play ambient music**: tick to have music, untick for a silent site.
   - **Music file (MP3)**: click → **Select** → choose the track.
   - **Volume (0 to 1)**: 0.2 is soft, 0.5 is the current level, 1 is loudest.
3. **Save.** The music starts on a visitor's first click or scroll, loops, and the little sound button at the bottom of the page lets them mute it.

The two tracks already there are `bansuri-studio.mp3` (current) and `bansuri-raga-alt.mp3` (a second flute recording); both are licensed for this site (see the `licenses` folder).

## Things that are OK to know

- Every save is kept forever. If you break something, open the same page in the editor, scroll the **History** panel (or go to GitHub → the repository → *Commits*) and restore an earlier version.
- Changes take 2 to 3 minutes to appear. If after 10 minutes nothing changed: Cloudflare → **Workers & Pages** → **yogaavecjitendra** → **Deployments**. A red deployment means the last save had a problem. Click **Retry**, or undo the last change in the editor.
- The site shows every review approved so far (file `src/content/reviews-seed.json`, also editable in GitHub). New Google reviews do not appear automatically unless a developer sets up the `cron/` worker.
- The private statistics dashboard (`/dashboard/`), the "leave a review" form and the newsletter box only work after the optional Cloudflare storage step (a KV namespace bound as `DASHBOARD_KV` plus a `DASHBOARD_PASS` secret; login name `jitendra`). Without it the public site is complete and nothing breaks.
- Everything from the project is in this repository: `docs/` (SEO and dashboard notes, project history), `deliverables/ads/` (16 ready ad creatives), `data/kv/` (your reviews and, if exported, subscribers and statistics), `cron/` (the Google-review sync worker).

## If you ever want a developer

Any web developer can work on this. Tell them: "It is an Astro static site on Cloudflare Pages, edited with Pages CMS. The repository is on my GitHub." That sentence is all they need.

## Domain renewal

The domain **yogaavecjitendra.fr** is registered in your name at GoDaddy and expires in **July 2028**. Renew it there before that date or the website goes offline.
