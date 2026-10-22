-- =============================================================================
-- 01_create_tables.sql
-- Website Traffic & Conversion Funnel Analysis  (PostgreSQL 13+)
--
-- Two schemas:
--   raw        staging copies of the original CSV exports, every column TEXT,
--              so that malformed values load and can be profiled in SQL.
--   analytics  typed star schema built by python/clean_data.py
--              (data/processed/model/*.csv). Constraints enforce the business rules.
--
-- Re-runnable: drops and recreates both schemas.
-- =============================================================================

DROP SCHEMA IF EXISTS raw CASCADE;
DROP SCHEMA IF EXISTS analytics CASCADE;
CREATE SCHEMA raw;
CREATE SCHEMA analytics;

-- -----------------------------------------------------------------------------
-- RAW STAGING (as exported, untyped)
-- -----------------------------------------------------------------------------
CREATE TABLE raw.sessions (
    session_id        TEXT,
    visitor_id        TEXT,
    session_start     TEXT,
    traffic_source    TEXT,
    marketing_medium  TEXT,
    campaign          TEXT,
    device_category   TEXT,
    country           TEXT,
    landing_page      TEXT,
    engaged_session   TEXT
);

CREATE TABLE raw.events (
    event_id         TEXT,
    session_id       TEXT,
    event_timestamp  TEXT,
    event_name       TEXT,
    page_path        TEXT,
    product_id       TEXT
);

CREATE TABLE raw.transactions (
    transaction_id         TEXT,
    session_id             TEXT,
    transaction_timestamp  TEXT,
    revenue                TEXT,
    currency               TEXT,
    transaction_status     TEXT
);

-- -----------------------------------------------------------------------------
-- ANALYTICS: DIMENSIONS
-- -----------------------------------------------------------------------------
CREATE TABLE analytics.dim_date (
    date_key            INTEGER PRIMARY KEY,          -- yyyymmdd
    date                DATE    NOT NULL UNIQUE,
    year                SMALLINT NOT NULL,
    quarter             TEXT    NOT NULL,
    month_number        SMALLINT NOT NULL CHECK (month_number BETWEEN 1 AND 12),
    month_name          TEXT    NOT NULL,
    year_month          TEXT    NOT NULL,
    month_start         DATE    NOT NULL,
    week_start          DATE    NOT NULL,
    day_of_week_number  SMALLINT NOT NULL CHECK (day_of_week_number BETWEEN 1 AND 7),
    day_of_week         TEXT    NOT NULL,
    is_weekend          SMALLINT NOT NULL CHECK (is_weekend IN (0, 1))
);

CREATE TABLE analytics.dim_traffic_source (
    traffic_source_key  INTEGER PRIMARY KEY,
    traffic_source      TEXT NOT NULL,
    marketing_medium    TEXT NOT NULL,
    campaign            TEXT NOT NULL,
    channel_group       TEXT NOT NULL,
    source_medium       TEXT NOT NULL,
    UNIQUE (traffic_source, marketing_medium, campaign)
);

CREATE TABLE analytics.dim_device (
    device_key       INTEGER PRIMARY KEY,
    device_category  TEXT NOT NULL UNIQUE,
    device_label     TEXT NOT NULL,
    device_sort      SMALLINT NOT NULL
);

CREATE TABLE analytics.dim_landing_page (
    landing_page_key  INTEGER PRIMARY KEY,
    landing_page      TEXT NOT NULL UNIQUE,
    page_type         TEXT NOT NULL
);

CREATE TABLE analytics.dim_funnel_stage (
    stage_order  SMALLINT PRIMARY KEY,
    stage_name   TEXT NOT NULL,
    event_name   TEXT NOT NULL
);

-- -----------------------------------------------------------------------------
-- ANALYTICS: FACTS
-- Grain: fact_sessions = 1 row per session; fact_events = 1 row per event;
--        fact_transactions = 1 row per valid transaction.
-- Every fact carries the session's dimension keys so dimensions filter each
-- fact directly. Facts are never joined to each other in the BI model.
-- -----------------------------------------------------------------------------
CREATE TABLE analytics.fact_sessions (
    session_id                   TEXT PRIMARY KEY,
    visitor_id                   TEXT      NOT NULL,
    session_start                TIMESTAMP NOT NULL,
    session_date_key             INTEGER   NOT NULL REFERENCES analytics.dim_date (date_key),
    traffic_source_key           INTEGER   NOT NULL REFERENCES analytics.dim_traffic_source (traffic_source_key),
    device_key                   INTEGER   NOT NULL REFERENCES analytics.dim_device (device_key),
    landing_page_key             INTEGER   NOT NULL REFERENCES analytics.dim_landing_page (landing_page_key),
    country                      TEXT      NOT NULL,
    engaged_session              SMALLINT  NOT NULL CHECK (engaged_session IN (0, 1)),
    page_views                   INTEGER   NOT NULL CHECK (page_views >= 0),
    reached_session              SMALLINT  NOT NULL CHECK (reached_session = 1),
    reached_product_view         SMALLINT  NOT NULL CHECK (reached_product_view IN (0, 1)),
    reached_add_to_cart          SMALLINT  NOT NULL CHECK (reached_add_to_cart <= reached_product_view),
    reached_checkout             SMALLINT  NOT NULL CHECK (reached_checkout <= reached_add_to_cart),
    reached_purchase             SMALLINT  NOT NULL CHECK (reached_purchase <= reached_checkout),
    has_product_view_event       SMALLINT  NOT NULL,
    has_add_to_cart_event        SMALLINT  NOT NULL,
    has_begin_checkout_event     SMALLINT  NOT NULL,
    has_purchase_event           SMALLINT  NOT NULL,
    purchase_sequence_violation  SMALLINT  NOT NULL CHECK (purchase_sequence_violation IN (0, 1)),
    is_purchasing_session        SMALLINT  NOT NULL CHECK (is_purchasing_session IN (0, 1))
);

CREATE TABLE analytics.fact_events (
    event_id            TEXT PRIMARY KEY,
    session_id          TEXT      NOT NULL REFERENCES analytics.fact_sessions (session_id),
    event_timestamp     TIMESTAMP NOT NULL,
    event_date_key      INTEGER   NOT NULL REFERENCES analytics.dim_date (date_key),
    session_date_key    INTEGER   NOT NULL REFERENCES analytics.dim_date (date_key),
    event_name          TEXT      NOT NULL CHECK (event_name IN ('session_start', 'page_view', 'product_view',
                                                                 'add_to_cart', 'begin_checkout', 'purchase')),
    page_path           TEXT,
    product_id          TEXT,
    traffic_source_key  INTEGER   NOT NULL REFERENCES analytics.dim_traffic_source (traffic_source_key),
    device_key          INTEGER   NOT NULL REFERENCES analytics.dim_device (device_key),
    landing_page_key    INTEGER   NOT NULL REFERENCES analytics.dim_landing_page (landing_page_key)
);

CREATE TABLE analytics.fact_transactions (
    transaction_id         TEXT PRIMARY KEY,
    session_id             TEXT          NOT NULL REFERENCES analytics.fact_sessions (session_id),
    transaction_timestamp  TIMESTAMP     NOT NULL,
    transaction_date_key   INTEGER       NOT NULL REFERENCES analytics.dim_date (date_key),
    session_date_key       INTEGER       NOT NULL REFERENCES analytics.dim_date (date_key),
    traffic_source_key     INTEGER       NOT NULL REFERENCES analytics.dim_traffic_source (traffic_source_key),
    device_key             INTEGER       NOT NULL REFERENCES analytics.dim_device (device_key),
    landing_page_key       INTEGER       NOT NULL REFERENCES analytics.dim_landing_page (landing_page_key),
    revenue                NUMERIC(12,2) NOT NULL CHECK (revenue > 0),
    currency               CHAR(3)       NOT NULL CHECK (currency = 'USD'),
    transaction_status     TEXT          NOT NULL CHECK (transaction_status IN ('completed', 'refunded')),
    is_refunded            SMALLINT      NOT NULL CHECK (is_refunded IN (0, 1))
);

-- Indexes for the analytical access paths
CREATE INDEX ix_fs_date     ON analytics.fact_sessions (session_date_key);
CREATE INDEX ix_fs_source   ON analytics.fact_sessions (traffic_source_key);
CREATE INDEX ix_fs_device   ON analytics.fact_sessions (device_key);
CREATE INDEX ix_fs_lp       ON analytics.fact_sessions (landing_page_key);
CREATE INDEX ix_fe_session  ON analytics.fact_events (session_id, event_name, event_timestamp);
CREATE INDEX ix_ft_session  ON analytics.fact_transactions (session_id);
