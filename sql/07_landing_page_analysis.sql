-- =============================================================================
-- 07_landing_page_analysis.sql
-- High-traffic pages, low-converting pages, top revenue pages, and a
-- reproducible "investigate" flag:
--   material traffic  : page carries >= 2% of all sessions in the period
--   significantly low : upper bound of the 95% Wilson interval for the page's
--                       conversion rate is BELOW the site-wide conversion rate
-- Same rule as python/analysis.py (landing_page_table).
-- =============================================================================

-- 7.1 Landing-page scorecard with investigation flag
WITH params AS (SELECT DATE '2025-01-01' AS start_date, DATE '2025-06-30' AS end_date,
                       1.96::NUMERIC AS z, 0.02::NUMERIC AS materiality_share),
sess AS (
    SELECT fs.landing_page_key,
           COUNT(*)                    AS sessions,
           SUM(fs.engaged_session)     AS engaged_sessions,
           SUM(fs.reached_add_to_cart) AS add_to_cart_sessions
    FROM analytics.fact_sessions fs
    JOIN analytics.dim_date d ON d.date_key = fs.session_date_key
    CROSS JOIN params p
    WHERE d.date BETWEEN p.start_date AND p.end_date
    GROUP BY fs.landing_page_key
),
tx AS (
    SELECT ft.landing_page_key,
           COUNT(DISTINCT ft.session_id) AS purchasing_sessions,
           SUM(ft.revenue)               AS revenue
    FROM analytics.fact_transactions ft
    JOIN analytics.dim_date d ON d.date_key = ft.session_date_key
    CROSS JOIN params p
    WHERE d.date BETWEEN p.start_date AND p.end_date
    GROUP BY ft.landing_page_key
),
lp AS (
    SELECT l.landing_page, l.page_type, s.sessions, s.engaged_sessions, s.add_to_cart_sessions,
           COALESCE(t.purchasing_sessions, 0) AS purchasing_sessions,
           COALESCE(t.revenue, 0)             AS revenue,
           COALESCE(t.purchasing_sessions, 0)::NUMERIC / NULLIF(s.sessions, 0) AS cvr
    FROM sess s
    JOIN analytics.dim_landing_page l USING (landing_page_key)
    LEFT JOIN tx t USING (landing_page_key)
),
site AS (
    SELECT SUM(purchasing_sessions)::NUMERIC / NULLIF(SUM(sessions), 0) AS site_cvr,
           SUM(sessions) AS total_sessions
    FROM lp
),
scored AS (
    SELECT lp.*, site.site_cvr,
           lp.sessions::NUMERIC / site.total_sessions AS share_of_sessions,
           -- Wilson score interval upper bound
           (lp.cvr + p.z^2 / (2 * lp.sessions)
              + p.z * SQRT(lp.cvr * (1 - lp.cvr) / lp.sessions + p.z^2 / (4 * lp.sessions^2.0)))
           / (1 + p.z^2 / lp.sessions) AS cvr_ci_high,
           p.materiality_share
    FROM lp CROSS JOIN site CROSS JOIN params p
)
SELECT landing_page, page_type, sessions,
       ROUND(share_of_sessions, 4)                                  AS share_of_sessions,
       ROUND(engaged_sessions::NUMERIC / NULLIF(sessions, 0), 4)    AS engagement_rate,
       ROUND(add_to_cart_sessions::NUMERIC / NULLIF(sessions, 0), 4) AS add_to_cart_rate,
       purchasing_sessions,
       ROUND(cvr, 4)                                                AS conversion_rate,
       ROUND(cvr_ci_high, 4)                                        AS cvr_ci_high,
       revenue,
       ROUND(revenue / NULLIF(sessions, 0), 2)                      AS revenue_per_session,
       RANK() OVER (ORDER BY sessions DESC)                         AS traffic_rank,
       RANK() OVER (ORDER BY revenue DESC)                          AS revenue_rank,
       (share_of_sessions >= materiality_share AND cvr_ci_high < site_cvr) AS investigate
FROM scored
ORDER BY sessions DESC;

-- 7.2 Pages that attract traffic but under-convert, ranked by "lost purchases"
--     (sessions × gap to site CVR). This is a prioritisation heuristic, not a forecast.
WITH lp AS (
    SELECT l.landing_page, COUNT(DISTINCT fs.session_id) AS sessions,
           COUNT(DISTINCT ft.session_id) AS purchasing_sessions
    FROM analytics.fact_sessions fs
    JOIN analytics.dim_landing_page l USING (landing_page_key)
    LEFT JOIN analytics.fact_transactions ft USING (session_id)   -- row-level join: COUNT(*) would fan out if a
    GROUP BY l.landing_page                                        -- session had 2+ transactions (none do today)
),
site AS (SELECT SUM(purchasing_sessions)::NUMERIC / SUM(sessions) AS site_cvr FROM lp)
SELECT landing_page, sessions, purchasing_sessions,
       ROUND(purchasing_sessions::NUMERIC / sessions, 4)                        AS conversion_rate,
       ROUND(site.site_cvr, 4)                                                  AS site_cvr,
       ROUND(GREATEST(sessions * site.site_cvr - purchasing_sessions, 0), 1)    AS purchase_gap_vs_site_avg
FROM lp CROSS JOIN site
ORDER BY purchase_gap_vs_site_avg DESC;

-- 7.3 Landing page × device conversion for the pages flagged by 7.1
SELECT l.landing_page, dv.device_label,
       COUNT(*)                                                       AS sessions,
       ROUND(AVG(fs.is_purchasing_session::NUMERIC), 4)               AS conversion_rate,
       ROUND(AVG(fs.reached_add_to_cart::NUMERIC), 4)                 AS add_to_cart_rate
FROM analytics.fact_sessions fs
JOIN analytics.dim_landing_page l USING (landing_page_key)
JOIN analytics.dim_device dv USING (device_key)
WHERE l.landing_page IN ('/collections/sale', '/campaign/spring-sale',
                         '/blog/how-to-choose-running-shoes', '/blog/summer-style-guide')
  AND dv.device_category <> 'unknown'
GROUP BY l.landing_page, dv.device_label, dv.device_sort
ORDER BY l.landing_page, dv.device_sort;
