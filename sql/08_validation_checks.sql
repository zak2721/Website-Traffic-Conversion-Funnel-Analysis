-- =============================================================================
-- 08_validation_checks.sql
-- Assertion-style validation. Every row returns PASS or FAIL.
-- python/reconcile.py runs this file and fails if any check returns FAIL.
-- =============================================================================

WITH
-- independent ordered funnel from events (same logic as 05_conversion_funnel.sql 5.1)
pv  AS (SELECT session_id, MIN(event_timestamp) ts FROM analytics.fact_events WHERE event_name = 'product_view' GROUP BY 1),
atc AS (SELECT e.session_id, MIN(e.event_timestamp) ts FROM analytics.fact_events e JOIN pv USING (session_id)
        WHERE e.event_name = 'add_to_cart' AND e.event_timestamp >= pv.ts GROUP BY 1),
co  AS (SELECT e.session_id, MIN(e.event_timestamp) ts FROM analytics.fact_events e JOIN atc USING (session_id)
        WHERE e.event_name = 'begin_checkout' AND e.event_timestamp >= atc.ts GROUP BY 1),
pur AS (SELECT e.session_id, MIN(e.event_timestamp) ts FROM analytics.fact_events e JOIN co USING (session_id)
        WHERE e.event_name = 'purchase' AND e.event_timestamp >= co.ts GROUP BY 1),
flags AS (
    SELECT SUM(reached_product_view) pv, SUM(reached_add_to_cart) atc, SUM(reached_checkout) co,
           SUM(reached_purchase) pur, COUNT(*) s
    FROM analytics.fact_sessions
),
channel_cvr AS (
    SELECT ts.channel_group,
           COUNT(DISTINCT ft.session_id)::NUMERIC / NULLIF(COUNT(DISTINCT fs.session_id), 0) AS cvr
    FROM analytics.fact_sessions fs
    JOIN analytics.dim_traffic_source ts USING (traffic_source_key)
    LEFT JOIN analytics.fact_transactions ft USING (session_id)
    GROUP BY 1
),
checks AS (
    SELECT 'pk_unique_sessions' AS check_name,
           (SELECT COUNT(*) - COUNT(DISTINCT session_id) FROM analytics.fact_sessions)::TEXT AS actual, '0' AS expected
    UNION ALL SELECT 'pk_unique_events',
           (SELECT COUNT(*) - COUNT(DISTINCT event_id) FROM analytics.fact_events)::TEXT, '0'
    UNION ALL SELECT 'pk_unique_transactions',
           (SELECT COUNT(*) - COUNT(DISTINCT transaction_id) FROM analytics.fact_transactions)::TEXT, '0'
    UNION ALL SELECT 'orphan_events',
           (SELECT COUNT(*) FROM analytics.fact_events e
             WHERE NOT EXISTS (SELECT 1 FROM analytics.fact_sessions s WHERE s.session_id = e.session_id))::TEXT, '0'
    UNION ALL SELECT 'orphan_transactions',
           (SELECT COUNT(*) FROM analytics.fact_transactions t
             WHERE NOT EXISTS (SELECT 1 FROM analytics.fact_sessions s WHERE s.session_id = t.session_id))::TEXT, '0'
    UNION ALL SELECT 'revenue_positive',
           (SELECT COUNT(*) FROM analytics.fact_transactions WHERE revenue <= 0 OR revenue IS NULL)::TEXT, '0'
    UNION ALL SELECT 'transaction_not_before_session',
           (SELECT COUNT(*) FROM analytics.fact_transactions t JOIN analytics.fact_sessions s USING (session_id)
             WHERE t.transaction_timestamp < s.session_start)::TEXT, '0'
    UNION ALL SELECT 'event_not_before_session',
           (SELECT COUNT(*) FROM analytics.fact_events e JOIN analytics.fact_sessions s USING (session_id)
             WHERE e.event_timestamp < s.session_start)::TEXT, '0'
    UNION ALL SELECT 'session_dates_in_dim_date_range',
           (SELECT COUNT(*) FROM analytics.fact_sessions fs
             WHERE fs.session_start::DATE NOT BETWEEN (SELECT MIN(date) FROM analytics.dim_date)
                                                  AND (SELECT MAX(date) FROM analytics.dim_date))::TEXT, '0'
    UNION ALL SELECT 'funnel_flags_match_events_product_view', (SELECT COUNT(*) FROM pv)::TEXT,  (SELECT pv::TEXT FROM flags)
    UNION ALL SELECT 'funnel_flags_match_events_add_to_cart',  (SELECT COUNT(*) FROM atc)::TEXT, (SELECT atc::TEXT FROM flags)
    UNION ALL SELECT 'funnel_flags_match_events_checkout',     (SELECT COUNT(*) FROM co)::TEXT,  (SELECT co::TEXT FROM flags)
    UNION ALL SELECT 'funnel_flags_match_events_purchase',     (SELECT COUNT(*) FROM pur)::TEXT, (SELECT pur::TEXT FROM flags)
    UNION ALL SELECT 'funnel_monotonic',
           (SELECT (s >= pv AND pv >= atc AND atc >= co AND co >= pur)::TEXT FROM flags), 'true'
    UNION ALL SELECT 'purchasing_flag_matches_transactions',
           (SELECT SUM(is_purchasing_session) FROM analytics.fact_sessions)::TEXT,
           (SELECT COUNT(DISTINCT session_id) FROM analytics.fact_transactions)::TEXT
    UNION ALL SELECT 'channel_cvr_within_0_1',
           (SELECT COUNT(*) FROM channel_cvr WHERE cvr < 0 OR cvr > 1 OR cvr IS NULL)::TEXT, '0'
    UNION ALL SELECT 'revenue_by_channel_equals_total (no fan-out)',
           (SELECT SUM(r)::TEXT FROM (SELECT SUM(revenue) r FROM analytics.fact_transactions ft
                                      JOIN analytics.dim_traffic_source USING (traffic_source_key) GROUP BY channel_group) x),
           (SELECT SUM(revenue)::TEXT FROM analytics.fact_transactions)
    UNION ALL SELECT 'revenue_by_device_equals_total (no fan-out)',
           (SELECT SUM(r)::TEXT FROM (SELECT SUM(revenue) r FROM analytics.fact_transactions GROUP BY device_key) x),
           (SELECT SUM(revenue)::TEXT FROM analytics.fact_transactions)
    UNION ALL SELECT 'zero_denominator_returns_null',
           (SELECT COALESCE((1::NUMERIC / NULLIF(0, 0))::TEXT, 'null')), 'null'
    UNION ALL SELECT 'empty_period_conversion_is_null',
           (SELECT COALESCE((COUNT(*) FILTER (WHERE is_purchasing_session = 1))::NUMERIC
                            / NULLIF(COUNT(*), 0), -1)::TEXT
              FROM analytics.fact_sessions WHERE session_start < DATE '1900-01-01'), '-1'
)
SELECT check_name, expected, actual, CASE WHEN actual = expected THEN 'PASS' ELSE 'FAIL' END AS status
FROM checks
ORDER BY status DESC, check_name;

-- Reconciliation totals consumed by python/reconcile.py (key|value)
SELECT 'total_sessions'      AS metric, COUNT(*)::TEXT AS value FROM analytics.fact_sessions
UNION ALL SELECT 'total_visitors', COUNT(DISTINCT visitor_id)::TEXT FROM analytics.fact_sessions
UNION ALL SELECT 'engaged_sessions', SUM(engaged_session)::TEXT FROM analytics.fact_sessions
UNION ALL SELECT 'purchasing_sessions', COUNT(DISTINCT session_id)::TEXT FROM analytics.fact_transactions
UNION ALL SELECT 'total_transactions', COUNT(DISTINCT transaction_id)::TEXT FROM analytics.fact_transactions
UNION ALL SELECT 'total_revenue', SUM(revenue)::TEXT FROM analytics.fact_transactions
UNION ALL SELECT 'net_revenue', SUM(revenue) FILTER (WHERE transaction_status = 'completed')::TEXT FROM analytics.fact_transactions
UNION ALL SELECT 'funnel_purchase_stage', SUM(reached_purchase)::TEXT FROM analytics.fact_sessions;
