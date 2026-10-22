-- =============================================================================
-- 06_device_analysis.sql
-- Desktop vs mobile vs tablet: sessions, conversion, revenue per session,
-- funnel completion, and a within-channel comparison that controls for the
-- fact that mobile traffic is concentrated in social channels.
-- 'unknown' device sessions (missing in source) are excluded from comparisons.
-- =============================================================================

-- 6.1 Device scorecard
WITH params AS (SELECT DATE '2025-01-01' AS start_date, DATE '2025-06-30' AS end_date),
sess AS (
    SELECT fs.device_key,
           COUNT(*)                  AS sessions,
           SUM(fs.engaged_session)   AS engaged_sessions,
           SUM(fs.reached_checkout)  AS checkout_sessions,
           SUM(fs.reached_purchase)  AS funnel_purchases
    FROM analytics.fact_sessions fs
    JOIN analytics.dim_date d ON d.date_key = fs.session_date_key
    CROSS JOIN params p
    WHERE d.date BETWEEN p.start_date AND p.end_date
    GROUP BY fs.device_key
),
tx AS (
    SELECT ft.device_key,
           COUNT(DISTINCT ft.session_id)     AS purchasing_sessions,
           COUNT(DISTINCT ft.transaction_id) AS transactions,
           SUM(ft.revenue)                   AS revenue
    FROM analytics.fact_transactions ft
    JOIN analytics.dim_date d ON d.date_key = ft.session_date_key
    CROSS JOIN params p
    WHERE d.date BETWEEN p.start_date AND p.end_date
    GROUP BY ft.device_key
)
SELECT dv.device_label,
       s.sessions,
       ROUND(s.sessions::NUMERIC / SUM(s.sessions) OVER (), 4)                       AS share_of_sessions,
       ROUND(s.engaged_sessions::NUMERIC / NULLIF(s.sessions, 0), 4)                 AS engagement_rate,
       COALESCE(t.purchasing_sessions, 0)                                            AS purchasing_sessions,
       ROUND(COALESCE(t.purchasing_sessions, 0)::NUMERIC / NULLIF(s.sessions, 0), 4) AS conversion_rate,
       COALESCE(t.revenue, 0)                                                        AS revenue,
       ROUND(COALESCE(t.revenue, 0) / NULLIF(SUM(COALESCE(t.revenue, 0)) OVER (), 0), 4) AS share_of_revenue,
       ROUND(COALESCE(t.revenue, 0) / NULLIF(s.sessions, 0), 2)                      AS revenue_per_session,
       ROUND(t.revenue / NULLIF(t.transactions, 0), 2)                               AS average_order_value,
       ROUND(s.funnel_purchases::NUMERIC / NULLIF(s.checkout_sessions, 0), 4)        AS checkout_completion_rate,
       ROUND(s.funnel_purchases::NUMERIC / NULLIF(s.sessions, 0), 4)                 AS funnel_completion_rate
FROM sess s
JOIN analytics.dim_device dv USING (device_key)
LEFT JOIN tx t USING (device_key)
WHERE dv.device_category <> 'unknown'
ORDER BY dv.device_sort;

-- 6.2 Device conversion WITHIN each channel (controls for channel mix)
WITH sess AS (
    SELECT ts.channel_group, fs.device_key, COUNT(*) AS sessions
    FROM analytics.fact_sessions fs
    JOIN analytics.dim_traffic_source ts USING (traffic_source_key)
    GROUP BY 1, 2
),
tx AS (
    SELECT ts.channel_group, ft.device_key, COUNT(DISTINCT ft.session_id) AS purchasing_sessions
    FROM analytics.fact_transactions ft
    JOIN analytics.dim_traffic_source ts USING (traffic_source_key)
    GROUP BY 1, 2
),
cvr AS (
    SELECT s.channel_group, dv.device_category, s.sessions,
           COALESCE(t.purchasing_sessions, 0)::NUMERIC / NULLIF(s.sessions, 0) AS conversion_rate
    FROM sess s
    JOIN analytics.dim_device dv USING (device_key)
    LEFT JOIN tx t USING (channel_group, device_key)
    WHERE dv.device_category IN ('desktop', 'mobile')
)
SELECT channel_group,
       MAX(sessions)        FILTER (WHERE device_category = 'desktop')           AS desktop_sessions,
       MAX(sessions)        FILTER (WHERE device_category = 'mobile')            AS mobile_sessions,
       ROUND(MAX(conversion_rate) FILTER (WHERE device_category = 'desktop'), 4) AS desktop_cvr,
       ROUND(MAX(conversion_rate) FILTER (WHERE device_category = 'mobile'), 4)  AS mobile_cvr,
       ROUND(MAX(conversion_rate) FILTER (WHERE device_category = 'mobile')
             / NULLIF(MAX(conversion_rate) FILTER (WHERE device_category = 'desktop'), 0), 3) AS mobile_to_desktop_ratio
FROM cvr
GROUP BY channel_group
ORDER BY mobile_to_desktop_ratio;

-- 6.3 Device mix by channel (explains why raw device comparisons can mislead)
SELECT ts.channel_group,
       ROUND(AVG(CASE WHEN dv.device_category = 'mobile'  THEN 1.0 ELSE 0 END), 4) AS mobile_share,
       ROUND(AVG(CASE WHEN dv.device_category = 'desktop' THEN 1.0 ELSE 0 END), 4) AS desktop_share,
       ROUND(AVG(CASE WHEN dv.device_category = 'tablet'  THEN 1.0 ELSE 0 END), 4) AS tablet_share
FROM analytics.fact_sessions fs
JOIN analytics.dim_traffic_source ts USING (traffic_source_key)
JOIN analytics.dim_device dv USING (device_key)
GROUP BY ts.channel_group
ORDER BY mobile_share DESC;
