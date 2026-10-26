# Working decisions

## Data

Online Retail II contains UK gift retailer transactions from 2009–2011, including wholesale customers. It is not a current Gulf retail dataset. Prices are GBP. Keep source records unchanged in DuckDB and record the download hash. Missing customer IDs remain in sales analysis but cannot support customer models. Preserve identical lines; they can be legitimate repeated items.

Merchandise SKU rule: five digits with up to two letter suffixes. Codes for manual adjustments, postage and fees are excluded from merchandising, sales and customer models. Raw rows remain inspectable. This rule should be reviewed before adapting to another retailer.

Positive purchase sales exclude nonpositive quantity, nonpositive price and credit invoices. This is not net revenue. Cancellation/credit rows are not automatically physical returns. There is no cost-of-goods, inventory, exposure, clicks or reliable stockout label. No margin, conversion uplift or stock availability claims.

## Models

Forecast weekly observed positive unit sales for the top 60 products selected using pre-validation sales. Missing product-weeks are zero observed purchases, which may include unavailability or prelaunch periods. We do not infer unconstrained demand.

Forecasts are issued after a complete week for the next four weeks. Feature windows end at the origin. Validation and holdout each cover four weeks from a fixed origin. Select by validation MAE; refit before holdout. After reporting test performance, refit for the final historical forward projection. These results do not establish present-day performance. This first experiment has one validation/test origin; rolling backtests and seasonal analysis remain to be added.

Neural challenger: MLP with two hidden layers (64,32). This is a small feed-forward neural model, not a transformer or sequential deep recommender. Failure to beat a baseline is a result to inspect.

Recommendations: train cosine item similarity on binary customer-product interactions for the top 1,500 historical products. Exclude prior purchases and compare against popularity on returning customers with an eligible new purchase during the following 28 days. This restricted cohort must not be described as all-customer performance. Catalogue coverage, repeat-purchase recommendations, sequential models and validation-based model selection remain future work.

## Interface

The HTML dashboard reads a versioned result snapshot. The optional FastAPI server recomputes recommendations from a saved model. Forecasts are batch results. Data is historical; no live commercial feed is connected. Initial styling is intentionally editable.

## Before release

- Review the use cases and dashboard layout together.
- Add rolling evaluation and segment diagnostics.
- Decide whether to prioritise sequential recommendations, uncertainty or customer inactivity modelling.
- Add run tracking, deployment configuration and monitoring after the model scope is settled.

This project lives under retail-intelligence/ in the shared data-science repository. The repository workflow publishes web/ through GitHub Pages; the Python API requires a separate runtime.
