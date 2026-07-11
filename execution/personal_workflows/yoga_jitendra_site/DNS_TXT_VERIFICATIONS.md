# Verification setup — GSC + Bing + Ahrefs

Refined path — HITL for Debanjan minimized to **2 copy-pastes total** by using GSC's meta-tag method + Bing's GSC-import instead of the 3× DNS-TXT-per-platform approach.

Total time: ~5 minutes.

---

## 1. Google Search Console — already verified as Domain property (2026-07-11)

Debanjan opened GSC and it went straight to a verified `sc-domain:yogaavecjitendra.fr` property — pre-existing setup (likely from an earlier Cloudflare↔Google DNS integration or a prior verification). No action needed.

**Only remaining GSC action (~30 sec):**
Left nav → Sitemaps (under Indexing) → paste `sitemap-index.xml` → Submit.

Do NOT submit `sitemap-0.xml` separately — the index file references it.

The "Processing data, please check again in a day or so" banner on Overview + Enhancements is normal GSC latency after fresh verification. Impressions/clicks data starts appearing in 2-4 weeks; index coverage in 1-3 days.

---

## 2. Bing Webmaster Tools (~1 min) — import from GSC

1. Sign in at [bing.com/webmasters](https://www.bing.com/webmasters) with the same Google account.
2. Click **Import from Google Search Console** (top banner or Sites → Import).
3. Authenticate → select `yogaavecjitendra.fr` → Import.

Bing pulls the property + your sitemaps automatically. No separate verification.

---

## 3. Ahrefs Webmaster Tools (~2 min) — DNS TXT, unlocks free Site Audit

Only tool that genuinely needs DNS. Two paths:

### 3a — you do the CF DNS click yourself (~2 min)
1. [ahrefs.com/webmaster-tools](https://ahrefs.com/webmaster-tools) → sign in → Add website `yogaavecjitendra.fr` → verify via **DNS TXT**.
2. Ahrefs shows a TXT value like `ahrefs-site-verification_abc123`.
3. Cloudflare Dashboard → `yogaavecjitendra.fr` zone → DNS → Records → Add:
   - Type `TXT`, Name `@`, Content = paste the string, TTL Auto, Save.
4. Back in Ahrefs → Verify → start a Site Audit.

### 3b — I add it via the CF API for you (~30 sec of your time)
Only works if you paste me a Cloudflare API token with `Zone.DNS Edit` permission for the yogaavecjitendra.fr zone.
1. CF dashboard → My Profile → API Tokens → Create Token → "Edit zone DNS" template → limit to `yogaavecjitendra.fr` → Create.
2. Paste the token into `.env` as `CF_DNS_EDIT_TOKEN=…` (I'll read it, never echo it back).
3. Get the Ahrefs TXT value from step 3a.1 above, paste to me.
4. I add the record via the CF API.

**Recommend 3a** unless you're setting up a lot of tools regularly — 3b needs a token you'd otherwise not need.

---

## After all three verified

Ping me and I'll:
- Confirm sitemap coverage in GSC (Coverage report shows N pages indexed).
- Kick off the first weekly `SEO_TRACKING.md` snapshot.
- Optionally wire IndexNow via a small Cloudflare Worker so every deploy auto-pings Bing.

---

## Skip / defer

- **Yandex Webmaster** — irrelevant for FR/EN Paris audience.
- **GSC Domain-property upgrade** — defer until subdomains exist.
- **Ahrefs paid tiers** — free tier is enough for a solo-teacher site.
