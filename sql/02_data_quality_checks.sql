-- =============================================================================
-- 02_data_quality_checks.sql
-- Part A  Profile the RAW staging tables (mirrors python/data_quality.py)
-- Part B  SQL standardisation views (the same cleaning rules as clean_data.py)
-- Part C  Reconcile SQL-cleaned sessions with the Python-cleaned analytics table
-- =============================================================================

-- ---------------------------------------------------------------- Part A
-- A1. Row counts, duplicate keys and exact duplicate rows
SELECT 'sessions' AS table_name,
       COUNT(*)                                   AS total_rows,
       COUNT(*) - COUNT(DISTINCT session_id)      AS duplicate_primary_keys,
       COUNT(*) - (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM raw.sessions) d) AS exact_duplicate_rows
FROM raw.sessions
UNION ALL
SELECT 'events', COUNT(*), COUNT(*) - COUNT(DISTINCT event_id),
       COUNT(*) - (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM raw.events) d)
FROM raw.events
UNION ALL
SELECT 'transactions', COUNT(*), COUNT(*) - COUNT(DISTINCT transaction_id),
       COUNT(*) - (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM raw.transactions) d)
FROM raw.transactions;

-- A2. Missing values in sessions (empty strings load as NULL with FORMAT csv)
SELECT COUNT(*) FILTER (WHERE campaign IS NULL)        AS missing_campaign,
       COUNT(*) FILTER (WHERE device_category IS NULL) AS missing_device,
       COUNT(*) FILTER (WHERE country IS NULL)         AS missing_country,
       COUNT(*) FILTER (WHERE landing_page IS NULL)    AS missing_landing_page
FROM raw.sessions;

-- A3. Non-standard labels (top variants per column)
SELECT 'traffic_source' AS column_name, traffic_source AS raw_value, COUNT(*) AS row_count
FROM raw.sessions
WHERE traffic_source NOT IN ('google','bing','(direct)','facebook','instagram','newsletter',
                             'partnerblog.com','dealsforum.com','tiktok')
GROUP BY traffic_source
UNION ALL
SELECT 'marketing_medium', marketing_medium, COUNT(*) FROM raw.sessions
WHERE marketing_medium NOT IN ('organic','cpc','(none)','paid_social','email','referral','social')
GROUP BY marketing_medium
UNION ALL
SELECT 'device_category', device_category, COUNT(*) FROM raw.sessions
WHERE device_category NOT IN ('desktop','mobile','tablet')
GROUP BY device_category
UNION ALL
SELECT 'event_name', event_name, COUNT(*) FROM raw.events
WHERE event_name NOT IN ('session_start','page_view','product_view','add_to_cart','begin_checkout','purchase')
GROUP BY event_name
ORDER BY column_name, row_count DESC;

-- A4. Timestamp parseability: both export formats must cast cleanly
SELECT COUNT(*) FILTER (WHERE session_start ~ 'T')  AS iso_t_format_rows,
       COUNT(*) FILTER (WHERE session_start !~ '^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}Z?$') AS unexpected_format_rows
FROM raw.sessions;

-- A5. Referential integrity and business rules on raw data
WITH s AS (SELECT DISTINCT session_id FROM raw.sessions)
SELECT
    (SELECT COUNT(*) FROM raw.events e       WHERE NOT EXISTS (SELECT 1 FROM s WHERE s.session_id = e.session_id)) AS orphan_events,
    (SELECT COUNT(*) FROM raw.transactions t WHERE NOT EXISTS (SELECT 1 FROM s WHERE s.session_id = t.session_id)) AS orphan_transactions,
    (SELECT COUNT(*) FROM raw.transactions WHERE revenue::NUMERIC < 0)                      AS negative_revenue,
    (SELECT COUNT(*) FROM raw.transactions WHERE LOWER(TRIM(transaction_status)) = 'test') AS test_transactions,
    (SELECT COUNT(*) FROM raw.transactions WHERE currency <> UPPER(currency))               AS lowercase_currency;

-- A6. Transactions recorded before their session started (impossible)
SELECT t.transaction_id, t.session_id,
       REPLACE(REPLACE(t.transaction_timestamp, 'T', ' '), 'Z', '')::TIMESTAMP AS transaction_ts,
       MIN(REPLACE(REPLACE(s.session_start, 'T', ' '), 'Z', '')::TIMESTAMP)    AS session_start_ts
FROM raw.transactions t
JOIN raw.sessions s USING (session_id)
GROUP BY t.transaction_id, t.session_id, t.transaction_timestamp
HAVING REPLACE(REPLACE(t.transaction_timestamp, 'T', ' '), 'Z', '')::TIMESTAMP
     < MIN(REPLACE(REPLACE(s.session_start, 'T', ' '), 'Z', '')::TIMESTAMP);

-- ---------------------------------------------------------------- Part B
-- B1. Standardised, de-duplicated sessions (same rules as python/clean_data.py)
CREATE OR REPLACE VIEW raw.v_sessions_standardised AS
WITH typed AS (
    SELECT
        session_id,
        visitor_id,
        REPLACE(REPLACE(session_start, 'T', ' '), 'Z', '')::TIMESTAMP              AS session_start,
        CASE REGEXP_REPLACE(LOWER(TRIM(traffic_source)), '^www\.', '')
             WHEN 'ig' THEN 'instagram' WHEN 'direct' THEN '(direct)'
             ELSE REGEXP_REPLACE(LOWER(TRIM(traffic_source)), '^www\.', '') END   AS traffic_source,
        CASE REGEXP_REPLACE(LOWER(TRIM(marketing_medium)), '[\s\-]+', '_', 'g')
             WHEN 'ppc' THEN 'cpc' WHEN 'e_mail' THEN 'email' WHEN 'none' THEN '(none)'
             ELSE REGEXP_REPLACE(LOWER(TRIM(marketing_medium)), '[\s\-]+', '_', 'g') END AS marketing_medium,
        COALESCE(campaign, '(not set)')                                              AS campaign,
        CASE LOWER(TRIM(device_category))
             WHEN 'pc' THEN 'desktop' WHEN 'smartphone' THEN 'mobile' WHEN 'ipad' THEN 'tablet'
             ELSE COALESCE(LOWER(TRIM(device_category)), 'unknown') END             AS device_category,
        COALESCE(country, '(not set)')                                               AS country,
        CASE WHEN SPLIT_PART(LOWER(TRIM(landing_page)), '?', 1) = '/' THEN '/'
             ELSE RTRIM(SPLIT_PART(LOWER(TRIM(landing_page)), '?', 1), '/') END     AS landing_page,
        engaged_session::SMALLINT                                                    AS engaged_session
    FROM raw.sessions
),
dedup AS (
    SELECT DISTINCT * FROM typed                      -- exact duplicates AFTER standardisation
),
ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY session_start) AS rn
    FROM dedup                                        -- conflicting duplicate IDs: keep earliest
)
SELECT session_id, visitor_id, session_start, traffic_source, marketing_medium, campaign,
       device_category, country, landing_page, engaged_session,
       CASE marketing_medium
            WHEN 'organic' THEN 'Organic Search' WHEN 'cpc' THEN 'Paid Search' WHEN '(none)' THEN 'Direct'
            WHEN 'paid_social' THEN 'Paid Social' WHEN 'social' THEN 'Organic Social'
            WHEN 'email' THEN 'Email' WHEN 'referral' THEN 'Referral' ELSE 'Other' END AS channel_group
FROM ranked
WHERE rn = 1;

-- B2. Standardised event names
CREATE OR REPLACE VIEW raw.v_events_standardised AS
SELECT DISTINCT ON (event_id)
       event_id, session_id,
       REPLACE(REPLACE(event_timestamp, 'T', ' '), 'Z', '')::TIMESTAMP AS event_timestamp,
       CASE REGEXP_REPLACE(LOWER(TRIM(event_name)), '[\s\-]+', '_', 'g')
            WHEN 'pageview' THEN 'page_view' WHEN 'view_item' THEN 'product_view'
            WHEN 'checkout_start' THEN 'begin_checkout'
            ELSE REGEXP_REPLACE(LOWER(TRIM(event_name)), '[\s\-]+', '_', 'g') END AS event_name,
       page_path, product_id
FROM raw.events
ORDER BY event_id;

-- B3. Valid transactions (business rules applied, quarantine excluded)
CREATE OR REPLACE VIEW raw.v_transactions_valid AS
WITH d AS (
    SELECT DISTINCT ON (transaction_id)
           transaction_id, session_id,
           REPLACE(REPLACE(transaction_timestamp, 'T', ' '), 'Z', '')::TIMESTAMP AS transaction_timestamp,
           revenue::NUMERIC(12,2)          AS revenue,
           UPPER(TRIM(currency))           AS currency,
           LOWER(TRIM(transaction_status)) AS transaction_status
    FROM raw.transactions
    ORDER BY transaction_id
)
SELECT d.*
FROM d
JOIN raw.v_sessions_standardised s USING (session_id)
WHERE d.transaction_status IN ('completed', 'refunded')
  AND d.revenue > 0
  AND d.transaction_timestamp >= s.session_start;

-- ---------------------------------------------------------------- Part C
-- C1. SQL cleaning must agree with the Python pipeline
SELECT 'sessions' AS entity,
       (SELECT COUNT(*) FROM raw.v_sessions_standardised)  AS sql_cleaned,
       (SELECT COUNT(*) FROM analytics.fact_sessions)      AS python_cleaned
UNION ALL
SELECT 'transactions',
       (SELECT COUNT(*) FROM raw.v_transactions_valid),
       (SELECT COUNT(*) FROM analytics.fact_transactions)
UNION ALL
SELECT 'revenue_cents',
       (SELECT ROUND(SUM(revenue) * 100) FROM raw.v_transactions_valid),
       (SELECT ROUND(SUM(revenue) * 100) FROM analytics.fact_transactions);

-- C2. Channel-level session counts must match row for row
SELECT COALESCE(a.channel_group, b.channel_group) AS channel_group,
       a.sessions AS sql_cleaned, b.sessions AS python_cleaned,
       (a.sessions = b.sessions) AS match
FROM (SELECT channel_group, COUNT(*) AS sessions FROM raw.v_sessions_standardised GROUP BY 1) a
FULL JOIN (SELECT ts.channel_group, COUNT(*) AS sessions
           FROM analytics.fact_sessions fs
           JOIN analytics.dim_traffic_source ts USING (traffic_source_key)
           GROUP BY 1) b USING (channel_group)
ORDER BY 1;

-- C3. Post-cleaning residual flags (expected, documented in reports/limitations.md)
SELECT SUM(purchase_sequence_violation)                                           AS purchase_before_checkout_sessions,
       SUM(CASE WHEN is_purchasing_session = 1 AND has_purchase_event = 0 THEN 1 ELSE 0 END) AS transaction_without_purchase_event,
       SUM(CASE WHEN reached_purchase = 1 AND is_purchasing_session = 0 THEN 1 ELSE 0 END)   AS ordered_purchase_without_valid_transaction
FROM analytics.fact_sessions;
