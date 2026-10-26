// Data & definitions: data quality audit, metric definitions, pipeline run.

import { load } from '../data.js';
import { escape, number, pct, compactPounds } from '../format.js';

const DEFINITIONS = [
  ['Sales', 'Quantity × unit price in GBP for purchase lines with a positive quantity and price, on real stock codes. Credit notes, postage, fees and manual adjustments are excluded. Gross sales, not net revenue or profit.'],
  ['Orders', 'Distinct invoice numbers. Average order value = sales ÷ orders, including orders without a customer ID.'],
  ['Active customers', 'Distinct customer IDs buying in the selected month and market. Counted directly for each slice, never summed across days.'],
  ['New customers', 'Customers whose first purchase in the data, in any market, falls in that month. December 2009 counts everyone, because earlier history isn\'t available.'],
  ['Markets', 'The five largest countries by sales get their own filter. Everything else is "Other markets".'],
  ['Comparisons', 'Each month is compared with the previous month and with the same month a year earlier. December 2011 stops on the 9th, so it is compared on the same 9 days of earlier months.'],
  ['RFM segments', 'Recency, frequency and monetary scores from 1 to 5 using percentile ranks, so tied customers share a score. Frequency and monetary are averaged, then mapped to eight named segments.'],
  ['Returns', 'Credit-note lines on real stock codes. Lines of 1,000+ units or £10,000+ are shown separately as large adjustments. Their cause is unknown.'],
  ['Basket pairs', 'Two products on the same invoice, among the 300 most-ordered products. Lift = observed co-occurrence ÷ what independent buying would predict.'],
  ['WAPE', 'Weighted absolute percentage error: total absolute forecast error ÷ total actual units. Unlike MAPE it does not explode on weeks with zero sales.'],
  ['Hit rate, recall, NDCG @10', 'Hit rate: share of customers with at least one future purchase in their top 10. Recall: share of their future purchases that appeared. NDCG also rewards ranking them near the top.'],
];

const AUDIT_LABELS = {
  source_rows: 'Rows in the source file',
  sales_rows: 'Rows counted as sales',
  credit_rows: 'Credit-note rows',
  fee_or_adjustment_rows: 'Fees, postage and adjustments',
  zero_or_negative_rows: 'Zero or negative quantity/price',
  missing_customer_rows: 'Rows without a customer ID',
  identical_rows: 'Exact repeated rows (kept)',
};

export async function render(container) {
  const meta = await load('meta');
  const a = meta.audit;
  container.innerHTML = `
    <div class="grid">
      <section class="card span-7"><h2>Definitions</h2><br><dl>${DEFINITIONS.map(([term, text]) => `<dt>${escape(term)}</dt><dd>${escape(text)}</dd>`).join('')}</dl></section>
      <section class="card span-5"><h2>Data quality</h2>
        <div class="table-wrap"><table><tbody>${Object.entries(AUDIT_LABELS).map(([key, label]) => `
          <tr><td>${label}</td><td class="num">${number(a[key])}</td><td class="num">${key === 'source_rows' ? '' : pct(a[key] / a.source_rows, 1)}</td></tr>`).join('')}
        </tbody></table></div>
        <p class="note">Nothing is deleted. Raw rows are loaded unchanged and every rule is a SQL view (sql/clean.sql), so each exclusion can be inspected. Exact repeated rows are kept because the same item can legitimately appear twice on an invoice.</p>
        <h3>Totals after cleaning</h3>
        <ul class="list">
          <li><span>Sales</span><span>${compactPounds(a.sales_gbp)}</span></li>
          <li><span>Orders</span><span>${number(a.orders)}</span></li>
          <li><span>Identified customers</span><span>${number(a.customers)}</span></li>
          <li><span>Products</span><span>${number(a.products)}</span></li>
          <li><span>Countries</span><span>${number(a.countries)}</span></li>
          <li><span>Period</span><span>${a.first_timestamp.slice(0, 10)} to ${a.last_timestamp.slice(0, 10)}</span></li>
        </ul>
        <h3>Pipeline run</h3>
        <ul class="list">
          <li><span>Generated</span><span>${escape(meta.generated_utc.replace('T', ' ').slice(0, 16))} UTC</span></li>
          ${Object.entries(meta.timings_seconds).map(([step, seconds]) => `<li><span>${escape(step)}</span><span>${seconds}s</span></li>`).join('')}
          <li><span>Python / scikit-learn</span><span>${escape(meta.python)} / ${escape(meta.scikit_learn)}</span></li>
        </ul>
        <p class="note">Source: ${escape(meta.source.citation || 'Online Retail II, UCI')}. Licence CC BY 4.0.</p>
      </section>
    </div>`;
}
