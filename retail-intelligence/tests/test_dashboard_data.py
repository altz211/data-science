"""Checks on the committed dashboard data, so a bad pipeline run can't be published."""
import json
from collections import defaultdict

import pytest

from retail.paths import WEB_DATA

pytestmark = pytest.mark.skipif(not (WEB_DATA / "overview.json").exists(), reason="run `python -m retail` first")


def load(name):
    return json.loads((WEB_DATA / f"{name}.json").read_text())


def records(table):
    return [dict(zip(table["columns"], row)) for row in table["rows"]]


def test_daily_figures_reconcile_with_monthly_kpis():
    overview = load("overview")
    monthly = {(r["period"], r["market"]): r for r in records(overview["kpis"])}
    daily = defaultdict(float)
    for row in records(overview["daily"]):
        daily[(row["day"][:7], row["market"])] += row["sales"]
    for key, total in daily.items():
        assert total == pytest.approx(monthly[key]["sales"], abs=0.05)


def test_markets_add_up_to_the_total():
    overview = load("overview")
    kpis = [r for r in records(overview["kpis"]) if r["period"] == "all"]
    total = next(r["sales"] for r in kpis if r["market"] == "All markets")
    assert sum(r["sales"] for r in kpis if r["market"] != "All markets") == pytest.approx(total, abs=1)


def test_headline_totals_match_the_audit():
    meta, overview = load("meta"), load("overview")
    everything = next(r for r in records(overview["kpis"]) if r["period"] == "all" and r["market"] == "All markets")
    assert everything["sales"] == pytest.approx(meta["audit"]["sales_gbp"], abs=1)
    assert everything["customers"] == meta["audit"]["customers"]
    assert meta["audit"]["source_rows"] == 1_067_371


def test_model_results_are_complete():
    forecast, recs, report = load("forecast"), load("recommendations"), load("report")
    assert forecast["products_count"] == len(forecast["products"]) == 100
    assert all(len(p["future"]) == 4 for p in forecast["products"])
    assert all(0 <= lo <= hi for p in forecast["products"] for _, f, lo, hi in p["future"])
    assert 0 < forecast["interval"]["coverage"] <= 1
    assert len(records(recs["metrics"])) == 4
    assert len(report["sections"]) >= 8


def test_published_tuning_finishes_before_holdout_issuance():
    from datetime import date, timedelta
    forecast = load("forecast")
    tuning_end = date.fromisoformat(forecast["tuning_origins"][-1]) + timedelta(weeks=4, days=6)
    holdout_issue = date.fromisoformat(forecast["holdout_issue_dates"][0])
    assert tuning_end < holdout_issue


def test_credit_sensitivity_preserves_the_inclusive_total():
    rows = records(load("products")["credit_sensitivity"])
    assert len(rows) == 3
    assert len({row["total_credits"] for row in rows}) == 1
    assert rows[0]["large_credits"] >= rows[1]["large_credits"] >= rows[2]["large_credits"]
