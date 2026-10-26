"""Four-week unit forecasts for the top products, with a rolling backtest.

Every Monday the buyer uses the last completed week to forecast the next four.
Five tuning origins choose the model; a three-origin gap ensures their outcomes
are observed before the five holdout forecasts begin.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from retail.warehouse import query

HORIZONS = (1, 2, 3, 4)
TOP_PRODUCTS = 100
ORIGINS = 10
INTERVAL = (0.1, 0.9)

FEATURES = ["product", "horizon", "lag_1", "lag_2", "lag_3", "lag_4", "mean_4", "mean_8",
            "mean_13", "std_8", "zero_weeks_8", "price", "last_year", "week_sin", "week_cos"]
NUMERIC = [f for f in FEATURES if f != "product"]

BASELINES = {
    "Last week": "lag_1",
    "4-week average": "mean_4",
    "Same week last year": "last_year",
}


# ---------------------------------------------------------------- data

def evaluation_origins(last_origin: pd.Timestamp) -> list[pd.Timestamp]:
    half = ORIGINS // 2
    holdout = list(pd.date_range(end=last_origin, periods=half, freq="W-MON"))
    tuning_end = holdout[0] - pd.Timedelta(weeks=max(HORIZONS))
    tuning = list(pd.date_range(end=tuning_end, periods=half, freq="W-MON"))
    return tuning + holdout


def load_panel(db) -> tuple[pd.DataFrame, pd.Timestamp, list[pd.Timestamp]]:
    """Weekly units for the top products, with zero-filled gaps.

    Products are ranked on sales known before the first backtest origin, so
    the choice of products can't peek at the evaluation weeks.
    """
    last_day = pd.Timestamp(query(db, "SELECT max(invoice_date) AS d FROM purchases").d[0])
    # The final week is incomplete (data stops on a Friday), so drop it.
    last_week = (last_day - pd.Timedelta(days=last_day.dayofweek)).normalize() - pd.Timedelta(weeks=1)
    last_origin = last_week - pd.Timedelta(weeks=max(HORIZONS))
    origins = evaluation_origins(last_origin)

    products = query(db, """
        SELECT product_id FROM purchases WHERE invoice_date < ?
        GROUP BY 1 ORDER BY sum(sales_gbp) DESC, product_id LIMIT ?
    """, [origins[0] + pd.Timedelta(weeks=1), TOP_PRODUCTS]).product_id.tolist()

    weekly = query(db, "SELECT * FROM weekly_sales WHERE product_id IN (SELECT unnest($1))", [products])
    weekly["week"] = pd.to_datetime(weekly.week)
    # The first week of data starts on a Tuesday, so begin at the first full week.
    weeks = pd.date_range(weekly.week.min() + pd.Timedelta(weeks=1), last_week, freq="W-MON")
    grid = pd.MultiIndex.from_product([products, weeks], names=["product_id", "week"])
    panel = (weekly.set_index(["product_id", "week"])[["units", "sales_gbp"]]
             .reindex(grid, fill_value=0).reset_index())
    return panel, last_week, origins


def make_features(panel: pd.DataFrame) -> pd.DataFrame:
    """One row per product x origin week x horizon.

    Everything except `actual` uses data up to and including the origin week.
    """
    panel = panel.sort_values(["product_id", "week"]).copy()
    units = panel.groupby("product_id").units
    sales = panel.groupby("product_id").sales_gbp

    base = panel[["product_id", "week"]].rename(columns={"week": "origin"})
    for lag in range(1, 5):
        base[f"lag_{lag}"] = units.shift(lag - 1)
    for window in (4, 8, 13):
        base[f"mean_{window}"] = units.transform(lambda s, w=window: s.rolling(w).mean())
    base["std_8"] = units.transform(lambda s: s.rolling(8).std())
    base["zero_weeks_8"] = units.transform(lambda s: s.eq(0).rolling(8).sum())
    units_8 = units.transform(lambda s: s.rolling(8).sum())
    base["price"] = sales.transform(lambda s: s.rolling(8).sum()) / units_8.replace(0, np.nan)
    base["product"] = pd.Categorical(base.product_id).codes

    frames = []
    for horizon in HORIZONS:
        frame = base.copy()
        frame["horizon"] = horizon
        frame["target_week"] = frame.origin + pd.Timedelta(weeks=horizon)
        frame["actual"] = units.shift(-horizon)
        # Same calendar week a year earlier: already history at the origin.
        frame["last_year"] = units.shift(52 - horizon)
        week_of_year = frame.target_week.dt.isocalendar().week.astype(float)
        frame["week_sin"] = np.sin(2 * np.pi * week_of_year / 52)
        frame["week_cos"] = np.cos(2 * np.pi * week_of_year / 52)
        frames.append(frame)
    examples = pd.concat(frames, ignore_index=True)
    return examples.dropna(subset=["mean_13"])  # need 13 weeks of history


# ---------------------------------------------------------------- models

def scale(frame: pd.DataFrame) -> np.ndarray:
    # Products sell anywhere from 10 to 5,000 units a week. Modelling sales
    # relative to their own recent level lets one model learn from all of them.
    return frame.mean_8.to_numpy() + 1


# Weight the scaled absolute loss back into units for the boosting models.
def boosting(loss="absolute_error", quantile=None):
    return HistGradientBoostingRegressor(
        loss=loss, quantile=quantile, max_iter=300, learning_rate=0.05,
        max_leaf_nodes=15, min_samples_leaf=40, l2_regularization=1.0,
        categorical_features=[0], random_state=42)


def neural_net():
    network = MLPRegressor(hidden_layer_sizes=(64, 32), alpha=1e-3, learning_rate_init=1e-3,
                           max_iter=300, early_stopping=True, random_state=42)
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                         TransformedTargetRegressor(network, func=np.log1p, inverse_func=np.expm1))


MODELS_TO_TRY = {
    "Gradient boosting": (boosting, FEATURES),
    "Neural network": (neural_net, NUMERIC),
}


def fit_predict(name: str, train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    make, features = MODELS_TO_TRY[name]
    model = make()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        model.fit(train[features], train.actual / scale(train),
                  **({"sample_weight": scale(train)} if name == "Gradient boosting" else {}))
    return np.maximum(0, model.predict(test[features]) * scale(test))


def fit_interval(train: pd.DataFrame, test: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    bounds = []
    for q in INTERVAL:
        model = boosting("quantile", q).fit(
            train[FEATURES], train.actual / scale(train), sample_weight=scale(train))
        bounds.append(np.maximum(0, model.predict(test[FEATURES]) * scale(test)))
    return np.minimum(*bounds), np.maximum(*bounds)


def baseline(name: str, frame: pd.DataFrame) -> np.ndarray:
    values = frame[BASELINES[name]]
    # No sales history a year back for some products: fall back to the recent average.
    return values.fillna(frame.mean_4).to_numpy()


# ---------------------------------------------------------------- evaluation

def scores(actual, predicted) -> dict:
    actual, predicted = np.asarray(actual, float), np.asarray(predicted, float)
    total = actual.sum()
    return {
        "mae": float(np.abs(predicted - actual).mean()),
        "wape": float(np.abs(predicted - actual).sum() / total) if total else None,
        "bias": float((predicted - actual).sum() / total) if total else None,
    }


def backtest(examples: pd.DataFrame, origins: list[pd.Timestamp]) -> pd.DataFrame:
    """Forecasts every model would have made at each origin."""
    results = []
    for origin in origins:
        # Only weeks that had already happened at the origin can be training targets.
        train = examples[(examples.target_week <= origin) & examples.actual.notna()]
        test = examples[examples.origin == origin].copy()
        for name in BASELINES:
            test[name] = baseline(name, test)
        for name in MODELS_TO_TRY:
            test[name] = fit_predict(name, train, test)
        test["low"], test["high"] = fit_interval(train, test)
        results.append(test)
    return pd.concat(results, ignore_index=True)


def summarise(predictions: pd.DataFrame, origins: list[pd.Timestamp]) -> tuple[pd.DataFrame, str]:
    half = len(origins) // 2
    if origins[half - 1] + pd.Timedelta(weeks=max(HORIZONS)) > origins[half]:
        raise ValueError("Tuning outcomes must be complete before holdout issuance")
    predictions["window"] = np.where(predictions.origin.isin(origins[:half]), "tuning", "holdout")
    models = list(BASELINES) + list(MODELS_TO_TRY)
    rows = [{"window": window, "model": model, **scores(group.actual, group[model])}
            for window, group in predictions.groupby("window") for model in models]
    metrics = pd.DataFrame(rows)
    tuning = metrics[metrics.window == "tuning"]
    selected = tuning.loc[tuning.wape.idxmin(), "model"]
    return metrics, selected


# ---------------------------------------------------------------- pipeline

def run(db) -> dict:
    panel, last_week, origins = load_panel(db)
    examples = make_features(panel)
    predictions = backtest(examples, origins)
    metrics, selected = summarise(predictions, origins)

    holdout = predictions[predictions.window == "holdout"]
    by_horizon = pd.DataFrame([
        {"model": model, "horizon": h, **scores(group.actual, group[model])}
        for h, group in holdout.groupby("horizon")
        for model in dict.fromkeys([selected, "4-week average", "Same week last year"])
    ])
    inside = holdout.actual.between(holdout.low, holdout.high)

    # Refit on everything for the forward-looking forecast.
    known = examples[examples.actual.notna()]
    future = examples[examples.origin == last_week].copy()
    future["forecast"] = fit_predict(selected, known, future) if selected in MODELS_TO_TRY \
        else baseline(selected, future)
    future["low"], future["high"] = fit_interval(known, future)

    return {
        "last_complete_week": f"{last_week:%Y-%m-%d}",
        "tuning_origins": [f"{o:%Y-%m-%d}" for o in origins[:len(origins) // 2]],
        "holdout_origins": [f"{o:%Y-%m-%d}" for o in origins[len(origins) // 2:]],
        "origin_definition": "Start of the last completed week; issued the following Monday",
        "tuning_issue_dates": [f"{o + pd.Timedelta(weeks=1):%Y-%m-%d}" for o in origins[:len(origins) // 2]],
        "holdout_issue_dates": [f"{o + pd.Timedelta(weeks=1):%Y-%m-%d}" for o in origins[len(origins) // 2:]],
        "products_count": int(panel.product_id.nunique()),
        "selected": selected,
        "metrics": metrics,
        "by_horizon": by_horizon,
        "interval": {"nominal": INTERVAL[1] - INTERVAL[0], "coverage": float(inside.mean()),
                     "holdout_forecasts": int(len(holdout))},
        "products": product_series(panel, predictions, future, selected),
    }


def product_series(panel, predictions, future, selected) -> list[dict]:
    """Per-product history, one-week-ahead backtest and the next four weeks."""
    history = panel[panel.week > panel.week.max() - pd.Timedelta(weeks=52)]
    one_week = predictions[(predictions.horizon == 1) & (predictions.window == "holdout")]
    totals = panel.groupby("product_id").sales_gbp.sum().sort_values(ascending=False)
    series = []
    for product_id in totals.index:
        h = history[history.product_id == product_id]
        b = one_week[one_week.product_id == product_id]
        f = future[future.product_id == product_id]
        series.append({
            "id": product_id,
            "history": [[f"{w:%Y-%m-%d}", u] for w, u in zip(h.week, h.units)],
            "backtest": [[f"{w:%Y-%m-%d}", a, round(p), round(n), round(lo), round(hi)]
                         for w, a, p, n, lo, hi in zip(b.target_week, b.actual, b[selected],
                                                       b["4-week average"], b.low, b.high)],
            "future": [[f"{w:%Y-%m-%d}", round(p), round(lo), round(hi)]
                       for w, p, lo, hi in zip(f.target_week, f.forecast, f.low, f.high)],
        })
    return series
