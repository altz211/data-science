// Page routing (#overview, #customers, ...), theme toggle and footer.

import { disposeAll, redrawAll } from './charts.js';
import { load } from './data.js';
import { escape } from './format.js';
import * as overview from './pages/overview.js';
import * as customers from './pages/customers.js';
import * as products from './pages/products.js';
import * as forecast from './pages/forecast.js';
import * as recommendations from './pages/recommendations.js';
import * as report from './pages/report.js';
import * as definitions from './pages/definitions.js';

const pages = {
  overview: { module: overview, section: 'Analytics', title: 'Overview', subtitle: 'Sales, orders and customers by month and market. Pick a month or click a bar to drill in.' },
  customers: { module: customers, section: 'Analytics', title: 'Customers', subtitle: 'Who buys, how often, and who is slipping away. Identified customers only.' },
  products: { module: products, section: 'Analytics', title: 'Products', subtitle: 'Where sales concentrate, what sells together, and what comes back.' },
  forecast: { module: forecast, section: 'Models', title: 'Sales forecast', subtitle: 'Four-week unit forecasts for the top 100 products, tested on the run-up to Christmas 2011.' },
  recommendations: { module: recommendations, section: 'Models', title: 'Recommendations', subtitle: '"Customers who bought this also bought", tested on what customers bought next.' },
  report: { module: report, section: 'Write-up', title: 'Findings report', subtitle: 'What the data says and what to do about it. Numbers update with every pipeline run.' },
  data: { module: definitions, section: 'Write-up', title: 'Data & definitions', subtitle: 'Where the numbers come from and exactly how each one is defined.' },
};

const container = document.getElementById('page');

async function show() {
  const name = location.hash.slice(1) in pages ? location.hash.slice(1) : 'overview';
  const page = pages[name];
  document.querySelectorAll('[data-page]').forEach((link) => {
    if (link.dataset.page === name) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
  document.getElementById('eyebrow').textContent = page.section;
  document.getElementById('title').textContent = page.title;
  document.getElementById('subtitle').textContent = page.subtitle;
  document.title = `${page.title} · Retail Intelligence`;

  disposeAll();
  container.innerHTML = '<p class="loading">Loading…</p>';
  try {
    await page.module.render(container);
  } catch (error) {
    console.error(error);
    container.innerHTML = `<p class="error">${escape(error.message)}</p>`;
  }
}

function setupTheme() {
  const button = document.getElementById('theme');
  const root = document.documentElement;
  let saved = null;
  try { saved = localStorage.getItem('theme'); } catch { /* storage blocked */ }
  if (saved) root.dataset.theme = saved;
  const isDark = () => root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
  const label = () => { button.textContent = isDark() ? 'Light mode' : 'Dark mode'; };
  button.addEventListener('click', () => {
    root.dataset.theme = isDark() ? 'light' : 'dark';
    try { localStorage.setItem('theme', root.dataset.theme); } catch { /* fine */ }
    label();
    redrawAll();
  });
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { label(); redrawAll(); });
  label();
}

setupTheme();
window.addEventListener('hashchange', show);
show();
load('meta').then((meta) => {
  document.getElementById('generated').textContent = `Pipeline run ${meta.generated_utc.slice(0, 10)}`;
}).catch(() => {});
