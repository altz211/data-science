import unittest
from pathlib import Path
import duckdb
import pandas as pd


class SalesDefinitions(unittest.TestCase):
    def test_credit_and_missing_customer_handling(self):
        rows = pd.DataFrame([
            ['1','12345','Example',2,'2011-01-01',5,None,'UK'],
            ['C2','12345','Example',-1,'2011-01-02',5,'10','UK'],
            ['3','12346','Free',1,'2011-01-03',0,'10','UK'],
        ], columns=['invoice','product_id','description','quantity','invoice_date','unit_price','customer_id','country'])
        rows.invoice_date = pd.to_datetime(rows.invoice_date)
        with duckdb.connect() as db:
            db.register('rows', rows)
            db.execute('CREATE TABLE raw_transactions AS SELECT * FROM rows')
            db.execute((Path(__file__).resolve().parents[1]/'sql/clean.sql').read_text())
            self.assertEqual(db.execute('SELECT sum(sales_gbp) FROM purchases').fetchone()[0],10)
            self.assertEqual(db.execute('SELECT count(*) FROM customer_summary').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*) FROM checked_transactions WHERE is_credit').fetchone()[0],1)


if __name__ == '__main__':
    unittest.main()
