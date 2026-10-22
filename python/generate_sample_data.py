"""
generate_sample_data.py
=======================
Generates a SYNTHETIC e-commerce web-analytics dataset (sessions, events,
transactions) for the "Website Traffic & Conversion Funnel Analysis" project.

IMPORTANT: Every record produced by this script is artificial. The behavioural
patterns (channel mix, device effects, landing-page effects) are modelling
assumptions chosen to make the analysis interesting. They are NOT measurements
of any real company and must never be presented as such.

The script also injects realistic data-quality defects (duplicates, inconsistent
labels, orphan records, clock skew, test orders, ...) so that the cleaning
pipeline has genuine problems to solve. Every injected defect is logged to
data/raw/generation_metadata.json so the cleaning results can be verified.

Usage:
    python python/generate_sample_data.py            # default seed 42
    python python/generate_sample_data.py --seed 7 --sessions-per-day 150
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"

START_DATE = datetime(2025, 1, 1)
END_DATE = datetime(2025, 6, 30)

# --------------------------------------------------------------------------
# Modelling assumptions
# --------------------------------------------------------------------------
# (source, medium, campaigns, share of traffic, add-to-cart multiplier)
CHANNELS = [
    ("google", "organic", [None], 0.30, 1.00),
    ("bing", "organic", [None], 0.03, 1.00),
    ("google", "cpc", ["brand_search", "generic_search"], 0.16, 1.15),
    ("(direct)", "(none)", [None], 0.17, 1.30),
    ("facebook", "paid_social", ["prospecting", "retargeting"], 0.10, 0.60),
    ("instagram", "paid_social", ["prospecting", "retargeting"], 0.07, 0.55),
    ("newsletter", "email", ["weekly_newsletter", "abandoned_cart"], 0.07, 1.60),
    ("partnerblog.com", "referral", [None], 0.03, 0.95),
    ("dealsforum.com", "referral", [None], 0.02, 0.80),
    ("instagram", "social", [None], 0.03, 0.50),
    ("tiktok", "social", [None], 0.02, 0.45),
]
CAMPAIGN_MULT = {"brand_search": 1.35, "generic_search": 0.90, "retargeting": 1.70,
                 "prospecting": 0.75, "abandoned_cart": 1.50, "weekly_newsletter": 0.95,
                 "spring_sale": 0.70}

# device: share for non-social traffic, (product-view, add-to-cart, checkout, purchase) multipliers
DEVICES = {
    "desktop": (0.44, (1.00, 1.00, 1.00, 1.00)),
    "mobile": (0.50, (0.95, 0.90, 0.85, 0.62)),
    "tablet": (0.06, (0.98, 0.95, 0.92, 0.85)),
}

# landing page: (product-view multiplier, add-to-cart multiplier)
LANDING_PAGES = {
    "/": (1.00, 1.00),
    "/collections/new-arrivals": (1.15, 1.00),
    "/collections/sale": (1.20, 0.85),
    "/products/classic-sneaker": (1.60, 1.15),
    "/products/everyday-backpack": (1.60, 1.10),
    "/products/wireless-earbuds": (1.60, 1.05),
    "/blog/how-to-choose-running-shoes": (0.40, 0.70),
    "/blog/summer-style-guide": (0.35, 0.65),
    "/campaign/spring-sale": (1.25, 0.45),
    "/search": (1.30, 1.10),
}
LP_PRODUCT = {"/products/classic-sneaker": "P001", "/products/everyday-backpack": "P007",
              "/products/wireless-earbuds": "P013"}

COUNTRIES = (["United States", "United Kingdom", "Canada", "Germany", "Australia", "France", "Netherlands"],
             [0.46, 0.14, 0.11, 0.09, 0.08, 0.07, 0.05])

BASE_P = {"product_view": 0.50, "add_to_cart": 0.20, "begin_checkout": 0.52, "purchase": 0.58}

N_PRODUCTS = 25


def landing_weights(source: str, medium: str, campaign: str | None, date: datetime) -> dict:
    """Channel-specific landing page mix (assumption)."""
    w = {lp: 1.0 for lp in LANDING_PAGES}
    if medium == "organic":
        w.update({"/blog/how-to-choose-running-shoes": 4.0, "/blog/summer-style-guide": 3.0,
                  "/products/classic-sneaker": 2.0, "/": 2.0, "/campaign/spring-sale": 0.0})
    elif medium == "cpc":
        w.update({"/": 3.0, "/products/classic-sneaker": 2.5, "/products/wireless-earbuds": 2.0,
                  "/blog/how-to-choose-running-shoes": 0.0, "/blog/summer-style-guide": 0.0,
                  "/campaign/spring-sale": 0.0, "/search": 0.0})
    elif medium == "(none)":
        w.update({"/": 8.0, "/search": 1.5, "/campaign/spring-sale": 0.2})
    elif medium in ("paid_social", "social"):
        w.update({"/campaign/spring-sale": 7.0 if campaign == "spring_sale" else 0.0,
                  "/collections/sale": 3.0, "/collections/new-arrivals": 2.5,
                  "/blog/how-to-choose-running-shoes": 0.3, "/search": 0.0, "/": 0.5})
    elif medium == "email":
        w.update({"/collections/new-arrivals": 3.0, "/collections/sale": 2.5,
                  "/campaign/spring-sale": 3.0 if datetime(2025, 3, 15) <= date <= datetime(2025, 4, 15) else 0.0,
                  "/blog/how-to-choose-running-shoes": 0.2, "/blog/summer-style-guide": 0.2, "/search": 0.0})
    elif medium == "referral":
        w.update({"/blog/how-to-choose-running-shoes": 2.0, "/products/everyday-backpack": 2.0,
                  "/collections/sale": 2.5, "/search": 0.0})
    return w


def daily_volume(day: datetime, base: float, rng: np.random.Generator) -> int:
    progress = (day - START_DATE).days / (END_DATE - START_DATE).days
    trend = 1.0 + 0.18 * progress                                   # gradual growth
    weekend = 0.82 if day.weekday() >= 5 else 1.0
    promo = 1.25 if datetime(2025, 3, 15) <= day <= datetime(2025, 4, 15) else 1.0
    return int(rng.poisson(base * trend * weekend * promo))


def build(seed: int, sessions_per_day: float):
    rng = np.random.default_rng(seed)
    prices = np.round(rng.lognormal(mean=3.7, sigma=0.45, size=N_PRODUCTS), 2)
    products = [f"P{i:03d}" for i in range(1, N_PRODUCTS + 1)]

    ch_share = np.array([c[3] for c in CHANNELS]); ch_share /= ch_share.sum()
    sessions, events, transactions = [], [], []
    visitor_pool: list[str] = []
    s_counter = e_counter = t_counter = 0

    day = START_DATE
    while day <= END_DATE:
        in_promo = datetime(2025, 3, 15) <= day <= datetime(2025, 4, 15)
        for _ in range(daily_volume(day, sessions_per_day, rng)):
            s_counter += 1
            session_id = f"S{s_counter:07d}"
            # visitor: ~28% of sessions come from returning visitors
            if visitor_pool and rng.random() < 0.28:
                visitor_id = visitor_pool[int(rng.integers(0, len(visitor_pool)))]
            else:
                visitor_id = f"V{len(visitor_pool) + 1:07d}"
                visitor_pool.append(visitor_id)

            share = ch_share.copy()
            if in_promo:   # paid social budget increase during the spring sale
                share[[4, 5]] *= 2.2; share /= share.sum()
            ci = int(rng.choice(len(CHANNELS), p=share))
            source, medium, campaigns, _, atc_mult = CHANNELS[ci]
            campaign = campaigns[int(rng.integers(0, len(campaigns)))]
            if medium == "paid_social" and in_promo and rng.random() < 0.6:
                campaign = "spring_sale"

            dev_names = list(DEVICES)
            dev_p = np.array([DEVICES[d][0] for d in dev_names])
            if medium in ("paid_social", "social"):
                dev_p = np.array([0.20, 0.74, 0.06])
            device = dev_names[int(rng.choice(3, p=dev_p / dev_p.sum()))]
            d_pv, d_atc, d_co, d_pur = DEVICES[device][1]

            lw = landing_weights(source, medium, campaign, day)
            lps = list(lw); lwp = np.array([lw[k] for k in lps]); lwp /= lwp.sum()
            landing = lps[int(rng.choice(len(lps), p=lwp))]
            lp_pv, lp_atc = LANDING_PAGES[landing]

            country = COUNTRIES[0][int(rng.choice(len(COUNTRIES[0]), p=COUNTRIES[1]))]
            hour_w = np.array([1, .6, .4, .3, .3, .4, .8, 1.4, 2, 2.3, 2.4, 2.5, 2.6, 2.4, 2.3, 2.3,
                               2.4, 2.6, 2.9, 3.2, 3.3, 2.9, 2.1, 1.4])
            hour = int(rng.choice(24, p=hour_w / hour_w.sum()))
            t = day + timedelta(hours=hour, minutes=int(rng.integers(0, 60)), seconds=int(rng.integers(0, 60)))
            session_start = t

            camp_mult = CAMPAIGN_MULT.get(campaign, 1.0)
            p_pv = min(0.97, BASE_P["product_view"] * lp_pv * d_pv)
            p_atc = min(0.90, BASE_P["add_to_cart"] * atc_mult * camp_mult * lp_atc * d_atc)
            p_co = min(0.95, BASE_P["begin_checkout"] * d_co)
            p_pur = min(0.95, BASE_P["purchase"] * d_pur * (1.08 if medium == "email" else 1.0))

            ev = []
            def add(name, path, product=None):
                nonlocal t
                ev.append((name, t, path, product))
                t += timedelta(seconds=int(rng.integers(4, 140)))

            add("session_start", landing)
            add("page_view", landing)
            n_extra_pv = int(rng.poisson(0.35))
            reached_pv = rng.random() < p_pv
            viewed: list[str] = []
            if reached_pv:
                n_views = 1 + int(rng.poisson(1.1))
                for k in range(n_views):
                    pid = LP_PRODUCT.get(landing) if (k == 0 and landing in LP_PRODUCT) else products[int(rng.integers(0, N_PRODUCTS))]
                    if k > 0 or landing not in LP_PRODUCT:
                        add("page_view", f"/products/{pid.lower()}")
                    add("product_view", f"/products/{pid.lower()}", pid)
                    viewed.append(pid)
            else:
                for _k in range(n_extra_pv):
                    add("page_view", rng.choice(["/", "/collections/sale", "/about", "/blog/summer-style-guide", "/search"]))

            purchased = False
            if reached_pv and rng.random() < p_atc:
                cart = list(dict.fromkeys(rng.choice(viewed, size=min(len(viewed), 1 + int(rng.poisson(0.4))))))
                for pid in cart:
                    add("add_to_cart", f"/products/{pid.lower()}", pid)
                if rng.random() < p_co:
                    add("page_view", "/checkout")
                    add("begin_checkout", "/checkout")
                    if rng.random() < p_pur:
                        add("page_view", "/checkout/confirmation")
                        add("purchase", "/checkout/confirmation")
                        purchased = True
                        t_counter += 1
                        qty = 1 + rng.poisson(0.5, size=len(cart))
                        rev = float(sum(prices[products.index(p)] * q for p, q in zip(cart, qty)))
                        if device == "mobile":
                            rev *= 0.95
                        status = "refunded" if rng.random() < 0.03 else "completed"
                        transactions.append({
                            "transaction_id": f"T{t_counter:07d}", "session_id": session_id,
                            "transaction_timestamp": ev[-1][1], "revenue": round(rev, 2),
                            "currency": "USD", "transaction_status": status})

            n_pv = sum(1 for e in ev if e[0] == "page_view")
            duration = (ev[-1][1] - session_start).total_seconds()
            engaged = int(n_pv >= 2 or reached_pv or purchased or (duration > 10 and rng.random() < 0.15))

            sessions.append({"session_id": session_id, "visitor_id": visitor_id,
                             "session_start": session_start, "traffic_source": source,
                             "marketing_medium": medium, "campaign": campaign,
                             "device_category": device, "country": country,
                             "landing_page": landing, "engaged_session": engaged})
            for name, ts, path, pid in ev:
                e_counter += 1
                events.append({"event_id": f"E{e_counter:08d}", "session_id": session_id,
                               "event_timestamp": ts, "event_name": name, "page_path": path,
                               "product_id": pid})
        day += timedelta(days=1)

    return pd.DataFrame(sessions), pd.DataFrame(events), pd.DataFrame(transactions)


def inject_defects(sessions, events, transactions, seed):
    """Inject documented, realistic data-quality problems. Returns defect log."""
    rng = np.random.default_rng(seed + 1)
    log = {}

    # ---- Sessions ---------------------------------------------------------
    idx = rng.choice(sessions.index, size=int(0.03 * len(sessions)), replace=False)
    variants = {"google": ["Google", " google", "GOOGLE"], "facebook": ["Facebook", "FACEBOOK "],
                "instagram": ["Instagram", "IG"], "(direct)": ["direct", "(Direct)"],
                "newsletter": ["Newsletter"], "bing": ["Bing"], "tiktok": ["TikTok"],
                "partnerblog.com": ["PartnerBlog.com"], "dealsforum.com": ["www.dealsforum.com"]}
    for i in idx:
        s = sessions.at[i, "traffic_source"]
        sessions.at[i, "traffic_source"] = rng.choice(variants[s])
    log["sessions_source_label_variants"] = int(len(idx))

    med_var = {"cpc": ["CPC", "ppc"], "paid_social": ["Paid Social", "paid-social"],
               "organic": ["Organic"], "email": ["Email", "e-mail"], "referral": ["Referral"],
               "social": ["Social"], "(none)": ["none"]}
    idx = rng.choice(sessions.index, size=int(0.02 * len(sessions)), replace=False)
    for i in idx:
        sessions.at[i, "marketing_medium"] = rng.choice(med_var[sessions.at[i, "marketing_medium"]])
    log["sessions_medium_label_variants"] = int(len(idx))

    dev_var = {"desktop": ["Desktop", "DESKTOP ", "pc"], "mobile": ["Mobile", "smartphone", "MOBILE"],
               "tablet": ["Tablet", "iPad"]}
    idx = rng.choice(sessions.index, size=int(0.025 * len(sessions)), replace=False)
    for i in idx:
        sessions.at[i, "device_category"] = rng.choice(dev_var[sessions.at[i, "device_category"]])
    log["sessions_device_label_variants"] = int(len(idx))

    idx = rng.choice(sessions.index, size=int(0.003 * len(sessions)), replace=False)
    sessions.loc[idx, "device_category"] = None
    log["sessions_missing_device"] = int(len(idx))

    idx = rng.choice(sessions.index, size=int(0.01 * len(sessions)), replace=False)
    sessions.loc[idx, "country"] = None
    log["sessions_missing_country"] = int(len(idx))

    idx = rng.choice(sessions.index, size=int(0.05 * len(sessions)), replace=False)
    for i in idx:
        lp = sessions.at[i, "landing_page"]
        src = str(sessions.at[i, "traffic_source"]).strip().lower()
        sessions.at[i, "landing_page"] = (lp + f"?utm_source={src}") if rng.random() < 0.7 else (lp.rstrip("/") + "/" if lp != "/" else "/")
    log["sessions_landing_page_query_or_slash"] = int(len(idx))

    dup = sessions.sample(n=40, random_state=seed)
    sessions = pd.concat([sessions, dup], ignore_index=True)
    log["sessions_exact_duplicate_rows"] = 40

    # ---- Events -------------------------------------------------------------
    ev_var = {"page_view": ["Page View", "PAGE_VIEW", "pageview"], "add_to_cart": ["ADD_TO_CART", "add-to-cart", "Add To Cart"],
              "product_view": ["view_item", "Product View"], "begin_checkout": ["Begin Checkout", "checkout_start"],
              "purchase": ["Purchase", "PURCHASE"], "session_start": ["Session Start"]}
    idx = rng.choice(events.index, size=int(0.02 * len(events)), replace=False)
    for i in idx:
        events.at[i, "event_name"] = rng.choice(ev_var[events.at[i, "event_name"]])
    log["events_name_label_variants"] = int(len(idx))

    # purchase recorded BEFORE checkout (client clock skew)
    co = events[events.event_name == "begin_checkout"].set_index("session_id")["event_timestamp"]
    pur_idx = events.index[(events.event_name == "purchase") & events.session_id.isin(co.index)]
    skew = rng.choice(pur_idx, size=25, replace=False)
    for i in skew:
        sid = events.at[i, "session_id"]
        events.at[i, "event_timestamp"] = co[sid] - timedelta(seconds=int(rng.integers(30, 300)))
    log["events_purchase_before_checkout"] = 25

    # tracking loss: purchase event dropped although transaction exists
    remaining = np.setdiff1d(pur_idx, skew)
    lost = rng.choice(remaining, size=int(0.015 * len(pur_idx)), replace=False)
    events = events.drop(index=lost)
    log["events_missing_purchase_event_with_transaction"] = int(len(lost))

    # orphan events (session never recorded in session table)
    orph = events.sample(n=150, random_state=seed + 2).copy()
    orph["session_id"] = [f"S9{n:06d}" for n in range(150)]
    orph["event_id"] = [f"E9{n:07d}" for n in range(150)]
    events = pd.concat([events, orph], ignore_index=True)
    log["events_orphan_rows"] = 150

    dup = events.sample(frac=0.005, random_state=seed + 3)
    events = pd.concat([events, dup], ignore_index=True)
    log["events_exact_duplicate_rows"] = int(len(dup))

    # ---- Transactions -------------------------------------------------------
    idx = rng.choice(transactions.index, size=8, replace=False)
    transactions.loc[idx, "revenue"] = -transactions.loc[idx, "revenue"]
    transactions.loc[idx, "transaction_status"] = "completed"
    log["transactions_negative_revenue"] = 8

    idx = rng.choice(transactions.index.difference(idx), size=int(0.02 * len(transactions)), replace=False)
    transactions.loc[idx, "currency"] = "usd"
    transactions.loc[idx[:len(idx) // 2], "transaction_status"] = transactions.loc[idx[:len(idx) // 2], "transaction_status"].str.upper()
    log["transactions_label_case_variants"] = int(len(idx))

    # test orders placed by QA on real sessions
    test_rows = transactions.sample(n=15, random_state=seed + 4).copy()
    test_rows["transaction_id"] = [f"TEST{n:04d}" for n in range(15)]
    test_rows["revenue"] = 1.00
    test_rows["transaction_status"] = "test"
    transactions = pd.concat([transactions, test_rows], ignore_index=True)
    log["transactions_test_orders"] = 15

    # orphan transactions
    orph = transactions.sample(n=5, random_state=seed + 5).copy()
    orph["transaction_id"] = [f"T9{n:06d}" for n in range(5)]
    orph["session_id"] = [f"S8{n:06d}" for n in range(5)]
    transactions = pd.concat([transactions, orph], ignore_index=True)
    log["transactions_orphan_rows"] = 5

    # transaction timestamp before session start (impossible)
    s_start = sessions.drop_duplicates("session_id").set_index("session_id")["session_start"]
    cand = transactions.index[transactions.transaction_id.str.match(r"^T\d{7}$") & (transactions.revenue > 0)]
    bad = rng.choice(cand, size=5, replace=False)
    for i in bad:
        transactions.at[i, "transaction_timestamp"] = s_start[transactions.at[i, "session_id"]] - timedelta(hours=int(rng.integers(2, 30)))
    log["transactions_before_session_start"] = 5

    dup = transactions.sample(n=30, random_state=seed + 6)
    transactions = pd.concat([transactions, dup], ignore_index=True)
    log["transactions_exact_duplicate_rows"] = 30

    return sessions, events, transactions, log


def to_raw_strings(df: pd.DataFrame, ts_cols, rng) -> pd.DataFrame:
    """Write timestamps in mixed ISO formats, as exported by different trackers."""
    out = df.copy()
    for c in ts_cols:
        s = pd.to_datetime(out[c])
        a = s.dt.strftime("%Y-%m-%d %H:%M:%S")
        b = s.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        out[c] = np.where(rng.random(len(out)) < 0.12, b, a)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--sessions-per-day", type=float, default=185)
    args = ap.parse_args()

    sessions, events, transactions = build(args.seed, args.sessions_per_day)
    clean_counts = {"sessions": len(sessions), "events": len(events), "transactions": len(transactions),
                    "visitors": int(sessions.visitor_id.nunique())}
    sessions, events, transactions, log = inject_defects(sessions, events, transactions, args.seed)

    rng = np.random.default_rng(args.seed + 99)
    sessions = sessions.sample(frac=1, random_state=args.seed).reset_index(drop=True)   # exports are unordered
    events = events.sample(frac=1, random_state=args.seed).reset_index(drop=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    to_raw_strings(sessions, ["session_start"], rng).to_csv(RAW_DIR / "sessions.csv", index=False)
    to_raw_strings(events, ["event_timestamp"], rng).to_csv(RAW_DIR / "events.csv", index=False)
    to_raw_strings(transactions, ["transaction_timestamp"], rng).to_csv(RAW_DIR / "transactions.csv", index=False)

    meta = {"synthetic": True,
            "disclaimer": "Synthetic data generated for a portfolio project. Not real company performance.",
            "seed": args.seed, "sessions_per_day_base": args.sessions_per_day,
            "date_range": [START_DATE.date().isoformat(), END_DATE.date().isoformat()],
            "generated_before_defects": clean_counts,
            "raw_row_counts": {"sessions": len(sessions), "events": len(events), "transactions": len(transactions)},
            "injected_defects": log}
    (RAW_DIR / "generation_metadata.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
