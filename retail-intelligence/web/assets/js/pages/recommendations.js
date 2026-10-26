// Recommendations: how each strategy scored, and the similar-products lists.

import { axis, plot, tooltip } from '../charts.js';
import { load } from '../data.js';
import { escape, number, pct, records, tile } from '../format.js';

let selectedProduct = null;

export async function render(container) {
  const data = await load('recommendations');
  const name = (id) => data.names[id] || id;
  const metrics = records(data.metrics);
  const best = metrics[0];
  const sellers = metrics.find((m) => m.model === 'Best sellers');
  selectedProduct ??= data.similar[0].id;

  container.innerHTML = `
    <div class="tiles">
      ${tile('Hit rate @ 10', pct(best.hit_rate_at_10), [{ label: `best sellers: ${pct(sellers.hit_rate_at_10)}` }])}
      ${tile('Recall @ 10', pct(best.recall_at_10, 1), [{ label: 'of next-month new products found' }])}
      ${tile('Catalogue coverage', pct(best.catalogue_coverage), [{ label: `of ${number(data.catalogue)} products ever recommended` }])}
      ${tile('Customers scored', number(best.customers), [{ label: `returning buyers, ${data.evaluation_days} days from ${data.cutoff}` }])}
    </div>
    <div class="grid">
      <section class="card span-7"><div class="card-head"><div><h2>Hit rate by strategy</h2>
        <p>Share of customers whose top 10 included a product they went on to buy for the first time</p></div></div><div class="chart" id="hit"></div></section>
      <section class="card span-5"><div class="card-head"><div><h2>Selling now</h2><p>Most-ordered products in the last 28 days of data</p></div></div>
        <ol class="list">${data.trending.slice(0, 10).map((id, i) => `<li><span>${i + 1}. ${escape(name(id))}</span><span>${escape(id)}</span></li>`).join('')}</ol></section>
      <section class="card span-12"><div class="card-head"><div><h2>All scores</h2>
        <p>Trained on purchases before ${data.cutoff}; scored on new products each customer bought over the next ${data.evaluation_days} days. The blend weight was chosen on the previous four weeks.</p></div></div>
        <div class="table-wrap"><table><thead><tr><th>Strategy</th><th class="num">Hit rate @10</th><th class="num">Recall @10</th>
          <th class="num">NDCG @10</th><th class="num">Catalogue coverage</th></tr></thead><tbody>${metrics.map((m, i) => `
          <tr class="${i === 0 ? 'highlight' : ''}"><td>${escape(m.model)}</td><td class="num">${pct(m.hit_rate_at_10, 1)}</td>
          <td class="num">${pct(m.recall_at_10, 1)}</td><td class="num">${m.ndcg_at_10.toFixed(3)}</td><td class="num">${pct(m.catalogue_coverage, 1)}</td></tr>`).join('')}
        </tbody></table></div>
        <p class="note">The evaluation window is the Christmas run-up, so "what's selling now" is hard to beat on its own. Blending it with purchase similarity keeps that seasonal signal while recommending a far wider range of products (coverage ${pct(best.catalogue_coverage)} vs ${pct(metrics.find((m) => m.model.startsWith('Trending')).catalogue_coverage)}). These are offline scores, not measured sales uplift.</p>
      </section>
      <section class="card span-12">
        <div class="card-head"><div><h2>Customers who bought this also bought</h2><p>Cosine similarity of the customers buying each product (1 = identical buyers)</p></div>
          <label class="field">Product<select id="product">${data.similar.map((p) =>
            `<option value="${escape(p.id)}" ${p.id === selectedProduct ? 'selected' : ''}>${escape(name(p.id))}</option>`).join('')}</select></label></div>
        <div class="table-wrap"><table><thead><tr><th>#</th><th>Product</th><th class="num">Similarity</th></tr></thead><tbody id="similar"></tbody></table></div>
      </section>
    </div>`;

  plot(document.getElementById('hit'), (c) => {
    const ordered = [...metrics].reverse();
    return {
      tooltip: tooltip(c, { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v) => pct(v, 1) }),
      grid: { left: 8, right: 48, top: 8, bottom: 8, containLabel: true },
      xAxis: { type: 'value', show: false, max: 0.6 },
      yAxis: axis(c, { type: 'category', data: ordered.map((m) => m.model.replace(' (similarity + trending)', '')), axisLine: { show: false }, axisLabel: { color: c.ink2 } }),
      series: [{
        type: 'bar', barMaxWidth: 14,
        data: ordered.map((m) => ({ value: m.hit_rate_at_10, itemStyle: { color: m === best ? c.series[0] : c.neutral, borderRadius: [0, 4, 4, 0] } })),
        label: { show: true, position: 'right', color: c.ink2, fontSize: 12, formatter: (p) => pct(p.value) },
      }],
    };
  });

  const drawSimilar = () => {
    const product = data.similar.find((p) => p.id === selectedProduct);
    document.getElementById('similar').innerHTML = product.similar.map(([id, score], i) => `
      <tr><td>${i + 1}</td><td>${escape(name(id))}<small>${escape(id)}</small></td>
      <td class="num"><div class="bar-cell"><i><b style="width:${score * 100}%"></b></i>${score.toFixed(2)}</div></td></tr>`).join('');
  };
  document.getElementById('product').addEventListener('change', (event) => {
    selectedProduct = event.target.value;
    drawSimilar();
  });
  drawSimilar();
}
