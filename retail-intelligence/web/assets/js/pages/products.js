// Products: sales concentration (ABC), best sellers, basket pairs and returns.

import { axis, legend, plot, tooltip } from '../charts.js';
import { load } from '../data.js';
import { axisPounds, compactPounds, escape, monthLabel, number, pct, pounds, records, tile } from '../format.js';

export async function render(container) {
  const data = await load('products');
  const name = (id) => data.names[id] || id;
  const abc = Object.fromEntries(records(data.abc).map((r) => [r.abc, r]));
  const credits = records(data.credits);
  const returnsShare = credits.reduce((s, r) => s + r.other_credits, 0) / credits.reduce((s, r) => s + r.sales, 0);
  const reversals = credits.reduce((s, r) => s + r.large_credits, 0);
  const pairs = records(data.pairs);
  const returns = records(data.returns);
  const top = records(data.top);

  container.innerHTML = `
    <div class="tiles">
      ${tile('Products sold', number(data.catalogue_size), [{ label: 'distinct stock codes' }])}
      ${tile('A-class products', number(abc.A.products), [{ label: `${pct(abc.A.products / data.catalogue_size)} of the range makes 80% of sales` }])}
      ${tile('All credits / sales', pct(returnsShare + reversals / credits.reduce((s, r) => s + r.sales, 0), 1), [{ label: `Other credits: ${pct(returnsShare, 1)} of sales` }])}
      ${tile('Large credit adjustments', compactPounds(reversals), [{ label: 'lines of 1,000+ units or £10k+, reported separately' }])}
    </div>
    <div class="grid">
      <section class="card span-5"><div class="card-head"><div><h2>Sales concentration</h2>
        <p>Cumulative share of sales by product rank. A = first 80%, B = next 15%, C = last 5%.</p></div></div><div class="chart" id="pareto"></div></section>
      <section class="card span-7"><div class="card-head"><div><h2>Best sellers</h2><p>Top 25 products by sales, whole history</p></div></div>
        <div class="chart" id="top" style="height:560px"></div></section>
      <section class="card span-12"><div class="card-head"><div><h2>Bought together</h2>
        <p>Pairs among the 300 most-ordered products, seen together in at least 150 orders. Lift = how many times more often than chance.</p></div></div>
        <div class="table-wrap"><table><thead><tr><th>Product</th><th>Goes with</th><th class="num">Orders together</th>
          <th class="num">Lift</th><th class="num">Buyers of the first who add the second</th></tr></thead>
          <tbody>${pairs.slice(0, 15).map((p) => `<tr><td>${escape(name(p.product_a))}<small>${escape(p.product_a)}</small></td>
            <td>${escape(name(p.product_b))}<small>${escape(p.product_b)}</small></td><td class="num">${number(p.together)}</td>
            <td class="num"><b>${number(p.lift, 1)}×</b></td><td class="num">${pct(p.confidence_a_b)}</td></tr>`).join('')}</tbody></table></div>
        <p class="note">Most strong pairs are colour or pattern variants of the same item: customers buy sets. Showing variants together, or as bundles, follows that habit.</p></section>
      <section class="card span-7"><div class="card-head"><div><h2>Credits each month</h2>
        <p>Credits grouped by line size; cause is unverified</p></div></div><div class="chart" id="credits"></div></section>
      <section class="card span-5"><div class="card-head"><div><h2>Highest credit-to-sales ratios</h2><p>Products with at least 2,000 units sold, excluding large credit adjustments</p></div></div>
        <div class="table-wrap"><table><thead><tr><th>Product</th><th class="num">Sold</th><th class="num">Credited</th></tr></thead>
          <tbody>${returns.slice(0, 10).map((r) => `<tr><td>${escape(name(r.product_id))}<small>${escape(r.product_id)}</small></td>
            <td class="num">${number(r.sold_units)}</td><td class="num"><b>${pct(r.return_rate)}</b></td></tr>`).join('')}</tbody></table></div></section>
      <section class="card span-12"><div class="card-head"><div><h2>Credit threshold sensitivity</h2><p>Large means either threshold is met on a line. The credit reason is unknown; all credits remain included in the total.</p></div></div>
        <div class="table-wrap"><table><thead><tr><th>Units threshold</th><th>Value threshold</th><th class="num">Large credits</th><th class="num">All credits</th></tr></thead>
        <tbody>${records(data.credit_sensitivity).map((r) => `<tr><td>${number(r.units_threshold)}</td><td>${pounds(r.value_threshold)}</td><td class="num">${pounds(r.large_credits)}</td><td class="num">${pounds(r.total_credits)}</td></tr>`).join('')}</tbody></table></div></section>
    </div>`;

  plot(document.getElementById('pareto'), (c) => {
    const points = data.pareto.x.map((x, i) => [x, data.pareto.y[i]]);
    const cut = (share) => points.find((p) => p[1] >= share)?.[0] ?? 1;
    return {
      tooltip: tooltip(c, { trigger: 'axis', formatter: (p) => `Top ${pct(p[0].value[0])} of products<br><b>${pct(p[0].value[1], 1)}</b> of sales` }),
      grid: { left: 48, right: 16, top: 24, bottom: 40 },
      xAxis: axis(c, { type: 'value', min: 0, max: 1, name: 'Share of products (best first)', nameLocation: 'middle', nameGap: 26,
        axisLabel: { color: c.muted, formatter: (v) => pct(v) } }),
      yAxis: axis(c, { type: 'value', min: 0, max: 1, axisLabel: { color: c.muted, formatter: (v) => pct(v) }, axisLine: { show: false } }),
      series: [{
        type: 'line', symbol: 'none', data: points, lineStyle: { width: 2, color: c.series[0] },
        markArea: {
          silent: true, label: { color: c.ink2, fontSize: 12, position: 'insideTop' },
          data: [
            [{ name: 'A', xAxis: 0, itemStyle: { color: c.series[0], opacity: 0.1 } }, { xAxis: cut(0.8) }],
            [{ name: 'B', xAxis: cut(0.8), itemStyle: { color: c.series[0], opacity: 0.05 } }, { xAxis: cut(0.95) }],
            [{ name: 'C', xAxis: cut(0.95), itemStyle: { color: c.surface, opacity: 0 } }, { xAxis: 1 }],
          ],
        },
      }],
    };
  });

  const best = [...top].reverse();
  plot(document.getElementById('top'), (c) => ({
    tooltip: tooltip(c, { trigger: 'axis', axisPointer: { type: 'shadow' },
      formatter: (p) => { const r = best[p[0].dataIndex]; return `${escape(name(r.product_id))}<br><b>${pounds(r.sales_gbp)}</b> · ${number(r.units)} units · ${number(r.customers)} customers`; } }),
    grid: { left: 8, right: 56, top: 4, bottom: 8, containLabel: true },
    xAxis: { type: 'value', show: false },
    yAxis: axis(c, { type: 'category', data: best.map((r) => name(r.product_id)), axisLine: { show: false },
      axisLabel: { color: c.ink2, fontSize: 11, width: 220, overflow: 'truncate' } }),
    series: [{ type: 'bar', barMaxWidth: 10, data: best.map((r) => r.sales_gbp), itemStyle: { color: c.series[0], borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right', color: c.muted, fontSize: 11, formatter: (p) => compactPounds(p.value) } }],
  }));

  plot(document.getElementById('credits'), (c) => ({
    color: [c.series[0], c.series[1]],
    legend: legend(c),
    tooltip: tooltip(c, { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v) => pounds(v) }),
    grid: { left: 56, right: 12, top: 32, bottom: 28 },
    xAxis: axis(c, { type: 'category', data: credits.map((r) => monthLabel(r.month)), splitLine: { show: false } }),
    yAxis: axis(c, { type: 'value', axisLabel: { color: c.muted, formatter: axisPounds }, axisLine: { show: false } }),
    series: [
      { name: 'Other credits', type: 'bar', stack: 'credits', barMaxWidth: 22, data: credits.map((r) => r.other_credits),
        itemStyle: { borderColor: c.surface, borderWidth: 1 } },
      { name: 'Large credit adjustments', type: 'bar', stack: 'credits', barMaxWidth: 22, data: credits.map((r) => r.large_credits),
        itemStyle: { borderRadius: [4, 4, 0, 0], borderColor: c.surface, borderWidth: 1 } },
    ],
  }));
}
