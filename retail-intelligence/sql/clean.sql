-- Cleaning rules. raw_transactions is loaded untouched; everything else is a view
-- so the rules stay visible and easy to change.

-- Flag every line instead of deleting anything.
CREATE OR REPLACE VIEW checked_transactions AS
SELECT *,
    starts_with(invoice, 'C') AS is_credit,
    -- Real stock codes are five digits plus an optional colour/size suffix.
    -- POST, M, DOT, BANK CHARGES, AMAZONFEE and similar are fees or adjustments.
    regexp_full_match(product_id, '[0-9]{5}[A-Z]{0,2}') AS is_merchandise,
    invoice_date IS NOT NULL
        AND quantity > 0
        AND unit_price > 0
        AND NOT starts_with(invoice, 'C') AS is_purchase
FROM raw_transactions;

-- Positive merchandise sales. This is gross sales in GBP, not net revenue or profit.
CREATE OR REPLACE VIEW purchases AS
SELECT invoice, product_id, description, quantity, invoice_date, unit_price,
       customer_id, country,
       quantity * unit_price AS sales_gbp
FROM checked_transactions
WHERE is_purchase AND is_merchandise;

-- Size flags separate unusually large credits; the data does not identify their cause.
CREATE OR REPLACE VIEW credits AS
SELECT invoice, product_id, invoice_date, customer_id, country,
       -quantity AS units,
       -quantity * unit_price AS value_gbp,
       -quantity >= 1000 OR -quantity * unit_price >= 10000 AS is_large_credit
FROM checked_transactions
WHERE is_credit AND is_merchandise AND quantity < 0;

-- Products change description over time; keep the latest name.
CREATE OR REPLACE VIEW product_summary AS
SELECT product_id,
       arg_max(description, invoice_date) AS description,
       sum(quantity)::DOUBLE AS units,
       sum(sales_gbp)::DOUBLE AS sales_gbp,
       count(DISTINCT invoice) AS orders,
       count(DISTINCT customer_id) AS customers
FROM purchases
GROUP BY product_id;

-- Weeks start on Monday.
CREATE OR REPLACE VIEW weekly_sales AS
SELECT date_trunc('week', invoice_date)::DATE AS week,
       product_id,
       sum(quantity)::DOUBLE AS units,
       sum(sales_gbp)::DOUBLE AS sales_gbp
FROM purchases
GROUP BY ALL;
