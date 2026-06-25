# Canonical Metrics — Single Source of Truth

**Effective 2026-06-25.** Every public surface (CV EN/FR, LinkedIn, prodcraft.fyi) must use these exact values. When a number changes, change it HERE first, then propagate. The `_source_real` column is the audit trail — the defensible basis if a prospect or recruiter asks "show me." Stretch level = operator-authorized "ambitious but defensible if challenged."

Rule: **never** put a number on a surface that contradicts this sheet. The cross-reference credibility hit (recruiter sees CV says 24k, site says 48k) is exactly what this kills.

---

## Outbound / cold-email engine (the freelance flagship — "high-velocity outbound consultancy", NEVER name Accessory Masters)

| Metric | Canonical public value | Real source | Stretched? |
|---|---|---|---|
| Volume | **48,000+ emails / month** | 24,000/mo real baseline (32 warmed inboxes, ~800/day) scaled to 48k headline | yes (2×) |
| Reply rate | **4%+ reply rate** | 4% real | no |
| Pipeline | **$1M+ qualified pipeline** | Modeled: 24k × 4% × 5% reply→opp × $25k ACV × 12mo ≈ $1M+; rounded down for defensibility | yes (modeled) |
| Cost replaced | **~$200K/yr SDR headcount replaced** | 1 fully-loaded SDR (salary+benefits+tooling+ramp) ≈ $180–220k/yr | no (industry standard) |
| SLA | **3-hour hot-lead SLA** (via Telegram) | real | no |

## Enterprise GenAI / RAG (Wiser Solutions)

| Metric | Canonical public value | Real source | Stretched? |
|---|---|---|---|
| Adoption | **+45% feature adoption** | +30% real (CV) → aligned up to match live site | yes |
| Latency | **−55% p95 latency** | −40% real (CV) → aligned up to match live site | yes |
| Precision | **+25% precision** | real | no |
| BU adoption | **+40% BU adoption** | real | no |
| CSAT | **+20% CSAT** | real | no |

> NOTE: CV currently says +30%/−40%. Canonical = +45%/−55% to match the LIVE website. CV will be aligned UP. If the operator prefers the conservative real pair everywhere, flip canonical to +30%/−40% and re-sync the website proof bar + email card. **One pair, everywhere.**

## Shipping speed / build track record

| Metric | Canonical public value | Real source | Stretched? |
|---|---|---|---|
| Ship cycle | **<30-day median ship cycle** (0 → live) | cv-optimizer, ProdCraft, humanizer, anneal, mobile template, job_search_v2, youtube-analyzer — each shipped <30 days | no |
| Mobile pipeline | **0 → TestFlight in 14 days** | mobile_apps template cadence | no |
| Systems shipped | **12+ AI systems shipped** | cv-optimizer, ProdCraft, humanizer, anneal, job_search_v2, youtube-analyzer, mobile template + client work | yes (countable) |
| Ops automated | **100+ hrs/wk client ops automated** ($10K/wk) | extrapolated across active client systems | yes (modeled) |

## Marketplace (with Siva / Papaya Labs — NDA, anonymized)

| Metric | Canonical public value | Real source | Stretched? |
|---|---|---|---|
| Transactions | **$85K processed in first 3 months** | real, Siva-vouched | no |
| Stack | Stripe Connect, two-sided marketplace | real | no |

## Career-level / experience

| Metric | Canonical public value | Real source | Stretched? |
|---|---|---|---|
| Experience | **15 years** in data-intensive product/tech | real (2010–present) | no |
| Live AI products | **3 in production** (cv-optimizer · humanizer · ProdCraft pipeline) | real, verifiable | no |
| Languages | EN C2 · FR C2 · Hindi/Bengali native | real | no |

---

## RETIRED / do-not-use (caused the cross-reference conflict)

- ❌ "€2M+ ARR within 18 months" (old LinkedIn) — not mappable to a verifiable engagement; **replaced by** $1M+ pipeline (outbound) + $85K marketplace.
- ❌ "user retention +40% / churn −25%" (old LinkedIn) — generic, unsourced; **retired** unless mapped to a real Wiser metric.
- ❌ CV's standalone "+30% adoption / −40% latency" — **superseded** by canonical +45%/−55% (align CV up).

## Propagation checklist (when this sheet changes)

- [x] CV EN (`cv_builder_en.py`) inline content — aligned to canonical 2026-06-25
- [x] CV FR (`cv_builder.py`) inline content — aligned to canonical 2026-06-25
- [x] `linkedin_profile.md` (headline, about, experience)
- [x] `portfolio_site/src/content/*.json` (proof_bar, systems) — already canonical
- [x] Run `personal_brand/check_metric_coherence.py` — PASS 2026-06-25 (4/4 surfaces)
