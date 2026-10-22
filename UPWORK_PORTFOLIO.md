# Upwork Portfolio Kit

Copy-paste material for adding this project to your Upwork profile.
Upwork changes its form fields and character limits from time to time, so if a field rejects the text, use the shorter version.

---

## Project title

**Primary:** Website Traffic & Conversion Funnel Analysis | Python, SQL, Power BI

**Shorter:** E-commerce Conversion Funnel Analysis (Python, SQL, Power BI)

## Your role

Data Analyst & Power BI Developer: data cleaning, SQL analysis, funnel analytics, dashboard design and business recommendations.

## Project description

**Short version:**

> Analysed 35,000+ e-commerce sessions to find why visitors don't buy. Cleaned messy tracking data (duplicates,
> inconsistent labels, broken event order) with Python, built a PostgreSQL star schema, and designed a 4-page Power BI
> dashboard with 40+ DAX measures. Found that mobile checkout completes at 37% vs 58% on desktop, and that Paid Social
> drives 20% of traffic but only 10% of revenue. Delivered prioritised, testable recommendations. All numbers
> validated across Python, SQL and DAX (28 automated tests). Synthetic dataset.

**Long version (if the field allows, or for the GitHub link description):**

> **Problem:** An online store had traffic from 7 marketing channels but couldn't tell which ones brought buyers,
> where shoppers dropped out, or whether mobile was under-performing.
>
> **What I did:**
> • Cleaned raw session, event and order exports with Python/pandas: standardised 5,900+ mislabelled values, removed
>   duplicates, quarantined invalid orders, and logged every decision.
> • Built a PostgreSQL star schema and wrote SQL (CTEs, window functions) for channel, device, landing-page and
>   funnel analysis.
> • Built an ordered, session-based conversion funnel that checks event timestamps instead of event presence alone.
> • Designed a Power BI data model and documented 40+ DAX measures and a 4-page dashboard.
> • Validated everything: Python, SQL and DAX definitions agree to the cent; 28 automated tests pass.
>
> **Results:** Biggest drop-off is product view → cart (80%). Mobile checkout completion is 37% vs 58% on desktop.
> Email converts at 6% vs a 2.5% site average. Recommendations come with a KPI to track and an estimated upper bound.
>
> *Built on a realistic synthetic dataset; the same pipeline runs on real GA4 data.*

## Skills / tags to select

Microsoft Power BI · Data Analysis · SQL · Python · PostgreSQL · Data Visualization · Dashboard · DAX ·
Data Cleaning · pandas · Google Analytics · Conversion Rate Optimization · Business Intelligence · Data Modeling ·
Jupyter Notebook

## Images to upload (in this order)

1. `portfolio/01_cover.png`: thumbnail / cover (4:3, 1600×1200)
2. `portfolio/02_mobile_checkout_gap.png`
3. `portfolio/03_channel_efficiency.png`
4. `portfolio/04_landing_pages_and_quality.png`
5. **Your own Power BI screenshots** from `screenshots/` once you've built the report (see below). These are the most persuasive images for Power BI jobs.

Add the GitHub repository link as the project URL.

---

## Before you publish: three things that matter

**1. Build the Power BI report yourself.** Most Power BI job posts want to see a real dashboard. The specs in `powerbi/`
let you build it in about 2–3 hours, and the expected values in `dax_measures.md` tell you when it's right. Then replace or
supplement the portfolio images with real screenshots. Don't upload the wireframes as if they were the dashboard; they
are watermarked as illustrative for that reason.

**2. Know it well enough to explain it on a call.** Clients often ask about portfolio projects in interviews. Walk through
the notebooks and be ready for questions like the ones below. Being able to answer them fluently is what turns this
project into credibility.

**3. Keep the synthetic-data disclosure.** Clients respect it, and it's already in the description above. Presenting
synthetic results as a real client engagement would be misleading and could breach Upwork's terms.

## Likely client questions and where the answers are

| Question | Answer in brief | Details |
|---|---|---|
| "Why do your two purchase numbers differ (913 vs 888)?" | One counts valid orders (for revenue KPIs); the other counts correctly-ordered journeys (for funnel diagnosis). The 25-session gap is fully reconciled. | Notebook 03 §3 |
| "How do you stop revenue from doubling in Power BI?" | Separate fact tables at their own grain, each related directly to the dimensions; no fact-to-fact joins; DISTINCTCOUNT for purchasing sessions. | `powerbi/data_model.md` |
| "Isn't the mobile gap just because mobile traffic is from social?" | No. Mobile under-converts desktop within every channel. | Notebook 02 §4, `sql/06` 6.2 |
| "How did you handle bad data?" | Standardise, de-duplicate after parsing timestamps, quarantine instead of deleting, log every step. | Notebook 01 |
| "How do you know your numbers are right?" | Python, SQL and DAX definitions reconcile; 28 tests + 20 SQL assertions. | `reports/metrics/reconciliation.md` |
| "Will your recommendations increase revenue by X%?" | The ~$12k figure is an upper bound to prioritise testing, not a promise; changes should be A/B tested. | `reports/business_recommendations.md` |

## Optional: a matching Project Catalog offer

*"I will analyse your website or Shopify traffic and build a conversion funnel dashboard in Power BI"*:
the deliverables in this repo (cleaning, funnel analysis, channel scorecard, dashboard, recommendations) map directly
onto a fixed-scope offer.
