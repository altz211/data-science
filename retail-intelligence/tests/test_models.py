import unittest
import numpy as np
import pandas as pd
from retail.forecast import make_examples, metrics
from retail.recommend import recommend


class ModelTests(unittest.TestCase):
    def test_forecast_features_ignore_future_sales(self):
        panel = pd.DataFrame({'product_id':'A', 'product':0,
            'week':pd.date_range('2020-01-06',periods=20,freq='W-MON'), 'units':np.arange(20.)})
        origin = panel.week.iloc[10]
        before = make_examples(panel).query('origin == @origin')
        panel.loc[panel.week > origin,'units'] = 9999
        after = make_examples(panel).query('origin == @origin')
        columns = ['recent','previous','average_4','average_8']
        pd.testing.assert_frame_equal(before[columns],after[columns])
        self.assertEqual(before.horizon.tolist(),[1,2,3,4])

    def test_recommendations_exclude_past_products(self):
        model = {'neighbors':{'A':[('B',.9),('C',.5)]},'popular':['A','B','C','D']}
        self.assertEqual(recommend(model,['A','B'],2),['C','D'])

    def test_zero_sales_metric_has_no_infinite_percentage(self):
        self.assertIsNone(metrics(np.array([0.]),np.array([1.]))['wape_pct'])


if __name__ == '__main__':
    unittest.main()
