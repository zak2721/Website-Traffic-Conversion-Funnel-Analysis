-- =============================================================================
-- 03_traffic_analysis.sql
-- Traffic volume, visitors, engagement, trends and source/medium distribution.
-- Change the dates in the `params` CTE of each query to filter the period.
-- =============================================================================

-- 3.1 Headline traffic KPIs for the period
WITH params AS (SELECT DATE '2025-01-01' AS start_date, DATE '2025-06-30' AS end_date),
s AS (
    SELECT fs.*
    FROM analytics.fact_sessions fs
    JOIN analytics.dim_date d ON d.date_key = fs.session_date_key
    CROSS JOIN params p
    WHERE d.date BETWEEN p.start_date AND p.end_date
)
SELECT COUNT(*)                                                        AS total_sessions,
       COUNT(DISTINCT visitor_id)                                      AS distinct_visitors,
       ROUND(COUNT(*)::NUMERIC / NULLIF(COUNT(DISTINCT visitor_id), 0), 3) AS sessions_per_visitor,
       SUM(engaged_session)                                            AS engaged_sessions,
       ROUND(SUM(engaged_session)::NUMERIC / NULLIF(COUNT(*), 0), 4)   AS engagement_rate,
       ROUND(AVG(page_views), 2)                                       AS avg_page_views_per_session
FROM s;

-- 3.2 Daily trend with 7-day moving average and day-over-day change
WITH params AS (SELECT DATE '2025-01-01' AS start_date, DATE '2025-06-30' AS end_date),
daily AS (
    SELECT d.date, d.day_of_week, d.is_weekend,
           COUNT(fs.session_id)                 AS sessions,
           COALESCE(SUM(fs.engaged_session), 0) AS engaged_sessions
    FROM analytics.dim_date d
    CROSS JOIN params p
    LEFT JOIN analytics.fact_sessions fs ON fs.session_date_key = d.date_key
    WHERE d.date BETWEEN p.start_date AND p.end_date
    GROUP BY d.date, d.day_of_week, d.is_weekend
)
SELECT date, day_of_week, is_weekend, sessions,
       ROUND(AVG(sessions) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 1) AS sessions_7d_avg,
       sessions - LAG(sessions) OVER (ORDER BY date)                                         AS change_vs_prior_day,
       ROUND(engaged_sessions::NUMERIC / NULLIF(sessions, 0), 4)                              AS engagement_rate
FROM daily
ORDER BY date;

-- 3.3 Monthly trend with month-over-month growth (LAG window function)
WITH params AS (SELECT DATE '2025-01-01' AS start_date, DATE '2025-06-30' AS end_date),
monthly AS (
    SELECT d.year_month,
           COUNT(*)                   AS sessions,
           COUNT(DISTINCT visitor_id) AS visitors,
           SUM(engaged_session)       AS engaged_sessions
    FROM analytics.fact_sessions fs
    JOIN analytics.dim_date d ON d.date_key = fs.session_date_key
    CROSS JOIN params p
    WHERE d.date BETWEEN p.start_date AND p.end_date
    GROUP BY d.year_month
)
SELECT year_month, sessions, visitors,
       ROUND(engaged_sessions::NUMERIC / NULLIF(sessions, 0), 4) AS engagement_rate,
       LAG(sessions) OVER (ORDER BY year_month)                  AS prior_month_sessions,
       ROUND((sessions - LAG(sessions) OVER (ORDER BY year_month))::NUMERIC
             / NULLIF(LAG(sessions) OVER (ORDER BY year_month), 0), 4) AS sessions_mom_growth
FROM monthly
ORDER BY year_month;

-- 3.4 Weekday vs weekend traffic profile
SELECT d.day_of_week_number, d.day_of_week,
       COUNT(*)                                                    AS sessions,
       ROUND(COUNT(*)::NUMERIC / COUNT(DISTINCT d.date), 1)        AS avg_sessions_per_day
FROM analytics.fact_sessions fs
JOIN analytics.dim_date d ON d.date_key = fs.session_date_key
GROUP BY d.day_of_week_number, d.day_of_week
ORDER BY d.day_of_week_number;

-- 3.5 Traffic distribution by source / medium with share of total
WITH params AS (SELECT DATE '2025-01-01' AS start_date, DATE '2025-06-30' AS end_date)
SELECT ts.channel_group, ts.source_medium,
       COUNT(*)                                                       AS sessions,
       ROUND(COUNT(*)::NUMERIC / SUM(COUNT(*)) OVER (), 4)            AS share_of_sessions,
       ROUND(AVG(fs.engaged_session), 4)                              AS engagement_rate,
       RANK() OVER (ORDER BY COUNT(*) DESC)                           AS traffic_rank
FROM analytics.fact_sessions fs
JOIN analytics.dim_traffic_source ts USING (traffic_source_key)
JOIN analytics.dim_date d ON d.date_key = fs.session_date_key
CROSS JOIN params p
WHERE d.date BETWEEN p.start_date AND p.end_date
GROUP BY ts.channel_group, ts.source_medium
ORDER BY sessions DESC;
