# Extract services — business.json service list + tagline

Used by: `preview/extract_services.py` (§7 of `PROJECT_SPEC.md`). Model: `claude-sonnet-5`, `temperature=0`.
Feeds `business.json.services[]` and `business.json.tagline` (see `CONTRACTS.md`).

## Inputs

- `{{site_text}}` — plain text scraped from the business's current website (may be empty string if the site
  is unreachable or has no website; in that case infer from `{{primary_type}}` and `{{business_name}}` alone).
- `{{primary_type}}` — Google Places `primaryType` for this business (e.g. `spa`, `beauty_salon`).
- `{{business_name}}` — the business's name, plain text.

## Rules

1. Choose **3 to 8** services, and **only** from this fixed allowed list — never invent a service name outside
   it:
   `Botox / Neuromodulators`, `Dermal Fillers`, `Laser Hair Removal`, `Chemical Peels`, `Microneedling`,
   `HydraFacial`, `IPL / Photofacial`, `Body Contouring`, `Skin Tightening`, `PRP / PRF`, `Weight Management`,
   `Facials`, `IV Therapy`, `Laser Skin Resurfacing`, `Acne Treatment`.
   Prefer services that `{{site_text}}` actually mentions; when `{{site_text}}` is empty or thin, choose the
   most common med-spa services consistent with `{{primary_type}}`.
2. Each service gets an `icon` key from this fixed set only: `syringe`, `sparkle`, `laser`, `droplet`, `leaf`,
   `sun`, `body`, `needle`, `scale`, `flask`. Reuse an icon across services if needed; never emit a key outside
   this set.
3. Each `blurb` is a **generic 6–10 word call to action**, no medical claims, no outcomes, no prices, no
   promises. Pattern example: `"Schedule a consultation to see if it's right for you."` Vary the CTA wording
   across services in the same output (do not repeat the same blurb verbatim for every entry).
4. `tagline`: **9 words or fewer**, about booking convenience only (e.g. speed, ease, being able to book
   online/after hours). No superlatives ("best", "premier", "top-rated", "#1", "leading"), no medical claims.
5. **Forbidden terms** — must not appear anywhere in `services[].blurb` or `tagline` (case-insensitive):
   `cure`, `guaranteed results`, `permanent`, `FDA approved`, `safe for everyone`, `no side effects`,
   `clinically proven`, `before/after`, `before and after`, and any dollar amount or price.

## Output — strict JSON only

Return **only** a single JSON object. No prose, no markdown code fences, no explanation before or after.

```json
{
  "services": [
    {"name": "Botox / Neuromodulators", "blurb": "Schedule a consultation to see if it's right for you.", "icon": "syringe"}
  ],
  "tagline": "Book your next treatment in under a minute."
}
```

- `services`: array of 3–8 objects, each `{"name", "blurb", "icon"}` as constrained above.
- `tagline`: string, ≤ 9 words.

Business: {{business_name}} ({{primary_type}})

Site text:
{{site_text}}
