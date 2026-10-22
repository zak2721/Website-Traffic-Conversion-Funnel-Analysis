# Dashboard Design Specification

Four report pages for Power BI Desktop. Canvas **16:9, 1280 × 720**. Measures are from `dax_measures.md`.
The wireframes in `powerbi/wireframes/` are **illustrative layout sketches, not screenshots** of a built report.

## Global design system

| Element | Specification |
|---|---|
| Theme | `powerbi/theme.json` (View → Themes → Browse for themes) |
| Background | `#F7F9FC` page, `#FFFFFF` visual cards, 8 px radius, light shadow |
| Font | Segoe UI; titles 14 pt semibold, KPI values 26 pt, labels 10 pt |
| Channel colours | Organic Search `#2E7D32`, Direct `#455A64`, Paid Search `#1565C0`, Paid Social `#C62828`, Email `#EF6C00`, Organic Social `#AD1457`, Referral `#6A1B9A` (consistent on every page) |
| Device colours | Desktop `#1565C0`, Mobile `#EF6C00`, Tablet `#6A1B9A` |
| Header band | 0–60 px: page title (left), date-range text `"Data: " & FORMAT(MIN(DimDate[date]),"d mmm yyyy") & " – " & …` (right) |
| Slicer band | 60–110 px, synced slicers (Date, Channel; Device on pages 3–4) |
| Footer | "Synthetic data, illustrative only. See README." 9 pt grey, bottom-left |
| Navigation | Page navigator buttons in the header (Insert → Buttons → Navigator → Page navigator) |
| Titles | Every visual title states the metric and unit, e.g. *"Revenue by channel (USD)"* |
| Accessibility | Alt text on every visual; never use colour alone (data labels on); contrast ≥ 4.5:1 |

---

## Page 1: Executive Traffic Overview

**Question answered:** *How much traffic did we get, how much converted, and which channels drive it?*

| Zone (x, y, w, h) | Visual | Fields / measures | Notes |
|---|---|---|---|
| (20, 120, 236, 110) ×5 | 5 KPI cards (new card visual) | Total Sessions · Purchasing Sessions · Purchase Conversion Rate · Total Revenue · Revenue per Session | Reference label = `Sessions Growth %` / `Revenue Growth %` vs previous period, green/red |
| (20, 245, 760, 220) | Line + clustered column | X `DimDate[date]` (drill to week / month) · Columns `Total Sessions` · Line `Purchase Conversion Rate` (secondary axis) | Title "Sessions and conversion rate over time". Add a 7-day average line via Analytics pane if on daily grain |
| (795, 245, 465, 220) | Clustered bar | Y `channel_group` · X `Total Sessions` | Sorted descending, data labels |
| (20, 480, 760, 220) | Clustered bar | Y `channel_group` · X `Share of Sessions`, `Share of Revenue` | The single most important executive chart: shows Paid Social's gap and Email's leverage |
| (795, 480, 465, 220) | Bar | Y `channel_group` · X `Total Revenue` | Tooltip: AOV, Revenue per Session |

**Slicers:** Date (between), Channel (dropdown). **Interactions:** clicking a channel bar cross-*filters* the trend
(not highlight). **Expected values (no slicers):** 35,822 · 913 · 2.55% · $64,207 · $1.79.

---

## Page 2: Marketing Channel Performance

**Question answered:** *Which channels and campaigns are efficient, not just big?*

| Zone | Visual | Fields / measures | Notes |
|---|---|---|---|
| (20, 120, 1240, 240) | Table (channel scorecard) | `channel_group` · Total Sessions · Share of Sessions · Purchasing Sessions · Purchase Conversion Rate · Total Revenue · Share of Revenue · Revenue per Session · Average Order Value · Engagement Rate | Conditional formatting: data bars on Sessions and Revenue; background colour scale (red→green) on Conversion Rate and Revenue per Session. Default sort: Revenue desc |
| (20, 375, 610, 325) | Scatter | X `Total Sessions` · Y `Purchase Conversion Rate` · Size `Total Revenue` · Legend `channel_group` | Constant line on Y = `Site Conversion Rate`. Quadrants: big & efficient / big & inefficient |
| (645, 375, 615, 325) | Line chart | X `DimDate[year_month]` · Y `Purchase Conversion Rate` · Legend `channel_group` | Channel-level trend. Use small multiples by channel if lines overlap |
| Drill-down | Matrix (optional tab or bookmark) | Rows `channel_group → source_medium → campaign` | Shows `spring_sale` 0.29% vs `retargeting` 1.84% inside Paid Social |

**Slicers:** Date, Channel, Campaign. **Tooltip page:** a small tooltip page showing the monthly sessions sparkline
and CVR for the hovered channel.

---

## Page 3: Conversion Funnel

**Question answered:** *Where do users drop out, and does it differ by device?*

| Zone | Visual | Fields / measures | Notes |
|---|---|---|---|
| (20, 120, 400, 110) | 2 cards | `Largest Drop-off Stage (%)` · `Largest Drop-off Stage (Sessions)` | Text measures |
| (435, 120, 825, 110) | 4 cards | Session → Product View % · Product View → Cart % · Cart → Checkout % · Checkout → Purchase % | |
| (20, 245, 610, 300) | **Clustered bar (not the funnel visual)** | Y `DimFunnelStage[stage_name]` (sorted by stage_order) · X `Funnel Stage Sessions` | Data labels: value + `Funnel % of Sessions` (use "custom label" field). Tooltip: Stage Conversion to Next %, Stage Drop-off %, Stage Sessions Lost, and `KPI vs Funnel Purchase Gap` on the final stage |
| (645, 245, 615, 300) | Matrix | Rows `DimFunnelStage[stage_name]` · Columns `DimDevice[device_label]` · Values `Funnel Stage Sessions`, `Stage Conversion to Next %` | Conditional formatting on the conversion column. Mobile's 37% checkout → purchase stands out |
| (20, 560, 1240, 140) | Clustered column | X stage transition (use `DimFunnelStage[stage_name]` filtered to stages 1–4) · Y `Stage Conversion to Next %` · Legend `device_label` | Device-level funnel comparison |

**Why a bar chart instead of the built-in funnel visual:** the funnel visual draws each stage as a % of the first
stage only and hides stage-to-stage conversion. With an 80% drop between two stages it also renders the lower stages
as slivers. A horizontal bar chart with explicit drop-off labels shows absolute *and* relative loss accurately.
(The funnel visual is acceptable as a small decorative element if stage-to-stage labels are added via tooltips.)

**Slicers:** Date, Channel, Device (tiles). **Note on page:** a text box explaining *"Purchase stage = ordered event
journey (888). Purchasing Sessions KPI = valid transactions (913). See notebook 03 for the reconciliation."*

---

## Page 4: Device and Landing-Page Analysis

**Question answered:** *Which devices and entry pages under-perform, and which deserve investigation?*

| Zone | Visual | Fields / measures | Notes |
|---|---|---|---|
| (20, 120, 610, 250) | Clustered column | X `device_label` · Y `Purchase Conversion Rate`, `Revenue per Session` | Exclude "Unknown" (visual-level filter) |
| (645, 120, 615, 250) | Matrix | Rows `channel_group` · Columns `device_label` · Values `Purchase Conversion Rate` | Proves the mobile gap exists within every channel. Colour scale per column |
| (20, 385, 1240, 315) | **Sortable performance table** | `landing_page` · `page_type` · Total Sessions · Share of Sessions · Engagement Rate · Add-to-Cart Rate · Purchase Conversion Rate · CVR vs Site (pp) · Total Revenue · Revenue per Session · Landing Page Investigate Flag | Icon set on Investigate Flag (red flag = 1). Diverging colour on CVR vs Site. Default sort: Sessions desc |

**Slicers:** Date, Device, Channel, Page type. **Drill-through:** right-click a landing page → drill through to a
hidden *Landing Page Detail* page (optional) with that page's trend and device split.

---

## Build checklist

- [ ] Theme applied, page size 16:9
- [ ] Slicers synced across pages (View → Sync slicers)
- [ ] Every visual has a title with units, alt text and data labels where values matter
- [ ] Cross-filter (not highlight) interactions on page 1 channel bars
- [ ] KPI cards match the expected values in `dax_measures.md`
- [ ] Funnel bar values never increase down the stages under any slicer combination
- [ ] Footer synthetic-data disclaimer on every page
- [ ] Export each page (File → Export → PDF, or screenshots) into `screenshots/` (see `screenshots/README.md`)
