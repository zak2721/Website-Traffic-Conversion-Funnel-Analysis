"""
analysis.py
===========
Exploratory and funnel analysis on the cleaned star-schema tables.
Writes metric tables to reports/metrics/ and charts to reports/figures/.
The notebooks import these functions so the narrative and the numbers come from
one implementation.

Usage:
    python python/analysis.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mtick  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import metrics as m  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "data" / "processed" / "model"
FIG = ROOT / "reports" / "figures"
MET = ROOT / "reports" / "metrics"

CHANNEL_ORDER = ["Organic Search", "Direct", "Paid Search", "Paid Social", "Email", "Organic Social", "Referral"]
DEVICE_ORDER = ["Desktop", "Mobile", "Tablet"]
PALETTE = {"Organic Search": "#2E7D32", "Direct": "#455A64", "Paid Search": "#1565C0", "Paid Social": "#C62828",
           "Email": "#EF6C00", "Organic Social": "#AD1457", "Referral": "#6A1B9A"}
DEVICE_PAL = {"Desktop": "#1565C0", "Mobile": "#EF6C00", "Tablet": "#6A1B9A", "Unknown": "#9E9E9E"}
MATERIALITY_SHARE = 0.02
SYNTH_NOTE = "Synthetic data — illustrative only"

sns.set_theme(style="whitegrid", context="notebook")
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 150, "axes.titleweight": "bold", "axes.titlesize": 13})


def load_model():
    fs = pd.read_csv(MODEL / "fact_sessions.csv", parse_dates=["session_start"])
    ft = pd.read_csv(MODEL / "fact_transactions.csv", parse_dates=["transaction_timestamp"])
    fe = pd.read_csv(MODEL / "fact_events.csv", parse_dates=["event_timestamp"])
    ts = pd.read_csv(MODEL / "dim_traffic_source.csv")
    dv = pd.read_csv(MODEL / "dim_device.csv")
    lp = pd.read_csv(MODEL / "dim_landing_page.csv")
    fs = fs.merge(ts, on="traffic_source_key").merge(dv, on="device_key").merge(lp, on="landing_page_key")
    fs["session_date"] = fs["session_start"].dt.normalize()
    fs["month"] = fs["session_start"].dt.to_period("M").astype(str)
    return fs, ft, fe


def _note(fig):
    fig.text(0.99, 0.005, SYNTH_NOTE, ha="right", va="bottom", fontsize=8, color="#888888")


def _save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    _note(fig)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(FIG / name, bbox_inches="tight")
    return fig


# ---------------------------------------------------------------- tables
def daily_trend(fs, ft):
    tx = ft.merge(fs[["session_id", "session_date"]], on="session_id")
    d = fs.groupby("session_date").agg(sessions=("session_id", "count"), engaged=("engaged_session", "sum"))
    t = tx.groupby("session_date").agg(purchasing_sessions=("session_id", "nunique"), revenue=("revenue", "sum"))
    d = d.join(t).fillna(0)
    d["sessions_7d_avg"] = d["sessions"].rolling(7, min_periods=7).mean()
    d["conversion_rate"] = m.safe_divide(d["purchasing_sessions"], d["sessions"])
    return d.reset_index()


def monthly_trend(fs, ft):
    tx = ft.merge(fs[["session_id", "month"]], on="session_id")
    mth = fs.groupby("month").agg(sessions=("session_id", "count"), visitors=("visitor_id", "nunique"),
                                 engaged_sessions=("engaged_session", "sum"))
    t = tx.groupby("month").agg(purchasing_sessions=("session_id", "nunique"),
                                transactions=("transaction_id", "nunique"), revenue=("revenue", "sum"))
    mth = mth.join(t).fillna(0)
    mth["conversion_rate"] = m.safe_divide(mth["purchasing_sessions"], mth["sessions"])
    mth["revenue_per_session"] = m.safe_divide(mth["revenue"], mth["sessions"])
    mth["aov"] = m.safe_divide(mth["revenue"], mth["transactions"])
    mth["sessions_growth_pct"] = mth["sessions"].pct_change()
    mth["revenue_growth_pct"] = mth["revenue"].pct_change()
    return mth.reset_index()


def with_ci(df):
    lo, hi = m.wilson_interval(df["purchasing_sessions"], df["sessions"])
    df = df.copy()
    df["cvr_ci_low"], df["cvr_ci_high"] = lo, hi
    return df


def landing_page_table(fs, ft):
    lp = with_ci(m.segment_performance(fs, ft, ["landing_page", "page_type"]))
    overall = m.safe_divide(ft["session_id"].nunique(), len(fs))
    # "material" traffic = at least 2% of all sessions (a fixed, documented threshold)
    lp["high_traffic"] = lp["share_of_sessions"] >= MATERIALITY_SHARE
    lp["cvr_significantly_below_site"] = lp["cvr_ci_high"] < overall
    lp["investigate"] = lp["high_traffic"] & lp["cvr_significantly_below_site"]
    lp["site_conversion_rate"] = overall
    return lp


def funnel_by(fs, col, order=None):
    rows = []
    for k, g in fs.groupby(col):
        f = m.funnel_summary(g)
        f.insert(0, col, k)
        rows.append(f)
    out = pd.concat(rows, ignore_index=True)
    if order:
        out = out[out[col].isin(order)]
    return out


# ---------------------------------------------------------------- charts
def fig_daily_sessions(daily):
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(daily["session_date"], daily["sessions"], color="#90CAF9", lw=1, label="Daily sessions")
    ax.plot(daily["session_date"], daily["sessions_7d_avg"], color="#0D47A1", lw=2.2, label="7-day average")
    ax.axvspan(pd.Timestamp("2025-03-15"), pd.Timestamp("2025-04-15"), color="#FFE0B2", alpha=0.6,
               label="Spring-sale campaign")
    ax.set(title="Daily sessions, Jan–Jun 2025", xlabel="Session date", ylabel="Sessions")
    ax.legend(loc="upper left")
    return _save(fig, "01_daily_sessions.png")


def fig_channel_sessions_revenue(ch):
    d = ch.sort_values("sessions", ascending=False).reset_index(drop=True)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    sns.barplot(data=d, y="channel_group", x="sessions", hue="channel_group", palette=PALETTE, legend=False, ax=axes[0])
    axes[0].set(title="Sessions by channel", xlabel="Sessions", ylabel="")
    sns.barplot(data=d, y="channel_group", x="revenue", hue="channel_group", palette=PALETTE, legend=False, ax=axes[1])
    axes[1].set(title="Revenue by channel (USD)", xlabel="Revenue (USD)", ylabel="")
    axes[1].xaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}"))
    axes[1].xaxis.set_major_locator(mtick.MaxNLocator(4))
    for ax, col, fmt in [(axes[0], "sessions", "{:,.0f}"), (axes[1], "revenue", "${:,.0f}")]:
        for i, v in enumerate(d[col]):
            ax.text(v, i, " " + fmt.format(v), va="center", fontsize=9)
        ax.set_xlim(0, d[col].max() * 1.2)
    return _save(fig, "02_sessions_and_revenue_by_channel.png")


def fig_share_gap(ch):
    d = ch.set_index("channel_group").sort_values("sessions", ascending=False)
    x = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.bar(x - 0.2, d["share_of_sessions"], 0.4, label="Share of sessions", color="#90A4AE")
    ax.bar(x + 0.2, d["share_of_revenue"], 0.4, label="Share of revenue", color="#1565C0")
    ax.set_xticks(x, d.index)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    ax.set(title="Share of sessions vs share of revenue by channel", ylabel="Share of total", xlabel="")
    ax.legend()
    return _save(fig, "03_session_vs_revenue_share.png")


def fig_cvr_by_channel(ch, site_cvr):
    d = with_ci(ch).set_index("channel_group").reindex(CHANNEL_ORDER).reset_index().sort_values("conversion_rate")
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.barh(d["channel_group"], d["conversion_rate"], color=[PALETTE[c] for c in d["channel_group"]])
    ax.errorbar(d["conversion_rate"], d["channel_group"],
                xerr=[d["conversion_rate"] - d["cvr_ci_low"], d["cvr_ci_high"] - d["conversion_rate"]],
                fmt="none", ecolor="black", capsize=3, lw=1)
    ax.axvline(site_cvr, ls="--", color="black", lw=1)
    ax.text(site_cvr, -0.75, f" site average {site_cvr:.2%}", fontsize=9, va="bottom")
    ax.set_ylim(-0.8, len(d) - 0.4)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=1))
    ax.set(title="Purchase conversion rate by channel (95% CI)", xlabel="Purchasing sessions ÷ sessions", ylabel="")
    return _save(fig, "04_conversion_rate_by_channel.png")


def fig_device(dev):
    d = dev[dev["device_label"].isin(DEVICE_ORDER)].set_index("device_label").reindex(DEVICE_ORDER).reset_index()
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    specs = [("sessions", "Sessions", "{:,.0f}"), ("conversion_rate", "Conversion rate", "{:.2%}"),
             ("revenue_per_session", "Revenue per session (USD)", "${:.2f}")]
    for ax, (col, title, fmt) in zip(axes, specs):
        sns.barplot(data=d, x="device_label", y=col, hue="device_label", palette=DEVICE_PAL, legend=False, ax=ax)
        ax.set(title=title, xlabel="", ylabel="")
        for i, v in enumerate(d[col]):
            ax.text(i, v, fmt.format(v), ha="center", va="bottom", fontsize=9)
        if col == "conversion_rate":
            ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=1))
    fig.suptitle("Device comparison", fontweight="bold")
    return _save(fig, "05_device_comparison.png")


def fig_landing_pages(lp):
    d = lp.sort_values("sessions")
    fig, ax = plt.subplots(figsize=(11, 5))
    colors = ["#C62828" if f else "#90A4AE" for f in d["investigate"]]
    ax.barh(d["landing_page"], d["sessions"], color=colors)
    for i, (s, c) in enumerate(zip(d["sessions"], d["conversion_rate"])):
        ax.text(s, i, f"  {s:,} sessions | CVR {c:.2%}", va="center", fontsize=9)
    ax.set_xlim(0, d["sessions"].max() * 1.45)
    ax.set(title="Landing-page traffic (red = ≥2% of sessions and CVR significantly below site average)",
           xlabel="Sessions", ylabel="")
    return _save(fig, "06_landing_page_traffic.png")


def fig_landing_quadrant(lp):
    fig, ax = plt.subplots(figsize=(10.5, 6))
    site = lp["site_conversion_rate"].iloc[0]
    sizes = 40 + 600 * lp["revenue"] / lp["revenue"].max()
    ax.scatter(lp["sessions"], lp["conversion_rate"], s=sizes, c=["#C62828" if f else "#1565C0" for f in lp["investigate"]],
               alpha=0.7, edgecolor="white")
    for _, r in lp.iterrows():
        ax.annotate(r["landing_page"], (r["sessions"], r["conversion_rate"]), xytext=(6, 4),
                    textcoords="offset points", fontsize=8.5)
    ax.axhline(site, ls="--", color="black", lw=1)
    thr = MATERIALITY_SHARE * lp["sessions"].sum()
    ax.axvline(thr, ls=":", color="grey", lw=1)
    ax.text(thr, ax.get_ylim()[1] * 0.97, " 2% of sessions", fontsize=8, color="grey", va="top")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=1))
    ax.set(title="Landing pages: traffic vs conversion (bubble size = revenue)", xlabel="Sessions",
           ylabel="Purchase conversion rate")
    ax.text(lp["sessions"].min(), site, f"site average {site:.2%}", ha="left", va="bottom", fontsize=8)
    return _save(fig, "07_landing_page_quadrant.png")


def fig_event_frequency(fe):
    order = ["session_start", "page_view", "product_view", "add_to_cart", "begin_checkout", "purchase"]
    d = fe["event_name"].value_counts().reindex(order)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(d.index, d.values, color="#546E7A")
    ax.set_yscale("log")
    for i, v in enumerate(d.values):
        ax.text(i, v, f"{v:,}", ha="center", va="bottom", fontsize=9)
    ax.set(title="Event frequency (log scale)", xlabel="Event name", ylabel="Events (log scale)")
    return _save(fig, "08_event_frequency.png")


def fig_monthly(mth):
    fig, ax1 = plt.subplots(figsize=(10, 4.2))
    ax1.bar(mth["month"], mth["revenue"], color="#1565C0", alpha=0.85, label="Revenue (USD)")
    ax1.yaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}"))
    ax1.set(ylabel="Revenue (USD)", xlabel="Month (by session date)")
    ax2 = ax1.twinx()
    ax2.plot(mth["month"], mth["conversion_rate"], color="#EF6C00", marker="o", lw=2, label="Conversion rate")
    ax2.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=1))
    ax2.set_ylim(0, mth["conversion_rate"].max() * 1.5)
    ax2.set_ylabel("Conversion rate")
    ax2.grid(False)
    h1, l1 = ax1.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper left")
    ax1.set_title("Monthly revenue and purchase conversion rate")
    return _save(fig, "09_monthly_revenue_conversion.png")


def fig_funnel(funnel):
    fig, ax = plt.subplots(figsize=(10, 4.6))
    d = funnel.iloc[::-1]
    ax.barh(d["stage"], d["sessions"], color=sns.color_palette("Blues_r", 5)[::-1])
    for i, (_, r) in enumerate(d.iterrows()):
        ax.text(r["sessions"], i, f"  {r['sessions']:,} ({r['pct_of_sessions']:.1%} of sessions)", va="center", fontsize=9)
    for i, (_, r) in enumerate(funnel.iloc[:-1].iterrows()):
        y = len(funnel) - 1 - i - 0.5
        ax.text(funnel["sessions"].max() * 1.02, y, f"↓ {r['drop_off_rate']:.1%} drop-off", va="center",
                fontsize=8.5, color="#C62828")
    ax.set_xlim(0, funnel["sessions"].max() * 1.35)
    ax.set(title="Ordered session funnel (each session counted once per stage)", xlabel="Sessions", ylabel="")
    return _save(fig, "10_conversion_funnel.png")


def fig_funnel_device(fd):
    d = fd[fd["stage_order"] < 5].copy()
    d["transition"] = d["stage"].map({"Session": "Session → Product view", "Product view": "Product view → Add to cart",
                                      "Add to cart": "Add to cart → Checkout", "Checkout started": "Checkout → Purchase"})
    fig, ax = plt.subplots(figsize=(11, 4.5))
    sns.barplot(data=d, x="transition", y="conversion_to_next", hue="device_label", hue_order=DEVICE_ORDER,
                palette=DEVICE_PAL, ax=ax)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    for c in ax.containers:
        ax.bar_label(c, labels=[f"{v.get_height():.0%}" for v in c], fontsize=8)
    ax.set(title="Stage-to-stage conversion by device", xlabel="", ylabel="Conversion to next stage")
    ax.set_ylim(0, 0.78)
    ax.legend(title="Device", ncol=3, loc="upper center")
    return _save(fig, "11_funnel_by_device.png")


def fig_campaigns(cmp):
    d = with_ci(cmp[cmp["campaign"] != "(not set)"]).sort_values("conversion_rate")
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.barh(d["campaign"], d["conversion_rate"], color="#5C6BC0")
    ax.errorbar(d["conversion_rate"], d["campaign"], xerr=[d["conversion_rate"] - d["cvr_ci_low"],
                d["cvr_ci_high"] - d["conversion_rate"]], fmt="none", ecolor="black", capsize=3, lw=1)
    for i, (c, s) in enumerate(zip(d["conversion_rate"], d["sessions"])):
        ax.text(d["cvr_ci_high"].iloc[i], i, f"  {c:.2%} (n={s:,})", va="center", fontsize=8.5)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=1))
    ax.set_xlim(0, d["cvr_ci_high"].max() * 1.35)
    ax.set(title="Conversion rate by campaign (95% CI)", xlabel="Purchase conversion rate", ylabel="")
    return _save(fig, "12_campaign_conversion.png")


def fig_device_within_channel(dch):
    d = dch.pivot(index="channel_group", columns="device_label", values="conversion_rate").sort_values("Desktop", ascending=False)
    fig, ax = plt.subplots(figsize=(11, 4.5))
    d[DEVICE_ORDER].plot(kind="bar", ax=ax, color=[DEVICE_PAL[c] for c in DEVICE_ORDER], width=0.8)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=1))
    ax.set(title="Conversion rate by device within each channel (controls for channel mix)",
           xlabel="", ylabel="Purchase conversion rate")
    ax.tick_params(axis="x", rotation=0)
    ax.legend(title="Device")
    return _save(fig, "13_device_within_channel.png")


# ---------------------------------------------------------------- main
def run_all(save_tables=True, close=True):
    fs, ft, fe = load_model()
    kpis = m.kpi_summary(fs, ft)
    funnel = m.funnel_summary(fs)
    ch = m.segment_performance(fs, ft, "channel_group")
    sm = m.segment_performance(fs, ft, ["channel_group", "source_medium"])
    dev = m.segment_performance(fs, ft, "device_label")
    lp = landing_page_table(fs, ft)
    cmp = m.segment_performance(fs, ft, ["campaign"])
    daily, mth = daily_trend(fs, ft), monthly_trend(fs, ft)
    fd = funnel_by(fs, "device_label", DEVICE_ORDER)
    fch = funnel_by(fs, "channel_group")
    dch = with_ci(m.segment_performance(fs[fs["device_label"].isin(DEVICE_ORDER)], ft, ["channel_group", "device_label"]))
    ev = fe["event_name"].value_counts().rename_axis("event_name").reset_index(name="events")
    ev["sessions_with_event"] = ev["event_name"].map(fe.groupby("event_name")["session_id"].nunique())

    # reconciliation between transaction-based KPI and event-based funnel
    recon = {
        "purchasing_sessions_transaction_based": kpis["purchasing_sessions"],
        "funnel_purchase_stage_event_based": int(fs["reached_purchase"].sum()),
        "purchase_event_before_checkout_sessions": int(fs["purchase_sequence_violation"].sum()),
        "transaction_without_purchase_event": int(((fs["is_purchasing_session"] == 1) & (fs["has_purchase_event"] == 0)).sum()),
        "ordered_purchase_without_valid_transaction": int(((fs["reached_purchase"] == 1) & (fs["is_purchasing_session"] == 0)).sum()),
    }
    tables = {"funnel_overall": funnel, "channel_performance": with_ci(ch), "source_medium_performance": sm,
              "device_performance": with_ci(dev), "landing_page_performance": lp, "campaign_performance": with_ci(cmp),
              "daily_trend": daily, "monthly_trend": mth, "funnel_by_device": fd, "funnel_by_channel": fch, "device_within_channel": dch,
              "event_frequency": ev}
    if save_tables:
        MET.mkdir(parents=True, exist_ok=True)
        for k, v in tables.items():
            v.to_csv(MET / f"{k}.csv", index=False)
        opportunity_sizing(tables).to_csv(MET / "opportunity_sizing.csv", index=False)
        (MET / "kpis.json").write_text(json.dumps({"kpis": kpis, "funnel_reconciliation": recon}, indent=2, default=float))

    figs = [fig_daily_sessions(daily), fig_channel_sessions_revenue(ch), fig_share_gap(ch),
            fig_cvr_by_channel(ch, kpis["purchase_conversion_rate"]), fig_device(dev), fig_landing_pages(lp),
            fig_landing_quadrant(lp), fig_event_frequency(fe), fig_monthly(mth), fig_funnel(funnel),
            fig_funnel_device(fd), fig_campaigns(cmp), fig_device_within_channel(dch)]
    if close:
        for f in figs:
            plt.close(f)
    return kpis, recon, tables


def opportunity_sizing(tables) -> pd.DataFrame:
    """Illustrative UPPER-BOUND scenarios (not forecasts): what the observed period would have looked like
    if a gap were fully closed, holding everything else constant. Used to rank where to test first."""
    fd = tables["funnel_by_device"].set_index(["device_label", "stage_order"])
    dev = tables["device_performance"].set_index("device_label")
    ch = tables["channel_performance"].set_index("channel_group")
    rows = []
    mob_co, desk_rate = fd.loc[("Mobile", 4), "sessions"], fd.loc[("Desktop", 4), "conversion_to_next"]
    mob_rate = fd.loc[("Mobile", 4), "conversion_to_next"]
    extra = mob_co * (desk_rate - mob_rate)
    rows.append({"scenario": "Mobile checkout→purchase rate matches desktop",
                 "basis": f"{mob_co:,.0f} mobile checkouts × ({desk_rate:.1%} − {mob_rate:.1%})",
                 "additional_purchases": extra, "aov_used": dev.loc["Mobile", "average_order_value"],
                 "additional_revenue": extra * dev.loc["Mobile", "average_order_value"]})
    mob_atc, d_atc, m_atc = fd.loc[("Mobile", 3), "sessions"], fd.loc[("Desktop", 3), "conversion_to_next"], fd.loc[("Mobile", 3), "conversion_to_next"]
    extra_co = mob_atc * (d_atc - m_atc)
    extra2 = extra_co * mob_rate
    rows.append({"scenario": "Mobile cart→checkout rate matches desktop (at current mobile checkout completion)",
                 "basis": f"{mob_atc:,.0f} mobile carts × ({d_atc:.1%} − {m_atc:.1%}) × {mob_rate:.1%}",
                 "additional_purchases": extra2, "aov_used": dev.loc["Mobile", "average_order_value"],
                 "additional_revenue": extra2 * dev.loc["Mobile", "average_order_value"]})
    ps = ch.loc["Paid Social"]
    target = 0.5 * (ps["conversion_rate"] + tables["channel_performance"]["purchasing_sessions"].sum()
                    / tables["channel_performance"]["sessions"].sum())
    extra3 = ps["sessions"] * (target - ps["conversion_rate"])
    rows.append({"scenario": "Paid Social CVR closes half the gap to site average",
                 "basis": f"{ps['sessions']:,.0f} sessions × ({target:.2%} − {ps['conversion_rate']:.2%})",
                 "additional_purchases": extra3, "aov_used": ps["average_order_value"],
                 "additional_revenue": extra3 * ps["average_order_value"]})
    out = pd.DataFrame(rows)
    out["period"] = "Jan–Jun 2025 (observed, synthetic)"
    return out


if __name__ == "__main__":
    k, r, t = run_all()
    print(json.dumps({"kpis": k, "funnel_reconciliation": r}, indent=2, default=float))
    print(f"Wrote {len(t)} metric tables to {MET.relative_to(ROOT)} and 13 figures to {FIG.relative_to(ROOT)}")
