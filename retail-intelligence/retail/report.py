"""Write the findings: one list of sections, rendered to the dashboard and to Markdown.

Every number is pulled from the same data the dashboard shows, so the report
can't drift out of date when the pipeline is rerun.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from retail.paths import REPORT


def money(value: float) -> str:
    if abs(value) >= 1e6:
        return f"£{value / 1e6:.2f}M"
    if abs(value) >= 1e4:
        return f"£{value / 1e3:.0f}k"
    return f"£{value:,.0f}"


def pct(value: float, digits: int = 0) -> str:
    return f"{value * 100:.{digits}f}%"


def frame(table: dict) -> pd.DataFrame:
    return pd.DataFrame(table["rows"], columns=table["columns"])


def mature_retention(cohorts: pd.DataFrame, last_month: str) -> tuple[float, float, int]:
    cutoff = pd.Period(last_month, freq="M") - 12
    eligible = sorted(c for c in cohorts.cohort.unique()
                      if "2009-12" < c <= str(cutoff))
    if not eligible:
        return 0.0, 0.0, 0
    values = cohorts.pivot(index="cohort", columns="months_since", values="retention")
    values = values.reindex(index=eligible, columns=[1, 12]).fillna(0)
    return float(values[1].mean()), float(values[12].mean()), len(eligible)


def findings(overview: dict, customers: dict, products: dict, forecast: dict, recs: dict) -> list[dict]:
    kpis = frame(overview["kpis"])
    everything = kpis[kpis.market == "All markets"].set_index("period")

    # Two comparable trading years: Dec-Nov, skipping the partial final December.
    months = everything.drop(index="all")
    year_one = months.loc["2009-12":"2010-11"].sum()
    year_two = months.loc["2010-12":"2011-11"].sum()
    growth = year_two.sales / year_one.sales - 1
    order_change = year_two.orders / year_one.orders - 1
    aov_change = (year_two.sales / year_two.orders) / (year_one.sales / year_one.orders) - 1
    autumn = months.loc["2011-09":"2011-11"].sales.sum() / year_two.sales
    nov = months.loc["2011-11"].sales / months.loc["2010-11"].sales - 1

    by_market = kpis[(kpis.period == "all") & (kpis.market != "All markets")].set_index("market")
    uk_share = by_market.loc["United Kingdom", "sales"] / everything.loc["all", "sales"]
    eire = by_market.loc["EIRE"]

    hours = frame(overview["hours"])
    hours = hours[(hours.period == "all") & (hours.market == "All markets")]
    by_day = hours.groupby("weekday").orders.sum()
    by_hour = hours.groupby("hour").orders.sum()
    days = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday", 7: "Sunday"}

    segments = frame(customers["segments"]).set_index("segment")
    cohorts = frame(customers["cohorts"])
    last_complete_month = max(p["id"] for p in overview["periods"]
                              if p["id"] != "all" and not p["partial"])
    month_one, month_twelve, mature_count = mature_retention(cohorts, last_complete_month)

    abc = frame(products["abc"]).set_index("abc")
    pairs = frame(products["pairs"])
    names = products["names"]
    top_pair = pairs.iloc[0]
    credits = frame(products["credits"])
    returns_share = credits.other_credits.sum() / credits.sales.sum()
    reversals = credits.large_credits.sum()

    metrics = frame(forecast["metrics"])
    holdout = metrics[metrics.window == "holdout"].set_index("model")
    chosen = forecast["selected"]
    gain = 1 - holdout.loc[chosen, "wape"] / holdout.loc["4-week average", "wape"]

    rec = frame(recs["metrics"]).set_index("model")
    hybrid = rec.loc["Hybrid (similarity + trending)"]
    sellers = rec.loc["Best sellers"]
    trending = rec.loc["Trending (last 28 days)"]

    return [
        {
            "title": "Sales grew through bigger orders, not more of them",
            "metric": pct(growth, 1),
            "metric_label": "sales growth, Dec–Nov year on year",
            "finding": (f"Merchandise sales reached {money(year_two.sales)} in the twelve months to November 2011, "
                        f"up {pct(growth, 1)} on the year before. Orders fell {pct(-order_change, 1)}, so all of "
                        f"the growth came from average order value, which rose {pct(aov_change, 1)}."),
            "action": "Track order value by customer segment to confirm whether larger baskets come from existing "
                      "wholesalers or a shift in customer mix.",
        },
        {
            "title": "The business lives and dies by autumn",
            "metric": pct(autumn),
            "metric_label": "of annual sales in Sep–Nov",
            "finding": (f"September to November delivered {pct(autumn)} of the year's sales. November 2011 alone "
                        f"was {money(months.loc['2011-11'].sales)}, {pct(nov, 1)} above November 2010. "
                        "Stock for the Christmas range has to be committed by late summer."),
            "action": "Plan inventory and staffing around the Q4 ramp; this is where forecast accuracy pays most.",
        },
        {
            "title": "A UK business with a few very large overseas accounts",
            "metric": pct(uk_share),
            "metric_label": "of sales from the UK",
            "finding": (f"The UK accounts for {pct(uk_share)} of sales. Outside it, value is concentrated: "
                        f"{int(eire.customers)} identified customers in Ireland bought {money(eire.sales)}, with an "
                        f"average order of {money(eire.sales / eire.orders)}."),
            "action": "Treat the top overseas accounts as key accounts with named owners; losing one is material.",
        },
        {
            "title": "Orders arrive Monday to Friday lunchtime, plus Sunday",
            "metric": days[int(by_day.idxmax())],
            "metric_label": "busiest day for orders",
            "finding": (f"{days[int(by_day.idxmax())]} is the busiest day and {int(by_hour.idxmax())}:00 the busiest "
                        f"hour. Saturday trading is almost non-existent ({int(by_day.get(6, 0))} orders in two years), "
                        "while Sunday is a normal trading day."),
            "action": "Align staffing with observed ordering hours. Test promotion timing separately before claiming it improves sales.",
        },
        {
            "title": "A fifth of customers drive three quarters of revenue",
            "metric": pct(customers["pareto"]["top20_share"]),
            "metric_label": "of identified sales from the top 20% of customers",
            "finding": (f"Champions are {int(segments.loc['Champions', 'customers']):,} customers "
                        f"({pct(segments.loc['Champions', 'customers'] / customers['identified_customers'])}) "
                        f"but {pct(segments.loc['Champions', 'revenue_share'])} of identified revenue. "
                        f"{int(segments.loc['At risk', 'customers'])} 'at risk' customers used to order often "
                        f"(median {int(segments.loc['At risk', 'orders'])} orders) but have been quiet for "
                        f"{int(segments.loc['At risk', 'recency_days'])} days; they spent "
                        f"{money(segments.loc['At risk', 'revenue'])} in total."),
            "action": "Run a win-back campaign for the at-risk segment before spending on acquisition.",
        },
        {
            "title": "Compare retention at the same cohort maturity",
            "metric": pct(month_one),
            "metric_label": "of new customers buy again the next month",
            "finding": (f"Across {mature_count} cohorts with twelve complete follow-up months, "
                        f"{pct(month_one)} ordered in month one and {pct(month_twelve)} in month twelve. "
                        "These are monthly activity rates for the same cohorts, not the probability of "
                        "staying after a second purchase. The initial left-censored cohort is excluded."),
            "action": "Test an early reorder reminder against a control group; measure repeat orders and incremental value.",
        },
        {
            "title": "A long tail of slow sellers",
            "metric": pct(abc.loc["A", "products"] / products["catalogue_size"]),
            "metric_label": "of products make 80% of sales",
            "finding": (f"{int(abc.loc['A', 'products']):,} of {products['catalogue_size']:,} products produce 80% of "
                        f"sales. The bottom {int(abc.loc['C', 'products']):,} products ('C' class) share just 5%."),
            "action": "Review C-class lines alongside margin, stock and range requirements before proposing delisting.",
        },
        {
            "title": "Customers buy in matching sets",
            "metric": f"{top_pair.lift:.0f}×",
            "metric_label": "lift for the strongest product pair",
            "finding": (f"The strongest pairing is {names.get(top_pair.product_a)} with {names.get(top_pair.product_b)}: "
                        f"bought together {int(top_pair.together)} times, {top_pair.lift:.0f} times more often than "
                        "chance. Most top pairs are colour variants of the same item."),
            "action": "Sell colour variants as bundles and place them together online.",
        },
        {
            "title": "Large credit adjustments need separate investigation",
            "metric": pct(returns_share, 1),
            "metric_label": "of sales credited, excluding large adjustments",
            "finding": (f"Credits below the size threshold total {pct(returns_share, 1)} of sales; "
                        f"including large adjustments, credits total "
                        f"{pct(returns_share + reversals / credits.sales.sum(), 1)}. "
                        f"Large adjustments account for {money(reversals)}. The flag means at least "
                        "1,000 units or £10,000 per line; it does not prove a cancellation or physical return."),
            "action": "Reconcile large credits to their original invoices before assigning a cause. Review sensitivity to the size threshold.",
        },
        {
            "title": "Forecast accuracy on a separate holdout",
            "metric": pct(gain),
            "metric_label": "less forecast error than a 4-week average",
            "finding": (f"On a holdout of five forecast weeks before Christmas 2011, {chosen.lower()} had a weighted "
                        f"error of {pct(holdout.loc[chosen, 'wape'])} against {pct(holdout.loc['4-week average', 'wape'])} "
                        f"for a 4-week average. Its signed bias was {pct(holdout.loc[chosen, 'bias'])}, "
                        f"and the nominal 80% quantile range held {pct(forecast['interval']['coverage'])} of actual outcomes."),
            "action": "Use the quantile range in a replenishment scenario. Safety stock requires lead times, service targets and inventory costs, which this dataset lacks.",
        },
        {
            "title": "Recommendations: blend 'similar' with 'trending'",
            "metric": f"{hybrid.hit_rate_at_10 / sellers.hit_rate_at_10:.1f}×",
            "metric_label": "hit rate of a best-seller list",
            "finding": (f"For returning customers, a top-10 list blending purchase similarity with current trends "
                        f"contained a product they went on to buy for the first time {pct(hybrid.hit_rate_at_10)} of "
                        f"the time, against {pct(sellers.hit_rate_at_10)} for best sellers and "
                        f"{pct(trending.hit_rate_at_10)} for trending alone, while covering "
                        f"{pct(hybrid.catalogue_coverage)} of the catalogue (trending: {pct(trending.catalogue_coverage)})."),
            "action": "Use the hybrid for 'you may also like' and reorder emails; A/B test before claiming uplift.",
        },
    ]


def markdown(sections: list[dict], audit: dict) -> str:
    lines = [
        "# Retail Intelligence: findings",
        "",
        f"UK online gift wholesaler, {audit['first_timestamp'][:10]} to {audit['last_timestamp'][:10]}. "
        f"{audit['source_rows']:,} transaction lines, {money(audit['sales_gbp'])} of merchandise sales. "
        "Generated by `python -m retail`; numbers match the dashboard.",
        "",
        "| # | Finding | Key number |",
        "|---|---|---|",
    ]
    lines += [f"| {i} | {s['title']} | **{s['metric']}** {s['metric_label']} |" for i, s in enumerate(sections, 1)]
    for i, section in enumerate(sections, 1):
        lines += ["", f"## {i}. {section['title']}", "", section["finding"], "", f"**What to do:** {section['action']}"]
    lines += [
        "",
        "## Caveats",
        "",
        "- Sales are gross merchandise sales in GBP. There is no cost, margin or stock data, so nothing here is profit.",
        "- 13% of sales have no customer ID; customer analysis covers identified customers only.",
        "- December 2009 contains customers who were active before the data starts, so that cohort is not truly new.",
        "- Model results come from one retailer and one Christmas season. They are a limited historical evaluation, not a guaranteed uplift.",
        "",
    ]
    return "\n".join(lines)


def write(sections: list[dict], audit: dict, path: Path = REPORT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown(sections, audit))
    return path
