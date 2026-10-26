"""The cleaning rules and reporting views, checked on a hand-built dataset."""
from retail.warehouse import audit, query, scalar


def test_sales_exclude_credits_fees_and_free_lines(db):
    # 10 + 10 + 5 + 20 + 10 + 6 = 61; credits, postage and the free sample are out.
    assert scalar(db, "SELECT sum(sales_gbp) FROM purchases") == 61
    assert scalar(db, "SELECT count(*) FROM purchases WHERE product_id = 'POST'") == 0


def test_credit_size_flag_preserves_all_credit_value(db):
    credits = query(db, "SELECT * FROM monthly_credits")
    assert credits.other_credits.sum() == 5
    assert credits.large_credits.sum() == 2000
    assert (credits.other_credits + credits.large_credits).sum() == 2005


def test_audit_counts_every_rule(db):
    result = audit(db)
    assert result["source_rows"] == 10
    assert result["sales_rows"] == 6
    assert result["credit_rows"] == 2
    assert result["fee_or_adjustment_rows"] == 1
    assert result["zero_or_negative_rows"] == 1
    assert result["missing_customer_rows"] == 1


def test_monthly_customers_are_distinct_and_new_means_first_ever(db):
    kpis = query(db, "SELECT * FROM monthly_kpis WHERE market = 'All markets'").set_index("period")
    assert kpis.loc["2011-01", "customers"] == 2
    assert kpis.loc["2011-01", "new_customers"] == 2
    # February: A is back (returning), plus a guest who has no ID.
    assert kpis.loc["2011-02", "customers"] == 1
    assert kpis.loc["2011-02", "new_customers"] == 0
    assert kpis.loc["2011-02", "guest_sales"] == 10
    # Whole history counts each customer once.
    assert kpis.loc["all", "customers"] == 3
    assert kpis.loc["all", "orders"] == 5


def test_daily_rows_add_up_to_monthly_totals(db):
    daily = query(db, "SELECT strftime(day, '%Y-%m') AS month, sum(sales) AS sales FROM daily_kpis "
                      "WHERE market = 'All markets' GROUP BY 1").set_index("month").sales
    monthly = query(db, "SELECT period, sales FROM monthly_kpis WHERE market = 'All markets' "
                        "AND period <> 'all'").set_index("period").sales
    assert daily.sort_index().tolist() == monthly.sort_index().tolist()


def test_cohorts_count_months_since_first_order(db):
    cohorts = query(db, "SELECT * FROM cohort_retention WHERE cohort = '2011-01' ORDER BY months_since")
    assert cohorts.months_since.tolist() == [0, 1]
    assert cohorts.customers.tolist() == [2, 1]


def test_rfm_ranks_the_recent_frequent_customer_highest(db):
    rfm = query(db, "SELECT * FROM customer_rfm").set_index("customer_id")
    assert rfm.loc["C", "recency_days"] < rfm.loc["B", "recency_days"]
    assert rfm.loc["A", "frequency"] == 2
    assert rfm.loc["A", "f"] > rfm.loc["B", "f"]
    assert set(rfm.segment) <= {"Champions", "Loyal", "Potential loyalists", "New customers",
                                "Needs attention", "At risk", "Hibernating", "Lost"}
