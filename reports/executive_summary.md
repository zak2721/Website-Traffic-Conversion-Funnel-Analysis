# Executive Summary: Website Traffic & Conversion Funnel Analysis

> **Synthetic data.** Figures describe a generated e-commerce dataset (Jan–Jun 2025, seed 42) built to demonstrate the
> method. They are not the performance of any real company.

## Headline numbers (1 Jan – 30 Jun 2025)

| Sessions | Visitors | Engagement rate | Purchasing sessions | Conversion rate | Revenue | AOV | Revenue / session |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 35,822 | 25,729 | 72.2% | 913 | 2.55% | $64,207 | $70.33 | $1.79 |

All figures are reconciled across Python, PostgreSQL and the DAX measure definitions (`reports/metrics/reconciliation.md`).

## Answers to the business questions

**1. Which channels generate the most traffic?**
Organic Search (11,480 sessions, 32.0%), then Paid Social (7,071, 19.7%), Direct (5,847, 16.3%) and Paid Search (5,605, 15.6%).

**2. Which channels generate the most purchasing sessions?**
Organic Search (232), Paid Search (223) and Direct (173). Together they produce 69% of all purchasing sessions.

**3. Which channels convert most efficiently?**
Email (6.04% conversion, $4.31 per session) and Paid Search (3.98%, $2.80). Paid Search earns as much revenue as
Organic Search ($15.7k each) from half the sessions. The least efficient are Organic Social (0.81%) and Paid Social
(1.19%, $0.90 per session). Paid Social takes 19.7% of sessions but returns 9.9% of revenue. The 95% confidence intervals of the top two
(Email, Paid Search) and bottom two (Paid Social, Organic Social) do not overlap with each other, so the ranking between those groups
is not sampling noise. (The two social channels cannot be separated from each other.)

**4. Where does the largest funnel drop-off occur?**
*Product view → add to cart*: 80.1% of product-viewing sessions never add an item (15,516 sessions lost).
In absolute terms, the first step (session → product view) loses slightly more (16,445 sessions), but much of that
is expected blog and bounce traffic. After the cart, about half of sessions are lost at each remaining step.

**5. Does mobile perform differently from desktop?**
Yes, substantially. Mobile is 55% of sessions but 35% of revenue. Its conversion rate (1.66%) is less than half of
desktop's (3.76%). The gap sits late in the funnel: checkout → purchase is **37.0% on mobile vs 57.5% on desktop**.
Mobile starts almost as many checkouts as desktop (866 vs 873) but completes far fewer (320 vs 502). Mobile under-converts
desktop in every channel, so this is not explained by mobile traffic coming from weaker channels.

**6. Which landing pages should be investigated?**
Four pages carry ≥ 2% of sessions and convert significantly below the site average:
`/collections/sale` (4,934 sessions, 2.01%), `/blog/how-to-choose-running-shoes` (0.96%),
`/blog/summer-style-guide` (0.54%) and `/campaign/spring-sale` (0.60%). The blog pages are content pages, and low
direct conversion is expected there. The sale and campaign pages are commercial pages and are the priority.
Product detail pages are the strongest entry points (≈4% conversion).

**7. What actions could improve conversion and revenue?**
In priority order (details in `business_recommendations.md`):
1. **Fix the mobile checkout.** It is the largest measurable gap. An upper-bound scenario (mobile matching desktop's
   checkout completion) is ≈178 extra orders / ≈$12.2k over the six months. This is a ceiling to test against, not a forecast.
2. **Rebalance and retarget Paid Social.** Cut or rework the `spring_sale` (0.29%) and `prospecting` (0.95%) campaigns;
   shift budget toward retargeting and test landing users on product pages rather than the campaign page.
3. **Scale proven high-intent programmes:** abandoned-cart email (7.28%), brand search (4.61%).
4. **Rework `/collections/sale` and the spring-sale page** (offer clarity, product relevance, add-to-cart prominence).
5. **Give blog traffic a path to products** and measure assisted conversions before judging it on last-click.

## What the data cannot tell us
These findings show *where* customers leave, not *why*. Channel and campaign comparisons are observational.
Audiences differ, so differences are associations, not causal effects. Every recommendation should be validated
with an A/B test or a holdout. See `limitations.md`.
