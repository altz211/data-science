import unittest
from fastapi.testclient import TestClient
from retail.api import app
from retail.paths import ROOT


@unittest.skipUnless((ROOT/'web/assets/results.json').exists(), 'Run the pipeline first')
class ApiTests(unittest.TestCase):
    def test_results_and_recommendations(self):
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/health').status_code, 200)
            data = client.get('/api/results').json()
            self.assertGreater(data['audit']['source_rows'], 1_000_000)
            if not data['customers']:
                self.assertEqual(client.get('/api/recommendations/example').status_code, 503)
                self.assertEqual(client.get('/').status_code, 200)
                return
            alias = next(iter(data['customers']))
            response = client.get('/api/recommendations/'+alias)
            self.assertEqual(response.status_code, 200)
            products = response.json()['products']
            self.assertEqual(len(products), 10)
            self.assertTrue(set(products).isdisjoint(data['customers'][alias]['history']))
            self.assertEqual(client.get('/api/recommendations/unknown').status_code, 404)
            self.assertEqual(client.get('/').status_code, 200)


if __name__ == '__main__':
    unittest.main()
