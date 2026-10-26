import json
import hashlib
import platform
import warnings
import joblib
import duckdb
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.exceptions import ConvergenceWarning
from retail.paths import DATABASE, ARTIFACTS, DATA

FEATURES = ['product', 'horizon', 'recent', 'previous', 'average_4', 'average_8', 'week_sin', 'week_cos']


def make_examples(panel):
    examples = []
    for product, group in panel.groupby('product_id', sort=True):
        group = group.sort_values('week')
        units = group.units.to_numpy()
        for i in range(7, len(group)):
            for horizon in range(1, 5):
                target_date = group.week.iloc[i] + pd.Timedelta(weeks=horizon)
                examples.append({'product_id': product, 'product': group['product'].iloc[i],
                    'origin': group.week.iloc[i], 'target_date': target_date, 'horizon': horizon,
                    'recent': units[i], 'previous': units[i-1],
                    'average_4': units[i-3:i+1].mean(), 'average_8': units[i-7:i+1].mean(),
                    'week_sin': np.sin(target_date.isocalendar().week * 2*np.pi/52),
                    'week_cos': np.cos(target_date.isocalendar().week * 2*np.pi/52),
                    'actual': units[i+horizon] if i+horizon < len(units) else np.nan})
    return pd.DataFrame(examples)


def predict(model, frame):
    return np.maximum(0, np.expm1(model.predict(frame[FEATURES])))


def metrics(actual, predictions):
    denominator = np.abs(actual).sum()
    return {'mae_units': float(np.abs(actual-predictions).mean()),
            'wape_pct': float(100*np.abs(actual-predictions).sum()/denominator) if denominator else None}


def model_factory(name):
    if name == 'boosted':
        return HistGradientBoostingRegressor(max_iter=150, max_leaf_nodes=15,
            l2_regularization=2, early_stopping=False, random_state=42)
    return make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(64, 32),
        max_iter=250, early_stopping=False, random_state=42, alpha=1))


def train(top_n=60):
    with duckdb.connect(str(DATABASE), read_only=True) as db:
        end = pd.Timestamp(db.execute('SELECT max(invoice_date) FROM purchases').fetchone()[0]).normalize()
        complete_end = end - pd.Timedelta(days=end.dayofweek)
        last_week = complete_end - pd.Timedelta(weeks=1)
        test_start = last_week - pd.Timedelta(weeks=3)
        validation_start = test_start - pd.Timedelta(weeks=4)
        products = db.execute('''SELECT product_id FROM purchases WHERE invoice_date < ?
            GROUP BY 1 ORDER BY sum(sales_gbp) DESC, product_id LIMIT ?''', [validation_start, top_n]).df().product_id.tolist()
        weekly = db.sql('SELECT * FROM weekly_sales').df()
    weeks = pd.date_range(weekly.week.min(), last_week, freq='W-MON')
    index = pd.MultiIndex.from_product([products, weeks], names=['product_id', 'week'])
    panel = weekly.set_index(['product_id', 'week']).reindex(index).fillna(0).reset_index()
    panel['product'] = pd.Categorical(panel.product_id, categories=products).codes
    examples = make_examples(panel)
    known = examples.actual.notna()
    training = examples[known & (examples.target_date < validation_start)]
    validation = examples[(examples.origin == validation_start-pd.Timedelta(weeks=1)) & known]
    test = examples[(examples.origin == test_start-pd.Timedelta(weeks=1)) & known]
    results = {'validation': {}, 'test': {}}
    models = {}
    for name in ['boosted', 'neural']:
        model = model_factory(name)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always', ConvergenceWarning)
            model.fit(training[FEATURES], np.log1p(training.actual))
        models[name] = model
        results['validation'][name] = {**metrics(validation.actual.values, predict(model, validation)),
            'convergence_warning': any(isinstance(w.message, ConvergenceWarning) for w in caught)}
    results['validation']['baseline'] = metrics(validation.actual.values, validation.average_4.values)
    winner = min(results['validation'], key=lambda name: results['validation'][name]['mae_units'])
    development = examples[known & (examples.target_date < test_start)]
    if winner == 'baseline':
        test_predictions = test.average_4.values
        model = None
    else:
        model = model_factory(winner)
        model.fit(development[FEATURES], np.log1p(development.actual))
        test_predictions = predict(model, test)
    results['test']['selected'] = metrics(test.actual.values, test_predictions)
    results['test']['baseline'] = metrics(test.actual.values, test.average_4.values)
    results.update({'selected_model': winner, 'validation_start': str(validation_start.date()),
        'test_start': str(test_start.date()), 'test_end': str(last_week.date()), 'products': len(products),
        'target': 'Weekly observed positive unit sales; not unconstrained demand.',
        'design': 'Fixed-origin four-week forecasts. Top products selected before validation. No future sales features.'})
    scored = test[['product_id','origin','target_date','horizon','actual']].copy()
    scored['prediction'] = test_predictions
    scored['baseline'] = test.average_4.values
    scored.to_csv(ARTIFACTS/'forecast_test.csv', index=False)
    future = examples[examples.origin == last_week].copy()
    if winner != 'baseline':
        model = model_factory(winner)
        model.fit(examples.loc[known, FEATURES], np.log1p(examples.loc[known, 'actual']))
        future['prediction'] = predict(model, future)
    else:
        future['prediction'] = future.average_4
    future[['product_id','target_date','horizon','prediction']].to_csv(ARTIFACTS/'forecast_next.csv', index=False)
    panel.to_csv(ARTIFACTS/'weekly_panel.csv', index=False)
    joblib.dump({'model': model, 'selected': winner, 'products': products, 'features': FEATURES}, ARTIFACTS/'forecast.joblib')
    (ARTIFACTS/'forecast_metrics.json').write_text(json.dumps(results, indent=2)+'\n')
    manifest = {'source': json.loads((DATA/'raw/source.json').read_text()),
        'python': platform.python_version(), 'sklearn': sklearn.__version__,
        'training_rows': len(training), 'test_rows': len(test),
        'final_model': 'Refitted using all complete observed weeks after holdout evaluation.',
        'features': FEATURES, 'test_predictions_sha256': hashlib.sha256((ARTIFACTS/'forecast_test.csv').read_bytes()).hexdigest()}
    (ARTIFACTS/'run.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    train()
