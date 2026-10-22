-- =============================================================================
-- 01b_load_data.sql
-- Loads the CSV files with psql's client-side \copy (no superuser or server file
-- access needed). Run from the REPOSITORY ROOT so the relative paths resolve:
--
--     psql -v ON_ERROR_STOP=1 -d webanalytics -f sql/01b_load_data.sql
--
-- Connection details come from standard libpq variables (PGHOST, PGPORT,
-- PGUSER, PGDATABASE, PGPASSWORD or ~/.pgpass). Never hard-code credentials.
-- =============================================================================

\echo 'Loading raw staging tables...'
TRUNCATE raw.sessions, raw.events, raw.transactions;
\copy raw.sessions     FROM 'data/raw/sessions.csv'     WITH (FORMAT csv, HEADER true)
\copy raw.events       FROM 'data/raw/events.csv'       WITH (FORMAT csv, HEADER true)
\copy raw.transactions FROM 'data/raw/transactions.csv' WITH (FORMAT csv, HEADER true)

\echo 'Loading analytics star schema (dimensions first, then facts)...'
TRUNCATE analytics.fact_transactions, analytics.fact_events, analytics.fact_sessions,
         analytics.dim_funnel_stage, analytics.dim_landing_page, analytics.dim_device,
         analytics.dim_traffic_source, analytics.dim_date;
\copy analytics.dim_date           FROM 'data/processed/model/dim_date.csv'           WITH (FORMAT csv, HEADER true)
\copy analytics.dim_traffic_source FROM 'data/processed/model/dim_traffic_source.csv' WITH (FORMAT csv, HEADER true)
\copy analytics.dim_device         FROM 'data/processed/model/dim_device.csv'         WITH (FORMAT csv, HEADER true)
\copy analytics.dim_landing_page   FROM 'data/processed/model/dim_landing_page.csv'   WITH (FORMAT csv, HEADER true)
\copy analytics.dim_funnel_stage   FROM 'data/processed/model/dim_funnel_stage.csv'   WITH (FORMAT csv, HEADER true)
\copy analytics.fact_sessions      FROM 'data/processed/model/fact_sessions.csv'      WITH (FORMAT csv, HEADER true)
\copy analytics.fact_events        FROM 'data/processed/model/fact_events.csv'        WITH (FORMAT csv, HEADER true)
\copy analytics.fact_transactions  FROM 'data/processed/model/fact_transactions.csv'  WITH (FORMAT csv, HEADER true)

ANALYZE;

SELECT 'raw.sessions' AS table_name, COUNT(*) AS row_count FROM raw.sessions
UNION ALL SELECT 'raw.events', COUNT(*) FROM raw.events
UNION ALL SELECT 'raw.transactions', COUNT(*) FROM raw.transactions
UNION ALL SELECT 'analytics.fact_sessions', COUNT(*) FROM analytics.fact_sessions
UNION ALL SELECT 'analytics.fact_events', COUNT(*) FROM analytics.fact_events
UNION ALL SELECT 'analytics.fact_transactions', COUNT(*) FROM analytics.fact_transactions;
