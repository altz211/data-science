import {
  initModels
} from './models.js';
const $ = id => document.getElementById(id);
const number = (value, digits = 0) => Number(value).toLocaleString('en-GB', {
  maximumFractionDigits: digits
});
const money = value => '£' + Number(value).toLocaleString('en-GB', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2
});
const compact = value => value >= 1e6 ? '£' + number(value / 1e6, 2) + 'M' : '£' + number(value, 0);
const escape = value => String(value).replace(/[&<>"']/g, char => ({
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;'
} [char]));
let data;
let metric = 'sales_gbp';
let page = 0;
let filteredProducts = [];
const pageSize = 6;
const titles = {
  overview: ['Retail performance', 'Sales, customer activity and product performance at a glance.', 'KPI overview'],
  forecast: ['Sales forecasts', 'Inspect model predictions against an untouched historical holdout.', 'Sales forecasts'],
  models: ['Model performance', 'Validation, baselines and the limits of the first experiments.', 'Model performance'],
  source: ['Data & definitions', 'Trace the reporting measures back to actual retail transactions.', 'Data & definitions']
};

function currentSlice() {
  return data.slices[$('period').value][$('market').value];
}

function periodInfo() {
  return data.periods.find(p => p.id === $('period').value);
}

function sparkline(values) {
  const min = Math.min(...values),
    span = Math.max(...values) - min || 1;
  return `<svg class="sparkline" viewBox="0 0 70 28" aria-hidden="true"><polyline points="${values.map((v,i)=>`${i/Math.max(1,values.length-1)*68},${25-(v-min)/span*22}`).join(' ')}" fill="none" stroke="#8aa8eb" stroke-width="1.5"/></svg>`;
}

function kpi(label, key, value, icon, values) {
  const previous = currentSlice().previous?.[key];
  const change = previous ? (currentSlice().metrics[key] / previous - 1) * 100 : null;
  const delta = change === null ? '—' : `${change >= 0 ? '↗' : '↘'} ${number(Math.abs(change),1)}%`;
  return `<article class="kpi-card"><div class="kpi-top"><span>${label}</span><span class="kpi-icon" aria-hidden="true">${icon}</span></div><div class="kpi-value">${value}</div><div class="kpi-bottom"><span class="delta ${change === null ? 'neutral' : change < 0 ? 'negative' : ''}">${delta}</span><span class="delta-label">${change === null ? 'No prior comparison' : 'vs prior period'}</span>${sparkline(values)}</div></article>`;
}

function renderTable() {
  const slice = currentSlice();
  const query = $('search').value.toLowerCase();
  filteredProducts = slice.products.filter(p => (p.description + ' ' + p.product_id).toLowerCase().includes(query));
  const pages = Math.max(1, Math.ceil(filteredProducts.length / pageSize));
  page = Math.min(page, pages - 1);
  $('products').innerHTML = filteredProducts.slice(page * pageSize, (page + 1) * pageSize).map(p => {
    const share = slice.metrics.sales_gbp ? p.sales_gbp / slice.metrics.sales_gbp * 100 : 0;
    return `<tr><td><span class="product-name" title="${escape(p.description)}">${escape(p.description)}</span><small>${escape(p.product_id)}</small></td><td>${money(p.sales_gbp)}</td><td>${number(p.units)}</td><td>${number(p.orders)}</td><td><div class="share-cell"><i><b style="width:${Math.min(100, share)}%"></b></i>${number(share,1)}%</div></td></tr>`;
  }).join('') || '<tr><td colspan="5">No products match this search.</td></tr>';
  $('table-count').textContent = `${filteredProducts.length ? page*pageSize+1 : 0}–${Math.min((page+1)*pageSize,filteredProducts.length)} of ${filteredProducts.length} · top 100 by sales`;
  $('page-number').textContent = `${page+1} / ${pages}`;
  $('previous-page').disabled = page === 0;
  $('next-page').disabled = page === pages - 1;
}

function trendRows() {
  if ($('period').value !== 'all') return {
    current: currentSlice().daily,
    previous: currentSlice().prior_daily
  };
  return {
    current: data.periods.filter(p => p.id !== 'all').map(p => ({
      day: p.id,
      ...data.slices[p.id][$('market').value].metrics
    })),
    previous: []
  };
}

function renderTrend() {
  const rows = trendRows();
  const values = rows.current.map(r => r[metric]);
  const previous = rows.previous.map(r => r[metric]);
  const max = Math.max(1, ...values, ...previous) * 1.15;
  const width = 800,
    height = 245,
    left = 52,
    right = 13,
    bottom = 30,
    top = 15;
  const count = Math.max(values.length, previous.length);
  const x = i => left + i / Math.max(1, count - 1) * (width - left - right);
  const y = value => height - bottom - value / max * (height - bottom - top);
  const grid = Array.from({
    length: 5
  }, (_, i) => {
    const v = max * i / 4;
    const label = metric === 'sales_gbp' ? (v >= 1000 ? number(v / 1000, 0) + 'k' : number(v)) : number(v);
    return `<line x1="${left}" x2="${width-right}" y1="${y(v)}" y2="${y(v)}" stroke="#eef1f6"/><text x="${left-10}" y="${y(v)+3}" text-anchor="end">${label}</text>`;
  }).join('');
  const tickIndices = [...new Set([0, Math.floor((values.length - 1) / 4), Math.floor((values.length - 1) / 2), Math.floor((values.length - 1) * 3 / 4), values.length - 1])];
  const ticks = tickIndices.map(i => `<text x="${x(i)}" y="${height-7}" text-anchor="middle">${rows.current[i].day.length===7?rows.current[i].day:rows.current[i].day.slice(8)}</text>`).join('');
  const points = values.map((v, i) => `${x(i)},${y(v)}`).join(' ');
  const fill = `${x(0)},${height-bottom} ${points} ${x(values.length-1)},${height-bottom}`;
  const prior = previous.length ? `<polyline points="${previous.map((v,i)=>`${x(i)},${y(v)}`).join(' ')}" fill="none" stroke="#b8c8e6" stroke-width="2" stroke-dasharray="5 4"/>` : '';
  const dots = values.map((v, i) => `<circle data-point="${i}" tabindex="0" role="img" aria-label="${escape(rows.current[i].day)}: ${number(v,2)} ${metric==='sales_gbp'?'GBP':metric}" cx="${x(i)}" cy="${y(v)}" r="3" fill="#386bdb" opacity=".01"/>`).join('');
  $('trend').innerHTML = `<svg viewBox="0 0 ${width} ${height}" aria-label="${metric==='sales_gbp'?'Sales in GBP':metric} by ${$('period').value==='all'?'month':'day of month'}" role="group">${grid}<polygon points="${fill}" fill="#f3f6ff"/>${prior}<polyline points="${points}" fill="none" stroke="#4d7ee4" stroke-width="2.5"/>${ticks}${dots}</svg>`;
  $('chart-unit').textContent = metric === 'sales_gbp' ? 'GBP' : metric === 'orders' ? 'Purchase invoices' : 'Units sold';
  $('chart-period').textContent = $('period').value === 'all' ? 'Monthly sales across the observed history' : `${periodInfo().label} · daily totals`;
  $('chart-detail').textContent = 'Hover or focus a point to inspect values. Dashed line: previous month, aligned by day number.';

  function inspect(i) {
    const current = rows.current[i],
      prior = rows.previous[i];
    if (!current) {
      $('chart-detail').textContent = `${prior.day}: ${metric==='sales_gbp'?money(prior[metric]):number(prior[metric])} · no matching day in selected period`;
      return;
    }
    $('chart-detail').textContent = `${current.day}: ${metric==='sales_gbp'?money(current[metric]):number(current[metric])}${prior?` · ${prior.day}: ${metric==='sales_gbp'?money(prior[metric]):number(prior[metric])}`:''}`;
  }
  $('trend').querySelectorAll('[data-point]').forEach(point => point.addEventListener('focus', () => inspect(Number(point.dataset.point))));
  const svg = $('trend').querySelector('svg');
  svg.addEventListener('pointermove', e => {
    const bounds = svg.getBoundingClientRect();
    const position = (e.clientX - bounds.left) / bounds.width * width;
    inspect(Math.max(0, Math.min(count - 1, Math.round((position - left) / (width - left - right) * (count - 1)))));
  });
}

function render() {
  const slice = currentSlice(),
    m = slice.metrics,
    info = periodInfo();
  $('comparison').textContent = info.comparison ? `Compared with ${info.comparison}${info.label.includes('partial')?' · matched elapsed days':''}` : 'Full observation window · no prior-period comparison';
  $('metrics').innerHTML = [
    kpi('Merchandise sales', 'sales_gbp', compact(m.sales_gbp), '£', slice.daily.map(r => r.sales_gbp)),
    kpi('Orders', 'orders', number(m.orders), '▤', slice.daily.map(r => r.orders)),
    kpi('Average order value', 'aov', money(m.aov), '↗', slice.daily.map(r => r.orders ? r.sales_gbp / r.orders : 0)),
    kpi('Active customers', 'customers', number(m.customers), '♙', slice.daily.map(r => r.customers || 0))
  ].join('');
  const concentration = m.sales_gbp ? slice.products.slice(0, 10).reduce((total, p) => total + p.sales_gbp, 0) / m.sales_gbp * 100 : 0;
  $('secondary').innerHTML = [
    ['Units sold', number(m.units), 'Merchandise units'],
    ['Active products', number(m.products), 'Distinct purchased SKUs'],
    ['Returning customers', $('period').value === 'all' ? '—' : number(m.returning_customers), 'Identified customers'],
    ['Top 10 sales share', number(concentration, 1) + '%', 'Product concentration']
  ].map(([label, value, note]) => `<article class="secondary-card"><span>${label}</span><strong>${value}</strong><small>${note}</small></article>`).join('');
  const mix = slice.markets.slice(0, 5);
  if (slice.markets.length > 5) mix.push({
    country: 'Other markets',
    sales_gbp: slice.markets.slice(5).reduce((total, r) => total + r.sales_gbp, 0)
  });
  $('market-bars').innerHTML = mix.map(r => `<button class="market-row" ${data.markets.includes(r.country)?`data-market="${escape(r.country)}"`:'disabled'} aria-label="${escape(r.country)}: ${money(r.sales_gbp)}"><div class="market-label"><span>${escape(r.country)}</span><strong>${number(m.sales_gbp?r.sales_gbp/m.sales_gbp*100:0,1)}%</strong></div><div class="bar-track"><div class="bar-fill" style="width:${m.sales_gbp?r.sales_gbp/m.sales_gbp*100:0}%"></div></div></button>`).join('');
  $('market-bars').querySelectorAll('[data-market]').forEach(button => button.addEventListener('click', () => {
    $('market').value = button.dataset.market;
    page = 0;
    render();
  }));
  const share = m.returning_share ?? 0;
  $('customer-mix').innerHTML = `<div class="mix-number"><strong>${m.returning_share===null?'—':number(share,1)+'%'}</strong><span>returning</span></div><div class="mix-track"><i style="width:${share}%"></i></div><div class="mix-labels"><span>Returning · ${number(m.returning_customers)}</span><span>First observed · ${number(m.customers-m.returning_customers)}</span></div>`;
  if ($('period').value === 'all') $('customer-mix').innerHTML = '<p class="note">Choose a reporting month to inspect returning customers. No purchase history exists before the start of this dataset.</p>';
  const days = Array.from({
    length: 7
  }, () => ({
    sales: 0,
    count: 0
  }));
  slice.daily.forEach(r => {
    const weekday = (new Date(r.day + 'T12:00:00Z').getUTCDay() + 6) % 7;
    days[weekday].sales += r.sales_gbp;
    days[weekday].count++;
  });
  const averages = days.map(r => r.count ? r.sales / r.count : 0),
    max = Math.max(1, ...averages);
  $('weekday-bars').innerHTML = `<div class="weekdays">${['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map((name,i)=>`<div class="weekday ${averages[i]===max?'peak':''}" title="${name}: ${money(averages[i])}"><i style="height:${Math.max(1,averages[i]/max*66)}px"></i>${name}</div>`).join('')}</div>`;
  $('scope-note').textContent = `${info.start} to ${info.end} · ${$('market').value} · Positive merchandise purchases only; credits and fee codes excluded. GBP. First-observed customer activity is limited to the available history.`;
  renderTrend();
  renderTable();
}

async function init() {
  const response = await fetch('assets/kpis.json');
  if (!response.ok) throw new Error('KPI results could not be loaded.');
  data = await response.json();
  $('period').innerHTML = [...data.periods].reverse().map(p => `<option value="${p.id}">${escape(p.label)}</option>`).join('');
  $('period').value = data.default_period;
  $('market').innerHTML = data.markets.map(m => `<option>${escape(m)}</option>`).join('');
  render();
  await initModels();
}
$('period').addEventListener('change', () => {
  page = 0;
  render();
});
$('market').addEventListener('change', () => {
  page = 0;
  render();
});
$('reset').addEventListener('click', () => {
  $('period').value = data.default_period;
  $('market').value = 'All markets';
  $('search').value = '';
  page = 0;
  render();
});
$('search').addEventListener('input', () => {
  page = 0;
  renderTable();
});
$('previous-page').addEventListener('click', () => {
  page--;
  renderTable();
});
$('next-page').addEventListener('click', () => {
  page++;
  renderTable();
});
document.querySelectorAll('[data-metric]').forEach(button => button.addEventListener('click', () => {
  metric = button.dataset.metric;
  document.querySelectorAll('[data-metric]').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
  renderTrend();
}));
document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => {
  const view = button.dataset.view;
  document.querySelectorAll('[data-view]').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
  document.querySelectorAll('.view').forEach(section => section.hidden = section.id !== view);
  [$('page-title').textContent, $('page-subtitle').textContent, $('breadcrumb').textContent] = titles[view];
  $('download').hidden = view !== 'overview';
}));
$('download').addEventListener('click', () => {
  const columns = ['period', 'market', 'product_id', 'description', 'sales_gbp', 'units', 'orders'];
  const rows = [columns, ...filteredProducts.map(p => [$('period').value, $('market').value, p.product_id, p.description, p.sales_gbp, p.units, p.orders])];
  const csv = rows.map(row => row.map(value => '"' + String(value).replaceAll('"', '""') + '"').join(',')).join('\n');
  const url = URL.createObjectURL(new Blob([csv], {
    type: 'text/csv;charset=utf-8'
  }));
  const a = document.createElement('a');
  a.href = url;
  a.download = `retail-products-${$('period').value}.csv`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
init().catch(error => $('comparison').textContent = error.message);
