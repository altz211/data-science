import json
from datetime import datetime, timezone
import duckdb
import joblib
import pandas as pd
from retail.paths import DATABASE, ARTIFACTS, ROOT
from retail.recommend import recommend


def export():
    with duckdb.connect(str(DATABASE), read_only=True) as db:
        products = db.sql('SELECT * FROM product_summary ORDER BY sales_gbp DESC LIMIT 500').df()
        catalogue = db.sql('SELECT product_id, description FROM product_summary').df()
        monthly = db.sql("SELECT strftime(invoice_date, '%Y-%m') AS month, sum(sales_gbp) AS sales_gbp, count(DISTINCT invoice) AS orders FROM purchases GROUP BY 1 ORDER BY 1").df()
        summary = db.sql('SELECT sum(sales_gbp) AS sales_gbp, count(DISTINCT invoice) AS orders, count(DISTINCT customer_id) AS customers, count(DISTINCT product_id) AS products FROM purchases').df().iloc[0].to_dict()
    model = joblib.load(ARTIFACTS/'recommendations.joblib')
    customers = json.loads((ARTIFACTS/'customers.json').read_text())
    for customer in customers.values():
        customer['recommendations'] = recommend(model, customer['history'])
    snapshot = {'generated_utc': datetime.now(timezone.utc).isoformat(), 'summary': summary,
        'catalogue': catalogue.to_dict('records'), 'monthly': monthly.to_dict('records'), 'products': products.to_dict('records'),
        'forecast_test': pd.read_csv(ARTIFACTS/'forecast_test.csv',dtype={'product_id':str}).to_dict('records'),
        'forecast_next': pd.read_csv(ARTIFACTS/'forecast_next.csv',dtype={'product_id':str}).to_dict('records'),
        'forecast_metrics': json.loads((ARTIFACTS/'forecast_metrics.json').read_text()),
        'recommendation_metrics': json.loads((ARTIFACTS/'recommendation_metrics.json').read_text()),
        'audit': json.loads((ARTIFACTS/'audit.json').read_text()), 'customers': customers}
    destination = ROOT/'web/assets/results.json'
    destination.write_text(json.dumps(snapshot,allow_nan=False)+'\n')
    print(destination)


if __name__ == '__main__':
    export()
