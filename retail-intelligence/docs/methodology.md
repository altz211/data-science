# Methodology

How the numbers are made, and why each choice was made the way it was.
For the findings themselves see [report.md](report.md).

## Data

[Online Retail II](https://doi.org/10.24432/C5CG6D) (Chen, 2012, UCI, CC BY 4.0): every invoice line of a
UK online gift wholesaler from 1 Dec 2009 to 9 Dec 2011. 1,067,371 rows, eight columns, prices in GBP.
Most customers are shops buying to resell, which explains the large orders.

`python -m retail` downloads the archive once, caches it as Parquet in `data/raw/` with its SHA-256,
and normalises column types and stock codes, then loads the rows into DuckDB. If UCI is unreachable, pass a local copy with `--source`.

## Cleaning

All rules are SQL views in [`sql/clean.sql`](../sql/clean.sql). Nothing is deleted, so any exclusion can be inspected.

| Rule | Why |
|---|---|
| Sales = positive quantity × positive price, non-credit invoices | Credits and zero-price lines are not sales |
| Stock code must be 5 digits + optional letters | `POST`, `M`, `DOT`, `BANK CHARGES`, `AMAZONFEE` are fees or adjustments |
| Stock codes upper-cased | `15056bl` and `15056BL` are the same product |
| Exact repeated rows kept | The same item can legitimately appear twice on an invoice |
| Missing customer IDs kept for sales, excluded from customer analysis | They are real orders (13% of sales) but can't be tracked |
| Credit lines of 1,000+ units or £10k+ flagged as large adjustments | Size is observable; a cancellation or physical return cannot be inferred. Show total credits and both size groups |

## Reporting views

[`sql/marts.sql`](../sql/marts.sql) builds everything the dashboard shows. `GROUPING SETS` produces every
month × market slice in one query, so distinct counts (customers, orders) are computed directly for
each slice rather than summed from smaller ones, which would double count. The previous version ran
roughly 800 separate queries; this one takes about seven seconds in total.

- **Markets:** the five largest countries by sales, plus "Other markets".
- **New customer:** first purchase anywhere in the data falls in that month. December 2009 is
  left-censored: it includes everyone who was already a customer.
- **Comparisons:** previous month and same month last year. December 2011 is partial (to the 9th),
  so it is compared on the same nine days, and customer counts are not compared.
- **RFM:** recency, frequency and monetary scores 1–5 from percentile ranks (ties share a score),
  frequency and monetary averaged, then mapped to eight named segments.
- **Basket pairs:** products on the same invoice among the 300 most ordered. Lift = observed ÷ expected
  under independent buying; only pairs seen in 150+ orders are shown.

## Observed sales forecast

**Question:** every Monday, how many units of each top-100 product will sell in each of the next four weeks?

**Backtest.** Five tuning origins and five holdout origins, separated by a three-origin gap.
An origin names the last completed week, not the decision date: a week starting 26 September
is available for a forecast issued the following Monday. Training targets include only completed weeks.
All four-week tuning outcomes must finish before the first holdout issue date. Products are chosen
using sales available at the earliest tuning issue. Actual dates are recorded in `web/data/forecast.json`.
The model choice is frozen for holdout; fitting may expand with newly observed history at each issue.

**Features** (all known at the origin): last four weeks, 4/8/13-week means, 8-week volatility, share of
zero weeks, average price, the same week last year, week-of-year (sin/cos), horizon, and product.

**Models.** Three baselines (last week, 4-week average, same week last year), gradient boosting and a
two-layer neural network (MLP). The target is units divided by the product's recent level, so one model
can learn from products selling 10 or 5,000 a week. Gradient boosting optimises absolute error: that
uses sample weights equal to the scaling factor to restore an absolute loss in original units.
The MLP instead fits a log-transformed relative-sales target. P10/P90 ranges come from separate weighted
quantile models. If endpoints cross they are sorted, using the same rule in testing and deployment.
The point model is independent and can lie outside the quantile range. Coverage is measured, not guaranteed.

**Metric.** WAPE (total absolute error ÷ total units). Unlike MAPE it doesn't explode on zero-sales weeks
and it weights big sellers in proportion to their volume.

**Known limits.** One season of holdout; overlapping horizons are correlated, so forecasts are not independent samples. No promotions,
stock-outs or price changes are in the data. Missing product-weeks are zero sales, which can also mean
out of stock.

Retention comparisons in the report use the same cohorts with twelve complete follow-up months,
excluding December 2009 and the partial final month. Monthly activity is not conditional retention
after a second purchase.

Credit sensitivity is exported at half, default and double the line-size thresholds. These are
descriptive groupings; none establishes the reason for a credit. Inventory policies need stock,
lead-time and cost inputs that are absent here.

## Recommendations

**Question:** which products should we show a returning customer?

- **Item similarity:** cosine similarity between products based on which customers bought them, among
  the 1,500 most-bought products. Recommend unseen products most similar to the customer's history.
- **Hybrid:** reciprocal rank fusion of the similarity list and "trending in the last 28 days". The fusion
  constant is chosen on the previous four weeks, then scored on the final four.
- **Baselines:** all-time best sellers and trending.

**Evaluation.** Train on purchases before 12 Nov 2011, then check which products each returning customer
bought *for the first time* in the next 28 days. Report hit rate, recall and NDCG at 10, plus catalogue
coverage (how much of the range ever gets recommended). New customers are excluded because there is
nothing to personalise for them.

**Known limits.** Offline scores only: they show which list contains what people went on to buy, not
whether showing it would have caused the sale. That needs an A/B test.

## Reproducibility

`requirements.txt` pins the exact versions behind the published results. `web/data/meta.json` records
the run time, library versions, source hash and how long each step took. CI runs the tests on every push
and only publishes the dashboard if the committed data reconciles.
