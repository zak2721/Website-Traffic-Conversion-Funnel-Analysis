-- =============================================================================
-- 04_channel_performance.sql
-- Sessions, purchasing sessions, conversion, revenue, RPS and AOV by channel.
--
-- Pattern used throughout: aggregate each fact table SEPARATELY to the reporting
-- grain, then join the aggregates. Joining fact_sessions to fact_transactions
-- row-by-row first would be safe here (≤1 transaction per session) but is not
-- safe in general and is avoided on principle.
--
-- Definitions
--   purchasing_sessions = distinct sessions with ≥1 valid transaction
--   conversion_rate     = purchasing_sessions / sessions
--   revenue             = SUM(revenue) of valid transactions (completed + refunded = gross)
--   revenue_per_session = revenue / sessions
--   average_order_value = revenue / distinct transactions
-- =============================================================================

-- 4.1 Channel scorecard
WITH params AS (SELECT DATE '2025-01-01' AS start_date, DATE '2025-06-30' AS end_date),
sess AS (
    SELECT ts.channel_group, COUNT(*) AS sessions, SUM(fs.engaged_session) AS engaged_sessions
    FROM analytics.fact_sessions fs
    JOIN analytics.dim_traffic_source ts USING (traffic_source_key)
    JOIN analytics.dim_date d ON d.date_key = fs.session_date_key
    CROSS JOIN params p
    WHERE d.date BETWEEN p.start_date AND p.end_date
    GROUP BY ts.channel_group
),
tx AS (
    SELECT ts.channel_group,
           COUNT(DISTINCT ft.session_id)     AS purchasing_sessions,
           COUNT(DISTINCT ft.transaction_id) AS transactions,
           SUM(ft.revenue)                   AS revenue,
           SUM(ft.revenue) FILTER (WHERE ft.transaction_status = 'completed') AS net_revenue
    FROM analytics.fact_transactions ft
    JOIN analytics.dim_traffic_source ts USING (traffic_source_key)
    JOIN analytics.dim_date d ON d.date_key = ft.session_date_key   -- attributed to session date
    CROSS JOIN params p
    WHERE d.date BETWEEN p.start_date AND p.end_date
    GROUP BY ts.channel_group
)
SELECT s.channel_group,
       s.sessions,
       ROUND(s.sessions::NUMERIC / SUM(s.sessions) OVER (), 4)                    AS share_of_sessions,
       ROUND(s.engaged_sessions::NUMERIC / NULLIF(s.sessions, 0), 4)              AS engagement_rate,
       COALESCE(t.purchasing_sessions, 0)                                         AS purchasing_sessions,
       ROUND(COALESCE(t.purchasing_sessions, 0)::NUMERIC / NULLIF(s.sessions, 0), 4) AS conversion_rate,
       COALESCE(t.revenue, 0)                                                     AS revenue,
       ROUND(COALESCE(t.revenue, 0) / NULLIF(SUM(COALESCE(t.revenue, 0)) OVER (), 0), 4) AS share_of_revenue,
       ROUND(COALESCE(t.revenue, 0) / NULLIF(s.sessions, 0), 2)                   AS revenue_per_session,
       ROUND(t.revenue / NULLIF(t.transactions, 0), 2)                            AS average_order_value,
       COALESCE(t.net_revenue, 0)                                                 AS net_revenue,
       RANK() OVER (ORDER BY COALESCE(t.revenue, 0) DESC)                         AS revenue_rank,
       RANK() OVER (ORDER BY COALESCE(t.purchasing_sessions, 0)::NUMERIC / NULLIF(s.sessions, 0) DESC) AS conversion_rank
FROM sess s
LEFT JOIN tx t USING (channel_group)
ORDER BY s.sessions DESC;

-- 4.2 Campaign scorecard (paid and email campaigns only)
WITH sess AS (
    SELECT ts.channel_group, ts.campaign, COUNT(*) AS sessions
    FROM analytics.fact_sessions fs
    JOIN analytics.dim_traffic_source ts USING (traffic_source_key)
    WHERE ts.campaign <> '(not set)'
    GROUP BY 1, 2
),
tx AS (
    SELECT ts.channel_group, ts.campaign,
           COUNT(DISTINCT ft.session_id) AS purchasing_sessions, SUM(ft.revenue) AS revenue
    FROM analytics.fact_transactions ft
    JOIN analytics.dim_traffic_source ts USING (traffic_source_key)
    WHERE ts.campaign <> '(not set)'
    GROUP BY 1, 2
)
SELECT s.channel_group, s.campaign, s.sessions,
       COALESCE(t.purchasing_sessions, 0)                                            AS purchasing_sessions,
       ROUND(COALESCE(t.purchasing_sessions, 0)::NUMERIC / NULLIF(s.sessions, 0), 4) AS conversion_rate,
       COALESCE(t.revenue, 0)                                                        AS revenue,
       ROUND(COALESCE(t.revenue, 0) / NULLIF(s.sessions, 0), 2)                      AS revenue_per_session
FROM sess s
LEFT JOIN tx t USING (channel_group, campaign)
ORDER BY conversion_rate DESC;

-- 4.3 Monthly channel trend with each channel's share of that month's sessions
WITH sess AS (
    SELECT d.year_month, ts.channel_group, COUNT(*) AS sessions
    FROM analytics.fact_sessions fs
    JOIN analytics.dim_traffic_source ts USING (traffic_source_key)
    JOIN analytics.dim_date d ON d.date_key = fs.session_date_key
    GROUP BY 1, 2
),
tx AS (
    SELECT d.year_month, ts.channel_group,
           COUNT(DISTINCT ft.session_id) AS purchasing_sessions, SUM(ft.revenue) AS revenue
    FROM analytics.fact_transactions ft
    JOIN analytics.dim_traffic_source ts USING (traffic_source_key)
    JOIN analytics.dim_date d ON d.date_key = ft.session_date_key
    GROUP BY 1, 2
)
SELECT s.year_month, s.channel_group, s.sessions,
       ROUND(s.sessions::NUMERIC / SUM(s.sessions) OVER (PARTITION BY s.year_month), 4) AS share_of_month_sessions,
       COALESCE(t.purchasing_sessions, 0)                                                AS purchasing_sessions,
       ROUND(COALESCE(t.purchasing_sessions, 0)::NUMERIC / NULLIF(s.sessions, 0), 4)     AS conversion_rate,
       COALESCE(t.revenue, 0)                                                            AS revenue,
       ROUND((s.sessions - LAG(s.sessions) OVER w)::NUMERIC / NULLIF(LAG(s.sessions) OVER w, 0), 4) AS sessions_mom_growth
FROM sess s
LEFT JOIN tx t USING (year_month, channel_group)
WINDOW w AS (PARTITION BY s.channel_group ORDER BY s.year_month)
ORDER BY s.channel_group, s.year_month;
