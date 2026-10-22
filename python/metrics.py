"""
metrics.py
==========
Single source of truth for KPI and funnel logic used by the cleaning pipeline,
the analysis notebooks, and the automated tests. SQL (sql/05_conversion_funnel.sql)
and DAX (powerbi/dax_measures.md) implement the same definitions.

Funnel definition (session-based, ordered)
------------------------------------------
Stage 1  Session            every valid session
Stage 2  Product view       session has >= 1 product_view
Stage 3  Add to cart        add_to_cart at/after the session's first product_view
Stage 4  Checkout started   begin_checkout at/after the first qualifying add_to_cart
Stage 5  Purchase           purchase at/after the first qualifying begin_checkout

Each session is counted at most once per stage, and a session can only reach a
stage if it reached the previous one, so stage counts are monotonically
non-increasing by construction.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FUNNEL_STAGES = [
    (1, "Session", None),
    (2, "Product view", "product_view"),
    (3, "Add to cart", "add_to_cart"),
    (4, "Checkout started", "begin_checkout"),
    (5, "Purchase", "purchase"),
]
STAGE_FLAG_COLS = ["reached_session", "reached_product_view", "reached_add_to_cart",
                   "reached_checkout", "reached_purchase"]


def safe_divide(numerator, denominator, default=np.nan):
    """Division that returns `default` instead of raising/inf when the denominator is 0 or null.
    Works with scalars, pandas Series, or a mix of both (Series / scalar broadcasts)."""
    if isinstance(numerator, pd.Series) or isinstance(denominator, pd.Series):
        num = numerator.astype("float64") if isinstance(numerator, pd.Series) else float(numerator)
        if isinstance(denominator, pd.Series):
            den = denominator.astype("float64").where(denominator != 0)
        else:
            den = np.nan if (denominator is None or pd.isna(denominator) or denominator == 0) else float(denominator)
        out = num / den
        if not isinstance(out, pd.Series):
            out = pd.Series(out, index=numerator.index)
        return out if (isinstance(default, float) and np.isnan(default)) else out.fillna(default)
    if denominator is None or pd.isna(denominator) or denominator == 0:
        return default
    return numerator / denominator


def ordered_funnel_flags(sessions: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Return one row per session with ordered-funnel stage flags and first-qualifying timestamps.

    sessions: needs `session_id`
    events:   needs `session_id`, `event_name`, `event_timestamp` (datetime64)
    """
    out = pd.DataFrame({"session_id": sessions["session_id"].drop_duplicates().values})
    if out.empty:
        for c in STAGE_FLAG_COLS:
            out[c] = pd.Series(dtype="int64")
        return out
    prev_ts = None  # Series indexed by session_id with the previous stage's qualifying timestamp
    for order, label, event_name in FUNNEL_STAGES:
        if event_name is None:
            continue
        ev = events.loc[events["event_name"] == event_name, ["session_id", "event_timestamp"]]
        if prev_ts is not None:
            ev = ev.merge(prev_ts.rename("prev_ts"), left_on="session_id", right_index=True, how="inner")
            ev = ev[ev["event_timestamp"] >= ev["prev_ts"]]
        first = ev.groupby("session_id")["event_timestamp"].min()
        out[f"{event_name}_ts"] = out["session_id"].map(first)
        prev_ts = first
    out["reached_session"] = 1
    out["reached_product_view"] = out["product_view_ts"].notna().astype(int)
    out["reached_add_to_cart"] = out["add_to_cart_ts"].notna().astype(int)
    out["reached_checkout"] = out["begin_checkout_ts"].notna().astype(int)
    out["reached_purchase"] = out["purchase_ts"].notna().astype(int)
    return out


def funnel_summary(flags: pd.DataFrame) -> pd.DataFrame:
    """Aggregate per-session stage flags into a stage table with conversion & drop-off."""
    counts = [int(flags[c].sum()) if len(flags) else 0 for c in STAGE_FLAG_COLS]
    rows = []
    first = counts[0]
    for i, (order, label, _) in enumerate(FUNNEL_STAGES):
        nxt = counts[i + 1] if i + 1 < len(counts) else None
        rows.append({
            "stage_order": order,
            "stage": label,
            "sessions": counts[i],
            "pct_of_sessions": safe_divide(counts[i], first),
            "conversion_to_next": safe_divide(nxt, counts[i]) if nxt is not None else np.nan,
            "drop_off_rate": (1 - safe_divide(nxt, counts[i])) if (nxt is not None and counts[i]) else np.nan,
            "sessions_lost": (counts[i] - nxt) if nxt is not None else np.nan,
        })
    return pd.DataFrame(rows)


def kpi_summary(fact_sessions: pd.DataFrame, fact_transactions: pd.DataFrame) -> dict:
    """Headline KPIs with the same definitions as the DAX library."""
    sessions = len(fact_sessions)
    valid = fact_transactions
    revenue = float(valid["revenue"].sum()) if len(valid) else 0.0
    n_tx = int(valid["transaction_id"].nunique()) if len(valid) else 0
    purchasing = int(valid["session_id"].nunique()) if len(valid) else 0
    net = float(valid.loc[valid["transaction_status"] == "completed", "revenue"].sum()) if len(valid) else 0.0
    return {
        "total_sessions": sessions,
        "total_visitors": int(fact_sessions["visitor_id"].nunique()) if sessions else 0,
        "engaged_sessions": int(fact_sessions["engaged_session"].sum()) if sessions else 0,
        "engagement_rate": safe_divide(fact_sessions["engaged_session"].sum() if sessions else 0, sessions),
        "purchasing_sessions": purchasing,
        "purchase_conversion_rate": safe_divide(purchasing, sessions),
        "total_transactions": n_tx,
        "total_revenue": round(revenue, 2),
        "net_revenue": round(net, 2),
        "average_order_value": safe_divide(revenue, n_tx),
        "revenue_per_session": safe_divide(revenue, sessions),
    }


def segment_performance(fact_sessions: pd.DataFrame, fact_transactions: pd.DataFrame, by: str | list) -> pd.DataFrame:
    """Sessions, purchasing sessions, CVR, revenue, RPS, AOV and funnel completion by a session attribute.
    Revenue is attributed through the session (transactions inherit the session's attributes)."""
    by = [by] if isinstance(by, str) else by
    tx = fact_transactions.merge(fact_sessions[["session_id"] + by], on="session_id", how="inner")
    s = fact_sessions.groupby(by).agg(sessions=("session_id", "count"),
                                     engaged_sessions=("engaged_session", "sum"),
                                     funnel_purchases=("reached_purchase", "sum"),
                                     add_to_cart_sessions=("reached_add_to_cart", "sum"),
                                     checkout_sessions=("reached_checkout", "sum"))
    t = tx.groupby(by).agg(purchasing_sessions=("session_id", "nunique"),
                           transactions=("transaction_id", "nunique"),
                           revenue=("revenue", "sum"))
    out = s.join(t, how="left").fillna({"purchasing_sessions": 0, "transactions": 0, "revenue": 0.0})
    out["purchasing_sessions"] = out["purchasing_sessions"].astype(int)
    out["transactions"] = out["transactions"].astype(int)
    out["engagement_rate"] = safe_divide(out["engaged_sessions"], out["sessions"])
    out["conversion_rate"] = safe_divide(out["purchasing_sessions"], out["sessions"])
    out["revenue_per_session"] = safe_divide(out["revenue"], out["sessions"])
    out["average_order_value"] = safe_divide(out["revenue"], out["transactions"])
    out["add_to_cart_rate"] = safe_divide(out["add_to_cart_sessions"], out["sessions"])
    out["checkout_completion_rate"] = safe_divide(out["funnel_purchases"], out["checkout_sessions"])
    out["funnel_completion_rate"] = safe_divide(out["funnel_purchases"], out["sessions"])
    out["share_of_sessions"] = safe_divide(out["sessions"], out["sessions"].sum())
    out["share_of_revenue"] = safe_divide(out["revenue"], out["revenue"].sum())
    return out.reset_index().sort_values("sessions", ascending=False).reset_index(drop=True)


def wilson_interval(successes, trials, z: float = 1.96):
    """95% Wilson score interval for a proportion (used to flag small-sample conversion rates)."""
    successes = np.asarray(successes, dtype=float)
    trials = np.asarray(trials, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = successes / trials
        denom = 1 + z ** 2 / trials
        centre = (p + z ** 2 / (2 * trials)) / denom
        half = z * np.sqrt(p * (1 - p) / trials + z ** 2 / (4 * trials ** 2)) / denom
    return centre - half, centre + half
