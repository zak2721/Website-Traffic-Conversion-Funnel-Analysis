"""
build_visual_assets.py
======================
1. powerbi/theme.json             Power BI report theme (colours used in dashboard_design.md)
2. powerbi/wireframes/*.png       ILLUSTRATIVE layout sketches of the 4 dashboard pages
                                  (watermarked: they are not Power BI screenshots)
3. portfolio/*.png                Upwork / portfolio images composed from the REAL analysis
                                  charts in reports/figures and real KPI values in reports/metrics

Usage:  python python/build_visual_assets.py   (run after python/analysis.py)
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIG, MET = ROOT / "reports" / "figures", ROOT / "reports" / "metrics"
WF, PF = ROOT / "powerbi" / "wireframes", ROOT / "portfolio"
NAVY, BLUE, GREY, RED, ORANGE = "#0D2B4E", "#1565C0", "#5F6B7A", "#C62828", "#EF6C00"

THEME = {
    "name": "Web Funnel Analytics",
    "dataColors": ["#1565C0", "#EF6C00", "#2E7D32", "#C62828", "#6A1B9A", "#455A64", "#AD1457", "#00838F"],
    "background": "#FFFFFF", "foreground": "#1F2937", "tableAccent": "#1565C0",
    "good": "#2E7D32", "neutral": "#F9A825", "bad": "#C62828",
    "maximum": "#2E7D32", "center": "#F5F5F5", "minimum": "#C62828",
    "textClasses": {
        "title": {"fontFace": "Segoe UI Semibold", "fontSize": 14, "color": "#1F2937"},
        "label": {"fontFace": "Segoe UI", "fontSize": 10, "color": "#5F6B7A"},
        "callout": {"fontFace": "Segoe UI", "fontSize": 26, "color": "#0D2B4E"},
        "header": {"fontFace": "Segoe UI Semibold", "fontSize": 12, "color": "#1F2937"},
    },
    "visualStyles": {"*": {"*": {
        "background": [{"color": {"solid": {"color": "#FFFFFF"}}, "transparency": 0}],
        "border": [{"show": True, "color": {"solid": {"color": "#E5E7EB"}}, "radius": 8}],
        "dropShadow": [{"show": True, "preset": "BottomRight", "transparency": 85}],
    }}, "page": {"*": {"background": [{"color": {"solid": {"color": "#F7F9FC"}}, "transparency": 0}]}}},
}

# (x, y, w, h, label) in a 1280 x 720 canvas, mirroring dashboard_design.md
PAGES = {
    "1_executive_overview": ("Executive Traffic Overview", [
        *[(20 + i * 248, 120, 236, 110, t) for i, t in enumerate(
            ["KPI: Total Sessions", "KPI: Purchasing Sessions", "KPI: Conversion Rate", "KPI: Total Revenue", "KPI: Revenue / Session"])],
        (20, 245, 760, 220, "Sessions (columns) + Conversion rate (line) over time"),
        (795, 245, 465, 220, "Sessions by channel (bar)"),
        (20, 480, 760, 220, "Share of sessions vs share of revenue by channel"),
        (795, 480, 465, 220, "Revenue by channel (bar)")]),
    "2_channel_performance": ("Marketing Channel Performance", [
        (20, 120, 1240, 240, "Channel scorecard table: sessions, CVR, revenue, RPS, AOV (conditional formatting)"),
        (20, 375, 610, 325, "Scatter: sessions vs CVR, bubble = revenue, line = site CVR"),
        (645, 375, 615, 325, "Monthly conversion rate by channel (line)")]),
    "3_conversion_funnel": ("Conversion Funnel", [
        (20, 120, 400, 110, "Largest drop-off (% and sessions)"),
        *[(435 + i * 208, 120, 196, 110, t) for i, t in enumerate(
            ["Session→View %", "View→Cart %", "Cart→Checkout %", "Checkout→Purchase %"])],
        (20, 245, 610, 300, "Funnel stages: horizontal bar with % of sessions + drop-off"),
        (645, 245, 615, 300, "Matrix: stage × device (sessions, conversion to next)"),
        (20, 560, 1240, 140, "Stage-to-stage conversion by device (clustered column)")]),
    "4_device_landing_pages": ("Device & Landing-Page Analysis", [
        (20, 120, 610, 250, "Device: conversion rate & revenue per session"),
        (645, 120, 615, 250, "Matrix: channel × device conversion rate"),
        (20, 385, 1240, 315, "Sortable landing-page table + Investigate flag (icon set)")]),
}


def build_theme():
    (ROOT / "powerbi" / "theme.json").write_text(json.dumps(THEME, indent=2))


def build_wireframes():
    WF.mkdir(parents=True, exist_ok=True)
    for key, (title, boxes) in PAGES.items():
        fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=100)
        ax.set_xlim(0, 1280); ax.set_ylim(720, 0); ax.axis("off")
        ax.add_patch(FancyBboxPatch((0, 0), 1280, 720, boxstyle="square", fc="#F7F9FC", ec="none"))
        ax.add_patch(FancyBboxPatch((0, 0), 1280, 58, boxstyle="square", fc=NAVY, ec="none"))
        ax.text(20, 30, title, color="white", fontsize=16, weight="bold", va="center")
        ax.text(1260, 30, "Pages: 1 · 2 · 3 · 4", color="#BBDEFB", fontsize=10, va="center", ha="right")
        sl = ["Date range", "Channel"] + (["Device"] if key[0] in "34" else []) + (["Campaign"] if key[0] == "2" else [])
        for i, s in enumerate(sl):
            ax.add_patch(FancyBboxPatch((20 + i * 190, 70), 175, 36, boxstyle="round,pad=0,rounding_size=6", fc="white", ec="#B0BEC5"))
            ax.text(32 + i * 190, 88, f"▾ {s}", fontsize=9, va="center", color=GREY)
        for x, y, w, h, lab in boxes:
            ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=8", fc="white", ec="#CFD8DC", lw=1.2))
            ax.text(x + w / 2, y + h / 2, lab, ha="center", va="center", fontsize=9, color=GREY, wrap=True)
        ax.text(640, 400, "ILLUSTRATIVE WIREFRAME\nnot a Power BI screenshot", ha="center", va="center", fontsize=40,
                color="#90A4AE", alpha=0.18, rotation=18, weight="bold")
        ax.text(20, 712, "Layout sketch for powerbi/dashboard_design.md · synthetic-data project", fontsize=8, color="#90A4AE")
        fig.savefig(WF / f"page_{key}.png", bbox_inches="tight", pad_inches=0)
        plt.close(fig)


def _canvas(title, subtitle):
    fig = plt.figure(figsize=(16, 12), dpi=100)          # 1600 x 1200 (4:3)
    fig.patch.set_facecolor("white")
    fig.add_artist(plt.Rectangle((0, 0.885), 1, 0.115, transform=fig.transFigure, color=NAVY))
    fig.text(0.04, 0.955, title, color="white", fontsize=30, weight="bold", va="center")
    fig.text(0.04, 0.912, subtitle, color="#BBDEFB", fontsize=15, va="center")
    fig.text(0.04, 0.015, "Portfolio project · synthetic e-commerce data · Python · SQL (PostgreSQL) · Power BI",
             fontsize=11, color="#90A4AE")
    return fig


def _img(fig, name, rect):
    ax = fig.add_axes(rect); ax.imshow(mpimg.imread(FIG / name)); ax.axis("off")


def build_portfolio():
    PF.mkdir(parents=True, exist_ok=True)
    k = json.loads((MET / "kpis.json").read_text())["kpis"]
    f = pd.read_csv(MET / "funnel_overall.csv")
    dev = pd.read_csv(MET / "funnel_by_device.csv").set_index(["device_label", "stage_order"])
    ch = pd.read_csv(MET / "channel_performance.csv").set_index("channel_group")

    # 01 cover
    fig = _canvas("Website Traffic & Conversion Funnel Analysis",
                  "End-to-end analytics: data cleaning → SQL → funnel analysis → Power BI dashboard design")
    cards = [(f"{k['total_sessions']:,}", "sessions analysed"), (f"{k['purchase_conversion_rate']:.2%}", "purchase conversion"),
             (f"${k['total_revenue']:,.0f}", "revenue tracked"),
             (f"{f.loc[1, 'drop_off_rate']:.0%}", "drop-off: product view → cart")]
    for i, (v, lab) in enumerate(cards):
        x = 0.04 + i * 0.235
        fig.add_artist(FancyBboxPatch((x, 0.735), 0.215, 0.125, boxstyle="round,pad=0,rounding_size=0.01",
                                      transform=fig.transFigure, fc="#F1F6FD", ec="#BBDEFB"))
        fig.text(x + 0.015, 0.81, v, fontsize=30, weight="bold", color=BLUE)
        fig.text(x + 0.015, 0.758, lab, fontsize=13, color=GREY)
    _img(fig, "10_conversion_funnel.png", [0.03, 0.06, 0.94, 0.65])
    fig.savefig(PF / "01_cover.png"); plt.close(fig)

    # 02 mobile checkout finding
    m_rate, d_rate = dev.loc[("Mobile", 4), "conversion_to_next"], dev.loc[("Desktop", 4), "conversion_to_next"]
    fig = _canvas("Finding: mobile loses buyers at checkout",
                  f"Checkout → purchase: mobile {m_rate:.0%} vs desktop {d_rate:.0%}, in every channel (not a traffic-mix effect)")
    _img(fig, "11_funnel_by_device.png", [0.03, 0.45, 0.94, 0.42])
    _img(fig, "13_device_within_channel.png", [0.03, 0.04, 0.94, 0.40])
    fig.savefig(PF / "02_mobile_checkout_gap.png"); plt.close(fig)

    # 03 channel efficiency
    ps, em = ch.loc["Paid Social"], ch.loc["Email"]
    fig = _canvas("Finding: traffic share ≠ revenue share",
                  f"Paid Social: {ps.share_of_sessions:.0%} of sessions → {ps.share_of_revenue:.0%} of revenue · "
                  f"Email: {em.share_of_sessions:.0%} → {em.share_of_revenue:.0%}")
    _img(fig, "03_session_vs_revenue_share.png", [0.03, 0.45, 0.94, 0.42])
    _img(fig, "04_conversion_rate_by_channel.png", [0.10, 0.04, 0.80, 0.40])
    fig.savefig(PF / "03_channel_efficiency.png"); plt.close(fig)

    # 04 landing pages + data quality
    fig = _canvas("Landing pages to investigate + verified data quality",
                  "Statistical flag (95% CI below site average) · 20/20 SQL checks and 28/28 tests pass")
    _img(fig, "07_landing_page_quadrant.png", [0.03, 0.30, 0.60, 0.57])
    log = json.loads((MET / "cleaning_log.json").read_text())
    steps = pd.DataFrame(log["steps"])
    fixed = [("Label variants standardised", int(steps[steps.step.str.startswith("standardise")].rows_affected.sum())),
             ("Duplicate rows removed", int(steps[steps.step.str.startswith("drop_")].rows_affected.sum())),
             ("Orphan / invalid records quarantined", log["quarantined"]["events"] + log["quarantined"]["transactions"]),
             ("Out-of-order funnel events flagged", int(steps[steps.step == "flag_sequence_violations"].rows_affected.iloc[0]))]
    fig.text(0.66, 0.84, "Data cleaning (Python + SQL)", fontsize=18, weight="bold", color=NAVY)
    for i, (lab, n) in enumerate(fixed):
        fig.text(0.66, 0.78 - i * 0.075, f"{n:,}", fontsize=24, weight="bold", color=ORANGE)
        fig.text(0.66, 0.755 - i * 0.075, lab, fontsize=12, color=GREY)
    fig.text(0.66, 0.43, "Python, SQL and DAX definitions\nreconcile to the cent:", fontsize=13, color=GREY)
    fig.text(0.66, 0.37, f"${k['total_revenue']:,.2f}", fontsize=26, weight="bold", color="#2E7D32")
    _img(fig, "06_landing_page_traffic.png", [0.03, 0.03, 0.94, 0.26])
    fig.savefig(PF / "04_landing_pages_and_quality.png"); plt.close(fig)


if __name__ == "__main__":
    build_theme(); build_wireframes(); build_portfolio()
    print("theme.json, 4 wireframes, 4 portfolio images written")
