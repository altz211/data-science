CREATE OR REPLACE VIEW checked_transactions AS
SELECT *,
    starts_with(upper(invoice), 'C') AS is_credit,
    regexp_full_match(product_id, '[0-9]{5}[A-Za-z]{0,2}') AS is_merchandise,
    invoice_date IS NOT NULL AND quantity > 0 AND unit_price > 0
        AND NOT starts_with(upper(invoice), 'C') AS is_purchase
FROM raw_transactions;

CREATE OR REPLACE VIEW purchases AS
SELECT *, quantity * unit_price AS sales_gbp
FROM checked_transactions
WHERE is_purchase AND is_merchandise;

CREATE OR REPLACE VIEW weekly_sales AS
SELECT date_trunc('week', invoice_date)::DATE AS week, product_id,
       sum(quantity)::DOUBLE AS units, sum(sales_gbp)::DOUBLE AS sales_gbp
FROM purchases
GROUP BY 1, 2;

CREATE OR REPLACE VIEW product_summary AS
SELECT product_id, arg_max(description, invoice_date) AS description,
       sum(quantity)::DOUBLE AS units, sum(sales_gbp)::DOUBLE AS sales_gbp,
       count(DISTINCT invoice) AS orders
FROM purchases GROUP BY 1;

CREATE OR REPLACE VIEW customer_summary AS
SELECT customer_id, count(DISTINCT invoice) AS orders,
       sum(sales_gbp)::DOUBLE AS sales_gbp, max(invoice_date) AS last_purchase
FROM purchases WHERE customer_id IS NOT NULL GROUP BY 1;
