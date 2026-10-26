// Thin wrapper around ECharts so every chart shares the same look.
// Colours come from CSS variables, so charts redraw correctly when the theme changes.

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

export function colors() {
  return {
    ink: css('--ink'),
    ink2: css('--ink-2'),
    muted: css('--muted'),
    grid: css('--grid'),
    axis: css('--axis'),
    surface: css('--surface'),
    neutral: css('--neutral'),
    series: [1, 2, 3, 4, 5, 6, 7, 8].map((i) => css(`--s${i}`)),
    sequential: [0, 1, 2, 3, 4, 5].map((i) => css(`--seq-${i}`)),
  };
}

/** Shared axis styling: hairline grid, muted labels, no ticks. */
export function axis(c, extra = {}) {
  return {
    axisLine: { lineStyle: { color: c.axis } },
    axisTick: { show: false },
    axisLabel: { color: c.muted, fontSize: 11, hideOverlap: true },
    splitLine: { lineStyle: { color: c.grid } },
    nameTextStyle: { color: c.muted, fontSize: 11 },
    ...extra,
  };
}

export function tooltip(c, extra = {}) {
  return {
    backgroundColor: c.surface,
    borderColor: c.axis,
    borderWidth: 1,
    textStyle: { color: c.ink, fontSize: 12 },
    extraCssText: 'box-shadow: 0 4px 14px rgba(0,0,0,.12); border-radius: 8px;',
    confine: true,
    ...extra,
  };
}

export function legend(c, extra = {}) {
  return { top: 0, left: 0, icon: 'roundRect', itemWidth: 12, itemHeight: 4, textStyle: { color: c.ink2, fontSize: 12 }, ...extra };
}

const live = new Set();

/**
 * Draw a chart into `element`. `build(colors)` returns an ECharts option and is
 * called again whenever the theme changes. Returns the ECharts instance.
 */
export function plot(element, build) {
  if (!window.echarts) {
    element.innerHTML = '<p class="error">Charts could not load (no connection to the ECharts CDN).</p>';
    return null;
  }
  // Redrawing into the same element replaces the old chart (and its click handlers).
  const existing = window.echarts.getInstanceByDom(element);
  if (existing) {
    live.forEach((entry) => entry.instance === existing && live.delete(entry));
    existing.dispose();
  }
  const instance = window.echarts.init(element, null, { renderer: 'svg' });
  const entry = {
    instance,
    draw: () => instance.setOption({
      animationDuration: 300,
      textStyle: { fontFamily: 'system-ui, -apple-system, "Segoe UI", sans-serif' },
      ...build(colors()),
    }, true),
  };
  entry.draw();
  live.add(entry);
  return instance;
}

export const redrawAll = () => live.forEach((entry) => entry.draw());

export function disposeAll() {
  live.forEach((entry) => entry.instance.dispose());
  live.clear();
}

let resizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => live.forEach((entry) => entry.instance.resize()), 120);
});
