# DAX Measure Library

Create a table named `_Measures` (Home → Enter data → one column → load → hide the column) and add the
measures below to it, grouped into **display folders** as listed. Every rate uses `DIVIDE()`, so a zero or blank
denominator returns BLANK instead of an error or infinity.

Expected values for the full period with no slicers (synthetic data, seed 42) are given so the report can be
checked against `reports/metrics/reconciliation.md` after it is built.

**Golden rules applied throughout**

* Session KPIs count **rows of `FactSessions`** (one row = one session), never events.
* Purchasing sessions = `DISTINCTCOUNT(FactTransactions[session_id])`, so a session with two orders counts once.
* Revenue comes only from `FactTransactions` (valid transactions; quarantined rows are not loaded), so it cannot be duplicated by event rows.
* All measures respond to DimDate, DimTrafficSource, DimDevice and DimLandingPage filters because every fact table relates to every dimension directly.

---

## 1. Traffic  (folder `1 Traffic`)

```DAX
Total Sessions =
COUNTROWS ( FactSessions )
```
*Numerator:* session rows · *Grain:* session · *Filters:* all dimensions · *Format:* `#,0` · **Expected: 35,822**

```DAX
Total Visitors =
DISTINCTCOUNT ( FactSessions[visitor_id] )
```
*Grain:* visitor · *Note:* non-additive. Monthly visitors do not sum to the period total, because a returning visitor is counted once per period. · `#,0` · **Expected: 25,729**

```DAX
Engaged Sessions =
CALCULATE ( [Total Sessions], FactSessions[engaged_session] = 1 )
```
`#,0` · **Expected: 25,853**

```DAX
Engagement Rate =
DIVIDE ( [Engaged Sessions], [Total Sessions] )
```
*Numerator:* engaged sessions · *Denominator:* all sessions · `0.0%` · **Expected: 72.2%**

```DAX
Events (not sessions) =
COUNTROWS ( FactEvents )
```
For event-frequency visuals only. **Never** use as a session count. · `#,0`

---

## 2. Funnel stage counts  (folder `2 Funnel`)

All read the pre-computed, **ordered** stage flags (see `python/metrics.py` for the definition). Each session counts at most once per stage.

```DAX
Product-Viewing Sessions =
SUM ( FactSessions[reached_product_view] )
```
**Expected: 19,377**

```DAX
Add-to-Cart Sessions =
SUM ( FactSessions[reached_add_to_cart] )
```
**Expected: 3,861**

```DAX
Checkout Sessions =
SUM ( FactSessions[reached_checkout] )
```
**Expected: 1,851**

```DAX
Funnel Purchase Sessions =
SUM ( FactSessions[reached_purchase] )
```
Event-based, ordered purchase stage. **Expected: 888**. This differs from `[Purchasing Sessions]` (913) by design; see §8.

---

## 3. Conversion  (folder `3 Conversion`)

```DAX
Purchasing Sessions =
DISTINCTCOUNT ( FactTransactions[session_id] )
```
*Grain:* session · Transaction-based (source of truth for executive KPIs) · `#,0` · **Expected: 913**

```DAX
Purchase Conversion Rate =
DIVIDE ( [Purchasing Sessions], [Total Sessions] )
```
*Numerator:* sessions with ≥1 valid transaction · *Denominator:* all sessions · `0.00%` · **Expected: 2.55%**

```DAX
Add-to-Cart Rate =
DIVIDE ( [Add-to-Cart Sessions], [Total Sessions] )
```
*Numerator:* sessions reaching the add-to-cart stage · *Denominator:* all sessions · `0.0%` · **Expected: 10.8%**

```DAX
Checkout Completion Rate =
DIVIDE ( [Funnel Purchase Sessions], [Checkout Sessions] )
```
*Numerator:* sessions completing purchase after checkout · *Denominator:* sessions that started checkout · `0.0%` · **Expected: 48.0%**

```DAX
Funnel Completion Rate =
DIVIDE ( [Funnel Purchase Sessions], [Total Sessions] )
```
`0.00%` · **Expected: 2.48%**

### Stage-to-stage rates (explicit, for cards and tables)

```DAX
Session → Product View % = DIVIDE ( [Product-Viewing Sessions], [Total Sessions] )
Product View → Cart %    = DIVIDE ( [Add-to-Cart Sessions], [Product-Viewing Sessions] )
Cart → Checkout %        = DIVIDE ( [Checkout Sessions], [Add-to-Cart Sessions] )
Checkout → Purchase %    = DIVIDE ( [Funnel Purchase Sessions], [Checkout Sessions] )
```
Expected: 54.1% · 19.9% · 47.9% · 48.0% (format `0.0%`). Drop-off for each = `1 -` the rate. Example:

```DAX
Product View → Cart Drop-off % =
VAR _rate = [Product View → Cart %]
RETURN IF ( NOT ISBLANK ( _rate ), 1 - _rate )
```
**Expected: 80.1%**. Create the other three drop-offs the same way.

---

## 4. Revenue  (folder `4 Revenue`)

```DAX
Total Revenue =
SUM ( FactTransactions[revenue] )
```
Gross purchase revenue (completed + refunded) · `$#,0` · **Expected: $64,206.74**

```DAX
Net Revenue =
CALCULATE ( [Total Revenue], FactTransactions[transaction_status] = "completed" )
```
Excludes refunded orders · **Expected: $62,536.95**

```DAX
Refunded Revenue =
CALCULATE ( [Total Revenue], FactTransactions[is_refunded] = 1 )
```

```DAX
Total Transactions =
DISTINCTCOUNT ( FactTransactions[transaction_id] )
```
`#,0` · **Expected: 913**

```DAX
Average Order Value =
DIVIDE ( [Total Revenue], [Total Transactions] )
```
*Numerator:* gross revenue · *Denominator:* distinct transactions · `$#,0.00` · **Expected: $70.33**

```DAX
Revenue per Session =
DIVIDE ( [Total Revenue], [Total Sessions] )
```
*Numerator:* gross revenue · *Denominator:* all sessions · `$#,0.00` · **Expected: $1.79**

```DAX
Revenue (Transaction Date) =
CALCULATE (
    [Total Revenue],
    USERELATIONSHIP ( FactTransactions[transaction_date_key], DimDate[date_key] )
)
```
Finance view: revenue on the order date via the inactive relationship. Equals `[Total Revenue]` over the full period; daily values differ only for orders that crossed midnight.

```DAX
Share of Revenue =
DIVIDE ( [Total Revenue], CALCULATE ( [Total Revenue], REMOVEFILTERS ( DimTrafficSource ) ) )

Share of Sessions =
DIVIDE ( [Total Sessions], CALCULATE ( [Total Sessions], REMOVEFILTERS ( DimTrafficSource ) ) )
```
Share within the current date / device / page selection, across channels.

---

## 5. Period comparison  (folder `5 Time Intelligence`)

"Previous period" = the period of **equal length immediately before** the selected date range (e.g. selecting
1–30 Apr compares with 2–31 Mar). This works for any slicer selection, not just whole months.

```DAX
Previous-Period Sessions =
VAR _start = MIN ( DimDate[date] )
VAR _end   = MAX ( DimDate[date] )
VAR _days  = DATEDIFF ( _start, _end, DAY ) + 1
RETURN
    CALCULATE (
        [Total Sessions],
        REMOVEFILTERS ( DimDate ),
        DATESBETWEEN ( DimDate[date], _start - _days, _start - 1 )
    )
```

```DAX
Previous-Period Revenue =
VAR _start = MIN ( DimDate[date] )
VAR _end   = MAX ( DimDate[date] )
VAR _days  = DATEDIFF ( _start, _end, DAY ) + 1
RETURN
    CALCULATE (
        [Total Revenue],
        REMOVEFILTERS ( DimDate ),
        DATESBETWEEN ( DimDate[date], _start - _days, _start - 1 )
    )
```

```DAX
Sessions Growth % =
VAR _prev = [Previous-Period Sessions]
RETURN IF ( NOT ISBLANK ( _prev ), DIVIDE ( [Total Sessions] - _prev, _prev ) )
```

```DAX
Revenue Growth % =
VAR _prev = [Previous-Period Revenue]
RETURN IF ( NOT ISBLANK ( _prev ), DIVIDE ( [Total Revenue] - _prev, _prev ) )
```
Format `+0.0%;-0.0%;0.0%`. Returns BLANK when there is no prior data (e.g. the first period in the dataset), so it never displays a misleading +∞ or −100%.

*Expected with the date slicer set to 1–31 Mar 2025: the previous period is the 31 days from 29 Jan to 28 Feb, so Sessions Growth = **+15.6%** (6,569 vs 5,681) and Revenue Growth = **−3.1%** ($9,857 vs $10,172). For calendar month vs calendar month (+28.2% sessions, +8.1% revenue) use the `PM` measures below.*

Month-over-month variants for monthly trend charts (where the axis is `DimDate[year_month]`):

```DAX
Sessions PM = CALCULATE ( [Total Sessions], DATEADD ( DimDate[date], -1, MONTH ) )
Revenue PM  = CALCULATE ( [Total Revenue],  DATEADD ( DimDate[date], -1, MONTH ) )

Sessions MoM % =
VAR _prev = [Sessions PM]
RETURN IF ( NOT ISBLANK ( _prev ), DIVIDE ( [Total Sessions] - _prev, _prev ) )

Revenue MoM % =
VAR _prev = [Revenue PM]
RETURN IF ( NOT ISBLANK ( _prev ), DIVIDE ( [Total Revenue] - _prev, _prev ) )
```
*Expected on a monthly axis: Mar 2025 Sessions MoM **+28.2%**, Revenue MoM **+8.1%**; Jan 2025 is BLANK.*

---

## 6. Funnel visual helpers  (folder `6 Funnel Visual`)

Put `DimFunnelStage[stage_name]` (sorted by `stage_order`) on the axis of a bar chart or matrix, then use:

```DAX
Funnel Stage Sessions =
SWITCH (
    SELECTEDVALUE ( DimFunnelStage[stage_order] ),
    1, [Total Sessions],
    2, [Product-Viewing Sessions],
    3, [Add-to-Cart Sessions],
    4, [Checkout Sessions],
    5, [Funnel Purchase Sessions]
)
```

```DAX
Funnel Next Stage Sessions =
SWITCH (
    SELECTEDVALUE ( DimFunnelStage[stage_order] ),
    1, [Product-Viewing Sessions],
    2, [Add-to-Cart Sessions],
    3, [Checkout Sessions],
    4, [Funnel Purchase Sessions]
)  -- BLANK for the final stage
```

```DAX
Funnel % of Sessions   = DIVIDE ( [Funnel Stage Sessions], [Total Sessions] )
Stage Conversion to Next % = DIVIDE ( [Funnel Next Stage Sessions], [Funnel Stage Sessions] )

Stage Drop-off % =
VAR _c = [Stage Conversion to Next %]
RETURN IF ( NOT ISBLANK ( _c ), 1 - _c )

Stage Sessions Lost =
VAR _next = [Funnel Next Stage Sessions]
RETURN IF ( NOT ISBLANK ( _next ), [Funnel Stage Sessions] - _next )
```

```DAX
Largest Drop-off Stage (%) =
VAR _t =
    ADDCOLUMNS (
        ALL ( DimFunnelStage[stage_order], DimFunnelStage[stage_name] ),
        "@drop", [Stage Drop-off %]          -- context transition per stage row
    )
VAR _top = TOPN ( 1, FILTER ( _t, NOT ISBLANK ( [@drop] ) ), [@drop], DESC )
RETURN
    MAXX ( _top, DimFunnelStage[stage_name] & " → next (" & FORMAT ( [@drop], "0.0%" ) & ")" )
```
**Expected: "Product view → next (80.1%)"**

```DAX
Largest Drop-off Stage (Sessions) =
VAR _t =
    ADDCOLUMNS (
        ALL ( DimFunnelStage[stage_order], DimFunnelStage[stage_name] ),
        "@lost", [Stage Sessions Lost]
    )
VAR _top = TOPN ( 1, FILTER ( _t, NOT ISBLANK ( [@lost] ) ), [@lost], DESC )
RETURN
    MAXX ( _top, DimFunnelStage[stage_name] & " → next (" & FORMAT ( [@lost], "#,0" ) & " sessions)" )
```
**Expected: "Session → next (16,445 sessions)"**

---

## 7. Landing-page diagnostics  (folder `7 Landing Pages`)

```DAX
Site Conversion Rate =
CALCULATE ( [Purchase Conversion Rate], REMOVEFILTERS ( DimLandingPage ) )

CVR vs Site (pp) =
VAR _lp = [Purchase Conversion Rate]
RETURN IF ( NOT ISBLANK ( _lp ), _lp - [Site Conversion Rate] )
```
Format `+0.00%;-0.00%`. Use it for conditional formatting (diverging red/green).

```DAX
Landing Page Investigate Flag =
-- Same rule as python/analysis.py and sql/07: >= 2% of sessions AND the upper bound of the
-- 95% Wilson interval for the page's conversion rate is below the site rate.
VAR _n     = [Total Sessions]
VAR _x     = [Purchasing Sessions] + 0
VAR _z     = 1.96
VAR _p     = DIVIDE ( _x, _n )
VAR _upper =
    DIVIDE (
        _p + _z ^ 2 / ( 2 * _n ) + _z * SQRT ( _p * ( 1 - _p ) / _n + _z ^ 2 / ( 4 * _n ^ 2 ) ),
        1 + _z ^ 2 / _n
    )
VAR _share = DIVIDE ( _n, CALCULATE ( [Total Sessions], REMOVEFILTERS ( DimLandingPage ) ) )
RETURN
    IF ( _n > 0, IF ( _share >= 0.02 && _upper < [Site Conversion Rate], 1, 0 ) )
```
**Expected (full period, no slicers): 1 for `/collections/sale`, both `/blog/…` pages, and `/campaign/spring-sale`.**
The flag is evaluated within the current slicer context. Selecting a single device or a short date range reduces
sample sizes, so the interval widens and fewer pages are flagged. That is the intended behaviour.

---

## 8. Data-quality transparency  (folder `8 Data Quality`)

```DAX
Purchase Sequence Violations =
SUM ( FactSessions[purchase_sequence_violation] )
```
**Expected: 25**

```DAX
KPI vs Funnel Purchase Gap =
[Purchasing Sessions] - [Funnel Purchase Sessions]
```
**Expected: 25** (= 913 − 888). Explained in `notebooks/03_conversion_funnel_analysis.ipynb` §3: sequence violations
(25) plus tracking loss (13), minus orders with a purchase event but a quarantined transaction (13). Show it in
a tooltip on the funnel page so users understand why the two purchase numbers differ.

---

## 9. Formatting standards

| Type | Format string | Examples |
|---|---|---|
| Counts | `#,0` | Sessions, transactions |
| Rates | `0.0%` (`0.00%` when < 5%) | Conversion rate, engagement rate |
| Currency totals | `$#,0` | Revenue |
| Currency per unit | `$#,0.00` | AOV, revenue per session |
| Growth | `+0.0%;-0.0%;0.0%` | Sessions growth |
| Percentage-point difference | `+0.00%;-0.00%;0.00%` | CVR vs site |

## 10. Validation checklist (run once the report is built)

1. Card values with no slicers equal the **Expected** values above (and `reports/metrics/reconciliation.md`).
2. A table of `[Total Revenue]` by `channel_group` totals exactly `[Total Revenue]` (no fan-out).
3. `[Funnel Stage Sessions]` never increases from one stage to the next, under any slicer combination.
4. Selecting a date range with no data shows BLANK for every rate (no errors, no 0% that hides missing data).
5. `[Revenue (Transaction Date)]` equals `[Total Revenue]` for the full period.
