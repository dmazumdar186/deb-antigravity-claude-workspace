Subject: Trusted Segments: cleaned values on screen, and how it gets built

Frédéric,

Thank you for yesterday. You pushed on two points, and you were right to.

First, the cleaned values. In the room I mixed two things. The two new date filters answer "is this still true?". The cleaned columns answer "is this written the same way?", for example eight spellings of London. Admins should see the second, and the deck already needs a screen for it, since each school can override the shared clean-up lists. Here is how it looks, using the 49 members from the case file:

https://trusted-segments-concept.pages.dev

It is clickable. "Visite" runs a seven-step tour, and the pins explain each element. Three rules keep it safe and light for admins:
- What the member typed is always one hover away and is never changed.
- Uncertain clean-ups are marked "suggested" until an admin confirms them.
- Admins review only those exceptions, sorted by members affected, so it takes minutes. AlumnForce maintains the shared lists.

Second, how exactly it gets built. The page "How it gets built" walks through the nine steps on your stack: MariaDB, the nightly job, OpenSearch and the segmenter, with the checks we would run on each school. The 90-second video covers both:

https://trusted-segments-concept.pages.dev/demo.mp4

Two decisions I would put to you:
1. Originals on hover, or a visible second column?
2. Should suggested clean-ups count in lists before an admin confirms them, or only after?

Happy to go through it whenever suits you.

Debanjan
