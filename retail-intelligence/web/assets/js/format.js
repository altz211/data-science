// Number formatting and small DOM helpers shared by every page.

const gb = (value, digits = 0) =>
  Number(value).toLocaleString('en-GB', { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const number = (value, digits = 0) => (value == null ? '—' : gb(value, digits));
export const pounds = (value, digits = 0) => (value == null ? '—' : '£' + gb(value, digits));
export const pct = (share, digits = 0) => (share == null ? '—' : gb(share * 100, digits) + '%');

export function compactPounds(value) {
  if (value == null) return '—';
  if (Math.abs(value) >= 1e6) return '£' + gb(value / 1e6, 2) + 'M';
  if (Math.abs(value) >= 1e4) return '£' + gb(value / 1e3, 0) + 'k';
  return '£' + gb(value, 0);
}

// Axis ticks: short, but never so rounded that two ticks read the same (1.5k, not 2k).
export function axisPounds(value) {
  if (Math.abs(value) >= 1e6) return '£' + gb(value / 1e6, 1) + 'M';
  if (Math.abs(value) >= 1e4) return '£' + gb(value / 1e3, 0) + 'k';
  if (Math.abs(value) >= 1e3) return '£' + gb(value / 1e3, 1) + 'k';
  return '£' + gb(value, 0);
}

export function axisNumber(value) {
  if (Math.abs(value) >= 1e6) return gb(value / 1e6, 1) + 'M';
  if (Math.abs(value) >= 1e4) return gb(value / 1e3, 0) + 'k';
  if (Math.abs(value) >= 1e3) return gb(value / 1e3, 1) + 'k';
  return gb(value, 0);
}

/** "+4.2%" style change, with a class for colouring. Returns null when there's nothing to compare. */
export function change(current, previous) {
  if (current == null || !previous) return null;
  const ratio = current / previous - 1;
  return { text: (ratio >= 0 ? '+' : '−') + gb(Math.abs(ratio) * 100, 1) + '%', className: ratio >= 0 ? 'up' : 'down' };
}

export const escape = (value) =>
  String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

/** {columns, rows} from the pipeline -> array of plain objects. */
export function records(table) {
  return table.rows.map((row) => Object.fromEntries(table.columns.map((column, i) => [column, row[i]])));
}

export function monthLabel(id) {
  const [year, month] = id.split('-').map(Number);
  return new Date(Date.UTC(year, month - 1, 1)).toLocaleDateString('en-GB', { month: 'short', year: 'numeric', timeZone: 'UTC' });
}

export function dayLabel(iso) {
  return new Date(iso + 'T12:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });
}

export function downloadCsv(filename, columns, rows) {
  const cell = (value) => '"' + String(value ?? '').replaceAll('"', '""') + '"';
  const csv = [columns, ...rows].map((row) => row.map(cell).join(',')).join('\n');
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

export function tile(label, value, deltas = []) {
  const parts = deltas
    .filter(Boolean)
    .map((d) => (d.change ? `<span><b class="${d.change.className}">${d.change.text}</b> ${escape(d.label)}</span>` : `<span>${escape(d.label)}</span>`));
  return `<div class="tile"><div class="label">${escape(label)}</div><div class="value">${value}</div><div class="deltas">${parts.join('')}</div></div>`;
}
