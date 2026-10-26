# Draft verification

- Source: 1,067,371 actual Online Retail II rows, 2009–2011.
- Initial five tests passed: forecast feature leakage, recommendation exclusions, zero-demand metric handling, SQL sales definitions and API endpoints.
- Three notebooks executed top-to-bottom with saved outputs using an in-process IPython runner. Jupyter kernel sockets were unavailable in this build environment. `python scripts/check_notebooks.py` uses a standard kernel on a local machine.
- Four notebook charts inspected for labels and values.
- Browser checked: saved results load, product search, product forecast selection and customer recommendations.
- Docker configuration included, not built or deployed here.

## Initial results

Selected forecast: boosted, chosen on validation MAE.

Holdout MAE: 165.71 units per product-week; baseline 176.23.
Holdout WAPE: 42.87%; baseline 45.60%.
One four-week holdout over 60 historically selected products; no claim of production reliability.

Recommendation Recall@10: 0.0569; popularity 0.0214.
Evaluation covers 1238 eligible returning customers with an unseen catalogue purchase, not all customers.

The shared repository workflow runs the tests and deploys the static dashboard. Python model training and API serving run separately.

## KPI redesign

Seven tests now pass, including distinct customer/AOV semantics and KPI slice reconciliation. Browser checked: market filtering, partial-month comparison, product pagination, metric switching and forecast navigation.
