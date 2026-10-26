# Review order

1. `artifacts/audit.json`: what the data contains and what was excluded.
2. `sql/clean.sql`: sales and customer definitions.
3. `notebooks/01_data_review.ipynb`: source and sales patterns.
4. `notebooks/02_forecasts.ipynb`: validation selection and holdout error.
5. `notebooks/03_recommendations.ipynb`: similarity versus popularity.
6. `web/index.html`: dashboard content and sections.
7. `web/assets/style.css`: layout, type and colour.
8. `web/assets/app.js`: dashboard behaviour.

Decide the next modelling step after reviewing results: rolling forecast tests, sequential recommendations, or customer inactivity. Keep the README brief; record reasoning in `docs/decisions.md`.
