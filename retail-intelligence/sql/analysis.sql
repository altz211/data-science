-- Monthly sales from valid positive purchases, excluding credit invoices.
SELECT date_trunc('month', invoice_date) AS month,
       sum(sales_gbp) AS sales_gbp, count(DISTINCT invoice) AS orders
FROM purchases GROUP BY 1 ORDER BY 1;

-- Product concentration, measured over the observed dataset.
SELECT product_id, description, sales_gbp,
       sales_gbp / sum(sales_gbp) OVER () AS share_of_sales
FROM product_summary ORDER BY sales_gbp DESC LIMIT 20;
