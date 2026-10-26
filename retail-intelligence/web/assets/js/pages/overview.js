// Overview: KPIs, trends, markets, trading hours and top products for one month x market.

import { axis, legend, plot, tooltip } from '../charts.js';
import { load } from '../data.js';
import {
  axisNumber, axisPounds, change, compactPounds, dayLabel, downloadCsv, escape,
  monthLabel, number, pct, pounds, records, tile,
} from '../format.js';

const METRICS = {
  sales: { label: 'Sales', format: compactPounds, axis: axisPounds },
  orders: { label: 'Orders', format: number, axis: axisNumber },
  units: { label: 'Units', format: number, axis: axisNumber },
};
const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const PAGE_SIZE = 10;

// Filter state survives page switches.
const state = { period: null, market: 'All markets', metric: 'sales', search: '', page: 0 };
let data;

function index(source) {
  const kpis = new Map(records(source.kpis).map((r) => [`${r.period}|${r.market}`, r]));
  const group = (table, key) => {
    const map = new Map();
    for (const row of records(table)) {
      const k = key(row);
      if (!map.has(k)) map.set(k, []);
      map.get(k).push(row);
    }
    return map;
  };
  return {
    ...source,
    kpi: (period, market) => kpis.get(`${period}|${market}`),
    daily: group(source.daily, (r) => r.market),
    hours: group(source.hours, (r) => `${r.period}|${r.market}`),
    countries: group(source.countries, (r) => r.period),
    topProducts: group(source.products, (r) => `${r.period}|${r.market}`),
    months: source.periods.filter((p) => p.id !== 'all'),
  };
}

function shiftMonth(id, months) {
  const [year, month] = id.split('-').map(Number);
  const date = new Date(Date.UTC(year, month - 1 + months, 1));
  return date.toISOString().slice(0, 7);
}

/** Sum daily rows between two ISO dates (inclusive) for one market. */
function dailyTotals(market, start, end) {
  const totals = { sales: 0, orders: 0, units: 0 };
  for (const row of data.daily.get(market) || []) {
    if (row.day >= start && row.day <= end) {
      totals.sales += row.sales; totals.orders += row.orders; totals.units += row.units;
    }
  }
  return totals;
}

/**
 * Comparison figures for the selected month: previous month and same month last year.
 * A partial month (December 2011 stops on the 9th) is compared on the same elapsed days,
 * and customer counts aren't compared because they can't be rebuilt from daily totals.
 */
function comparisons(period, market) {
  if (period.id === 'all') return {};
  const result = {};
  for (const [key, offset] of [['previous', -1], ['lastYear', -12]]) {
    const id = shiftMonth(period.id, offset);
    if (!data.kpi(id, market)) continue;
    if (!period.partial) {
      result[key] = { ...data.kpi(id, market), label: monthLabel(id) };
    } else {
      const lastDay = period.end.slice(8);
      result[key] = { ...dailyTotals(market, `${id}-01`, `${id}-${lastDay}`), customers: null, new_customers: null,
        label: `${monthLabel(id)} 1–${Number(lastDay)}` };
    }
  }
  return result;
}

function controls() {
  const periods = [...data.periods].reverse();
  return `
    <div class="filters" role="group" aria-label="Filters">
      <label>Month<select id="period">${periods.map((p) =>
        `<option value="${p.id}" ${p.id === state.period ? 'selected' : ''}>${escape(p.label)}${p.partial ? ' (to ' + dayLabel(p.end) + ')' : ''}</option>`).join('')}</select></label>
      <label>Market<select id="market">${data.markets.map((m) =>
        `<option ${m === state.market ? 'selected' : ''}>${escape(m)}</option>`).join('')}</select></label>
      <div class="field">Chart measure<div class="segmented" id="metric">${Object.entries(METRICS).map(([key, m]) =>
        `<button type="button" data-metric="${key}" aria-pressed="${key === state.metric}">${m.label}</button>`).join('')}</div></div>
      <p class="context" id="context"></p>
    </div>`;
}

function layout() {
  return `
    ${controls()}
    <div class="tiles" id="tiles"></div>
    <div class="grid">
      <section class="card span-8"><div class="card-head"><div><h2 id="trend-title">Daily trend</h2><p id="trend-note"></p></div></div><div class="chart" id="trend"></div></section>
      <section class="card span-4"><div class="card-head"><div><h2>Sales by country</h2><p>Share of the selected month's sales</p></div></div><div class="chart" id="countries"></div></section>
      <section class="card span-12"><div class="card-head"><div><h2 id="months-title">Every month</h2><p>Click a bar to select that month. The last bar is a partial month.</p></div></div><div class="chart short" id="months"></div></section>
      <section class="card span-5"><div class="card-head"><div><h2>When orders arrive</h2><p>Orders by weekday and hour (UK time)</p></div></div><div class="chart" id="hours" style="height:420px"></div></section>
      <section class="card span-7">
        <div class="card-head"><div><h2>Top products</h2><p id="products-note"></p></div>
          <div class="filters" style="margin:0"><input type="search" id="search" placeholder="Search products" aria-label="Search top products" value="${escape(state.search)}"><button class="ghost" id="export" type="button">Export CSV</button></div></div>
        <div class="table-wrap"><table><thead><tr><th>#</th><th>Product</th><th class="num">Sales</th><th class="num">Units</th><th class="num">Orders</th><th class="num">Share of sales</th></tr></thead><tbody id="products"></tbody></table></div>
        <div class="table-foot"><span id="count"></span><div class="pager"><button type="button" id="prev" aria-label="Previous page">←</button><span id="page-no"></span><button type="button" id="next" aria-label="Next page">→</button></div></div>
      </section>
    </div>`;
}

function renderTiles(period) {
  const current = data.kpi(period.id, state.market);
  const compare = comparisons(period, state.market);
  const deltas = (key, value = (r) => r[key]) =>
    ['previous', 'lastYear'].map((which) => {
      const other = compare[which];
      if (!other || value(other) == null) return null;
      return { change: change(value(current), value(other)), label: `vs ${other.label}` };
    });
  const aov = (r) => (r.orders ? r.sales / r.orders : null);
  const none = period.id === 'all' ? [{ label: 'Whole history, no comparison' }] : null;
  document.getElementById('tiles').innerHTML = [
    tile('Sales', compactPounds(current.sales), none || deltas('sales')),
    tile('Orders', number(current.orders), none || deltas('orders')),
    tile('Average order value', pounds(aov(current)), none || deltas('aov', aov)),
    tile('Active customers', number(current.customers), none || (period.partial ? [{ label: 'Partial month, not compared' }] : deltas('customers'))),
    tile('New customers', number(current.new_customers),
      period.id === 'all' ? [{ label: 'Everyone is new over the whole history' }] : [{ label: `${pct(current.new_customers / current.customers)} of active customers` }]),
    tile('Units sold', number(current.units), none || deltas('units')),
  ].join('');

  const guest = current.sales ? current.guest_sales / current.sales : 0;
  document.getElementById('context').textContent =
    `${period.label}${period.partial ? ' (data ends ' + dayLabel(period.end) + ')' : ''} · ${state.market} · ` +
    `${current.trading_days} trading days · ${pct(guest)} of sales from customers without an ID`;
}

function renderTrend(period) {
  const metric = METRICS[state.metric];
  const element = document.getElementById('trend');
  if (period.id === 'all') {
    // Whole history: compare the two complete Dec-Nov trading years month by month.
    const years = [['Dec 2009 – Nov 2010', '2009-12'], ['Dec 2010 – Nov 2011', '2010-12']];
    const labels = Array.from({ length: 12 }, (_, i) => monthLabel(shiftMonth('2009-12', i)).split(' ')[0]);
    document.getElementById('trend-title').textContent = `${metric.label}: year on year`;
    document.getElementById('trend-note').textContent = 'Two complete trading years, December to November';
    plot(element, (c) => ({
      color: [c.neutral, c.series[0]],
      legend: legend(c),
      tooltip: tooltip(c, { trigger: 'axis', valueFormatter: metric.format }),
      grid: { left: 56, right: 12, top: 36, bottom: 28 },
      xAxis: axis(c, { type: 'category', data: labels, splitLine: { show: false } }),
      yAxis: axis(c, { type: 'value', axisLabel: { color: c.muted, formatter: metric.axis }, axisLine: { show: false } }),
      series: years.map(([name, start]) => ({
        name, type: 'line', symbolSize: 7, lineStyle: { width: 2 },
        data: labels.map((_, i) => data.kpi(shiftMonth(start, i), state.market)?.[state.metric] ?? 0),
      })),
    }));
    return;
  }

  const compare = comparisons(period, state.market);
  const reference = compare.lastYear || compare.previous;
  const referenceId = compare.lastYear ? shiftMonth(period.id, -12) : shiftMonth(period.id, -1);
  const days = (id, end) => (data.daily.get(state.market) || []).filter((r) => r.day.startsWith(id) && r.day <= end);
  const currentRows = days(period.id, period.end);
  const length = Number(new Date(Date.UTC(+period.id.slice(0, 4), +period.id.slice(5), 0)).getUTCDate());
  const byDay = (rows) => {
    const values = Array(length).fill(0);
    rows.forEach((r) => { values[Number(r.day.slice(8)) - 1] = r[state.metric]; });
    return values;
  };
  const lastDay = Number(period.end.slice(8));
  const currentValues = byDay(currentRows).map((v, i) => (i < lastDay ? v : null));
  const referenceValues = reference ? byDay(days(referenceId, `${referenceId}-31`)) : null;

  document.getElementById('trend-title').textContent = `Daily ${metric.label.toLowerCase()}`;
  document.getElementById('trend-note').textContent = reference
    ? `${period.label} against ${monthLabel(referenceId)}, aligned by day of month. Gaps are days without trading (mostly Saturdays).`
    : `${period.label}. No earlier month to compare.`;
  plot(element, (c) => ({
    legend: legend(c),
    tooltip: tooltip(c, { trigger: 'axis', valueFormatter: metric.format }),
    grid: { left: 56, right: 12, top: 36, bottom: 28 },
    xAxis: axis(c, { type: 'category', data: Array.from({ length }, (_, i) => String(i + 1)), splitLine: { show: false } }),
    yAxis: axis(c, { type: 'value', axisLabel: { color: c.muted, formatter: metric.axis }, axisLine: { show: false } }),
    series: [
      { name: period.label, type: 'bar', data: currentValues, barMaxWidth: 18, itemStyle: { color: c.series[0], borderRadius: [4, 4, 0, 0] } },
      ...(referenceValues ? [{ name: monthLabel(referenceId), type: 'line', data: referenceValues, symbol: 'none',
        lineStyle: { width: 2, color: c.ink2 }, itemStyle: { color: c.ink2 }, z: 3 }] : []),
    ],
  }));
}

function renderMonths(period) {
  const metric = METRICS[state.metric];
  document.getElementById('months-title').textContent = `${metric.label} every month · ${state.market}`;
  const chart = plot(document.getElementById('months'), (c) => ({
    tooltip: tooltip(c, { trigger: 'axis', valueFormatter: metric.format }),
    grid: { left: 56, right: 12, top: 12, bottom: 28 },
    xAxis: axis(c, { type: 'category', data: data.months.map((m) => m.label), splitLine: { show: false } }),
    yAxis: axis(c, { type: 'value', axisLabel: { color: c.muted, formatter: metric.axis }, axisLine: { show: false } }),
    series: [{
      type: 'bar', name: metric.label, barMaxWidth: 26, cursor: 'pointer',
      data: data.months.map((m) => ({
        value: data.kpi(m.id, state.market)?.[state.metric] ?? 0,
        itemStyle: {
          color: period.id === 'all' || m.id === period.id ? c.series[0] : c.neutral,
          opacity: m.partial ? 0.55 : 1,
          borderRadius: [4, 4, 0, 0],
        },
      })),
    }],
  }));
  chart?.on('click', (event) => {
    state.period = data.months[event.dataIndex].id;
    state.page = 0;
    document.getElementById('period').value = state.period;
    update();
  });
}

function renderCountries(period) {
  const rows = data.countries.get(period.id) || [];
  const total = rows.reduce((sum, r) => sum + r.sales, 0);
  const top = rows.slice(0, 8);
  const rest = rows.slice(8).reduce((sum, r) => sum + r.sales, 0);
  if (rest > 0) top.push({ country: `${rows.length - 8} other countries`, sales: rest });
  const ordered = top.reverse();
  const chart = plot(document.getElementById('countries'), (c) => ({
    tooltip: tooltip(c, { trigger: 'item', formatter: (p) => `${escape(p.name)}<br><b>${compactPounds(p.value)}</b> · ${pct(p.value / total, 1)}` }),
    grid: { left: 8, right: 48, top: 4, bottom: 4, containLabel: true },
    xAxis: { type: 'value', show: false, max: (v) => v.max * 1.05 },
    yAxis: axis(c, { type: 'category', data: ordered.map((r) => r.country), axisLine: { show: false },
      axisLabel: { color: c.ink2, fontSize: 12, width: 110, overflow: 'truncate' } }),
    series: [{
      type: 'bar', barMaxWidth: 14, cursor: 'pointer',
      label: { show: true, position: 'right', color: c.ink2, fontSize: 11, formatter: (p) => pct(p.value / total, 1) },
      data: ordered.map((r) => ({
        value: r.sales,
        itemStyle: {
          color: state.market === 'All markets' || r.country === state.market ? c.series[0] : c.neutral,
          borderRadius: [0, 4, 4, 0],
        },
      })),
    }],
  }));
  chart?.on('click', (event) => {
    const country = ordered[event.dataIndex].country;
    if (!data.markets.includes(country)) return;
    state.market = state.market === country ? 'All markets' : country;
    document.getElementById('market').value = state.market;
    state.page = 0;
    update();
  });
}

function renderHours(period) {
  const rows = data.hours.get(`${period.id}|${state.market}`) || [];
  const hours = Array.from({ length: 15 }, (_, i) => i + 6);
  const cells = rows.filter((r) => r.hour >= 6 && r.hour <= 20).map((r) => [r.hour - 6, r.weekday - 1, r.orders]);
  const max = Math.max(1, ...cells.map((cell) => cell[2]));
  plot(document.getElementById('hours'), (c) => ({
    tooltip: tooltip(c, { formatter: (p) => `${WEEKDAYS[p.value[1]]} ${hours[p.value[0]]}:00<br><b>${number(p.value[2])}</b> orders` }),
    grid: { left: 40, right: 8, top: 4, bottom: 52 },
    xAxis: axis(c, { type: 'category', data: hours.map((h) => `${h}`), splitArea: { show: false }, axisLine: { show: false } }),
    yAxis: axis(c, { type: 'category', data: WEEKDAYS, inverse: true, axisLine: { show: false } }),
    visualMap: {
      min: 0, max, calculable: false, orient: 'horizontal', left: 'center', bottom: 0, itemWidth: 10, itemHeight: 120,
      text: [number(max), '0'], textStyle: { color: c.muted, fontSize: 11 }, inRange: { color: c.sequential },
    },
    series: [{ type: 'heatmap', data: cells, itemStyle: { borderColor: c.surface, borderWidth: 2, borderRadius: 3 },
      emphasis: { itemStyle: { borderColor: c.ink, borderWidth: 1 } } }],
  }));
}

function productRows(period) {
  const rows = data.topProducts.get(`${period.id}|${state.market}`) || [];
  const query = state.search.trim().toLowerCase();
  return rows
    .map((row, i) => ({ ...row, rank: i + 1, name: data.names[row.product_id] || row.product_id }))
    .filter((row) => !query || `${row.name} ${row.product_id}`.toLowerCase().includes(query));
}

function renderProducts(period) {
  const total = data.kpi(period.id, state.market).sales;
  const rows = productRows(period);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  state.page = Math.min(state.page, pages - 1);
  const shown = rows.slice(state.page * PAGE_SIZE, (state.page + 1) * PAGE_SIZE);
  const best = Math.max(...rows.map((r) => r.sales), 1);
  document.getElementById('products').innerHTML = shown.map((r) => `
    <tr><td>${r.rank}</td><td>${escape(r.name)}<small>${escape(r.product_id)}</small></td>
      <td class="num">${pounds(r.sales)}</td><td class="num">${number(r.units)}</td><td class="num">${number(r.orders)}</td>
      <td class="num"><div class="bar-cell"><i><b style="width:${(r.sales / best) * 100}%"></b></i>${pct(r.sales / total, 1)}</div></td></tr>`).join('')
    || '<tr><td colspan="6">No products match.</td></tr>';
  document.getElementById('products-note').textContent = `Top 50 by sales · ${period.label} · ${state.market}`;
  document.getElementById('count').textContent = rows.length
    ? `${state.page * PAGE_SIZE + 1}–${Math.min(rows.length, (state.page + 1) * PAGE_SIZE)} of ${rows.length}` : '0 products';
  document.getElementById('page-no').textContent = `${state.page + 1} / ${pages}`;
  document.getElementById('prev').disabled = state.page === 0;
  document.getElementById('next').disabled = state.page >= pages - 1;
}

function update() {
  const period = data.periods.find((p) => p.id === state.period);
  document.querySelectorAll('#metric button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.metric === state.metric)));
  renderTiles(period);
  renderTrend(period);
  renderCountries(period);
  renderMonths(period);
  renderHours(period);
  renderProducts(period);
}

function bind() {
  const on = (id, event, handler) => document.getElementById(id).addEventListener(event, handler);
  on('period', 'change', (e) => { state.period = e.target.value; state.page = 0; update(); });
  on('market', 'change', (e) => { state.market = e.target.value; state.page = 0; update(); });
  on('metric', 'click', (e) => {
    const button = e.target.closest('[data-metric]');
    if (!button) return;
    state.metric = button.dataset.metric;
    update();
  });
  on('search', 'input', (e) => { state.search = e.target.value; state.page = 0; renderProducts(data.periods.find((p) => p.id === state.period)); });
  on('prev', 'click', () => { state.page -= 1; renderProducts(data.periods.find((p) => p.id === state.period)); });
  on('next', 'click', () => { state.page += 1; renderProducts(data.periods.find((p) => p.id === state.period)); });
  on('export', 'click', () => {
    const period = data.periods.find((p) => p.id === state.period);
    downloadCsv(`top-products-${state.period}-${state.market.replaceAll(' ', '-').toLowerCase()}.csv`,
      ['rank', 'product_id', 'product', 'sales_gbp', 'units', 'orders'],
      productRows(period).map((r) => [r.rank, r.product_id, r.name, r.sales, r.units, r.orders]));
  });
}

export async function render(container) {
  data ??= index(await load('overview'));
  state.period ??= data.default_period;
  container.innerHTML = layout();
  bind();
  update();
}
