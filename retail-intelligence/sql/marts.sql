-- Reporting views on top of clean.sql. Each dashboard page reads from these.
-- GROUPING SETS builds every period x market slice in one pass, so distinct
-- counts (customers, orders) are always computed directly, never summed.

-- The five biggest countries get their own filter; the rest are grouped.
CREATE OR REPLACE VIEW markets AS
SELECT country,
       CASE WHEN row_number() OVER (ORDER BY sum(sales_gbp) DESC) <= 5
            THEN country ELSE 'Other markets' END AS market
FROM purchases
GROUP BY country;

CREATE OR REPLACE VIEW sales AS
SELECT p.*,
       m.market,
       strftime(p.invoice_date, '%Y-%m') AS month,
       p.invoice_date::DATE AS day,
       isodow(p.invoice_date) AS weekday,  -- 1 = Monday
       hour(p.invoice_date) AS hour
FROM purchases p
JOIN markets m USING (country);

CREATE OR REPLACE VIEW customer_first AS
SELECT customer_id,
       min(invoice_date) AS first_purchase,
       strftime(min(invoice_date), '%Y-%m') AS first_month
FROM purchases
WHERE customer_id IS NOT NULL
GROUP BY customer_id;

-- One row per (month or 'all') x (market or 'All markets').
-- A "new" customer made their first ever purchase, in any market, that month.
CREATE OR REPLACE VIEW monthly_kpis AS
SELECT coalesce(s.month, 'all') AS period,
       coalesce(s.market, 'All markets') AS market,
       sum(s.sales_gbp) AS sales,
       count(DISTINCT s.invoice) AS orders,
       sum(s.quantity) AS units,
       count(DISTINCT s.product_id) AS products,
       count(DISTINCT s.customer_id) AS customers,
       count(DISTINCT s.customer_id) FILTER (WHERE c.first_month = s.month) AS new_customers,
       coalesce(sum(s.sales_gbp) FILTER (WHERE s.customer_id IS NULL), 0) AS guest_sales,
       count(DISTINCT s.day) AS trading_days
FROM sales s
LEFT JOIN customer_first c USING (customer_id)
GROUP BY GROUPING SETS ((s.month, s.market), (s.month), (s.market), ());

-- Orders and sales add up across days (an invoice has one date and one country),
-- so daily rows are safe to sum on the client. Customers are not.
CREATE OR REPLACE VIEW daily_kpis AS
SELECT day,
       coalesce(market, 'All markets') AS market,
       sum(sales_gbp) AS sales,
       count(DISTINCT invoice) AS orders,
       sum(quantity) AS units
FROM sales
GROUP BY GROUPING SETS ((day, market), (day));

CREATE OR REPLACE VIEW trading_hours AS
SELECT coalesce(month, 'all') AS period,
       coalesce(market, 'All markets') AS market,
       weekday, hour,
       count(DISTINCT invoice) AS orders
FROM sales
GROUP BY GROUPING SETS ((month, market, weekday, hour), (month, weekday, hour),
                        (market, weekday, hour), (weekday, hour));

CREATE OR REPLACE VIEW country_sales AS
SELECT coalesce(month, 'all') AS period, country,
       sum(sales_gbp) AS sales,
       count(DISTINCT customer_id) AS customers
FROM sales
GROUP BY GROUPING SETS ((month, country), (country));

CREATE OR REPLACE VIEW top_products AS
WITH totals AS (
    SELECT coalesce(month, 'all') AS period,
           coalesce(market, 'All markets') AS market,
           product_id,
           sum(sales_gbp) AS sales,
           sum(quantity) AS units,
           count(DISTINCT invoice) AS orders
    FROM sales
    GROUP BY GROUPING SETS ((month, market, product_id), (month, product_id),
                            (market, product_id), (product_id))
)
SELECT *
FROM totals
QUALIFY row_number() OVER (PARTITION BY period, market ORDER BY sales DESC, product_id) <= 50;

-- RFM scoring for identified customers, as of the day after the data ends.
-- percent_rank keeps tied customers (e.g. everyone with one order) in the same band.
CREATE OR REPLACE VIEW customer_rfm AS
WITH base AS (
    SELECT customer_id,
           date_diff('day', max(invoice_date)::DATE,
                     (SELECT max(invoice_date)::DATE + 1 FROM purchases)) AS recency_days,
           count(DISTINCT invoice) AS frequency,
           sum(sales_gbp) AS monetary
    FROM purchases
    WHERE customer_id IS NOT NULL
    GROUP BY customer_id
),
scored AS (
    SELECT *,
           least(5, 1 + floor(5 * percent_rank() OVER (ORDER BY recency_days DESC)))::INT AS r,
           least(5, 1 + floor(5 * percent_rank() OVER (ORDER BY frequency)))::INT AS f,
           least(5, 1 + floor(5 * percent_rank() OVER (ORDER BY monetary)))::INT AS m
    FROM base
)
SELECT *,
       ceil((f + m) / 2)::INT AS fm,
       CASE
           WHEN r >= 4 AND ceil((f + m) / 2) >= 4 THEN 'Champions'
           WHEN r = 3 AND ceil((f + m) / 2) >= 4 THEN 'Loyal'
           WHEN r >= 4 AND ceil((f + m) / 2) >= 2 THEN 'Potential loyalists'
           WHEN r >= 4 THEN 'New customers'
           WHEN r = 3 THEN 'Needs attention'
           WHEN ceil((f + m) / 2) >= 4 THEN 'At risk'
           WHEN ceil((f + m) / 2) >= 2 THEN 'Hibernating'
           ELSE 'Lost'
       END AS segment
FROM scored;

-- Share of each acquisition cohort still buying N months later.
-- December 2009 also contains everyone who was already a customer before the data starts.
CREATE OR REPLACE VIEW cohort_retention AS
SELECT c.first_month AS cohort,
       date_diff('month', date_trunc('month', c.first_purchase),
                 date_trunc('month', s.invoice_date)) AS months_since,
       count(DISTINCT s.customer_id) AS customers
FROM sales s
JOIN customer_first c USING (customer_id)
GROUP BY ALL;

-- Products bought in the same order, among the 300 most frequently ordered.
-- lift > 1 means the pair appears together more often than chance.
CREATE OR REPLACE VIEW basket_pairs AS
WITH popular AS (
    SELECT product_id FROM product_summary ORDER BY orders DESC LIMIT 300
),
baskets AS (
    SELECT DISTINCT invoice, product_id
    FROM purchases
    WHERE product_id IN (SELECT product_id FROM popular)
),
item_orders AS (
    SELECT product_id, count(*) AS orders FROM baskets GROUP BY product_id
),
pairs AS (
    SELECT a.product_id AS product_a, b.product_id AS product_b, count(*) AS together
    FROM baskets a
    JOIN baskets b ON a.invoice = b.invoice AND a.product_id < b.product_id
    GROUP BY ALL
)
SELECT p.*,
       together / ia.orders AS confidence_a_b,
       together / ib.orders AS confidence_b_a,
       together * n.orders / (ia.orders * ib.orders) AS lift
FROM pairs p
JOIN item_orders ia ON ia.product_id = p.product_a
JOIN item_orders ib ON ib.product_id = p.product_b
CROSS JOIN (SELECT count(DISTINCT invoice) AS orders FROM purchases) n;

CREATE OR REPLACE VIEW monthly_credits AS
SELECT strftime(invoice_date, '%Y-%m') AS month,
       coalesce(sum(value_gbp) FILTER (WHERE NOT is_large_credit), 0) AS other_credits,
       coalesce(sum(value_gbp) FILTER (WHERE is_large_credit), 0) AS large_credits,
       count(DISTINCT invoice) AS credit_notes
FROM credits
GROUP BY ALL;

CREATE OR REPLACE VIEW product_returns AS
SELECT c.product_id,
       sum(c.units) AS returned_units,
       sum(c.value_gbp) AS returned_value,
       any_value(p.units) AS sold_units,
       sum(c.units) / any_value(p.units) AS return_rate
FROM credits c
JOIN product_summary p USING (product_id)
WHERE NOT c.is_large_credit
GROUP BY c.product_id;
