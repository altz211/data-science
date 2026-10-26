# Retail Intelligence

Real Online Retail II transactions, product sales forecasts and customer recommendations.

[Open the dashboard](https://altz211.github.io/data-science/retail-intelligence/)

## Run

1. Create a Python 3.11+ environment.
2. `pip install -e ".[notebooks,test]"`
3. `python -m retail.pipeline` — download data, build SQL views, train and evaluate models, export dashboard results.
4. `python -m uvicorn retail.api:app --reload`
5. Open http://localhost:8000.

The included dashboard snapshot works without rebuilding: `python -m http.server 8000 --directory web`. Run the pipeline first to generate the recommendation model and customer examples; these files are not published in this repository.

Tests: `python -m unittest discover -s tests`.

## Decisions

- Start with actual transactions and temporal evaluation.
- Compare a four-week sales baseline with boosted trees and a two-hidden-layer neural network.
- Recommend unseen products using purchase similarity, with a popularity benchmark.
- Keep notebooks for inspection and scripts for repeatable runs.
- Finalise the product scope and interface together before deployment.

Dataset: Chen, D. (2012), [Online Retail II](https://doi.org/10.24432/C5CG6D), CC BY 4.0.

See [decisions](docs/decisions.md) for definitions and remaining work.

GitHub Pages serves the saved analysis and predictions. Run the Python API locally to use the model endpoints. The shared repository workflow tests this project and publishes its web folder.
