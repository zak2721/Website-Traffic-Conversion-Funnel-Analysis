# Power Query Guide: Importing the Model CSVs

Builds the eight model tables in Power BI Desktop from `data/processed/model/`. Estimated time: 20–30 minutes.

## Step 1: Create the folder parameter (makes the report portable)

1. **Home → Transform data → Manage Parameters → New Parameter**
2. Name `DataFolder`, Type **Text**, Current value: the full path to `data/processed/model/` **including the trailing slash**,
   e.g. `C:\Projects\Website-Traffic-Conversion-Analysis\data\processed\model\`
3. Anyone who clones the repository changes only this value (**Transform data → Edit parameters**).

## Step 2: Create one blank query per table

**Home → New Source → Blank Query → Advanced Editor**, paste the M code, then rename the query to the table name shown.
Each query reads the file through `DataFolder`, promotes headers, and sets explicit types with the `en-US` culture so
dates and decimals parse identically on any regional setting.

### FactSessions
```m
let
    Source   = Csv.Document(File.Contents(DataFolder & "fact_sessions.csv"),
                            [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(Promoted, {
        {"session_id", type text}, {"visitor_id", type text}, {"session_start", type datetime},
        {"session_date_key", Int64.Type}, {"traffic_source_key", Int64.Type}, {"device_key", Int64.Type},
        {"landing_page_key", Int64.Type}, {"country", type text}, {"engaged_session", Int64.Type},
        {"page_views", Int64.Type}, {"reached_session", Int64.Type}, {"reached_product_view", Int64.Type},
        {"reached_add_to_cart", Int64.Type}, {"reached_checkout", Int64.Type}, {"reached_purchase", Int64.Type},
        {"has_product_view_event", Int64.Type}, {"has_add_to_cart_event", Int64.Type},
        {"has_begin_checkout_event", Int64.Type}, {"has_purchase_event", Int64.Type},
        {"purchase_sequence_violation", Int64.Type}, {"is_purchasing_session", Int64.Type}}, "en-US")
in
    Typed
```

### FactEvents
```m
let
    Source   = Csv.Document(File.Contents(DataFolder & "fact_events.csv"),
                            [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(Promoted, {
        {"event_id", type text}, {"session_id", type text}, {"event_timestamp", type datetime},
        {"event_date_key", Int64.Type}, {"session_date_key", Int64.Type}, {"event_name", type text},
        {"page_path", type text}, {"product_id", type text}, {"traffic_source_key", Int64.Type},
        {"device_key", Int64.Type}, {"landing_page_key", Int64.Type}}, "en-US"),
    // product_id is legitimately empty for non-product events: keep as null, do not filter
    BlankToNull = Table.ReplaceValue(Typed, "", null, Replacer.ReplaceValue, {"product_id"})
in
    BlankToNull
```

### FactTransactions
```m
let
    Source   = Csv.Document(File.Contents(DataFolder & "fact_transactions.csv"),
                            [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(Promoted, {
        {"transaction_id", type text}, {"session_id", type text}, {"transaction_timestamp", type datetime},
        {"transaction_date_key", Int64.Type}, {"session_date_key", Int64.Type},
        {"traffic_source_key", Int64.Type}, {"device_key", Int64.Type}, {"landing_page_key", Int64.Type},
        {"revenue", Currency.Type}, {"currency", type text}, {"transaction_status", type text},
        {"is_refunded", Int64.Type}}, "en-US")
in
    Typed
```
`Currency.Type` (fixed decimal) avoids floating-point drift when summing revenue.

### DimDate
```m
let
    Source   = Csv.Document(File.Contents(DataFolder & "dim_date.csv"),
                            [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(Promoted, {
        {"date_key", Int64.Type}, {"date", type date}, {"year", Int64.Type}, {"quarter", type text},
        {"month_number", Int64.Type}, {"month_name", type text}, {"year_month", type text},
        {"month_start", type date}, {"week_start", type date}, {"day_of_week_number", Int64.Type},
        {"day_of_week", type text}, {"is_weekend", Int64.Type}}, "en-US")
in
    Typed
```

### DimTrafficSource, DimDevice, DimLandingPage, DimFunnelStage
Same pattern; change the file name and the type list:

| Query | File | Types |
|---|---|---|
| DimTrafficSource | dim_traffic_source.csv | `traffic_source_key` Int64; all other columns text |
| DimDevice | dim_device.csv | `device_key`, `device_sort` Int64; others text |
| DimLandingPage | dim_landing_page.csv | `landing_page_key` Int64; others text |
| DimFunnelStage | dim_funnel_stage.csv | `stage_order` Int64; others text |

## Step 3: Data-quality checks inside Power Query (before loading)

For each fact query, temporarily use **View → Column quality / Column distribution / Column profile**
(set profiling to *entire data set* in the status bar):

* Key columns must show **0% error and 0% empty**, and `session_id` / `event_id` / `transaction_id` must show *distinct = unique*.
* `revenue` minimum must be > 0.
* `event_name` must show exactly six distinct values.

If a check fails, the CSVs were not produced by the current `clean_data.py`: re-run the pipeline rather than patching in Power Query.
Cleaning lives in Python/SQL **once**, so the logic is tested and is not duplicated across tools.

## Step 4: Load and finish the model

1. **Close & Apply.**
2. Untick **Enable load** for nothing (all eight tables load). If you add helper queries, disable their load.
3. Create the relationships in `data_model.md` §3 (Model view). Turn off **auto-detect relationships**
   (File → Options → Current file → Data load) first, so Power BI doesn't guess.
4. Mark `DimDate` as the date table; set sort-by columns; hide key and flag columns.
5. Create the `_Measures` table and add the measures from `dax_measures.md`.

## Alternative: connect to PostgreSQL instead of CSVs

After running `sql/01_create_tables.sql` and `sql/01b_load_data.sql`:
**Get Data → PostgreSQL database**, server `localhost`, database `webanalytics`, and select the `analytics.*` tables.
Use **Import** mode. Store credentials in Power BI's credential manager, never in the M code or the repository.
Column names and types are identical, so the model and measures need no changes.
