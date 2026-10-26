# KPI dashboard

The landing page supports monthly reporting and five main market filters, with an all-market view. November 2011 is the default because it is the last complete month.

- Merchandise sales: positive quantity × unit price, with credit invoices and fee codes excluded.
- Orders: distinct invoice numbers in the selected slice.
- Average order value: sales / orders, including orders with missing customer IDs.
- Active customers: distinct nonmissing customer IDs in the selected slice. Never sum daily distinct counts to form a monthly count.
- Returning customers: active identified customers with an earlier observed purchase before the reporting period, anywhere in the retailer history. This is not lifetime retention.
- Product concentration: sales from the top ten products / all sales in the selected slice.

Completed months compare with the full previous calendar month. The final partial month compares the same elapsed days. Daily lines align by day number, not weekday. No trading-day adjustment or budget targets are assumed.

Markets and dates filter all overview components. Product search and CSV export cover the selected slice's top 100 products; the table shows six rows per page. The forecast and model views retain their own fixed historical evaluation periods and are not recalculated by the KPI filters.

Rebuild after the data pipeline: `python -m retail.kpis`. All reporting queries run against the same `purchases` view. `sql/kpis.sql` defines the headline measures; `retail/kpis.py` exports aggregate reporting slices, never customer identifiers or histories.

Layout references reviewed: DashThis data-visualisation examples, Qlik dashboard examples and ZoomCharts' retail supply-chain/sales example. The interface is original HTML/CSS/JavaScript; no vendor template or library was copied.
