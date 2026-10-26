-- One reporting slice. Dates are inclusive start and exclusive end.
SELECT sum(p.sales_gbp)::DOUBLE AS sales_gbp,
       count(DISTINCT p.invoice) AS orders,
       sum(p.quantity)::DOUBLE AS units,
       count(DISTINCT p.product_id) AS products,
       count(DISTINCT p.customer_id) AS customers,
       count(DISTINCT CASE WHEN f.first_seen < $start THEN p.customer_id END) AS returning_customers
FROM purchases p
LEFT JOIN (SELECT customer_id, min(invoice_date) AS first_seen
           FROM purchases WHERE customer_id IS NOT NULL GROUP BY 1) f USING (customer_id)
WHERE p.invoice_date >= $start AND p.invoice_date < $end
  AND ($market = 'All markets' OR p.country = $market);
