// Sales forecast: backtest scores, error by horizon, and a per-product view.

import { axis, legend, plot, tooltip } from '../charts.js';
import { load } from '../data.js';
import { axisNumber, dayLabel, escape, number, pct, records, tile } from '../format.js';

let selectedProduct = null;

export async function render(container) {
  const data = await load('forecast');
  const metrics = records(data.metrics);
  const holdout = Object.fromEntries(metrics.filter((m) => m.window === 'holdout').map((m) => [m.model, m]));
  const models = [...new Set(metrics.map((m) => m.model))];
  const chosen = holdout[data.selected];
  const baseline = holdout['4-week average'];
  selectedProduct ??= data.products[0].id;

  container.innerHTML = `
    <div class="tiles">
      ${tile('Chosen model', escape(data.selected), [{ label: 'lowest error on the tuning weeks' }])}
      ${tile('Holdout error (WAPE)', pct(chosen.wape), [{ label: `4-week average: ${pct(baseline.wape)}` }])}
      ${tile('Error reduction', pct(1 - chosen.wape / baseline.wape), [{ label: 'vs the 4-week average rule of thumb' }])}
      ${tile('80% interval coverage', pct(data.interval.coverage), [{ label: `of ${number(data.interval.holdout_forecasts)} holdout forecasts` }])}
    </div>
    <div class="grid">
      <section class="card span-12">
        <div class="card-head"><div><h2>One product, week by week</h2><p id="product-note"></p></div>
          <label class="field">Product<select id="product">${data.products.map((p) =>
            `<option value="${escape(p.id)}" ${p.id === selectedProduct ? 'selected' : ''}>${escape(p.name)}</option>`).join('')}</select></label></div>
        <div class="chart tall" id="product-chart"></div>
        <div class="table-wrap"><table id="future"></table></div>
      </section>
      <section class="card span-7"><div class="card-head"><div><h2>Weighted error by model</h2>
        <p>WAPE = total absolute error ÷ total units. Lower is better. Tuning picks the model; holdout is untouched until the end.</p></div></div>
        <div class="chart" id="models"></div></section>
      <section class="card span-5"><div class="card-head"><div><h2>Error by weeks ahead</h2><p>Holdout only</p></div></div>
        <div class="chart" id="horizon"></div></section>
      <section class="card span-12"><div class="card-head"><div><h2>Full results</h2>
        <p>Bias below zero means forecasts were too low. Forecast issue dates: tuning ${data.tuning_issue_dates[0]} to ${data.tuning_issue_dates.at(-1)}; holdout ${data.holdout_issue_dates[0]} to ${data.holdout_issue_dates.at(-1)}, each forecasting 1–4 weeks ahead.</p></div></div>
        <div class="table-wrap"><table><thead><tr><th>Model</th><th class="num">Tuning WAPE</th><th class="num">Holdout WAPE</th>
          <th class="num">Holdout MAE (units)</th><th class="num">Holdout bias</th></tr></thead><tbody>${models.map((model) => {
            const tune = metrics.find((m) => m.model === model && m.window === 'tuning');
            const test = holdout[model];
            return `<tr class="${model === data.selected ? 'highlight' : ''}"><td>${escape(model)} ${model === data.selected ? '<span class="pill win">chosen</span>' : ''}</td>
              <td class="num">${pct(tune.wape, 1)}</td><td class="num">${pct(test.wape, 1)}</td><td class="num">${number(test.mae, 1)}</td>
              <td class="num">${(test.bias >= 0 ? '+' : '') + pct(test.bias, 1)}</td></tr>`;
          }).join('')}</tbody></table></div>
        <p class="note">Gradient boosting uses lags, rolling means, volatility, price, the same week last year and week of year, trained on sales relative to each product's recent level so one model learns from all products. The neural network is a two-layer MLP on the same features. Nominal 80% ranges come from separate quantile models. Crossing endpoints are sorted consistently in evaluation and deployment; a point forecast can fall outside this range. These forecast observed sales, without stockout or inventory data.</p>
      </section>
    </div>`;

  plot(document.getElementById('models'), (c) => ({
    color: [c.neutral, c.series[0]],
    legend: legend(c),
    tooltip: tooltip(c, { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v) => pct(v, 1) }),
    grid: { left: 8, right: 16, top: 32, bottom: 8, containLabel: true },
    xAxis: axis(c, { type: 'value', axisLabel: { color: c.muted, formatter: (v) => pct(v) }, axisLine: { show: false } }),
    yAxis: axis(c, { type: 'category', data: [...models].reverse(), axisLine: { show: false },
      axisLabel: { color: c.ink2, formatter: (v) => (v === data.selected ? `{b|${v}}` : v), rich: { b: { fontWeight: 700, color: c.ink } } } }),
    series: ['tuning', 'holdout'].map((window) => ({
      name: window === 'tuning' ? 'Tuning weeks' : 'Holdout weeks', type: 'bar', barMaxWidth: 10, barGap: '20%',
      itemStyle: { borderRadius: [0, 4, 4, 0] },
      data: [...models].reverse().map((model) => metrics.find((m) => m.model === model && m.window === window).wape),
    })),
  }));

  const horizon = records(data.by_horizon);
  const horizonModels = [...new Set(horizon.map((h) => h.model))];
  plot(document.getElementById('horizon'), (c) => ({
    color: c.series,
    legend: legend(c),
    tooltip: tooltip(c, { trigger: 'axis', valueFormatter: (v) => pct(v, 1) }),
    grid: { left: 48, right: 16, top: 40, bottom: 36 },
    xAxis: axis(c, { type: 'category', data: ['1', '2', '3', '4'], name: 'Weeks ahead', nameLocation: 'middle', nameGap: 24, splitLine: { show: false } }),
    yAxis: axis(c, { type: 'value', min: 0, axisLabel: { color: c.muted, formatter: (v) => pct(v) }, axisLine: { show: false } }),
    series: horizonModels.map((model) => ({
      name: model, type: 'line', symbolSize: 8, lineStyle: { width: 2 },
      data: [1, 2, 3, 4].map((h) => horizon.find((r) => r.model === model && r.horizon === h).wape),
    })),
  }));

  const drawProduct = () => {
    const product = data.products.find((p) => p.id === selectedProduct);
    const firstBacktest = product.backtest[0][0];
    document.getElementById('product-note').textContent =
      `Actual weekly units, one-week-ahead forecasts during the backtest (from ${dayLabel(firstBacktest)}), and the next four weeks after ${dayLabel(data.last_complete_week)}.`;

    const band = [...product.backtest.map((b) => [b[0], b[4], b[5]]), ...product.future.map((f) => [f[0], f[2], f[3]])];
    plot(document.getElementById('product-chart'), (c) => ({
      legend: legend(c, { data: ['Actual units', 'Forecast', '4-week average', '80% interval', 'Next 4 weeks'] }),
      tooltip: tooltip(c, {
        trigger: 'axis',
        formatter: (points) => {
          const date = points[0].axisValue;
          const lines = points.filter((p) => !p.seriesName.startsWith('band'))
            .map((p) => `${p.marker}${escape(p.seriesName)}: <b>${number(p.value[1])}</b>`);
          const range = band.find((b) => b[0] === date);
          if (range) lines.push(`80% interval: ${number(range[1])} – ${number(range[2])}`);
          return `${dayLabel(date)}<br>${lines.join('<br>')}`;
        },
      }),
      grid: { left: 52, right: 16, top: 40, bottom: 28 },
      xAxis: axis(c, { type: 'category', boundaryGap: false, splitLine: { show: false },
        data: [...product.history.map((h) => h[0]), ...product.future.map((f) => f[0])], axisLabel: { color: c.muted, formatter: dayLabel } }),
      yAxis: axis(c, { type: 'value', min: 0, axisLabel: { color: c.muted, formatter: axisNumber }, axisLine: { show: false } }),
      series: [
        { name: 'band-low', type: 'line', stack: 'band', symbol: 'none', lineStyle: { opacity: 0 }, data: band.map((b) => [b[0], b[1]]), silent: true },
        { name: 'band-width', type: 'line', stack: 'band', symbol: 'none', lineStyle: { opacity: 0 }, silent: true,
          areaStyle: { color: c.series[0], opacity: 0.14 }, data: band.map((b) => [b[0], b[2] - b[1]]) },
        { name: '80% interval', type: 'line', data: [], itemStyle: { color: c.series[0], opacity: 0.3 }, lineStyle: { width: 8, opacity: 0.3 } },
        { name: 'Actual units', type: 'line', symbol: 'none', lineStyle: { width: 2, color: c.ink }, itemStyle: { color: c.ink },
          data: product.history.map((h) => [h[0], h[1]]) },
        { name: '4-week average', type: 'line', symbol: 'none', lineStyle: { width: 1.5, color: c.series[1] }, itemStyle: { color: c.series[1] },
          data: product.backtest.map((b) => [b[0], b[3]]) },
        { name: 'Forecast', type: 'line', symbolSize: 6, lineStyle: { width: 2, color: c.series[0] }, itemStyle: { color: c.series[0] },
          data: product.backtest.map((b) => [b[0], b[2]]) },
        { name: 'Next 4 weeks', type: 'line', symbolSize: 7, lineStyle: { width: 2, type: 'dashed', color: c.series[0] },
          itemStyle: { color: c.series[0] }, data: product.future.map((f) => [f[0], f[1]]) },
      ],
    }));

    document.getElementById('future').innerHTML = `<thead><tr><th>Week starting</th>${product.future.map((f) => `<th class="num">${dayLabel(f[0])}</th>`).join('')}</tr></thead>
      <tbody><tr><td>Forecast units</td>${product.future.map((f) => `<td class="num"><b>${number(f[1])}</b></td>`).join('')}</tr>
      <tr><td>80% range</td>${product.future.map((f) => `<td class="num">${number(f[2])} – ${number(f[3])}</td>`).join('')}</tr></tbody>`;
  };

  document.getElementById('product').addEventListener('change', (event) => {
    selectedProduct = event.target.value;
    drawProduct();
  });
  drawProduct();
}
