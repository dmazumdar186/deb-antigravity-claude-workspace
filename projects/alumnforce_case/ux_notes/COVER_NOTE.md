Subject: Trusted Segments: cleaned values on screen, and how it gets built

Frédéric,

Thank you for yesterday. Here are the answers to your two questions.

First, the cleaned values. They do a different job from the two new date filters. The date filters answer "is this still true?". The cleaned columns answer "is this written the same way?", for example eight spellings of London. You were right that admins should see the second; the per-school override in the deck needs a screen anyway. Here is how it looks, using the 49 members from the case file:

https://trusted-segments-concept.pages.dev

It is clickable. The "Visite" button runs an eight-step tour, and the pins (in English) explain the key elements. Four rules:
- The city and country the member typed are one hover away, and no field a member typed is ever overwritten.
- Uncertain clean-ups are marked "suggested" until an admin confirms them.
- Admins review only those exceptions, sorted by members affected. AlumnForce maintains the shared lists.
- All of it sits behind the reliability flag: with the flag off, the segmenter is unchanged, as on slide 6.

Second, how exactly it gets built. This page walks through the nine steps on your stack, with the checks to run on each school:

https://trusted-segments-concept.pages.dev/build

The prototype also shows the scrubber. Under the sentence box, run one of the two fictional examples: "What leaves the platform" puts what the admin typed next to what the AI model receives: e-mails, phones and exact matches of a member's first and last name from that school's member list are removed, any other capitalised two-word sequence becomes a placeholder restored locally, and every hit is logged rather than blocked.

The video, under 90 seconds, walks through all of it:

https://trusted-segments-concept.pages.dev/demo.mp4

Two choices I made in the prototype; tell me if you would overturn either:
1. Originals on hover rather than a second column: the table stays readable.
2. Suggested clean-ups count in lists, marked "suggested", with a one-click confirm: a list never silently shrinks.

Happy to go through it whenever suits you.

Debanjan Mazumdar
