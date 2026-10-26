# v3 jury round 2 (2026-10-26) — REVISE; cover approved in substance ("a cover I'd run"). ► = decided. Assertion per item.
1. Chapter images (01–03, dialog, register-success): the same feathered portrait at the same size in the same left slot =
   stock layout; hard bottom edge at ~y 835. ► Per chapter a different still from the film with a different crop and scale:
   01 a full-bleed lunge (Aśva Sañcālanāsana) bleeding off the left edge; 02 a tight crop on the hands in Praṇāmāsana
   (≤ 40 % width); 03 the standing Praṇāmāsana small in a lot of sky (figure ≤ 35 % height). All four edges feathered to the
   paper (no rectangle: assert edge alpha ≤ .05 on all four sides, 16 points per chapter).
2. page-full-static: ~1,000 px of empty gradient after the cover; chapters far apart. ► Dawn resolves to cream within 30 svh;
   chapters ≈ 1 viewport each; no band between sections taller than 20 svh (assert on the static page and on
   mobile-chapters).
3. Dialog + Contact subscribe: bordered box, black pill = the last template elements. ► Newsletter opens as a bottom sheet
   (phones) / inline sheet (desktop) with no border and no box shadow on a cream scrim; submit is the underlined serif link
   "Keep me posted →"; Contact's SUBSCRIBE pill becomes the same link style. Assert: no `button` with a filled dark background
   anywhere; no element with a 1 px dark border around the newsletter form.
4. Chapter ring: floats empty near the nav. ► Tie it to scroll: it fills (stroke-dasharray) as the chapter is read and sits
   beside the chapter number "01 —" at the chapter's top-left; assert its dash offset changes with scroll inside each
   chapter and that it sits within 24 px of the chapter number.
5. Register-success: remove the stray rule above the confirmation; no faded header text may overlap "Group class" (assert
   no text-box intersections in the chapter after success).
6. Mobile cover: headline + sūtra sit in a flat navy band. ► No band: type sits on the sky with a soft top gradient scrim only
   (max 45 % alpha, 0 by 35 % height); assert no element with a solid background behind the copy on phones.
Re-verify all; fresh screens; report ≤ 200 words.
