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

## Photos in the gallery

Open **About (French)** or **About (English)**. The **Gallery** list is the set of photos shown. Use the **+** button to add one, the trash icon to remove one, and drag to reorder.

## Things that are OK to know

- Every save is kept forever. If you break something, open the same page in the editor, scroll the **History** panel (or go to GitHub → the repository → *Commits*) and restore an earlier version.
- Changes take 2 to 3 minutes to appear. If after 10 minutes nothing changed: Cloudflare → **Workers & Pages** → **yogaavecjitendra** → **Deployments**. A red deployment means the last save had a problem. Click **Retry**, or undo the last change in the editor.
- The site shows the Google reviews that were saved in it. New Google reviews do not appear automatically; you can add them under **Recommendations**.
- The newsletter sign-up box and the "leave a review" form are switched off. Nothing to do.

## If you ever want a developer

Any web developer can work on this. Tell them: "It is an Astro static site on Cloudflare Pages, edited with Pages CMS. The repository is on my GitHub." That sentence is all they need.

## Domain renewal

The domain **yogaavecjitendra.fr** is registered in your name at GoDaddy and expires in **July 2028**. Renew it there before that date or the website goes offline.
