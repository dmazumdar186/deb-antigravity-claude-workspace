# Post-mortem: ASSET picked https://demo.voyagedemo.site/ (9 Nov 2026)

Observed (curl, 9 Nov): one real WordPress 7.1.4 site with its own theme (`voyages-demo`), on a neutral domain behind Cloudflare, standard `/wp-login.php`. A complete agency website, not a feature demo: Accueil, Congrès (catalogue, filters, 6 "DEMO –" congresses, "Tarif préférentiel disponible"), Services, Business Travel, MICE, Conseil, Savings Scan, SmartFees, Compte entreprise, Contact, Demander un devis (devis vol form with departure city, dates, passengers, class), Mentions légales. Pages mirror ASSET's own live services (diagnostic → Savings Scan, notes de frais → SmartFees). Fictional brand "Voyages Démo", clearly labelled.

## What they did that we did not
1. Answered the literal ask: "a relevant WordPress project, demo link". One WordPress site, one link, loads instantly.
2. Showed ASSET its future website, all pages, with the five stories inside it. We showed two platforms, a test-plan-style hub and instructions.
3. No friction: no 15–30 s Playground boot, no "reload if stuck", no sandbox rules, no two logins to switch between.
4. Neutral, credible hosting (own domain); ours read `playground.wordpress.net` and `debanjan186.workers.dev`.
5. Confident, short copy. Ours grew hedges round by round (red-team wording on scope, timing, retention).

## What cost us
- Offering a custom platform when the client wrote "in WordPress" twice: read as not listening, and as choice overload.
- Effort went where the buyer cannot see it: per-browser sandboxes, write caps, HKDF keys, 7 red-team rounds on an email. Valuable for production, invisible in a demo decision.
- Time and tokens: ~24 h of a shared pool; the 6 Nov target was met only at EOD.
- The gate loop never converged; each pass added caveats that made the text weaker for a buyer.

## Rules for next time (promote to site-redesign / proposal directives)
1. Build exactly the platform the client names. Alternatives go in the proposal, not the demo.
2. A demo is the client's future site with their journeys inside, on a real neutral domain; not a feature lab or a "how to test" hub.
3. Zero-friction first click: hosted for real (managed WP / Cloudflare), no in-browser boot, no instructions needed.
4. Budget the hardening to the stage: demo = credible and safe with fictional data; production-grade security belongs to the build.
5. Outward text: cap red-team at 2 rounds on substance (facts, commitments, price/date); style and hedging findings are advisory, not blocking.
6. Ship the simple thing first, then iterate if time remains.
