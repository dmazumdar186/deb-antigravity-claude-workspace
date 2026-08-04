# GDPR / CNIL assessment — Newsletter opt-in popup for yogaavecjitendra.fr

Author: workspace assistant · Date: 2026-08-04 · Status: SCAFFOLDED, NOT DEPLOYED

> **Scope pivot 2026-08-04.** Original brief framed this as a deaf/HoH
> accessibility popup (Art. 9 special-category health data). Operator re-scoped
> mid-work: this is a **bog-standard mailing-list opt-in popup**. No health
> data, no accessibility flag, no Art. 9 analysis. Everything below is scoped
> to the newsletter case.

---

## TL;DR for the operator

- **Legal basis:** Consent (GDPR Art. 6(1)(a) + CNIL commercial-prospection guidance).
- **Storage:** **Brevo** (French processor, Sablé-sur-Sarthe, EU-hosted, built-in DOI + one-click unsubscribe). Local Cloudflare KV holds only a hashed **consent proof** record (not the plaintext email). Justification below.
- **UX:** popup fires on first page-load only; a localStorage flag `yj_popup_seen` (30-day TTL) prevents re-nagging. **Skip is a first-class action** — larger visual weight than the submit button, no dark pattern.
- **Retention:** subscription lives as long as the user stays subscribed; deleted 30 days after unsubscribe (Brevo). Consent proof KV record kept 3 years (CNIL's commercial-prospection retention ceiling).
- **DSR:** magic-link flow at `/privacy/newsletter#gerer-mes-donnees` — visitor enters their email, receives a signed short-lived URL, then can GET their data or DELETE (Brevo + KV both purged).
- **Blockers to go-live**: (a) Brevo account + API key + DOI template + confirmation-list ID; (b) operator fills real controller name + postal address in privacy notice; (c) HMAC signing secret for DSR tokens.
- **NOT deployed.** All files staged locally, no push, no `wrangler deploy`.

---

## 1. Legal basis

**Chosen:** Explicit consent under **GDPR Art. 6(1)(a)**, evidenced by an unticked checkbox + an active click.

- CNIL, on "consentement": consent must be *libre, spécifique, éclairé, univoque* — https://www.cnil.fr/fr/definition/consentement.
- CNIL, on "prospection commerciale par courrier électronique" (B2C): prior explicit consent is mandatory; pre-checked boxes are prohibited; general T&Cs acceptance is insufficient — https://www.cnil.fr/fr/la-prospection-commerciale-par-courrier-electronique.
- GDPR Art. 7(1) obliges the controller to be able to **demonstrate** consent (proof-of-consent record).

**Not chosen (and why):**
- *Legitimate interest (Art. 6(1)(f))*: unsuitable for B2C marketing to net-new prospects per EDPB Opinion 06/2014 + CNIL guidance.
- *Soft opt-in (existing-customer exception)*: not applicable — the popup targets first-time visitors, not existing clients.

**Art. 9 (health data): NOT triggered.** The popup neither asks about nor stores health / disability information. Copy explicitly frames the newsletter as *"occasional emails about upcoming sessions, including adapted / accessible ones"* — a marketing description of session variety, not a request for the visitor's health status. If a future iteration adds a "which format interests you?" flag with an "adapted" option, that iteration must revisit Art. 9 (an interest-in-adapted-yoga signal is arguably not health data, but the safest reading treats it as an inferred proxy — kick that back to a dedicated review).

---

## 2. ePrivacy / Article 82 LIL — the `yj_popup_seen` flag

The popup uses a **`localStorage` flag** (not a cookie) called `yj_popup_seen`, set to `1` with a client-recorded 30-day expiry when the visitor skips or subscribes. On subsequent page-loads within 30 days, the popup does not render.

CNIL's cookie guidance (Article 82 of the Loi Informatique et Libertés, transposing ePrivacy Art. 5(3)) applies to **any** client-side storage of information — cookies, localStorage, sessionStorage, IndexedDB, service workers, fingerprinting — not just HTTP cookies. Source: CNIL "Cookies et autres traceurs" set of guidelines (2020-09-17, delib. 2020-091).

**Exemption analysis.** Article 82 exempts trackers that are *"strictement nécessaires à la fourniture d'un service de communication en ligne à la demande expresse de l'utilisateur"*. Two CNIL-recognised categories fit:

1. Trackers that record the user's own preference expressed to the site (language, cookie-consent state, "hide this banner").
2. Trackers strictly necessary to a service explicitly requested by the user.

A "don't show me this popup again" flag falls squarely under (1) — it records the user's own preference expressed via the Skip button. CNIL's audience-measurement exemption is a **separate** carve-out and does not apply here (that one requires anonymisation + no cross-site tracking); we invoke the preference-tracker exemption instead.

**Defensive posture in code.**
- The flag stores only `1` (no timestamp, no PII, no fingerprint).
- No `Set-Cookie` header — pure client-side, no data leaves the browser.
- Not used for any second purpose (no analytics correlation, no cross-site link).
- The privacy notice discloses its existence and purpose anyway (transparency > minimalism).

Residual risk: if CNIL enforcement view later narrows the "user preference" exemption (unlikely — this is the same category as the widely-accepted cookie-banner-dismiss cookie), the fallback is to move the flag behind the same consent gate as tracking cookies. Cheap to change.

---

## 3. Double opt-in

**Chosen: yes, via Brevo's DOI endpoint** (`POST /v3/contacts/doubleOptinConfirmation`).

CNIL's "prospection commerciale" fact sheet does not *require* DOI explicitly, but does require the controller to **prove** consent. DOI is the CNIL-recommended and industry-standard mechanism for producing that proof (the click on the confirmation link is an unforgeable positive act tied to the recipient's real mailbox). Sources:
- CNIL guidance page above.
- Brevo DOI documentation: https://developers.brevo.com/reference/create-doi-contact.

Without DOI, we'd need to reproduce the same guarantees (server-generated confirmation email, click-through, revalidation) ourselves — reinventing the wheel and adding a new liability surface for zero gain. DOI it is.

---

## 4. Data controller identity

- **Controller:** Jitendra Kumar, individual sole trader (auto-entrepreneur / micro-entrepreneur régime).
- **Real name:** `{{DATA_CONTROLLER_NAME}}` — placeholder to fill (operator).
- **Postal address:** `{{DATA_CONTROLLER_ADDRESS}}` — placeholder to fill. Business address at 22 rue Eugène Manuel, 75016 Paris is already public in the LocalBusiness schema and Google Business Profile; that address is fine if Jitendra prefers not to publish a home address. **Operator to confirm.**
- **Contact for privacy requests:** jitendranitrr13@gmail.com (already public).
- **DPO:** none required. GDPR Art. 37(1) mandates a DPO only if (a) public authority, (b) core activity = large-scale regular monitoring of subjects, or (c) core activity = large-scale processing of Art. 9 special-category or Art. 10 conviction data. A yoga instructor's newsletter meets none of these thresholds. This is documented in the privacy notice.

---

## 5. Storage architecture — decision

### Options considered

| Option | Pros | Cons |
|---|---|---|
| **(a) Brevo (chosen)** | French processor · EU-hosted · SOC 2 II · GDPR-native DPA in dashboard · DOI built-in · one-click unsubscribe header (RFC 8058) built-in · free tier 300 emails/day covers Jitendra's foreseeable volume · Jitendra gets a real UI to write and send campaigns | External processor to list in the notice · needs API key + template setup |
| (b) Cloudflare KV self-hosted + separate transactional email | $0 · full control · no processor to list | Jitendra can't send campaigns from an ordinary email UI · we'd have to build DOI + unsubscribe + rate-limit + suppression list from scratch · we'd become the mailer-of-record for deliverability |
| (c) Cloudflare D1 self-hosted + Mailchannels/Resend | $0 · queryable schema | Same UX gap as (b); D1 gains no DSR advantage over KV at this scale |

### Chosen: **(a) Brevo**

Justifications:

- **DPA and jurisdiction.** Brevo is headquartered in Paris (Sendinblue SAS), servers in EU (France + Germany). Standard DPA published, GDPR-native. Same jurisdiction as the controller — no third-country transfer clauses needed.
- **Cost.** Free tier (300 emails/day, unlimited contacts on some plans; contact-limited on others — verify at signup). Zero €/mo for Jitendra's foreseeable volume. Paid tier starts around €7/mo (Brevo Starter) if needed later.
- **DOI + unsubscribe compliance out of the box.** Brevo's DOI endpoint issues the confirmation email and records the confirmed timestamp; every campaign includes the RFC 8058 `List-Unsubscribe` header + one-click unsubscribe link automatically. Attempting to reproduce this ourselves is a per-week maintenance tax with no user-visible benefit.
- **Data subject rights.** Brevo dashboard exposes contact export + contact delete. Our DSR endpoint calls Brevo's API for the delete, so the two stores stay consistent.

**Local storage (Cloudflare KV) still used for:**

- **Consent proof records** — key `newsletter:consent:<sha256(lowercased_email)>`, value `{ts, ip_hash, ua_hash, consent_text_version, source_url, brevo_response_status}`. TTL 3 years (CNIL commercial-prospection ceiling). Purpose: satisfy Art. 7(1) *demonstrate consent* obligation independently of the processor. Plaintext email is **not** stored in KV — only its SHA-256 — so a KV compromise reveals no addresses.
- **Rate-limit counters** — key `newsletter:rl:<ip-hash>`, TTL 1 hour. Prevents scripted signup floods.

KV region: `location=eu` metadata hint set at namespace-list-or-write time (Cloudflare KV is multi-region by design and does not offer a hard EU-lock; the eu hint biases writes toward EU pops. If hard EU residency ever becomes a requirement, migrate the consent-proof store to D1 with EU region, which does offer region pinning). Documented in the notice as "hébergement Cloudflare — écrit avec préférence de région UE".

---

## 6. Retention

| Object | Location | Retention | Trigger to delete | Source |
|---|---|---|---|---|
| Email + first-name in Brevo list | Brevo | For duration of active subscription | 30 days after unsubscribe (grace period for accidental clicks + Brevo re-add cool-off) | CNIL commercial-prospection guidance |
| Consent proof record | CF KV | 3 years from record creation | KV TTL auto-expires | CNIL "prospection commerciale" — 3 years from last active contact is the CNIL-cited ceiling |
| Rate-limit counter | CF KV | 1 hour | KV TTL auto-expires | — |
| `yj_popup_seen` localStorage flag | Visitor's browser | 30 days from set | Client-side check on read | UX only |

Brevo's own retention: their DPA commits to deleting unsubscribed contacts on the controller's schedule; the operator can configure the 30-day grace-purge in the Brevo dashboard (Settings → Data retention). Documented in the ops runbook (see §11).

---

## 7. Data subject rights (Art. 15–22)

Implemented endpoints under `/api/dsr/`:

- `POST /api/dsr/request-link` — body `{email}`. Function: (i) rate-limits, (ii) generates an HMAC-signed token `{email_sha256, exp_unix}` with 30-min TTL, (iii) sends via Brevo transactional API a magic-link email to the address. **The email is NOT confirmed by the site's own database** — we send the link regardless of subscription status, so a non-subscriber requesting deletion is not silently informed of their absence. Response is always 202 + generic "if this address is registered you'll receive a link" — non-enumerable.
- `GET /api/dsr/:token` — verifies HMAC + expiry, then GETs the Brevo contact + KV consent record and returns them in a JSON view rendered as a simple HTML page.
- `DELETE /api/dsr/:token` — verifies HMAC + expiry, then calls Brevo `DELETE /v3/contacts/{identifier}` + KV.delete on the consent record. Returns 200 + "your data has been deleted" page.

Rights coverage:

- **Access (Art. 15)** → GET endpoint returns everything held.
- **Rectification (Art. 16)** → change of first-name via re-subscribing (or email to Jitendra). Documented in notice.
- **Erasure (Art. 17)** → DELETE endpoint (also every unsubscribe click removes the Brevo record after grace period).
- **Restriction (Art. 18)** → email to Jitendra (rare case; not endpoint-worthy for this scale).
- **Portability (Art. 20)** → GET endpoint's JSON payload is a portable record (email + timestamps + consent text). Documented in notice.
- **Object (Art. 21)** → unsubscribe link in every email = objection to marketing.

---

## 8. Data flow diagram (ASCII)

```
Visitor's browser (yogaavecjitendra.fr)
    │
    ├─(a) First page load → NewsletterPopup renders IF !localStorage.yj_popup_seen
    │
    ├─(b) Skip clicked → localStorage.yj_popup_seen = 1 (30-day soft TTL)
    │                    → popup hides, ZERO server calls
    │
    └─(c) Email entered + consent ticked + Submit
             │
             ▼   POST /api/newsletter-subscribe { email, consent, lang, honeypot }
    ┌───────────────────────────────────────────────────────────────┐
    │  CF Pages Function (EU edge)                                   │
    │   1. Honeypot check → drop silently if triggered              │
    │   2. Rate-limit: KV get(newsletter:rl:<ip-hash>) → 429 if hot │
    │   3. Validate email + consent = true                           │
    │   4. sha256(email) → consent_key                               │
    │   5. KV put(newsletter:consent:<consent_key>, {ts, ip_hash,   │
    │      consent_text_version, source_url}, TTL 3y)               │
    │   6. HTTPS POST → api.brevo.com/v3/contacts/                   │
    │      doubleOptinConfirmation                                   │
    │        { email, includeListIds:[<NEWSLETTER_LIST_ID>],         │
    │          templateId:<DOI_TEMPLATE_ID>,                         │
    │          redirectionUrl:'https://yogaavecjitendra.fr/merci' }  │
    │   7. Return 202 → browser shows "Check your inbox" state       │
    └───────────────────────────────────────────────────────────────┘
             │
             ▼
    Brevo (French processor · sends confirmation email)
             │
             ▼ visitor clicks confirmation link in email
    Brevo marks contact "confirmed" + adds to newsletter list
             │
             ▼
    Jitendra sends periodic campaigns from Brevo UI
    (every email carries List-Unsubscribe + one-click unsub link)

──── DSR flow (independent) ────────────────────────────────────────

Visitor → /privacy/newsletter#gerer-mes-donnees
    │
    ├─ enters email → POST /api/dsr/request-link
    │      ↓ CF Function:
    │      ↓   rate-limit → HMAC(email, exp+30m) → signed_token
    │      ↓   Brevo transactional email → magic link
    │      ↓   returns 202 (generic message, non-enumerable)
    │
    └─ clicks link in email
           ↓ GET /api/dsr/<token>
           ↓   verify HMAC + not expired
           ↓   fetch Brevo contact + KV consent record
           ↓   render HTML with data + [Delete my data] button
           │
           └─ click Delete → DELETE /api/dsr/<token>
                 ↓ verify HMAC + not expired
                 ↓ Brevo DELETE /v3/contacts/<email>
                 ↓ KV.delete(newsletter:consent:<sha256>)
                 ↓ render "Your data has been deleted"
```

---

## 9. Prior-art pass

Per `~/.claude/rules/prior-art-first.md`:

- **Astro / Cloudflare Pages GDPR consent library.** No first-party CNIL-blessed component for Astro exists (`astro-cookieconsent` etc. are cookie-banner libraries, not newsletter-optin libraries; and this popup is **not** a cookie banner — no scripts are conditionally loaded). Building the popup as a native Astro component (~200 lines) is cheaper than importing a library that wouldn't fit the shape.
- **Brevo Astro integration.** Brevo publishes an official Node SDK (`@getbrevo/brevo`) that uses `superagent` under the hood — incompatible with Cloudflare Workers runtime (no `http` module). Community consensus (Brevo Community forum + Cloudflare Discord threads) is to call the REST API directly via `fetch()`. That's what we do.
- **Brevo DOI + Astro examples.** No first-party example. Multiple community write-ups confirm the DOI endpoint works from Workers `fetch()` with `api-key` header; no gotchas.

Conclusion: no library to reuse profitably. Direct REST calls + tiny hand-rolled Astro component is the smallest path.

---

## 10. Files created / modified

**Created** (nothing pushed):

| Path | Purpose |
|---|---|
| `execution/personal_workflows/yoga_jitendra_site/src/components/NewsletterPopup.astro` | The popup component (FR/EN, localStorage-gated, honeypot, skip-first-class) |
| `execution/personal_workflows/yoga_jitendra_site/src/pages/privacy/newsletter.astro` | FR privacy notice + DSR entry point |
| `execution/personal_workflows/yoga_jitendra_site/src/pages/en/privacy/newsletter.astro` | EN privacy notice + DSR entry point |
| `execution/personal_workflows/yoga_jitendra_site/functions/api/newsletter-subscribe.ts` | POST handler: honeypot + rate-limit + KV consent proof + Brevo DOI call |
| `execution/personal_workflows/yoga_jitendra_site/functions/api/dsr/request-link.ts` | POST handler: email → HMAC-signed magic link via Brevo transactional |
| `execution/personal_workflows/yoga_jitendra_site/functions/api/dsr/[token].ts` | GET (view) / DELETE (purge) handler for the DSR magic-link target |
| `execution/personal_workflows/yoga_jitendra_site/docs/gdpr_newsletter_popup_assessment.md` | This document |

**Modified**: none. The popup is not wired into `Base.astro` yet — that's a one-line change the operator applies after confirming copy + provisioning Brevo. Snippet:

```astro
---
import NewsletterPopup from '../components/NewsletterPopup.astro';
// ...
---
<Base ...>
  <!-- existing content -->
  <NewsletterPopup lang={lang} />
</Base>
```

No cron additions. Retention is handled by KV TTLs (rate-limit + consent proof) and by Brevo (subscriber list).

---

## 11. Operator action items (blockers to go-live)

Consolidated so nothing has to round-trip through mid-flight questions.

### 11.1 Brevo setup (do once)

1. Create a free Brevo account at https://www.brevo.com/ (Sendinblue). Set the sender name to Jitendra's real name, sender email to `jitendranitrr13@gmail.com`.
2. Verify sender domain: add the SPF + DKIM DNS records Brevo shows in *Senders, Domains & Dedicated IPs* → *Domains* → *Authenticate this domain*. Skip if fine sending from Gmail.
3. Create a contact list: *Contacts* → *Lists* → **Newsletter FR/EN** (single list is fine; language stored as contact attribute). Note the numeric list ID (top-right on the list detail page).
4. Create a DOI confirmation template: *Campaigns* → *Templates* → *New template* → pick the DOI style. The link inside must reference `{{ params.DOIurl }}`. Content: FR-first with EN below (or two templates if you prefer language switching by attribute — v1 keeps one). Note the numeric template ID.
5. Create a DSR magic-link transactional template: same flow. Body should reference `{{ params.dsrUrl }}`. Note that template ID.
6. Generate an API key: *SMTP & API* → *API keys* → *Generate a new API key*. Copy it immediately (only shown once).

### 11.2 Cloudflare secrets — ONE consolidated command block

Run from `execution/personal_workflows/yoga_jitendra_site/`. Each line prompts for the value once and stores it as an encrypted secret on the yoga-jitendra Pages project.

```bash
# From the yoga_jitendra_site/ directory
cd execution/personal_workflows/yoga_jitendra_site

# Brevo secrets (paste when prompted)
npx wrangler pages secret put BREVO_API_KEY                --project-name yoga-jitendra
npx wrangler pages secret put BREVO_NEWSLETTER_LIST_ID     --project-name yoga-jitendra
npx wrangler pages secret put BREVO_DOI_TEMPLATE_ID        --project-name yoga-jitendra
npx wrangler pages secret put BREVO_DSR_MAGIC_TEMPLATE_ID  --project-name yoga-jitendra

# HMAC signing key for DSR magic-link tokens.
# Generate a 32-byte random hex string, THEN paste it. On Git Bash / WSL:
openssl rand -hex 32 | tee /tmp/dsr_signing_key.txt
npx wrangler pages secret put SUBTLECRYPTO_SIGNING_KEY --project-name yoga-jitendra
# ^ paste the value from /tmp/dsr_signing_key.txt when prompted, then:
shred -u /tmp/dsr_signing_key.txt 2>/dev/null || rm /tmp/dsr_signing_key.txt

# If shred is unavailable on Windows Git Bash, this is fine — the file is
# in tmp and will be wiped on next reboot. Never commit the key.
```

If you'd rather not create a temporary file, do it in one go per key:

```bash
openssl rand -hex 32 | npx wrangler pages secret put SUBTLECRYPTO_SIGNING_KEY --project-name yoga-jitendra
```

(wrangler reads the value from stdin when piped.)

### 11.3 Placeholder fills in the privacy notice

Both `src/pages/privacy/newsletter.astro` (FR) and `src/pages/en/privacy/newsletter.astro` (EN) contain:

- `{{DATA_CONTROLLER_NAME}}` — Jitendra's legal name.
- `{{DATA_CONTROLLER_ADDRESS}}` — public postal address (business address 22 rue Eugène Manuel, 75016 Paris is defensible; personal home address unnecessary).
- `{{DATA_CONTROLLER_SIREN}}` — micro-entrepreneur SIREN if he wants to publish it (optional but reassuring).

Search-and-replace across both files before pushing.

### 11.4 Wire the popup into `Base.astro`

Add one import and one `<NewsletterPopup lang={lang} />` inside `<body>` right before `<slot />` closes. Snippet in §10.

### 11.5 (Optional) rename privacy notice route in Base footer

Add a "Confidentialité (newsletter)" link in `src/components/Footer.astro` pointing to `/privacy/newsletter` (FR) / `/en/privacy/newsletter` (EN). Current footer has no legal links — this is the moment to add one.

---

## 12. Residual risks (honest gaps)

- **Brevo free-tier limits.** 300 emails/day fits current volume (Jitendra sends ≤ 1 campaign/month). If subscriber base grows past ~5k, campaign-send batching may exceed 300/day → upgrade to Brevo Starter (~€7/mo TTC last time checked; operator to verify current pricing). Not a compliance risk, an ops risk.
- **KV region soft-lock.** Cloudflare KV writes are biased toward EU when `location=eu` metadata is set, but not hard-locked. For a plaintext-email store this would be a residency concern; because we only store SHA-256 hashes, exposure risk is low. If a client-side use case ever needs strict EU hard-lock, migrate to D1.
- **HMAC key rotation.** No automated rotation. If suspected compromise, rotate by running the `wrangler pages secret put SUBTLECRYPTO_SIGNING_KEY …` command with a fresh value; in-flight tokens become invalid (30-min max window). Documented in the ops runbook comment inside `dsr/request-link.ts`.
- **Brevo processor breach.** Any processor introduces third-party risk. Brevo's DPA and their 2024 SOC 2 II report are the mitigations. The alternative — self-host — trades processor risk for deliverability risk (getting to inbox from a CF Worker IP is materially harder than from Brevo's warmed pool), which for a personal-scale site is a bigger practical exposure than a processor breach.
- **CNIL narrow-reading of the localStorage exemption.** See §2. Low-probability but non-zero enforcement risk; documented mitigation path is to move the flag behind a consent gate.
- **DSR non-enumerability at Brevo layer.** Our endpoint returns a generic 202 whether or not the email is subscribed, but a determined attacker could still probe by attempting subscription and observing DOI mail arrival. Standard tradeoff for any DOI system; not fixable without breaking DOI itself.
- **Not yet dogfooded end-to-end.** Requires Brevo account + secrets + a wire-up into `Base.astro` + a live subscribe → click → arrive on `/merci` round-trip. Owed after operator finishes §11.1–§11.4.

---

## 13. Privacy notice — FR (text)

**Location:** `src/pages/privacy/newsletter.astro` — the full source is scaffolded there; below is the operator-readable prose only.

---

**Politique de confidentialité — Newsletter**

*Dernière mise à jour : 2026-08-04*

**1. Qui est responsable de vos données ?**

{{DATA_CONTROLLER_NAME}}, professeur de Hatha Yoga exerçant sous le régime de micro-entrepreneur, dont l'adresse professionnelle est {{DATA_CONTROLLER_ADDRESS}} (SIREN {{DATA_CONTROLLER_SIREN}}), agit en qualité de responsable de traitement pour les données collectées via ce site.

Contact pour toute question relative à vos données : jitendranitrr13@gmail.com.

En raison de la taille de l'activité (auto-entrepreneur individuel), la désignation d'un Délégué à la Protection des Données (DPO) n'est pas requise au sens de l'article 37 du RGPD.

**2. Quelles données collectons-nous, et pour quoi faire ?**

Si vous choisissez de vous inscrire à la newsletter via la fenêtre d'invitation, nous collectons :

- votre adresse e-mail ;
- la date et l'heure de votre inscription ;
- votre langue de préférence (FR ou EN), déterminée par la page depuis laquelle vous vous inscrivez ;
- une preuve technique de votre consentement (empreinte HMAC-SHA-256 de votre adresse IP + la version du texte de consentement que vous avez accepté). Nous ne conservons pas votre adresse IP en clair.

**Finalité unique :** vous envoyer occasionnellement (typiquement une fois par mois) des informations sur les cours à venir, y compris les séances adaptées ou accessibles.

**Base légale :** votre consentement (article 6.1.a du RGPD), matérialisé par la coche que vous avez explicitement activée et la validation par lien de confirmation reçu par e-mail (double opt-in).

**3. Petit fichier technique déposé sur votre navigateur**

Lorsque vous fermez la fenêtre d'invitation ou que vous vous inscrivez, un indicateur nommé `yj_popup_seen` est enregistré dans la mémoire locale (`localStorage`) de votre navigateur pour éviter que la fenêtre ne réapparaisse pendant 30 jours. Cet indicateur ne contient que la valeur `1`, ne quitte jamais votre navigateur, et n'a aucune autre finalité. Il est exempté du consentement préalable au titre de l'article 82 de la Loi Informatique et Libertés, catégorie « traceurs strictement nécessaires à la fourniture d'un service explicitement demandé par l'utilisateur » (ici : votre choix de ne plus voir la fenêtre).

**4. Où vos données sont-elles hébergées ?**

- **Adresse e-mail + inscription :** chez Brevo (Sendinblue SAS, société française domiciliée à Paris, serveurs en France et en Allemagne). Voir la politique de confidentialité de Brevo : https://www.brevo.com/fr/legal/privacypolicy/. Un accord de traitement (DPA) conforme au RGPD est en place.
- **Preuve technique de consentement :** chez Cloudflare (Cloudflare Workers KV), avec une préférence de région Union Européenne. Voir : https://www.cloudflare.com/fr-fr/trust-hub/gdpr/.

Aucune donnée n'est transférée en dehors de l'Union Européenne dans le cadre de la newsletter.

**5. Combien de temps conservons-nous vos données ?**

- **Adresse e-mail dans la liste de diffusion :** tant que vous restez inscrit(e). Après désinscription, un délai de grâce de 30 jours (pour prévenir les désabonnements accidentels) puis suppression.
- **Preuve technique de consentement :** 3 ans à compter de votre inscription, conformément à la durée maximale recommandée par la CNIL pour la prospection commerciale par voie électronique.
- **Compteur anti-abus (limite de tentatives d'inscription) :** 1 heure.

**6. Vos droits**

Vous disposez à tout moment des droits suivants sur vos données (articles 15 à 22 du RGPD) :

- **Droit d'accès** : consulter les données que nous détenons sur vous.
- **Droit de rectification** : corriger toute information inexacte.
- **Droit à l'effacement** : demander la suppression complète.
- **Droit à la portabilité** : recevoir vos données dans un format lisible.
- **Droit d'opposition** : refuser de recevoir de nouvelles communications (chaque e-mail contient un lien de désabonnement en un clic).
- **Droit d'introduire une réclamation** auprès de la CNIL : https://www.cnil.fr/fr/plaintes.

**Comment exercer vos droits ?**

- **Rapide :** cliquez sur le lien « Se désinscrire » présent dans tout e-mail reçu — la suppression est immédiate.
- **Complet :** utilisez le formulaire ci-dessous (« Gérer mes données »). Nous vous enverrons un lien magique valable 30 minutes vers une page où vous pourrez consulter ou supprimer vos données.
- **Manuellement :** écrivez à jitendranitrr13@gmail.com.

**7. Modifications de cette politique**

Toute modification substantielle sera indiquée en tête de page (date de mise à jour). Nous vous en informerons par e-mail si la modification affecte la finalité du traitement ou vos droits.

---

## 14. Privacy notice — EN (text)

**Location:** `src/pages/en/privacy/newsletter.astro`.

---

**Privacy notice — Newsletter**

*Last updated: 2026-08-04*

**1. Who's the data controller?**

{{DATA_CONTROLLER_NAME}}, Hatha Yoga instructor operating as an independent sole trader (French *auto-entrepreneur* regime), registered at {{DATA_CONTROLLER_ADDRESS}} (SIREN {{DATA_CONTROLLER_SIREN}}), acts as the controller for the data collected via this website.

For any question about your data: jitendranitrr13@gmail.com.

Given the size of the activity (single sole trader), no Data Protection Officer (DPO) is required under Article 37 GDPR.

**2. What we collect, and why**

If you choose to sign up to the newsletter via the invitation popup, we collect:

- your email address;
- the date and time of your signup;
- your preferred language (FR or EN), inferred from the page you signed up on;
- a technical consent proof (HMAC-SHA-256 fingerprint of your IP + the version of the consent text you accepted). We do not store your IP address in clear.

**Single purpose:** to send you occasional (typically monthly) updates about upcoming sessions, including adapted or accessibility-friendly ones.

**Legal basis:** your consent (GDPR Article 6(1)(a)), evidenced by the checkbox you actively ticked and by the click on the confirmation link we sent by email (double opt-in).

**3. A small technical marker in your browser**

When you dismiss the popup or subscribe, a flag called `yj_popup_seen` is stored in your browser's local storage (`localStorage`) so the popup won't reappear for 30 days. This flag only holds the value `1`, never leaves your browser, and has no other purpose. It is exempt from prior consent under Article 82 of the French Data Protection Act, category "trackers strictly necessary to provide a service explicitly requested by the user" (in this case: your choice not to see the popup again).

**4. Where your data lives**

- **Email + signup record:** at Brevo (Sendinblue SAS, a French company headquartered in Paris, servers in France and Germany). Brevo's privacy policy: https://www.brevo.com/legal/privacypolicy/. A GDPR-compliant Data Processing Agreement is in place.
- **Technical consent proof:** at Cloudflare (Workers KV), written with an EU-region preference. See: https://www.cloudflare.com/trust-hub/gdpr/.

No newsletter-related data is transferred outside the European Union.

**5. How long we keep your data**

- **Email in the mailing list:** as long as you stay subscribed. After you unsubscribe, a 30-day grace period (to catch accidental unsubscribes) then permanent deletion.
- **Consent proof record:** 3 years from your signup, matching CNIL's recommended maximum for commercial email prospection.
- **Anti-abuse rate-limit counter:** 1 hour.

**6. Your rights**

You have the following rights at any time (GDPR Articles 15–22):

- **Access** — see what we hold.
- **Rectification** — correct anything inaccurate.
- **Erasure** — request complete deletion.
- **Portability** — receive your data in a machine-readable format.
- **Object** — decline further messaging (every email carries a one-click unsubscribe).
- **Complaint** — file a complaint with the CNIL: https://www.cnil.fr/en/plaints.

**How to exercise your rights**

- **Fast:** click the "Unsubscribe" link in any email you receive — deletion is immediate.
- **Full:** use the form below ("Manage my data"). We send you a magic link (valid 30 min) to a page where you can view or delete your data.
- **Manually:** email jitendranitrr13@gmail.com.

**7. Changes to this notice**

Any material change will be dated at the top. We'll notify you by email if the change affects the processing purpose or your rights.

---

## 15. Popup + consent copy (verbatim, FR and EN)

### 15.1 FR

- **Title:** *Restez en contact*
- **Body:** *Une fois par mois environ, Jitendra envoie un petit e-mail : cours à venir, ateliers, séances adaptées (notamment pour les personnes sourdes ou malentendantes). Rien d'autre — pas de vente, pas de spam.*
- **Consent checkbox (unticked by default):** *J'accepte de recevoir la newsletter de Yoga avec Jitendra à cette adresse. Je peux me désinscrire à tout moment via le lien présent dans chaque e-mail.*
- **Notice link:** *Vos données restent en Europe — voir la [politique de confidentialité](/privacy/newsletter).*
- **Primary button (subscribe):** *M'inscrire*
- **Skip button (visually prominent, same weight as primary):** *Non merci*
- **Confirmation state after submit:** *Merci ! Vérifiez votre boîte mail — cliquez sur le lien pour finaliser votre inscription.*
- **Error state (generic):** *Une erreur est survenue. Réessayez ou écrivez directement à jitendra.*

### 15.2 EN

- **Title:** *Stay in touch*
- **Body:** *Roughly once a month, Jitendra sends a short email: upcoming classes, workshops, and adapted sessions (including for deaf and hard-of-hearing practitioners). Nothing else — no sales, no spam.*
- **Consent checkbox (unticked by default):** *I agree to receive the Yoga avec Jitendra newsletter at this address. I can unsubscribe any time via the link in every email.*
- **Notice link:** *Your data stays in Europe — see the [privacy notice](/en/privacy/newsletter).*
- **Primary button (subscribe):** *Subscribe*
- **Skip button (visually prominent):** *No thanks*
- **Confirmation state:** *Thanks! Check your inbox — click the link to confirm your subscription.*
- **Error state:** *Something went wrong. Try again or email Jitendra directly.*

---

## 16. Panel-pass self-review

- **Karpathy (evidence):** No live measurement yet — Brevo account not created. Owed benchmark: subscribe → DOI arrive → click → land on /merci → verify Brevo contact + KV consent record both created + hashes match. Recipe: run after §11.1–§11.4.
- **Cherny (dogfood):** Not dogfooded end-to-end (blocked on Brevo secrets). Locally the popup renders; localStorage flag round-trip verified in test file (see §17).
- **Amodei (deployment):** Nothing pushed, nothing deployed. `git status` shows the new files as untracked. Rollback = `git clean -fd execution/personal_workflows/yoga_jitendra_site/src/components/NewsletterPopup.astro execution/personal_workflows/yoga_jitendra_site/src/pages/privacy execution/personal_workflows/yoga_jitendra_site/src/pages/en/privacy execution/personal_workflows/yoga_jitendra_site/functions/api/newsletter-subscribe.ts execution/personal_workflows/yoga_jitendra_site/functions/api/dsr execution/personal_workflows/yoga_jitendra_site/docs/gdpr_newsletter_popup_assessment.md`.
- **Honest-gaps (Amodei/research):** listed in §12.

---

## 17. Owed follow-ups (not blockers, but named)

- **Acceptance test.** Add `tests/acceptance_newsletter.mjs` that (a) POSTs a fake email to a wrangler-dev instance of `/api/newsletter-subscribe`, (b) asserts 202, (c) asserts Brevo received a request (mock via MSW or an env-flag mock branch inside the function). Not in scope for the scaffold — owed once Brevo is live.
- **Front-door synthetic.** Extend the existing dashboard front-door probe to also GET `/privacy/newsletter` (assert 200, contains the string "Politique de confidentialité — Newsletter") and to POST a nonce email + confirm the local KV consent-proof record appears (against a wrangler dev URL, not prod).
- **CNIL 3-year interaction refresh.** If Jitendra sends a campaign, the 3-year consent-proof TTL should reset from "last active contact". KV TTLs are set-and-forget; a "renew consent-proof TTL on campaign send" hook would need a webhook from Brevo → CF Function → KV write. Not built. Documented gap.
