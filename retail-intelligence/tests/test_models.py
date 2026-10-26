import numpy as np
import pandas as pd
import pytest

from retail.forecast import HORIZONS, make_features, scores
from retail.recommend import fit, ranking_scores, recommend


def panel(units):
    weeks = pd.date_range("2020-01-06", periods=len(units), freq="W-MON")
    return pd.DataFrame({"product_id": "A", "week": weeks, "units": units, "sales_gbp": np.array(units) * 2.0})


def test_forecast_features_never_see_the_future():
    units = list(np.arange(60.0))
    origin = pd.Timestamp("2020-01-06") + pd.Timedelta(weeks=30)
    before = make_features(panel(units)).query("origin == @origin")
    changed = units[:31] + [9999.0] * 29   # rewrite everything after the origin
    after = make_features(panel(changed)).query("origin == @origin")
    features = ["lag_1", "lag_4", "mean_4", "mean_13", "std_8", "price", "zero_weeks_8"]
    pd.testing.assert_frame_equal(before[features].reset_index(drop=True), after[features].reset_index(drop=True))
    assert sorted(before.horizon) == list(HORIZONS)
    # ...while the target itself does change, which proves the test can fail.
    assert not before.actual.equals(after.actual)


def test_last_year_feature_points_at_the_same_week_a_year_earlier():
    units = list(np.arange(70.0))
    examples = make_features(panel(units))
    row = examples[(examples.origin == pd.Timestamp("2020-01-06") + pd.Timedelta(weeks=60)) & (examples.horizon == 2)]
    assert row.last_year.item() == 62 - 52


def test_scores_handle_weeks_with_no_sales():
    result = scores([0, 0], [1, 2])
    assert result["wape"] is None
    assert result["mae"] == 1.5
    assert scores([10, 10], [8, 14])["wape"] == 0.3


def test_recommendations_skip_owned_products_and_top_up_with_best_sellers():
    model = {"neighbours": {"A": [("B", 0.9), ("C", 0.5)]}, "popular": ["A", "B", "C", "D"], "trending": []}
    assert recommend(model, ["A", "B"], k=2) == ["C", "D"]


def test_fusion_blends_similar_and_trending_products():
    model = {"neighbours": {"A": [("B", 0.9), ("C", 0.5)]}, "popular": ["A", "B", "C", "D", "E"],
             "trending": ["E", "B"], "fusion_k": 5}
    ranked = recommend(model, ["A"], k=3)
    assert ranked[0] == "B"          # top of both lists
    assert set(ranked) == {"B", "C", "E"}


def test_similarity_model_learns_co_purchases():
    purchases = pd.DataFrame({
        "customer_id": ["1", "1", "2", "2", "3"],
        "product_id": ["A", "B", "A", "B", "C"],
        "invoice_date": pd.Timestamp("2011-01-01"),
    })
    model = fit(purchases)
    best, similarity = model["neighbours"]["A"][0]
    assert best == "B" and similarity == pytest.approx(1.0)
    assert "C" not in dict(model["neighbours"]["A"])   # never bought together


def test_ranking_scores():
    recall, ndcg, hit = ranking_scores(["X", "B", "Y"], {"B", "Z"})
    assert recall == 0.5 and hit == 1.0 and 0 < ndcg < 1


def test_tuning_labels_are_known_before_first_holdout_forecast():
    from retail.forecast import evaluation_origins
    origins = evaluation_origins(pd.Timestamp("2011-10-31"))
    tuning, holdout = origins[:5], origins[5:]
    last_tuning_label_end = tuning[-1] + pd.Timedelta(weeks=max(HORIZONS), days=6)
    first_holdout_issue = holdout[0] + pd.Timedelta(weeks=1)
    assert last_tuning_label_end < first_holdout_issue
    assert not ({o + pd.Timedelta(weeks=h) for o in tuning for h in HORIZONS}
                & {o + pd.Timedelta(weeks=h) for o in holdout for h in HORIZONS})


def test_retention_compares_only_equally_mature_cohorts():
    from retail.report import mature_retention
    cohorts = pd.DataFrame({"cohort": ["2009-12", "2010-01", "2010-01", "2010-02", "2011-01"],
                            "months_since": [1, 1, 12, 0, 1],
                            "retention": [1.0, 0.4, 0.2, 1.0, 1.0]})
    one, twelve, count = mature_retention(cohorts, "2011-02")
    assert (one, twelve, count) == (0.2, 0.1, 2)


def test_holdout_values_cannot_change_model_selection():
    from retail.forecast import BASELINES, MODELS_TO_TRY, evaluation_origins, summarise
    origins = evaluation_origins(pd.Timestamp("2011-10-31"))
    predictions = pd.DataFrame({"origin": origins, "actual": 10.0})
    for model in list(BASELINES) + list(MODELS_TO_TRY):
        predictions[model] = 15.0
    predictions["Last week"] = 10.0
    _, selected = summarise(predictions.copy(), origins)
    predictions.loc[5:, "Last week"] = 10000.0
    predictions.loc[5:, "Neural network"] = 10.0
    _, after = summarise(predictions, origins)
    assert selected == after == "Last week"


def test_overlapping_tuning_outcomes_are_rejected():
    from retail.forecast import summarise
    origins = list(pd.date_range("2011-08-29", periods=10, freq="W-MON"))
    with pytest.raises(ValueError, match="Tuning outcomes"):
        summarise(pd.DataFrame(), origins)
