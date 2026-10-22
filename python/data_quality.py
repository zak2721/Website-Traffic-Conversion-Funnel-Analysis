"""
data_quality.py
===============
Reusable data-quality profiling for the sessions / events / transactions tables.
The same checks are run on the raw files (before cleaning) and on the cleaned
files (after cleaning) so the impact of every cleaning decision is measurable.

Usage:
    python python/data_quality.py --stage raw        # profile data/raw
    python python/data_quality.py --stage processed  # profile data/processed
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_COLUMNS = {
    "sessions": ["session_id", "visitor_id", "session_start", "traffic_source", "marketing_medium",
                 "campaign", "device_category", "country", "landing_page", "engaged_session"],
    "events": ["event_id", "session_id", "event_timestamp", "event_name", "page_path", "product_id"],
    "transactions": ["transaction_id", "session_id", "transaction_timestamp", "revenue", "currency",
                     "transaction_status"],
}
PRIMARY_KEYS = {"sessions": "session_id", "events": "event_id", "transactions": "transaction_id"}
TIMESTAMP_COLS = {"sessions": "session_start", "events": "event_timestamp", "transactions": "transaction_timestamp"}

ALLOWED = {
    "traffic_source": {"google", "bing", "(direct)", "facebook", "instagram", "newsletter",
                       "partnerblog.com", "dealsforum.com", "tiktok"},
    "marketing_medium": {"organic", "cpc", "(none)", "paid_social", "email", "referral", "social"},
    "device_category": {"desktop", "mobile", "tablet", "unknown"},
    "event_name": {"session_start", "page_view", "product_view", "add_to_cart", "begin_checkout", "purchase"},
    "transaction_status": {"completed", "refunded"},
    "currency": {"USD"},
}


def parse_ts(s: pd.Series) -> pd.Series:
    """Parse mixed ISO-8601 strings ('2025-01-01 10:00:00' and '2025-01-01T10:00:00Z') as naive UTC."""
    out = pd.to_datetime(s, format="ISO8601", errors="coerce", utc=True)
    return out.dt.tz_localize(None)


def load(stage: str):
    base = ROOT / "data" / ("raw" if stage == "raw" else "processed")
    suffix = "" if stage == "raw" else "_clean"
    return {name: pd.read_csv(base / f"{name}{suffix}.csv", dtype=str, keep_default_na=True)
            for name in ("sessions", "events", "transactions")}


def profile_table(name: str, df: pd.DataFrame) -> dict:
    pk = PRIMARY_KEYS[name]
    ts = parse_ts(df[TIMESTAMP_COLS[name]])
    res = {
        "rows": int(len(df)),
        "columns": list(df.columns),
        "missing_required_columns": [c for c in REQUIRED_COLUMNS[name] if c not in df.columns],
        "missing_values": {c: int(v) for c, v in df.isna().sum().items() if v > 0},
        "exact_duplicate_rows": int(df.duplicated().sum()),
        "duplicate_primary_keys": int(df[pk].duplicated().sum()),
        "null_primary_keys": int(df[pk].isna().sum()),
        "unparseable_timestamps": int(ts.isna().sum() - df[TIMESTAMP_COLS[name]].isna().sum()),
        "timestamp_min": str(ts.min()), "timestamp_max": str(ts.max()),
        "non_standard_labels": {},
    }
    for col, allowed in ALLOWED.items():
        if col in df.columns:
            bad = df.loc[df[col].notna() & ~df[col].isin(allowed), col]
            if len(bad):
                res["non_standard_labels"][col] = {"rows": int(len(bad)),
                                                   "examples": sorted(bad.unique().tolist())[:12]}
    return res


def relationship_checks(t: dict) -> dict:
    s, e, tx = t["sessions"], t["events"], t["transactions"]
    sids = set(s["session_id"].dropna())
    rev = pd.to_numeric(tx["revenue"], errors="coerce")
    status = tx["transaction_status"].str.strip().str.lower()

    # timestamp logic
    s_start = s.drop_duplicates("session_id").set_index("session_id")["session_start"].pipe(parse_ts)
    tx_ts = parse_ts(tx["transaction_timestamp"])
    tx_before_session = int((tx_ts < tx["session_id"].map(s_start)).sum())
    e_ts = parse_ts(e["event_timestamp"])
    ev_before_session = int((e_ts < e["session_id"].map(s_start)).sum())

    # purchase vs checkout ordering (standard labels only; label variants are a separate check)
    en = e["event_name"]
    first_co = e_ts[en == "begin_checkout"].groupby(e.loc[en == "begin_checkout", "session_id"]).min()
    last_pur = e_ts[en == "purchase"].groupby(e.loc[en == "purchase", "session_id"]).max()
    both = pd.concat([first_co.rename("co"), last_pur.rename("pur")], axis=1).dropna()
    pur_sessions = set(e.loc[en == "purchase", "session_id"])
    tx_sessions = set(tx.loc[status.isin(["completed", "refunded"]) & (rev > 0), "session_id"])

    return {
        "orphan_events (session_id not in sessions)": int((~e["session_id"].isin(sids)).sum()),
        "orphan_transactions (session_id not in sessions)": int((~tx["session_id"].isin(sids)).sum()),
        "events_before_session_start": ev_before_session,
        "transactions_before_session_start": tx_before_session,
        "revenue_unparseable": int(rev.isna().sum() - tx["revenue"].isna().sum()),
        "revenue_negative": int((rev < 0).sum()),
        "revenue_zero": int((rev == 0).sum()),
        "test_transactions": int((status == "test").sum()),
        "sessions_with_purchase_before_checkout": int((both["pur"] < both["co"]).sum()),
        "sessions_with_transaction_but_no_purchase_event": len(tx_sessions - pur_sessions),
        "sessions_with_purchase_event_but_no_valid_transaction": len((pur_sessions & sids) - tx_sessions),
        "sessions_without_session_start_event": len(sids - set(e.loc[en == "session_start", "session_id"])),
    }


def run(stage: str) -> dict:
    tables = load(stage)
    report = {"stage": stage, "tables": {n: profile_table(n, df) for n, df in tables.items()},
              "relationships": relationship_checks(tables)}
    return report


def to_markdown(rep: dict) -> str:
    lines = [f"## Data-quality profile: `{rep['stage']}`", ""]
    lines += ["| Table | Rows | Exact duplicate rows | Duplicate PKs | Unparseable timestamps | Timestamp range |",
              "|---|---:|---:|---:|---:|---|"]
    for n, p in rep["tables"].items():
        lines.append(f"| {n} | {p['rows']:,} | {p['exact_duplicate_rows']:,} | {p['duplicate_primary_keys']:,} | "
                     f"{p['unparseable_timestamps']:,} | {p['timestamp_min'][:19]} → {p['timestamp_max'][:19]} |")
    lines += ["", "**Missing values**", ""]
    for n, p in rep["tables"].items():
        mv = ", ".join(f"`{c}`: {v:,}" for c, v in p["missing_values"].items()) or "none"
        lines.append(f"- {n}: {mv}")
    lines += ["", "**Non-standard labels**", ""]
    any_lbl = False
    for n, p in rep["tables"].items():
        for col, d in p["non_standard_labels"].items():
            any_lbl = True
            lines.append(f"- {n}.`{col}`: {d['rows']:,} rows (e.g. {', '.join(repr(x) for x in d['examples'][:6])})")
    if not any_lbl:
        lines.append("- none")
    lines += ["", "**Relationship and business-rule checks**", "", "| Check | Count |", "|---|---:|"]
    for k, v in rep["relationships"].items():
        lines.append(f"| {k} | {v:,} |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["raw", "processed"], default="raw")
    args = ap.parse_args()
    rep = run(args.stage)
    out = ROOT / "reports" / "metrics" / f"data_quality_{args.stage}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2, default=str))
    print(to_markdown(rep))


if __name__ == "__main__":
    main()
