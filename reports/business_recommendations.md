# Business Recommendations

> Synthetic data. Each recommendation lists the **observed finding** (calculated), the **interpretation**
> (a hypothesis unless stated otherwise), and **how to measure success**. No recommendation promises a specific uplift.
> Opportunity sizes are upper-bound scenarios from `reports/metrics/opportunity_sizing.csv`.

---

## R1. Simplify and de-risk the mobile checkout  (Priority: High)

| | |
|---|---|
| **Observed finding** | Mobile checkout → purchase completion is 37.0% vs 57.5% on desktop. Cart → checkout is also lower (44.2% vs 52.9%). |
| **Supporting metrics** | Mobile: 866 checkouts → 320 purchases. Desktop: 873 → 502. Mobile CVR is below desktop in all 7 channels (`device_within_channel.csv`). |
| **Interpretation** | The user has already shown purchase intent, so the loss is likely friction in the mobile checkout (form length, payment options, errors, speed). *Hypothesis: the data shows where users leave, not why.* |
| **Recommended action** | (1) Review session recordings and form analytics for mobile checkout. (2) Add express wallets (Apple Pay / Google Pay) and guest checkout. (3) A/B test a shorter mobile checkout. |
| **KPI to track** | Mobile `Checkout → Purchase %` (primary); mobile `Purchase Conversion Rate`; mobile `Revenue per Session`. |
| **Size of prize (upper bound)** | If mobile matched desktop completion: ≈178 more orders, ≈$12.2k over Jan–Jun. A realistic test target is a fraction of this. |
| **Uncertainty** | Desktop users may differ in intent, so full parity may be unattainable. Tablet results rest on small samples. |

## R2. Re-target and re-balance Paid Social spend  (Priority: High)

| | |
|---|---|
| **Observed finding** | Paid Social: 19.7% of sessions, 9.9% of revenue, 1.19% CVR, $0.90 per session vs $1.79 site average. |
| **Supporting metrics** | `spring_sale` campaign 0.29% CVR (1,362 sessions); `prospecting` 0.95%; `retargeting` 1.84%. View → cart for Paid Social is 11.1% vs 19.9% overall. |
| **Interpretation** | Social visitors engage (74% engagement) but rarely add to cart. That points to audience/offer mismatch rather than a site defect. *Hypothesis.* |
| **Recommended action** | Pause or rework `spring_sale` creative and targeting. Shift budget from prospecting toward retargeting. Test sending social clicks to product pages (≈4% CVR) instead of the campaign page (0.60%). |
| **KPI to track** | Paid Social `Revenue per Session`, `Product View → Cart %`, and cost per purchase (requires ad-spend data). |
| **Size of prize (upper bound)** | Closing half the CVR gap to site average: ≈48 orders, ≈$3.6k over Jan–Jun. |
| **Uncertainty** | No cost data is available, so ROAS cannot be calculated. A low-converting channel may still be profitable if cheap, or may drive later direct/organic purchases (last-click attribution). |

## R3. Scale high-intent programmes that already work  (Priority: Medium)

| | |
|---|---|
| **Observed finding** | Abandoned-cart email converts at 7.28% ($5.16 per session). Brand search at 4.61%. Weekly newsletter at 4.82%. |
| **Supporting metrics** | Email = 6.7% of sessions but 16.1% of revenue. |
| **Interpretation** | These audiences already know the brand or the product. Reaching more of them is likely efficient, but returns diminish as volume grows. |
| **Recommended action** | Extend abandoned-cart triggers (e.g. abandoned *checkout*, browse abandonment); grow the email list via blog pages; protect brand-search coverage. |
| **KPI to track** | Email sessions, Email `Purchase Conversion Rate`, list growth. |
| **Uncertainty** | High CVR partly reflects audience selection; incremental impact should be measured with a holdout group. |

## R4. Fix the under-converting commercial landing pages  (Priority: Medium)

| | |
|---|---|
| **Observed finding** | `/collections/sale`: 4,934 sessions (2nd highest), 2.01% CVR, 8.6% add-to-cart rate. `/campaign/spring-sale`: 0.60% CVR, 3.4% add-to-cart despite 76% engagement. |
| **Supporting metrics** | Both flagged: ≥ 2% of sessions and 95% CI upper bound below the 2.55% site rate. |
| **Interpretation** | Visitors browse but do not find something worth adding to cart (assortment, sizing availability, price clarity). *Hypothesis.* |
| **Recommended action** | Audit stock/size availability on sale items; surface best-sellers first; make add-to-cart available from the listing; test clearer discount messaging. |
| **KPI to track** | Page `Add-to-Cart Rate` and `Purchase Conversion Rate` (Page 4 of the dashboard). |
| **Uncertainty** | Page performance is confounded with the channels that feed it (the spring-sale page is mostly Paid Social). |

## R5. Connect blog content to products  (Priority: Low / strategic)

| | |
|---|---|
| **Observed finding** | Two blog posts bring 7,278 organic sessions (20% of all traffic) with ~51% engagement and 0.5–1.0% CVR. |
| **Interpretation** | Blogs are top-of-funnel. Last-click conversion understates their value, but there is clearly no strong path to products. |
| **Recommended action** | Add contextual product links and email sign-up to posts; track blog → product-view rate and assisted conversions. |
| **KPI to track** | Blog `Session → Product View %`, email sign-ups from blog, assisted conversions (needs multi-session attribution). |
| **Uncertainty** | Current data uses last-click, session-level attribution only. |

---

## Suggested measurement plan
1. Add the Power BI Page 3 device funnel to the weekly trading meeting.
2. Run R1 and R2 as controlled experiments (A/B or geo/audience holdout) with pre-registered success metrics.
3. Bring in ad-spend data so channel decisions can use cost per purchase and ROAS, not just conversion rate.
