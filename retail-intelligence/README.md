# Retail Intelligence

Retail sales, customers, products and models using 1.07 million Online Retail II transaction lines.

[Dashboard](https://altz211.github.io/data-science/retail-intelligence/) · [Findings](docs/report.md) · [Methodology](docs/methodology.md) · [Notebook](notebooks/walkthrough.ipynb)

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -e .
python -m retail
uvicorn retail.api:app --reload
pytest
```

Use `python -m retail --source online_retail_II.xlsx` for a local copy, or `--skip-models` to reuse saved model results.
For the static dashboard, run `python -m http.server --directory web`.

## Decisions

- Keep SQL reporting views and the Python pipeline together in this project folder.
- Serve saved aggregate results on GitHub Pages; the API and model training run locally.
- Compare forecasts with simple baselines. Finish tuning outcomes before the holdout starts.
- Keep all credit adjustments visible. Their size does not identify the reason for a credit.
- Treat recommendations and inventory actions as ideas to test, rather than proven sales uplift.

Data: [Online Retail II](https://doi.org/10.24432/C5CG6D), Chen (2012), UCI, CC BY 4.0.
Charts: Apache ECharts 5.5.1, Apache-2.0; bundled locally with its license and notice.
