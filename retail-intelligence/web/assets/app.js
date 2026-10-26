const $ = id => document.getElementById(id);
const format = (value, digits = 0) => Number(value).toLocaleString('en-GB', {
  maximumFractionDigits: digits
});
const escape = value => String(value).replace(/[&<>"']/g, char => ({
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;'
} [char]));
let data;
let products;

function chart(labels, series, unit) {
  const width = 1000,
    height = 280,
    left = 70,
    bottom = 35;
  const max = Math.max(1, ...series.flatMap(s => s.values)) * 1.1;
  const x = i => left + i / Math.max(1, labels.length - 1) * (width - left - 20);
  const y = value => height - bottom - value / max * (height - bottom - 15);
  const lines = series.map(s => `<polyline fill="none" stroke="${s.color}" stroke-width="3" ${s.dash ? 'stroke-dasharray="6 5"' : ''} points="${s.values.map((v,i)=>`${x(i)},${y(v)}`).join(' ')}"/>`).join('');
  const grid = Array.from({
    length: 5
  }, (_, i) => `<line x1="${left}" x2="980" y1="${y(max*i/4)}" y2="${y(max*i/4)}" stroke="#e3e8ed"/><text x="60" y="${y(max*i/4)+4}" text-anchor="end">${format(max*i/4)}</text>`).join('');
  const ticks = labels.map((label, i) => labels.length > 10 && i % 3 ? '' : `<text x="${x(i)}" y="270" text-anchor="middle">${escape(label)}</text>`).join('');
  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escape(unit)} time series. Exact forecast values appear below.">${grid}${lines}${ticks}</svg>`;
}

function productTable() {
  const query = $('search').value.toLowerCase();
  $('products').innerHTML = data.products.filter(p => (p.description + p.product_id).toLowerCase().includes(query)).map(p =>
    `<tr><td>${escape(p.description)}<small>${escape(p.product_id)}</small></td><td>${format(p.units)}</td><td>${format(p.orders)}</td><td>£${format(p.sales_gbp,2)}</td></tr>`).join('');
}

function forecast() {
  const id = $('product').value;
  const rows = data.forecast_test.filter(r => r.product_id === id);
  $('forecast-chart').innerHTML = chart(rows.map(r => r.target_date.slice(5)), [{
    values: rows.map(r => r.actual),
    color: '#172c3d'
  }, {
    values: rows.map(r => r.prediction),
    color: '#255f92'
  }, {
    values: rows.map(r => r.baseline),
    color: '#bd813d',
    dash: true
  }], 'Weekly unit sales');
  $('future').innerHTML = `<h3>Holdout: actual vs predicted units</h3><table><tr><th>Week</th><th>Actual</th><th>Selected model</th><th>Baseline</th></tr>${rows.map(r=>`<tr><td>${r.target_date}</td><td>${format(r.actual)}</td><td>${format(r.prediction)}</td><td>${format(r.baseline)}</td></tr>`).join('')}</table><h3>After the final observed complete week</h3><p class="note">Historical forward projections from the final refitted model. These are not present-day forecasts.</p><table>${data.forecast_next.filter(r=>r.product_id===id).map(r=>`<tr><td>${r.target_date}</td><td>${format(r.prediction)} units</td></tr>`).join('')}</table>`;
}

async function recommendations() {
  const name = $('customer').value;
  const customer = data.customers[name];
  if (!customer) return;
  let ranking = customer.recommendations;
  try {
    if (location.hostname.endsWith('.github.io')) throw new Error('Using saved predictions');
    const response = await fetch(`/api/recommendations/${encodeURIComponent(name)}`);
    if (response.ok) ranking = (await response.json()).products;
  } catch {
    /* Saved predictions also work without the Python server. */ }
  if ($('customer').value !== name) return;
  $('recommendations').innerHTML = ranking.map((id, i) => `<article class="product-card"><span class="rank">${String(i+1).padStart(2,'0')} / PRODUCT ${escape(id)}</span><h3>${escape(products.get(id)?.description || 'Product outside the overview catalogue')}</h3>${customer.actual_next.includes(id) ? '<span class="match">Purchased in the following 28 days</span>' : '<small>Not observed in subsequent purchases</small>'}</article>`).join('');
  $('customer-note').textContent = `${customer.history.length} distinct prior products. Displayed recommendations exclude past purchases; subsequent matches do not prove incremental sales.`;
}

function resultsTable(rows) {
  return `<div class="table-wrap"><table><thead><tr><th>Model</th><th>MAE units</th><th>WAPE</th></tr></thead><tbody>${Object.entries(rows).map(([name,m])=>`<tr><td>${escape(name)}${m.convergence_warning ? ' · convergence warning' : ''}</td><td>${format(m.mae_units,1)}</td><td>${format(m.wape_pct,1)}%</td></tr>`).join('')}</tbody></table></div>`;
}

async function init() {
  const response = await fetch('assets/results.json');
  if (!response.ok) throw new Error('Run python -m retail.pipeline to prepare the dataset and model results.');
  data = await response.json();
  products = new Map(data.catalogue.map(p => [p.product_id, p]));
  $('status').textContent = `Saved analysis · ${data.audit.first_date.slice(0,10)} to ${data.audit.last_date.slice(0,10)} · ${format(data.audit.source_rows)} source rows`;
  $('metrics').innerHTML = [
    ['Positive purchase sales', `£${format(data.summary.sales_gbp)}`],
    ['Purchase invoices', format(data.summary.orders)],
    ['Known customers', format(data.summary.customers)],
    ['Products purchased', format(data.summary.products)]
  ].map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`).join('');
  $('sales-chart').innerHTML = chart(data.monthly.map(r => r.month), [{
    values: data.monthly.map(r => r.sales_gbp),
    color: '#255f92'
  }], 'Monthly positive purchase sales in GBP');
  productTable();
  const ids = [...new Set(data.forecast_test.map(r => r.product_id))];
  $('product').innerHTML = ids.map(id => `<option value="${escape(id)}">${escape(products.get(id)?.description || id)}</option>`).join('');
  $('customer').innerHTML = Object.keys(data.customers).map(name => `<option>${escape(name)}</option>`).join('');
  if (!Object.keys(data.customers).length) {
    $('customer').disabled = true;
    $('customer-note').textContent = 'Customer examples and live recommendations are available after running the Python pipeline locally. This public page contains aggregate results only.';
  }
  const fm = data.forecast_metrics;
  $('forecast-scope').textContent = `${fm.products} products · selected model: ${fm.selected_model} · holdout starts ${fm.test_start}`;
  $('recommendation-scope').textContent = `History available before ${data.recommendation_metrics.cutoff}`;
  $('forecast-results').innerHTML = `<h3>Validation</h3>${resultsTable(fm.validation)}<h3>Untouched holdout</h3>${resultsTable(fm.test)}`;
  const rm = data.recommendation_metrics;
  $('recommendation-results').innerHTML = `<table><tr><th>Model</th><th>Recall@10</th><th>NDCG@10</th><th>Customers</th></tr>${['item_similarity','popularity'].map(name=>`<tr><td>${name}</td><td>${format(rm[name].recall_at_10,3)}</td><td>${format(rm[name].ndcg_at_10,3)}</td><td>${rm[name].evaluated_customers}</td></tr>`).join('')}</table><p class="note">${escape(rm.scope)}</p>`;
  $('audit').innerHTML = Object.entries(data.audit).map(([name, value]) => `<p class="note"><strong>${escape(name.replaceAll('_',' '))}:</strong> ${escape(value)}</p>`).join('');
  forecast();
  recommendations();
}
$('search').addEventListener('input', productTable);
$('product').addEventListener('change', forecast);
$('customer').addEventListener('change', recommendations);
document.querySelectorAll('[data-tab]').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('[data-tab]').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
  document.querySelectorAll('.tab').forEach(section => section.hidden = section.id !== button.dataset.tab);
}));
init().catch(error => $('status').textContent = error.message);
