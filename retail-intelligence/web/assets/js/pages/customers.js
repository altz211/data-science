// Customers: RFM segments, cohort retention, new vs returning, revenue concentration.

import { axis, legend, plot, tooltip } from '../charts.js';
import { load } from '../data.js';
import { axisNumber, escape, monthLabel, number, pct, pounds, records, tile } from '../format.js';

export async function render(container) {
  const data = await load('customers');
  const segments = records(data.segments);
  const champions = segments.find((s) => s.segment === 'Champions');
  const atRisk = segments.find((s) => s.segment === 'At risk');

  container.innerHTML = `
    <div class="tiles">
      ${tile('Identified customers', number(data.identified_customers), [{ label: `plus ${pct(data.guest_sales_share)} of sales with no customer ID` }])}
      ${tile('Top 20% of customers', pct(data.pareto.top20_share), [{ label: 'of identified sales' }])}
      ${tile('Champions', pct(champions.revenue_share), [{ label: `of revenue from ${number(champions.customers)} customers` }])}
      ${tile('At-risk revenue', pounds(atRisk.revenue), [{ label: `${number(atRisk.customers)} lapsed high-value customers` }])}
    </div>
    <div class="grid">
      <section class="card span-7"><div class="card-head"><div><h2>Segments: share of customers vs share of revenue</h2>
        <p>RFM scoring (recency, frequency, monetary) as of 10 Dec 2011</p></div></div><div class="chart" id="segments"></div></section>
      <section class="card span-5"><div class="card-head"><div><h2>RFM grid</h2>
        <p>Customers by recency score and frequency-and-spend score (5 = best)</p></div></div><div class="chart" id="grid"></div></section>
      <section class="card span-12"><div class="card-head"><div><h2>What each segment means</h2></div></div>
        <div class="table-wrap"><table><thead><tr><th>Segment</th><th class="num">Customers</th><th class="num">Revenue</th><th class="num">Share</th>
          <th class="num">Median days since last order</th><th class="num">Median orders</th><th class="num">Median spend</th><th>What to do</th></tr></thead>
          <tbody>${segments.map((s) => `<tr><td><b>${escape(s.segment)}</b></td><td class="num">${number(s.customers)}</td>
            <td class="num">${pounds(s.revenue)}</td><td class="num">${pct(s.revenue_share, 1)}</td><td class="num">${number(s.recency_days)}</td>
            <td class="num">${number(s.orders)}</td><td class="num">${pounds(s.spend)}</td><td>${escape(s.note)}</td></tr>`).join('')}</tbody></table></div></section>
      <section class="card span-12"><div class="card-head"><div><h2>Cohort retention</h2>
        <p>Share of each month's new customers who ordered again N months later. The Dec 2009 cohort includes customers who existed before the data starts.</p></div></div>
        <div class="chart tall" id="cohorts"></div></section>
      <section class="card span-7"><div class="card-head"><div><h2>New and returning customers each month</h2>
        <p>Returning = first purchase in an earlier month</p></div></div><div class="chart" id="monthly"></div></section>
      <section class="card span-5"><div class="card-head"><div><h2>Revenue concentration</h2>
        <p>Cumulative share of identified sales by customer rank</p></div></div><div class="chart" id="pareto"></div></section>
    </div>`;

  const ordered = [...segments].reverse();
  plot(document.getElementById('segments'), (c) => ({
    color: [c.series[0], c.series[1]],
    legend: legend(c),
    tooltip: tooltip(c, { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v) => pct(v, 1) }),
    grid: { left: 8, right: 16, top: 30, bottom: 8, containLabel: true },
    xAxis: axis(c, { type: 'value', axisLabel: { color: c.muted, formatter: (v) => pct(v) }, axisLine: { show: false } }),
    yAxis: axis(c, { type: 'category', data: ordered.map((s) => s.segment), axisLine: { show: false }, axisLabel: { color: c.ink2 } }),
    series: [
      { name: 'Share of customers', type: 'bar', barGap: '20%', barMaxWidth: 10, itemStyle: { borderRadius: [0, 4, 4, 0] },
        data: ordered.map((s) => s.customers / data.identified_customers) },
      { name: 'Share of revenue', type: 'bar', barMaxWidth: 10, itemStyle: { borderRadius: [0, 4, 4, 0] },
        data: ordered.map((s) => s.revenue_share) },
    ],
  }));

  const grid = records(data.rfm_grid);
  const maxGrid = Math.max(...grid.map((g) => g.customers));
  plot(document.getElementById('grid'), (c) => ({
    tooltip: tooltip(c, { formatter: (p) => `Recency ${p.value[0] + 1}, frequency & spend ${p.value[1] + 1}<br><b>${number(p.value[2])}</b> customers` }),
    grid: { left: 44, right: 8, top: 4, bottom: 56 },
    xAxis: axis(c, { type: 'category', data: ['1', '2', '3', '4', '5'], name: 'Recency score →', nameLocation: 'middle', nameGap: 24, axisLine: { show: false } }),
    yAxis: axis(c, { type: 'category', data: ['1', '2', '3', '4', '5'], name: 'Frequency & spend →', nameLocation: 'middle', nameGap: 28, axisLine: { show: false } }),
    visualMap: { show: false, min: 0, max: maxGrid, inRange: { color: c.sequential } },
    series: [{
      type: 'heatmap', data: grid.map((g) => [g.r - 1, g.fm - 1, g.customers]),
      label: { show: true, color: c.ink, fontSize: 11, formatter: (p) => number(p.value[2]),
        textBorderColor: c.surface, textBorderWidth: 2 },
      itemStyle: { borderColor: c.surface, borderWidth: 2, borderRadius: 3 },
    }],
  }));

  const cohorts = records(data.cohorts);
  const names = [...new Set(cohorts.map((r) => r.cohort))];
  const offsets = Math.max(...cohorts.map((r) => r.months_since));
  plot(document.getElementById('cohorts'), (c) => ({
    tooltip: tooltip(c, { formatter: (p) => `${monthLabel(names[p.value[1]])} cohort, month ${p.value[0]}<br><b>${pct(p.value[2], 1)}</b> active in this month` }),
    grid: { left: 70, right: 12, top: 8, bottom: 64 },
    xAxis: axis(c, { type: 'category', data: Array.from({ length: offsets + 1 }, (_, i) => String(i)), name: 'Months since first order',
      nameLocation: 'middle', nameGap: 24, axisLine: { show: false } }),
    yAxis: axis(c, { type: 'category', data: names.map(monthLabel), inverse: true, axisLine: { show: false } }),
    visualMap: { min: 0, max: 0.4, orient: 'horizontal', left: 'center', bottom: 0, itemWidth: 10, itemHeight: 140,
      text: ['40%+', '0%'], textStyle: { color: c.muted, fontSize: 11 }, inRange: { color: c.sequential } },
    series: [{ type: 'heatmap', data: cohorts.filter((r) => r.months_since > 0).map((r) => [r.months_since, names.indexOf(r.cohort), r.retention]),
      itemStyle: { borderColor: c.surface, borderWidth: 1.5, borderRadius: 2 } }],
  }));

  const monthly = records(data.monthly);
  plot(document.getElementById('monthly'), (c) => ({
    color: [c.series[0], c.series[2]],
    legend: legend(c),
    tooltip: tooltip(c, { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: number }),
    grid: { left: 48, right: 12, top: 32, bottom: 28 },
    xAxis: axis(c, { type: 'category', data: monthly.map((m) => monthLabel(m.month)), splitLine: { show: false } }),
    yAxis: axis(c, { type: 'value', axisLabel: { color: c.muted, formatter: axisNumber }, axisLine: { show: false } }),
    series: [
      { name: 'Returning', type: 'bar', stack: 'customers', barMaxWidth: 22, data: monthly.map((m) => m.returning),
        itemStyle: { borderColor: c.surface, borderWidth: 1 } },
      { name: 'New', type: 'bar', stack: 'customers', barMaxWidth: 22, data: monthly.map((m) => m.new_customers),
        itemStyle: { borderRadius: [4, 4, 0, 0], borderColor: c.surface, borderWidth: 1 } },
    ],
  }));

  plot(document.getElementById('pareto'), (c) => ({
    tooltip: tooltip(c, { trigger: 'axis', formatter: (p) => `Top ${pct(p[0].value[0])} of customers<br><b>${pct(p[0].value[1], 1)}</b> of sales` }),
    grid: { left: 48, right: 16, top: 12, bottom: 40 },
    xAxis: axis(c, { type: 'value', min: 0, max: 1, name: 'Share of customers (largest first)', nameLocation: 'middle', nameGap: 26,
      axisLabel: { color: c.muted, formatter: (v) => pct(v) } }),
    yAxis: axis(c, { type: 'value', min: 0, max: 1, axisLabel: { color: c.muted, formatter: (v) => pct(v) }, axisLine: { show: false } }),
    series: [{
      type: 'line', symbol: 'none', lineStyle: { width: 2, color: c.series[0] }, areaStyle: { color: c.series[0], opacity: 0.08 },
      data: data.pareto.x.map((x, i) => [x, data.pareto.y[i]]),
      markPoint: { symbol: 'circle', symbolSize: 9, itemStyle: { color: c.series[0], borderColor: c.surface, borderWidth: 2 },
        label: { show: true, position: 'right', color: c.ink, fontSize: 12, formatter: `Top 20% → ${pct(data.pareto.top20_share)}` },
        data: [{ coord: [0.2, data.pareto.top20_share] }] },
    }],
  }));
}
