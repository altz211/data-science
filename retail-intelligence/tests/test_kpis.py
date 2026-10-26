import json
import unittest
from pathlib import Path
import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


class KpiTests(unittest.TestCase):
    def test_unique_customers_and_order_value(self):
        rows = pd.DataFrame([
            ['1','10','United Kingdom','2011-01-01',10.0,2,'12345'],
            ['2','10','United Kingdom','2011-01-02',5.0,1,'12345'],
            ['3','11','United Kingdom','2011-01-02',7.0,1,'12346'],
            ['4',None,'United Kingdom','2011-01-02',3.0,1,'12345'],
        ], columns=['invoice','customer_id','country','invoice_date','sales_gbp','quantity','product_id'])
        rows.invoice_date = pd.to_datetime(rows.invoice_date)
        with duckdb.connect() as db:
            db.register('purchases', rows)
            result = db.execute((ROOT/'sql/kpis.sql').read_text(), {
                'start':pd.Timestamp('2011-01-02'), 'end':pd.Timestamp('2011-01-03'), 'market':'All markets'
            }).df().iloc[0]
        self.assertEqual(result.customers, 2)
        self.assertEqual(result.orders, 3)
        self.assertEqual(result.returning_customers, 1)
        self.assertEqual(result.sales_gbp/result.orders, 5)

    def test_snapshot_reconciles_and_comparisons_match(self):
        data = json.loads((ROOT/'web/assets/kpis.json').read_text())
        existing = json.loads((ROOT/'web/assets/results.json').read_text())
        self.assertAlmostEqual(data['slices']['all']['All markets']['metrics']['sales_gbp'], existing['summary']['sales_gbp'], places=4)
        self.assertEqual(data['slices']['all']['All markets']['metrics']['customers'], existing['summary']['customers'])
        self.assertEqual(next(p for p in data['periods'] if p['id']=='2011-11')['comparison'], '2011-10-01 to 2011-10-31')
        self.assertEqual(next(p for p in data['periods'] if p['id']=='2011-12')['comparison'], '2011-11-01 to 2011-11-09')
        for period in data['slices'].values():
            for market in period.values():
                metrics = market['metrics']
                self.assertAlmostEqual(sum(r['sales_gbp'] for r in market['daily']), metrics['sales_gbp'], places=4)
                self.assertLessEqual(metrics['returning_customers'], metrics['customers'])
                self.assertAlmostEqual(sum(r['sales_gbp'] for r in market['markets']), metrics['sales_gbp'], places=4)


if __name__ == '__main__':
    unittest.main()
