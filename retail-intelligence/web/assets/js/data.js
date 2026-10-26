// Each page's data lives in its own JSON file, fetched once on first visit.

const cache = new Map();

export function load(name) {
  if (!cache.has(name)) {
    cache.set(name, fetch(`data/${name}.json`).then((response) => {
      if (!response.ok) throw new Error(`Could not load ${name}.json (${response.status}). Run \`python -m retail\` to generate it.`);
      return response.json();
    }));
  }
  return cache.get(name);
}
