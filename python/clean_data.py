"""
clean_data.py
=============
Cleans the raw sessions / events / transactions CSVs and builds the analysis-ready
star-schema tables used by SQL and Power BI.

Raw files in data/raw/ are never modified.

Outputs
-------
data/processed/sessions_clean.csv, events_clean.csv, transactions_clean.csv
data/processed/quarantine_events.csv, quarantine_transactions.csv   (excluded rows + reason)
data/processed/model/  fact_sessions, fact_events, fact_transactions,
                       dim_date, dim_traffic_source, dim_device, dim_landing_page, dim_funnel_stage
reports/metrics/cleaning_log.json                                   (every decision + rows affected)

Usage:
    python python/clean_data.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data_quality import parse_ts  # noqa: E402
from metrics import ordered_funnel_flags, FUNNEL_STAGES  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
MODEL = OUT / "model"

SOURCE_ALIASES = {"ig": "instagram", "direct": "(direct)"}
MEDIUM_ALIASES = {"ppc": "cpc", "e_mail": "email", "none": "(none)"}
DEVICE_ALIASES = {"pc": "desktop", "smartphone": "mobile", "ipad": "tablet"}
EVENT_ALIASES = {"pageview": "page_view", "view_item": "product_view", "checkout_start": "begin_checkout"}
CHANNEL_GROUP = {"organic": "Organic Search", "cpc": "Paid Search", "(none)": "Direct",
                 "paid_social": "Paid Social", "social": "Organic Social", "email": "Email",
                 "referral": "Referral"}

LOG: list[dict] = []


def log(step, table, rows, decision, rationale):
    LOG.append({"step": step, "table": table, "rows_affected": int(rows), "decision": decision,
                "rationale": rationale})


def norm_text(s: pd.Series) -> pd.Series:
    return s.astype("string").str.strip().str.lower()


def standardise(s: pd.Series, aliases: dict, underscore=False) -> pd.Series:
    out = norm_text(s)
    if underscore:
        out = out.str.replace(r"[\s\-]+", "_", regex=True)
    return out.replace(aliases)


def clean_landing_page(s: pd.Series) -> pd.Series:
    p = s.astype("string").str.strip().str.lower().str.split("?").str[0]
    return p.where(p == "/", p.str.rstrip("/"))


def page_type(path: str) -> str:
    if path == "/":
        return "Home"
    for prefix, label in [("/products/", "Product"), ("/collections/", "Collection"), ("/blog/", "Blog"),
                          ("/campaign/", "Campaign"), ("/search", "Search")]:
        if path.startswith(prefix):
            return label
    return "Other"


# --------------------------------------------------------------------------
def clean_sessions(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["session_start"] = parse_ts(df["session_start"])
    log("parse_timestamps", "sessions", df["session_start"].isna().sum(),
        "Parsed mixed ISO-8601 formats ('YYYY-MM-DD HH:MM:SS' and 'YYYY-MM-DDTHH:MM:SSZ') as UTC.",
        "Two export formats were mixed in one column; both represent UTC.")

    before = df[["traffic_source", "marketing_medium", "device_category"]].copy()
    df["traffic_source"] = standardise(df["traffic_source"], SOURCE_ALIASES).str.replace(r"^www\.", "", regex=True)
    df["marketing_medium"] = standardise(df["marketing_medium"], MEDIUM_ALIASES, underscore=True)
    df["device_category"] = standardise(df["device_category"], DEVICE_ALIASES)
    for c in before:
        changed = (before[c].astype("string") != df[c]).fillna(False).sum()
        log("standardise_labels", "sessions", changed, f"Trimmed, lower-cased and mapped aliases in `{c}`.",
            "Case/spelling variants would split one channel or device into several groups.")

    lp_before = df["landing_page"].copy()
    df["landing_page"] = clean_landing_page(df["landing_page"])
    log("normalise_landing_page", "sessions", (lp_before != df["landing_page"]).sum(),
        "Removed query strings (e.g. ?utm_source=...) and trailing slashes from landing_page.",
        "UTM parameters and slashes create duplicate page rows for the same URL.")

    n = df["device_category"].isna().sum()
    df["device_category"] = df["device_category"].fillna("unknown")
    log("fill_missing_device", "sessions", n, "Missing device_category set to 'unknown'; sessions retained.",
        "The session itself is valid; deleting it would understate traffic. 'unknown' is reported separately.")
    n = df["country"].isna().sum()
    df["country"] = df["country"].fillna("(not set)")
    log("fill_missing_country", "sessions", n, "Missing country set to '(not set)'; sessions retained.",
        "Country is descriptive only and not used in KPI denominators.")
    n = df["campaign"].isna().sum()
    df["campaign"] = df["campaign"].fillna("(not set)")
    log("fill_missing_campaign", "sessions", n, "Missing campaign set to '(not set)'.",
        "Expected: organic, direct and referral traffic has no campaign. This is not an error.")

    df["engaged_session"] = pd.to_numeric(df["engaged_session"], errors="coerce").fillna(0).astype(int)

    n0 = len(df)
    df = df.drop_duplicates()
    log("drop_exact_duplicates", "sessions", n0 - len(df),
        "Dropped rows identical after parsing/standardisation.",
        "Re-sent tracking payloads; some duplicates differed only in timestamp text format, "
        "so de-duplication is done after parsing rather than on raw strings.")
    n0 = len(df)
    df = df.sort_values("session_start").drop_duplicates("session_id", keep="first")
    log("drop_conflicting_duplicate_ids", "sessions", n0 - len(df),
        "Kept the earliest record for any session_id still duplicated.", "session_id must be unique.")

    df["channel_group"] = df["marketing_medium"].map(CHANNEL_GROUP).fillna("Other")
    return df.reset_index(drop=True)


def clean_events(raw: pd.DataFrame, valid_sessions: set) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = raw.copy()
    df["event_timestamp"] = parse_ts(df["event_timestamp"])
    before = df["event_name"].copy()
    df["event_name"] = standardise(df["event_name"], EVENT_ALIASES, underscore=True)
    log("standardise_event_names", "events", (before != df["event_name"]).sum(),
        "Normalised event names (case, spaces, hyphens) and mapped aliases "
        "(pageview→page_view, view_item→product_view, checkout_start→begin_checkout).",
        "Funnel stages are identified by event name; variants would silently drop sessions from stages.")
    df["page_path"] = clean_landing_page(df["page_path"])

    n0 = len(df)
    df = df.drop_duplicates()
    log("drop_exact_duplicates", "events", n0 - len(df), "Dropped rows identical after parsing/standardisation.",
        "Duplicate hits would inflate event counts (session-based stage counts are unaffected).")
    n0 = len(df)
    df = df.drop_duplicates("event_id", keep="first")
    log("drop_conflicting_duplicate_ids", "events", n0 - len(df), "Kept first record per event_id.",
        "event_id must be unique.")

    orphan = ~df["session_id"].isin(valid_sessions)
    q = df[orphan].assign(quarantine_reason="orphan_session_id")
    df = df[~orphan]
    log("quarantine_orphan_events", "events", len(q),
        "Moved events whose session_id is absent from the sessions table to quarantine_events.csv.",
        "Without a session they have no channel/device/landing page and cannot be attributed.")
    return df.reset_index(drop=True), q


def clean_transactions(raw: pd.DataFrame, sessions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = raw.copy()
    df["transaction_timestamp"] = parse_ts(df["transaction_timestamp"])
    df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce")
    before = df[["transaction_status", "currency"]].copy()
    df["transaction_status"] = norm_text(df["transaction_status"])
    df["currency"] = df["currency"].astype("string").str.strip().str.upper()
    log("standardise_labels", "transactions",
        ((before["transaction_status"] != df["transaction_status"]) | (before["currency"] != df["currency"])).sum(),
        "Lower-cased transaction_status and upper-cased currency codes.", "Case variants of the same value.")

    n0 = len(df)
    df = df.drop_duplicates()
    log("drop_exact_duplicates", "transactions", n0 - len(df), "Dropped rows identical after parsing.",
        "Duplicate order confirmations would double-count revenue.")
    n0 = len(df)
    df = df.drop_duplicates("transaction_id", keep="first")
    log("drop_conflicting_duplicate_ids", "transactions", n0 - len(df), "Kept first record per transaction_id.",
        "transaction_id must be unique.")

    s_start = sessions.set_index("session_id")["session_start"]
    reasons = pd.Series(pd.NA, index=df.index, dtype="string")
    rules = [
        ("test_order", df["transaction_status"].eq("test"),
         "Internal QA orders (status 'test') are not customer revenue."),
        ("non_positive_revenue", df["revenue"].isna() | (df["revenue"] <= 0),
         "Business rule: revenue must be > 0. Negative values on 'completed' orders look like sign errors, "
         "but the correct value cannot be confirmed, so they are excluded rather than 'fixed'."),
        ("orphan_session_id", ~df["session_id"].isin(s_start.index),
         "Revenue cannot be attributed to a channel without a session."),
        ("before_session_start", df["transaction_timestamp"] < df["session_id"].map(s_start),
         "A purchase cannot precede the session that produced it; record is unreliable."),
    ]
    for reason, mask, why in rules:
        new = mask & reasons.isna()
        reasons[new] = reason
        log(f"quarantine_{reason}", "transactions", new.sum(),
            f"Moved to quarantine_transactions.csv (reason='{reason}').", why)
    q = df[reasons.notna()].assign(quarantine_reason=reasons[reasons.notna()])
    df = df[reasons.isna()].copy()
    df["is_refunded"] = (df["transaction_status"] == "refunded").astype(int)
    log("retain_refunded", "transactions", df["is_refunded"].sum(),
        "Refunded orders retained (flag is_refunded=1). 'Total Revenue' = gross purchase revenue; "
        "'Net Revenue' excludes refunds.", "The purchase did happen (it is a conversion); refunds are a later event.")
    return df.reset_index(drop=True), q


# --------------------------------------------------------------------------
def build_model(sessions, events, transactions):
    MODEL.mkdir(parents=True, exist_ok=True)

    dates = pd.date_range(sessions["session_start"].min().normalize(),
                          max(sessions["session_start"].max(), events["event_timestamp"].max()).normalize(), freq="D")
    dim_date = pd.DataFrame({"date": dates})
    dim_date["date_key"] = dim_date["date"].dt.strftime("%Y%m%d").astype(int)
    dim_date["year"] = dim_date["date"].dt.year
    dim_date["quarter"] = "Q" + dim_date["date"].dt.quarter.astype(str)
    dim_date["month_number"] = dim_date["date"].dt.month
    dim_date["month_name"] = dim_date["date"].dt.strftime("%b")
    dim_date["year_month"] = dim_date["date"].dt.strftime("%Y-%m")
    dim_date["month_start"] = dim_date["date"].dt.to_period("M").dt.start_time
    dim_date["week_start"] = (dim_date["date"] - pd.to_timedelta(dim_date["date"].dt.weekday, unit="D"))
    dim_date["day_of_week_number"] = dim_date["date"].dt.weekday + 1
    dim_date["day_of_week"] = dim_date["date"].dt.strftime("%a")
    dim_date["is_weekend"] = (dim_date["date"].dt.weekday >= 5).astype(int)
    dim_date = dim_date[["date_key", "date", "year", "quarter", "month_number", "month_name", "year_month",
                         "month_start", "week_start", "day_of_week_number", "day_of_week", "is_weekend"]]

    ts = (sessions[["traffic_source", "marketing_medium", "campaign", "channel_group"]]
          .drop_duplicates().sort_values(["channel_group", "traffic_source", "marketing_medium", "campaign"])
          .reset_index(drop=True))
    ts.insert(0, "traffic_source_key", range(1, len(ts) + 1))
    ts["source_medium"] = ts["traffic_source"] + " / " + ts["marketing_medium"]

    dev = pd.DataFrame({"device_key": [1, 2, 3, 4],
                        "device_category": ["desktop", "mobile", "tablet", "unknown"],
                        "device_label": ["Desktop", "Mobile", "Tablet", "Unknown"],
                        "device_sort": [1, 2, 3, 4]})

    lp = pd.DataFrame({"landing_page": sorted(sessions["landing_page"].unique())})
    lp.insert(0, "landing_page_key", range(1, len(lp) + 1))
    lp["page_type"] = lp["landing_page"].map(page_type)

    stages = pd.DataFrame([{"stage_order": o, "stage_name": n, "event_name": e or "session_start"}
                           for o, n, e in FUNNEL_STAGES])

    s = (sessions.merge(ts, on=["traffic_source", "marketing_medium", "campaign", "channel_group"])
         .merge(dev[["device_key", "device_category"]], on="device_category")
         .merge(lp[["landing_page_key", "landing_page"]], on="landing_page"))
    s["session_date_key"] = s["session_start"].dt.strftime("%Y%m%d").astype(int)

    flags = ordered_funnel_flags(sessions, events)
    s = s.merge(flags, on="session_id", how="left")
    # unordered presence flags + sequence diagnostics
    pres = events.pivot_table(index="session_id", columns="event_name", values="event_id", aggfunc="count")
    for ev in ["product_view", "add_to_cart", "begin_checkout", "purchase"]:
        s[f"has_{ev}_event"] = s["session_id"].map(pres[ev] if ev in pres else pd.Series(dtype=float)).notna().astype(int)
    s["purchase_sequence_violation"] = ((s["has_purchase_event"] == 1) & (s["reached_purchase"] == 0)).astype(int)
    tx_sessions = set(transactions["session_id"])
    s["is_purchasing_session"] = s["session_id"].isin(tx_sessions).astype(int)
    s["page_views"] = s["session_id"].map(events[events.event_name == "page_view"].groupby("session_id").size()).fillna(0).astype(int)

    fact_sessions = s[["session_id", "visitor_id", "session_start", "session_date_key", "traffic_source_key",
                       "device_key", "landing_page_key", "country", "engaged_session", "page_views",
                       "reached_session", "reached_product_view", "reached_add_to_cart", "reached_checkout",
                       "reached_purchase", "has_product_view_event", "has_add_to_cart_event",
                       "has_begin_checkout_event", "has_purchase_event", "purchase_sequence_violation",
                       "is_purchasing_session"]].sort_values("session_start")

    keys = s[["session_id", "session_date_key", "traffic_source_key", "device_key", "landing_page_key"]]
    fe = events.merge(keys, on="session_id", how="inner")
    fe["event_date_key"] = fe["event_timestamp"].dt.strftime("%Y%m%d").astype(int)
    fact_events = fe[["event_id", "session_id", "event_timestamp", "event_date_key", "session_date_key",
                      "event_name", "page_path", "product_id", "traffic_source_key", "device_key",
                      "landing_page_key"]].sort_values("event_timestamp")

    ft = transactions.merge(keys, on="session_id", how="inner")
    ft["transaction_date_key"] = ft["transaction_timestamp"].dt.strftime("%Y%m%d").astype(int)
    fact_tx = ft[["transaction_id", "session_id", "transaction_timestamp", "transaction_date_key",
                  "session_date_key", "traffic_source_key", "device_key", "landing_page_key", "revenue",
                  "currency", "transaction_status", "is_refunded"]].sort_values("transaction_timestamp")

    out = {"fact_sessions": fact_sessions, "fact_events": fact_events, "fact_transactions": fact_tx,
           "dim_date": dim_date, "dim_traffic_source": ts, "dim_device": dev, "dim_landing_page": lp,
           "dim_funnel_stage": stages}
    for name, d in out.items():
        d.to_csv(MODEL / f"{name}.csv", index=False, date_format="%Y-%m-%d %H:%M:%S")
    # dim_date / month_start should be plain dates
    dim_date.assign(date=dim_date["date"].dt.date, month_start=dim_date["month_start"].dt.date,
                    week_start=dim_date["week_start"].dt.date).to_csv(MODEL / "dim_date.csv", index=False)
    return out


def main():
    raw = {n: pd.read_csv(RAW / f"{n}.csv", dtype=str) for n in ("sessions", "events", "transactions")}
    sessions = clean_sessions(raw["sessions"])
    events, q_events = clean_events(raw["events"], set(sessions["session_id"]))
    transactions, q_tx = clean_transactions(raw["transactions"], sessions)

    OUT.mkdir(parents=True, exist_ok=True)
    fmt = "%Y-%m-%d %H:%M:%S"
    sessions.drop(columns="channel_group").to_csv(OUT / "sessions_clean.csv", index=False, date_format=fmt)
    events.to_csv(OUT / "events_clean.csv", index=False, date_format=fmt)
    transactions.drop(columns="is_refunded").to_csv(OUT / "transactions_clean.csv", index=False, date_format=fmt)
    q_events.to_csv(OUT / "quarantine_events.csv", index=False, date_format=fmt)
    q_tx.to_csv(OUT / "quarantine_transactions.csv", index=False, date_format=fmt)

    model = build_model(sessions, events, transactions)
    viol = int(model["fact_sessions"]["purchase_sequence_violation"].sum())
    log("flag_sequence_violations", "fact_sessions", viol,
        "Sessions whose purchase event precedes checkout are kept but do NOT reach the ordered-funnel "
        "purchase stage (flag purchase_sequence_violation=1). Their valid transactions still count as revenue.",
        "Likely client clock skew. Removing the money would understate revenue; counting the journey would "
        "violate the ordered funnel definition.")

    summary = {"rows_out": {k: len(v) for k, v in model.items()},
               "quarantined": {"events": len(q_events), "transactions": len(q_tx)},
               "quarantined_revenue": round(float(q_tx.loc[q_tx.revenue > 0, "revenue"].sum()), 2),
               "steps": LOG}
    (ROOT / "reports" / "metrics").mkdir(parents=True, exist_ok=True)
    (ROOT / "reports" / "metrics" / "cleaning_log.json").write_text(json.dumps(summary, indent=2, default=str))
    for e in LOG:
        print(f"[{e['table']:<13}] {e['step']:<34} rows={e['rows_affected']:>6,}")
    print(json.dumps({k: v for k, v in summary.items() if k != "steps"}, indent=2))


if __name__ == "__main__":
    main()
