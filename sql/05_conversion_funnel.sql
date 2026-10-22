-- =============================================================================
-- 05_conversion_funnel.sql
-- Ordered, session-based conversion funnel computed directly from fact_events
-- (independent of the pre-computed reached_* flags, which 08_validation_checks.sql
-- compares against this result).
--
-- Funnel definition
--   1 Session           every session in the period
--   2 Product view      >= 1 product_view
--   3 Add to cart       add_to_cart at/after the FIRST product_view
--   4 Checkout started  begin_checkout at/after the first QUALIFYING add_to_cart
--   5 Purchase          purchase at/after the first QUALIFYING begin_checkout
-- Each session counts once per stage; a stage requires the previous stage,
-- so counts never increase down the funnel.
-- =============================================================================

-- 5.1 Overall funnel with stage-to-stage conversion and drop-off
WITH params AS (SELECT DATE '2025-01-01' AS start_date, DATE '2025-06-30' AS end_date),
s AS (
    SELECT fs.session_id
    FROM analytics.fact_sessions fs
    JOIN analytics.dim_date d ON d.date_key = fs.session_date_key
    CROSS JOIN params p
    WHERE d.date BETWEEN p.start_date AND p.end_date
),
pv AS (
    SELECT e.session_id, MIN(e.event_timestamp) AS ts
    FROM analytics.fact_events e JOIN s USING (session_id)
    WHERE e.event_name = 'product_view'
    GROUP BY e.session_id
),
atc AS (
    SELECT e.session_id, MIN(e.event_timestamp) AS ts
    FROM analytics.fact_events e JOIN pv USING (session_id)
    WHERE e.event_name = 'add_to_cart' AND e.event_timestamp >= pv.ts
    GROUP BY e.session_id
),
co AS (
    SELECT e.session_id, MIN(e.event_timestamp) AS ts
    FROM analytics.fact_events e JOIN atc USING (session_id)
    WHERE e.event_name = 'begin_checkout' AND e.event_timestamp >= atc.ts
    GROUP BY e.session_id
),
pur AS (
    SELECT e.session_id, MIN(e.event_timestamp) AS ts
    FROM analytics.fact_events e JOIN co USING (session_id)
    WHERE e.event_name = 'purchase' AND e.event_timestamp >= co.ts
    GROUP BY e.session_id
),
stages AS (
    SELECT 1 AS stage_order, 'Session' AS stage, COUNT(*) AS sessions FROM s
    UNION ALL SELECT 2, 'Product view',     COUNT(*) FROM pv
    UNION ALL SELECT 3, 'Add to cart',      COUNT(*) FROM atc
    UNION ALL SELECT 4, 'Checkout started', COUNT(*) FROM co
    UNION ALL SELECT 5, 'Purchase',         COUNT(*) FROM pur
)
SELECT stage_order, stage, sessions,
       ROUND(sessions::NUMERIC / NULLIF(FIRST_VALUE(sessions) OVER (ORDER BY stage_order), 0), 4) AS pct_of_sessions,
       ROUND(LEAD(sessions) OVER (ORDER BY stage_order)::NUMERIC / NULLIF(sessions, 0), 4)        AS conversion_to_next,
       ROUND(1 - LEAD(sessions) OVER (ORDER BY stage_order)::NUMERIC / NULLIF(sessions, 0), 4)    AS drop_off_rate,
       sessions - LEAD(sessions) OVER (ORDER BY stage_order)                                      AS sessions_lost
FROM stages
ORDER BY stage_order;

-- 5.2 Largest absolute and percentage losses (uses the pre-computed flags for brevity;
--     08_validation_checks.sql proves the flags equal 5.1)
WITH counts AS (
    SELECT 1 AS stage_order, 'Session → Product view' AS transition,
           SUM(reached_session) AS from_n, SUM(reached_product_view) AS to_n FROM analytics.fact_sessions
    UNION ALL SELECT 2, 'Product view → Add to cart', SUM(reached_product_view), SUM(reached_add_to_cart) FROM analytics.fact_sessions
    UNION ALL SELECT 3, 'Add to cart → Checkout',     SUM(reached_add_to_cart),  SUM(reached_checkout)    FROM analytics.fact_sessions
    UNION ALL SELECT 4, 'Checkout → Purchase',        SUM(reached_checkout),     SUM(reached_purchase)    FROM analytics.fact_sessions
)
SELECT transition, from_n, to_n, from_n - to_n AS sessions_lost,
       ROUND(1 - to_n::NUMERIC / NULLIF(from_n, 0), 4)                   AS drop_off_rate,
       RANK() OVER (ORDER BY from_n - to_n DESC)                         AS rank_absolute_loss,
       RANK() OVER (ORDER BY 1 - to_n::NUMERIC / NULLIF(from_n, 0) DESC) AS rank_pct_loss
FROM counts
ORDER BY stage_order;

-- 5.3 Funnel by device (stage counts and stage-to-stage conversion)
WITH base AS (
    SELECT dv.device_label, dv.device_sort,
           SUM(fs.reached_session)      AS s1, SUM(fs.reached_product_view) AS s2,
           SUM(fs.reached_add_to_cart)  AS s3, SUM(fs.reached_checkout)     AS s4,
           SUM(fs.reached_purchase)     AS s5
    FROM analytics.fact_sessions fs
    JOIN analytics.dim_device dv USING (device_key)
    WHERE dv.device_category <> 'unknown'
    GROUP BY dv.device_label, dv.device_sort
)
SELECT device_label, s1 AS sessions, s2 AS product_view, s3 AS add_to_cart, s4 AS checkout, s5 AS purchase,
       ROUND(s2::NUMERIC / NULLIF(s1, 0), 4) AS session_to_view,
       ROUND(s3::NUMERIC / NULLIF(s2, 0), 4) AS view_to_cart,
       ROUND(s4::NUMERIC / NULLIF(s3, 0), 4) AS cart_to_checkout,
       ROUND(s5::NUMERIC / NULLIF(s4, 0), 4) AS checkout_to_purchase,
       ROUND(s5::NUMERIC / NULLIF(s1, 0), 4) AS funnel_completion_rate
FROM base
ORDER BY device_sort;

-- 5.4 Funnel by channel
SELECT ts.channel_group,
       SUM(fs.reached_session)                                                              AS sessions,
       ROUND(SUM(fs.reached_product_view)::NUMERIC / NULLIF(SUM(fs.reached_session), 0), 4)     AS session_to_view,
       ROUND(SUM(fs.reached_add_to_cart)::NUMERIC  / NULLIF(SUM(fs.reached_product_view), 0), 4) AS view_to_cart,
       ROUND(SUM(fs.reached_checkout)::NUMERIC     / NULLIF(SUM(fs.reached_add_to_cart), 0), 4)  AS cart_to_checkout,
       ROUND(SUM(fs.reached_purchase)::NUMERIC     / NULLIF(SUM(fs.reached_checkout), 0), 4)     AS checkout_to_purchase,
       ROUND(SUM(fs.reached_purchase)::NUMERIC     / NULLIF(SUM(fs.reached_session), 0), 4)      AS funnel_completion_rate
FROM analytics.fact_sessions fs
JOIN analytics.dim_traffic_source ts USING (traffic_source_key)
GROUP BY ts.channel_group
ORDER BY sessions DESC;

-- 5.5 Ordered vs unordered: why event presence alone is not enough
SELECT SUM(has_purchase_event)          AS sessions_with_purchase_event,
       SUM(reached_purchase)            AS sessions_reaching_ordered_purchase_stage,
       SUM(purchase_sequence_violation) AS purchase_logged_before_checkout
FROM analytics.fact_sessions;
