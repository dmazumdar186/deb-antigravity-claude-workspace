Subject: Trusted Segments: cleaned values on screen, and how it gets built

Frédéric,

Thank you for yesterday. Here are the answers.

First, the cleaned values. You were right that admins should see them; the per-school override in the deck needs a screen anyway. The two date filters still do a separate job: they answer "is this still true?". Here is how it looks, using the 49 members Annex B returns on the case file (IDs only, no names; the page is not indexed):

https://trusted-segments-concept.pages.dev

It is clickable. The "Visite" button runs an eight-step tour, and the pins (in English) explain the key elements. Four rules:
- The city and country the member typed are one hover away, and no field a member typed is ever overwritten.
- Uncertain clean-ups are marked "suggested" until an admin confirms them.
- Admins review only those exceptions, sorted by members affected. The shared lists start from AlumnForce's reference tables and grow from schools' confirmations: a mapping confirmed by several schools is promoted to them (Annex D).
- What admins see sits behind the reliability flag: with it off, the segmenter is unchanged, as on slide 6.

Second, how exactly it gets built. This page walks through the nine steps on your stack, with the checks to run on each school:

https://trusted-segments-concept.pages.dev/build

The prototype also shows the scrubber. Under the sentence box, click one of the two fictional examples; the "What leaves the platform" panel puts what the admin typed next to what the AI model receives, with the pre-flight rules from slide 8 applied.

The video, under 90 seconds, walks through the tour and the build page:

https://trusted-segments-concept.pages.dev/demo.mp4

Two choices I made in the prototype; tell me if you would overturn either:
1. Originals on hover rather than a second column: the table stays readable.
2. Suggested clean-ups count in lists, marked "suggested", with a one-click confirm: a list never silently shrinks.

Happy to go through it whenever suits you.

Debanjan Mazumdar
