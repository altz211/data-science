"""Turn the reporting views into the JSON files behind the dashboard.

Tables are written as {"columns": [...], "rows": [[...], ...]}, which is about
half the size of a list of dicts and just as easy to read in JavaScript.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from retail.paths import WEB_DATA
from retail.warehouse import query, scalar

SEGMENT_NOTES = {
    "Champions": "Bought recently, buy often and spend the most. Protect: early access, no discounts needed.",
    "Loyal": "Frequent, high-value buyers who have gone a little quiet. Keep them engaged with new ranges.",
    "Potential loyalists": "Recent buyers with a few orders. Nudge towards a regular reorder cycle.",
    "New customers": "One recent order. The second order is the one that matters; follow up quickly.",
    "Needs attention": "Middling recency and value. Worth a targeted reminder before they drift.",
    "At risk": "Used to buy often and spend well, but not for months. Highest-value win-back target.",
    "Hibernating": "Low value and long inactive. Include in seasonal campaigns only.",
    "Lost": "One small order a long time ago. Lowest priority.",
}
SEGMENT_ORDER = list(SEGMENT_NOTES)


def table(frame: pd.DataFrame, digits: int = 2) -> dict:
    """Compact column/row form with sensible rounding and no NaN."""
    frame = frame.copy()
    for column in frame.columns:
        if pd.api.types.is_float_dtype(frame[column]):
            frame[column] = frame[column].round(digits)
        elif pd.api.types.is_datetime64_any_dtype(frame[column]):
            frame[column] = frame[column].dt.strftime("%Y-%m-%d")
    frame = frame.astype(object).where(frame.notna(), None)
    return {"columns": list(frame.columns), "rows": frame.values.tolist()}


def write_json(name: str, payload: dict, folder: Path = WEB_DATA) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.json"
    path.write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False, default=_plain))
    return path


def _plain(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (pd.Timestamp,)):
        return value.strftime("%Y-%m-%d")
    raise TypeError(f"Can't serialise {type(value)}")


def product_names(db, ids) -> dict:
    ids = sorted(set(ids))
    names = query(db, "SELECT product_id, description FROM product_summary WHERE product_id IN (SELECT unnest($1))", [ids])
    return dict(zip(names.product_id, names.description.str.split().str.join(" ").str.title()))


def periods(db) -> list[dict]:
    first, last = query(db, "SELECT min(day) AS first, max(day) AS last FROM sales").iloc[0]
    first, last = pd.Timestamp(first), pd.Timestamp(last)
    result = []
    for start in pd.date_range(first.replace(day=1), last, freq="MS"):
        month_end = start + pd.offsets.MonthEnd(0)
        end = min(month_end, last)
        result.append({"id": start.strftime("%Y-%m"), "label": start.strftime("%b %Y"),
                       "start": f"{start:%Y-%m-%d}", "end": f"{end:%Y-%m-%d}",
                       "partial": bool(end < month_end)})
    result.append({"id": "all", "label": "All history", "start": f"{first:%Y-%m-%d}",
                   "end": f"{last:%Y-%m-%d}", "partial": False})
    return result


def overview(db) -> dict:
    markets = query(db, "SELECT market FROM sales GROUP BY 1 ORDER BY sum(sales_gbp) DESC").market.tolist()
    markets = ["All markets"] + [m for m in markets if m != "Other markets"] + ["Other markets"]
    kpis = query(db, "SELECT * FROM monthly_kpis ORDER BY period, market")
    products = query(db, "SELECT * FROM top_products ORDER BY period, market, sales DESC")
    complete = [p for p in periods(db) if p["id"] != "all" and not p["partial"]]
    return {
        "markets": markets,
        "periods": periods(db),
        "default_period": complete[-1]["id"],
        "kpis": table(kpis),
        "daily": table(query(db, "SELECT * FROM daily_kpis ORDER BY day, market")),
        "hours": table(query(db, "SELECT * FROM trading_hours ORDER BY ALL")),
        "countries": table(query(db, "SELECT * FROM country_sales ORDER BY period, sales DESC")),
        "products": table(products),
        "names": product_names(db, products.product_id),
    }


def customers(db) -> dict:
    rfm = query(db, "SELECT * FROM customer_rfm")
    total = rfm.monetary.sum()
    segments = (rfm.groupby("segment")
                .agg(customers=("customer_id", "size"), revenue=("monetary", "sum"),
                     recency_days=("recency_days", "median"), orders=("frequency", "median"),
                     spend=("monetary", "median"))
                .reindex(SEGMENT_ORDER).dropna(how="all").reset_index())
    segments["revenue_share"] = segments.revenue / total
    segments["note"] = segments.segment.map(SEGMENT_NOTES)

    grid = rfm.groupby(["r", "fm"]).size().rename("customers").reset_index()

    cohorts = query(db, "SELECT * FROM cohort_retention ORDER BY cohort, months_since")
    sizes = cohorts[cohorts.months_since == 0].set_index("cohort").customers
    cohorts["retention"] = cohorts.customers / cohorts.cohort.map(sizes)

    monthly = query(db, """
        SELECT period AS month, customers, new_customers, customers - new_customers AS returning,
               sales, guest_sales
        FROM monthly_kpis WHERE market = 'All markets' AND period <> 'all' ORDER BY 1
    """)
    return {
        "segments": table(segments, 4),
        "rfm_grid": table(grid),
        "cohorts": table(cohorts[["cohort", "months_since", "customers", "retention"]], 4),
        "monthly": table(monthly),
        "pareto": pareto(rfm.monetary),
        "identified_customers": len(rfm),
        "guest_sales_share": scalar(db, "SELECT sum(guest_sales) / sum(sales) FROM monthly_kpis WHERE period = 'all' AND market = 'All markets'"),
    }


def products(db) -> dict:
    summary = query(db, "SELECT * FROM product_summary ORDER BY sales_gbp DESC")
    share = summary.sales_gbp.cumsum() / summary.sales_gbp.sum()
    summary["abc"] = np.select([share <= 0.8, share <= 0.95], ["A", "B"], "C")
    abc = (summary.groupby("abc")
           .agg(products=("product_id", "size"), sales=("sales_gbp", "sum"))
           .reset_index())
    abc["sales_share"] = abc.sales / summary.sales_gbp.sum()

    pairs = query(db, """
        SELECT * FROM basket_pairs WHERE together >= 150
        ORDER BY lift DESC LIMIT 30
    """)
    frequent = query(db, "SELECT * FROM basket_pairs ORDER BY together DESC LIMIT 15")
    returns = query(db, """
        SELECT * FROM product_returns WHERE sold_units >= 2000
        ORDER BY return_rate DESC LIMIT 15
    """)
    credits = query(db, """
        SELECT c.*, k.sales, c.other_credits / k.sales AS returns_share
        FROM monthly_credits c
        JOIN monthly_kpis k ON k.period = c.month AND k.market = 'All markets'
        ORDER BY month
    """)
    top = summary.head(25)[["product_id", "sales_gbp", "units", "orders", "customers"]]
    ids = set(top.product_id) | set(pairs.product_a) | set(pairs.product_b) \
        | set(frequent.product_a) | set(frequent.product_b) | set(returns.product_id)
    return {
        "abc": table(abc, 4),
        "pareto": pareto(summary.sales_gbp),
        "top": table(top),
        "pairs": table(pairs, 3),
        "frequent_pairs": table(frequent, 3),
        "returns": table(returns, 4),
        "credits": table(credits, 4),
        "names": product_names(db, ids),
        "credit_sensitivity": table(query(db, """
            SELECT units_threshold, value_threshold,
                   sum(value_gbp) FILTER (WHERE units >= units_threshold OR value_gbp >= value_threshold) AS large_credits,
                   sum(value_gbp) AS total_credits
            FROM credits CROSS JOIN (VALUES (500, 5000), (1000, 10000), (2000, 20000)) t(units_threshold, value_threshold)
            GROUP BY 1, 2 ORDER BY 1
        """)),
        "catalogue_size": len(summary),
    }


def pareto(values: pd.Series, points: int = 100) -> dict:
    """Cumulative share of value held by the top x% of items."""
    ordered = np.sort(np.asarray(values, dtype=float))[::-1]
    cumulative = np.cumsum(ordered) / ordered.sum()
    x = np.linspace(0, 1, points + 1)
    index = np.clip((x * len(ordered)).astype(int) - 1, 0, len(ordered) - 1)
    y = np.where(x == 0, 0, cumulative[index])
    return {"x": x.round(3).tolist(), "y": y.round(4).tolist(),
            "top20_share": float(cumulative[max(0, int(0.2 * len(ordered)) - 1)])}


def export(db, folder: Path = WEB_DATA) -> dict:
    payloads = {"overview": overview(db), "customers": customers(db), "products": products(db)}
    for name, payload in payloads.items():
        write_json(name, payload, folder)
    return payloads
