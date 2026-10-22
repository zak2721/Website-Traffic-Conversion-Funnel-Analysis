"""
Automated data-quality and metric tests.

Run from the repository root:
    pytest -v

The PostgreSQL reconciliation test is skipped automatically when `psql` or the
database is unavailable (set PGDATABASE etc. to point at your database).
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

import clean_data as cd  # noqa: E402
import metrics as m  # noqa: E402
from data_quality import REQUIRED_COLUMNS  # noqa: E402

MODEL = ROOT / "data" / "processed" / "model"
PROCESSED = ROOT / "data" / "processed"


# ---------------------------------------------------------------- fixtures
@pytest.fixture(scope="session")
def model():
    fs = pd.read_csv(MODEL / "fact_sessions.csv", parse_dates=["session_start"])
    fe = pd.read_csv(MODEL / "fact_events.csv", parse_dates=["event_timestamp"])
    ft = pd.read_csv(MODEL / "fact_transactions.csv", parse_dates=["transaction_timestamp"])
    dims = {n: pd.read_csv(MODEL / f"{n}.csv") for n in
            ["dim_date", "dim_traffic_source", "dim_device", "dim_landing_page", "dim_funnel_stage"]}
    return fs, fe, ft, dims


@pytest.fixture(scope="session")
def enriched(model):
    fs, fe, ft, dims = model
    return fs.merge(dims["dim_traffic_source"], on="traffic_source_key").merge(dims["dim_device"], on="device_key")


# ---------------------------------------------------------------- schema
@pytest.mark.parametrize("name", ["sessions", "events", "transactions"])
def test_required_columns_clean_tables(name):
    df = pd.read_csv(PROCESSED / f"{name}_clean.csv", nrows=5)
    missing = set(REQUIRED_COLUMNS[name]) - set(df.columns)
    assert not missing, f"{name}_clean.csv missing {missing}"


def test_required_columns_model(model):
    fs, fe, ft, _ = model
    assert {"session_id", "visitor_id", "session_date_key", "traffic_source_key", "device_key",
            "landing_page_key", "engaged_session", "reached_purchase"} <= set(fs.columns)
    assert {"event_id", "session_id", "event_timestamp", "event_name"} <= set(fe.columns)
    assert {"transaction_id", "session_id", "revenue", "transaction_status", "session_date_key",
            "transaction_date_key"} <= set(ft.columns)


# ---------------------------------------------------------------- identifiers
def test_primary_keys_unique(model):
    fs, fe, ft, dims = model
    assert fs["session_id"].is_unique
    assert fe["event_id"].is_unique
    assert ft["transaction_id"].is_unique
    assert dims["dim_date"]["date_key"].is_unique
    assert dims["dim_traffic_source"]["traffic_source_key"].is_unique
    assert dims["dim_landing_page"]["landing_page_key"].is_unique


def test_no_null_identifiers(model):
    fs, fe, ft, _ = model
    assert fs[["session_id", "visitor_id"]].notna().all().all()
    assert fe[["event_id", "session_id"]].notna().all().all()
    assert ft[["transaction_id", "session_id"]].notna().all().all()


def test_session_references_valid(model):
    fs, fe, ft, _ = model
    sids = set(fs["session_id"])
    assert fe["session_id"].isin(sids).all(), "orphan events in model"
    assert ft["session_id"].isin(sids).all(), "orphan transactions in model"


def test_dimension_keys_resolve(model):
    fs, fe, ft, dims = model
    for fact in (fs, fe, ft):
        assert fact["traffic_source_key"].isin(dims["dim_traffic_source"]["traffic_source_key"]).all()
        assert fact["device_key"].isin(dims["dim_device"]["device_key"]).all()
        assert fact["landing_page_key"].isin(dims["dim_landing_page"]["landing_page_key"]).all()
    assert fs["session_date_key"].isin(dims["dim_date"]["date_key"]).all()
    assert ft["transaction_date_key"].isin(dims["dim_date"]["date_key"]).all()
    assert fe["event_date_key"].isin(dims["dim_date"]["date_key"]).all()


def test_dim_date_is_contiguous(model):
    d = pd.to_datetime(model[3]["dim_date"]["date"]).sort_values()
    assert (d.diff().dropna() == pd.Timedelta(days=1)).all()


# ---------------------------------------------------------------- timestamps
def test_timestamps_valid(model):
    fs, fe, ft, _ = model
    for s in (fs["session_start"], fe["event_timestamp"], ft["transaction_timestamp"]):
        assert s.notna().all()
        assert s.min() >= pd.Timestamp("2025-01-01") and s.max() < pd.Timestamp("2025-07-02")


def test_no_event_or_transaction_before_session_start(model):
    fs, fe, ft, _ = model
    start = fs.set_index("session_id")["session_start"]
    assert (fe["event_timestamp"] >= fe["session_id"].map(start)).all()
    assert (ft["transaction_timestamp"] >= ft["session_id"].map(start)).all()


# ---------------------------------------------------------------- revenue rules
def test_revenue_business_rules(model):
    ft = model[2]
    assert (ft["revenue"] > 0).all()
    assert ft["currency"].eq("USD").all()
    assert ft["transaction_status"].isin(["completed", "refunded"]).all()
    assert (ft["is_refunded"] == (ft["transaction_status"] == "refunded").astype(int)).all()


def test_quarantine_reasons_documented():
    q = pd.read_csv(PROCESSED / "quarantine_transactions.csv")
    assert q["quarantine_reason"].notna().all()
    assert set(q["quarantine_reason"]) <= {"test_order", "non_positive_revenue", "orphan_session_id",
                                           "before_session_start"}


# ---------------------------------------------------------------- funnel
def test_funnel_counts_monotonic(model):
    f = m.funnel_summary(model[0])
    assert f["sessions"].is_monotonic_decreasing
    assert f.loc[0, "sessions"] == len(model[0])


def test_funnel_flags_hierarchical(model):
    fs = model[0]
    cols = m.STAGE_FLAG_COLS
    for a, b in zip(cols, cols[1:]):
        assert (fs[b] <= fs[a]).all(), f"{b} reached without {a}"


def test_funnel_flags_recompute_from_events(model):
    fs, fe, _, _ = model
    flags = m.ordered_funnel_flags(fs[["session_id"]], fe).set_index("session_id")
    stored = fs.set_index("session_id")
    for c in m.STAGE_FLAG_COLS:
        assert (flags[c] == stored.loc[flags.index, c]).all(), c


def test_ordered_funnel_logic_on_toy_data():
    ts = pd.Timestamp("2025-01-01 10:00:00")
    sessions = pd.DataFrame({"session_id": ["A", "B", "C", "D"]})
    rows = [
        # A: perfect journey
        ("A", "product_view", 1), ("A", "add_to_cart", 2), ("A", "begin_checkout", 3), ("A", "purchase", 4),
        # B: purchase logged BEFORE checkout -> must stop at checkout
        ("B", "product_view", 1), ("B", "add_to_cart", 2), ("B", "purchase", 3), ("B", "begin_checkout", 4),
        # C: add_to_cart before any product_view -> stops at product view
        ("C", "add_to_cart", 1), ("C", "product_view", 2),
        # D: duplicate stage events count once
        ("D", "product_view", 1), ("D", "product_view", 2), ("D", "add_to_cart", 3), ("D", "add_to_cart", 4),
    ]
    ev = pd.DataFrame([{"session_id": s, "event_name": e, "event_timestamp": ts + pd.Timedelta(minutes=k)}
                       for s, e, k in rows])
    f = m.ordered_funnel_flags(sessions, ev).set_index("session_id")
    assert f.loc["A", "reached_purchase"] == 1
    assert f.loc["B", "reached_checkout"] == 1 and f.loc["B", "reached_purchase"] == 0
    assert f.loc["C", "reached_product_view"] == 1 and f.loc["C", "reached_add_to_cart"] == 0
    assert f.loc["D", "reached_add_to_cart"] == 1 and f.loc["D", "reached_checkout"] == 0
    summary = m.funnel_summary(f)
    assert summary["sessions"].tolist() == [4, 4, 3, 2, 1]


def test_purchasing_flag_matches_transactions(model):
    fs, _, ft, _ = model
    assert fs["is_purchasing_session"].sum() == ft["session_id"].nunique()


def test_funnel_vs_kpi_reconciliation(model):
    """Transaction-based purchasing sessions vs event-based funnel purchase stage must reconcile exactly."""
    fs = model[0]
    kpi = fs["is_purchasing_session"].sum()
    funnel = fs["reached_purchase"].sum()
    viol = fs["purchase_sequence_violation"].sum()
    tx_no_event = ((fs["is_purchasing_session"] == 1) & (fs["has_purchase_event"] == 0)).sum()
    ordered_no_tx = ((fs["reached_purchase"] == 1) & (fs["is_purchasing_session"] == 0)).sum()
    # sequence violations that also had a valid transaction
    viol_with_tx = ((fs["purchase_sequence_violation"] == 1) & (fs["is_purchasing_session"] == 1)).sum()
    assert funnel == kpi - viol_with_tx - tx_no_event + ordered_no_tx
    assert viol >= viol_with_tx


# ---------------------------------------------------------------- rates & safe division
def test_conversion_rates_within_bounds(enriched, model):
    ft = model[2]
    for by in ["channel_group", "device_label", "campaign"]:
        seg = m.segment_performance(enriched, ft, by)
        for c in ["conversion_rate", "engagement_rate", "add_to_cart_rate", "funnel_completion_rate"]:
            v = seg[c].dropna()
            assert ((v >= 0) & (v <= 1)).all(), f"{c} by {by} out of bounds"
        assert seg["checkout_completion_rate"].dropna().between(0, 1).all()


def test_safe_divide_handles_zero_and_null():
    assert np.isnan(m.safe_divide(5, 0))
    assert m.safe_divide(5, 0, default=0) == 0
    assert np.isnan(m.safe_divide(5, None))
    assert m.safe_divide(6, 3) == 2
    s = m.safe_divide(pd.Series([1, 2, 3]), pd.Series([1, 0, 3]))
    assert s.iloc[0] == 1 and np.isnan(s.iloc[1]) and s.iloc[2] == 1
    s2 = m.safe_divide(pd.Series([2, 4]), 2)
    assert s2.tolist() == [1, 2]
    assert m.safe_divide(pd.Series([2, 4]), 0).isna().all()


def test_empty_dataset_does_not_crash():
    fs = pd.DataFrame(columns=["session_id", "visitor_id", "engaged_session"] + m.STAGE_FLAG_COLS)
    ft = pd.DataFrame(columns=["transaction_id", "session_id", "revenue", "transaction_status"])
    k = m.kpi_summary(fs, ft)
    assert k["total_sessions"] == 0 and k["total_revenue"] == 0
    assert np.isnan(k["purchase_conversion_rate"]) and np.isnan(k["average_order_value"])
    f = m.funnel_summary(fs)
    assert f["sessions"].sum() == 0 and f["conversion_to_next"].isna().all()
    flags = m.ordered_funnel_flags(pd.DataFrame({"session_id": []}),
                                   pd.DataFrame(columns=["session_id", "event_name", "event_timestamp"]))
    assert len(flags) == 0


# ---------------------------------------------------------------- aggregation integrity
def test_revenue_has_no_fanout(enriched, model):
    ft = model[2]
    total = ft["revenue"].sum()
    for by in ["channel_group", "device_label"]:
        assert m.segment_performance(enriched, ft, by)["revenue"].sum() == pytest.approx(total, abs=0.005)


def test_dax_equivalent_measures_match_python(model):
    """Re-implements the documented DAX semantics (powerbi/dax_measures.md) in pandas.
    DAX itself cannot run here; this checks the definitions are numerically consistent."""
    fs, _, ft, dims = model
    k = m.kpi_summary(fs, ft)
    dax_total_sessions = fs["session_id"].nunique()                      # COUNTROWS(FactSessions)
    dax_purchasing = ft["session_id"].nunique()                          # DISTINCTCOUNT(FactTransactions[session_id])
    dax_revenue = ft["revenue"].sum()                                    # SUM(FactTransactions[revenue])
    dax_aov = dax_revenue / ft["transaction_id"].nunique()               # DIVIDE([Total Revenue],[Total Transactions])
    assert dax_total_sessions == k["total_sessions"]
    assert dax_purchasing == k["purchasing_sessions"]
    assert dax_revenue == pytest.approx(k["total_revenue"], abs=0.005)
    assert dax_aov == pytest.approx(k["average_order_value"])
    # active relationship = session date; inactive = transaction date. Monthly totals differ only by
    # orders that crossed midnight, and both must sum to the same grand total.
    by_session = ft.groupby(ft["session_date_key"] // 100)["revenue"].sum()
    by_tx = ft.groupby(ft["transaction_date_key"] // 100)["revenue"].sum()
    assert by_session.sum() == pytest.approx(by_tx.sum())


# ---------------------------------------------------------------- cleaning rules
def test_standardisation_rules():
    s = pd.Series([" Google", "IG", "direct", "www.dealsforum.com", None])
    out = cd.standardise(s, cd.SOURCE_ALIASES).str.replace(r"^www\.", "", regex=True)
    assert out.tolist()[:4] == ["google", "instagram", "(direct)", "dealsforum.com"]
    med = cd.standardise(pd.Series(["Paid Social", "paid-social", "PPC", "e-mail", "none"]), cd.MEDIUM_ALIASES, underscore=True)
    assert med.tolist() == ["paid_social", "paid_social", "cpc", "email", "(none)"]
    lp = cd.clean_landing_page(pd.Series(["/", "/collections/sale/", "/campaign/spring-sale?utm_source=facebook"]))
    assert lp.tolist() == ["/", "/collections/sale", "/campaign/spring-sale"]


def test_cleaning_recovers_generator_ground_truth(model):
    meta = json.loads((ROOT / "data" / "raw" / "generation_metadata.json").read_text())
    truth, d = meta["generated_before_defects"], meta["injected_defects"]
    fs, fe, ft, _ = model
    assert meta["synthetic"] is True
    assert len(fs) == truth["sessions"]
    assert len(fe) == truth["events"] - d["events_missing_purchase_event_with_transaction"]
    assert len(ft) == truth["transactions"] - d["transactions_negative_revenue"] - d["transactions_before_session_start"]


def test_raw_files_unchanged_by_cleaning():
    """Raw row counts must still equal what the generator wrote (cleaning never edits raw files)."""
    meta = json.loads((ROOT / "data" / "raw" / "generation_metadata.json").read_text())
    for name, n in meta["raw_row_counts"].items():
        assert len(pd.read_csv(ROOT / "data" / "raw" / f"{name}.csv", usecols=[0])) == n


# ---------------------------------------------------------------- cross-system reconciliation
def _psql_available():
    if not shutil.which("psql"):
        return False
    r = subprocess.run(["psql", "-At", "-c", "SELECT COUNT(*) FROM analytics.fact_sessions"],
                       capture_output=True, text=True, env={**os.environ, "PGDATABASE": os.environ.get("PGDATABASE", "webanalytics")})
    return r.returncode == 0


@pytest.mark.skipif(not _psql_available(), reason="PostgreSQL / psql not available or database not loaded")
def test_python_sql_totals_reconcile(model):
    fs, _, ft, _ = model
    env = {**os.environ, "PGDATABASE": os.environ.get("PGDATABASE", "webanalytics")}
    q = ("SELECT (SELECT COUNT(*) FROM analytics.fact_sessions), "
         "(SELECT COUNT(DISTINCT session_id) FROM analytics.fact_transactions), "
         "(SELECT SUM(revenue) FROM analytics.fact_transactions), "
         "(SELECT SUM(reached_purchase) FROM analytics.fact_sessions)")
    out = subprocess.run(["psql", "-At", "-F", "|", "-c", q], capture_output=True, text=True, env=env, check=True).stdout.strip()
    sessions, purchasing, revenue, funnel = out.split("|")
    k = m.kpi_summary(fs, ft)
    assert int(sessions) == k["total_sessions"]
    assert int(purchasing) == k["purchasing_sessions"]
    assert float(revenue) == pytest.approx(k["total_revenue"], abs=0.005)
    assert int(funnel) == fs["reached_purchase"].sum()
