// Data for the static site: loads the exported files lazily and assembles the
// records the views render. Replaces what used to be a server API.

import { Index, LETTERS, parseQuery } from './search.js';

// transformers.js runs the query encoder in the browser (pinned version)
const TRANSFORMERS = 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@4.3.1';
const DATA = 'data/';

const fetchJSON = async (f) => {
  const r = await fetch(DATA + f);
  if (!r.ok) throw new Error(`Could not load ${f} (${r.status})`);
  return r.json();
};
const fetchBuffer = async (f) => {
  const r = await fetch(DATA + f);
  if (!r.ok) throw new Error(`Could not load ${f} (${r.status})`);
  return r.arrayBuffer();
};

// ------------------------------------------------------------------- base

let indexP = null;
export const index = () => (indexP ??= Promise.all([fetchJSON('meta.json'), fetchJSON('motifs.json'), fetchJSON('tree.json')])
  .then(([meta, motifs, tree]) => new Index({ meta, motifs, tree })));
export const meta = async () => (await index()).meta;

// --------------------------------------------------- the model and vectors

const listeners = new Set();
export const model = { status: 'idle', loaded: 0, total: 0, error: null };
const emit = () => listeners.forEach((f) => f(model));
export const onModel = (f) => { listeners.add(f); f(model); return () => listeners.delete(f); };

let extractorP = null, vectorsP = null;

function loadVectors() {
  return (vectorsP ??= (async () => {
    const [ix, vec, proj] = await Promise.all([index(), fetchBuffer('vectors.i8'), fetchBuffer('projection.f32')]);
    ix.setVectors(new Int8Array(vec), new Float32Array(proj));
    return ix;
  })());
}

function loadModel() {
  return (extractorP ??= (async () => {
    model.status = 'loading';
    emit();
    const ix = await index();
    const { pipeline, env } = await import(TRANSFORMERS);
    // 'local:name' is a model served next to the site (docs/models/name), for testing.
    // transformers.js only fetches local files in Node, so point its download
    // address at this site instead of Hugging Face.
    let name = ix.meta.model;
    env.allowLocalModels = false;
    if (name.startsWith('local:')) {
      name = name.slice(6);
      env.remoteHost = new URL('models/', location.href).href;
      env.remotePathTemplate = '{model}/';
    }
    const files = new Map();
    const ex = await pipeline('feature-extraction', name, {
      dtype: 'q8',
      device: 'wasm',
      progress_callback: (p) => {
        if (p.status === 'progress' && p.total) {
          files.set(p.file, [p.loaded, p.total]);
          model.loaded = [...files.values()].reduce((a, [l]) => a + l, 0);
          model.total = [...files.values()].reduce((a, [, t]) => a + t, 0);
          emit();
        }
      },
    });
    model.status = 'ready';
    emit();
    return ex;
  })().catch((e) => {
    model.status = 'error';
    model.error = e.message || String(e);
    extractorP = null;
    emit();
    throw e;
  }));
}

/** Start fetching the model and vectors in the background. */
export const warm = () => { loadModel().catch(() => {}); loadVectors().catch(() => {}); };

async function embed(text) {
  const ex = await loadModel();
  const out = await ex(text, { pooling: 'cls', normalize: true });
  return out.data;
}

// -------------------------------------------------------------- references

const refsCache = new Map();
const refsFor = (letter) => {
  if (!refsCache.has(letter)) refsCache.set(letter, fetchJSON(`refs/${letter}.json`));
  return refsCache.get(letter);
};
async function allRefs() {
  const parts = await Promise.all(LETTERS.map(refsFor));
  return parts.flatMap((p) => Object.entries(p).map(([id, r]) => [id, r.r || '']));
}

// ----------------------------------------------------------------- records

const ROW = { id: 0, title: 1, note: 2, parent: 3, cultures: 4, regions: 5, types: 6, cf: 7, alt: 8 };

export function brief(ix, i) {
  const r = ix.rows[i];
  const cultures = r[ROW.cultures].map((c) => ix.meta.cultures[c]);
  return {
    id: r[0], kind: 'motif', title: r[1], note: r[2], letter: r[0][0],
    cultures: cultures.slice(0, 8), n_cultures: cultures.length,
    path: ix.path(r[0]).slice(-3).map((p) => ({ id: p.id, title: p.title })),
    n_children: (ix.children[r[0]] || []).length,
  };
}

function briefChild(ix, id) {
  const n = ix.node(id);
  return {
    id, kind: n.kind, title: n.title, n_children: (ix.children[id] || []).length,
    has_note: n.kind === 'motif' && !!ix.rows[n.row][ROW.note],
  };
}

let citedBy = null;
function citedByIndex(ix) {
  if (!citedBy) {
    citedBy = new Map();
    ix.rows.forEach((r, i) => r[ROW.cf].forEach((j) => {
      if (!citedBy.has(j)) citedBy.set(j, []);
      citedBy.get(j).push(i);
    }));
  }
  return citedBy;
}

/** Everything about a node, for the motif page and the browser. */
export async function full(id) {
  const ix = await index();
  let node = ix.node(id);
  if (!node) {
    const alt = ix.lookupId(id);
    if (!alt) throw new Error(`There is no motif ${id} in the index.`);
    id = alt;
    node = ix.node(id);
  }
  const out = {
    id, kind: node.kind, title: node.title, letter: id[0],
    path: ix.path(id).map((p) => ({ id: p.id, title: p.title, kind: p.kind })),
    children: (ix.children[id] || []).map((c) => briefChild(ix, c)),
  };
  if (node.kind !== 'motif') return out;

  const r = ix.rows[node.row];
  const extra = (await refsFor(id[0]))[id] || {};
  const pairs = r[ROW.cultures].map((c) => [ix.meta.cultures[c], ix.meta.regions[ix.meta.culture_regions[c]] || 'Elsewhere']);
  Object.assign(out, {
    note: r[ROW.note], refs: extra.r || '', reading: extra.p || '', types: r[ROW.types], alt_titles: r[ROW.alt] || [],
    cultures: pairs.map(([c]) => c), culture_regions: pairs,
    category: ix.categories[id[0]],
    cf: r[ROW.cf].map((j) => brief(ix, j)),
    cited_by: (citedByIndex(ix).get(node.row) || []).map((j) => brief(ix, j)),
    echoes: (extra.e || []).map((j) => brief(ix, j)),
    kin: (extra.k || []).map((j) => brief(ix, j)),
  });
  const sibs = ix.children[r[ROW.parent]] || [];
  const k = sibs.indexOf(id);
  out.prev = k > 0 ? briefChild(ix, sibs[k - 1]) : null;
  out.next = k >= 0 && k + 1 < sibs.length ? briefChild(ix, sibs[k + 1]) : null;
  return out;
}

/** The 23 branches with their motif counts. */
export async function branches() {
  const ix = await index();
  const counts = Object.fromEntries(LETTERS.map((L) => [L, 0]));
  ix.rows.forEach((r) => counts[r[0][0]]++);
  return LETTERS.map((L) => ({ id: L, title: ix.categories[L], count: counts[L] }));
}

export async function random() {
  const ix = await index();
  const pool = ix.meta.notable;
  return brief(ix, pool[Math.floor(Math.random() * pool.length)]);
}

/** Search; resolves once the model and vectors are in (unless no embedding is needed). */
export async function search(query, { k = 60 } = {}) {
  const ix = await index();
  const { text } = parseQuery(query);
  const needsModel = !!text && !ix.lookupId(text);
  if (needsModel) await loadVectors();
  const t0 = performance.now();
  const { results, filters } = await ix.search(query, embed, { k, refs: allRefs });
  const items = results.map(({ row, score, via }) => ({ ...brief(ix, row), score, via }));
  const facets = { categories: {}, regions: {} };
  for (const { row } of results) {
    const r = ix.rows[row];
    facets.categories[r[0][0]] = (facets.categories[r[0][0]] || 0) + 1;
    for (const g of r[ROW.regions]) {
      const name = ix.meta.regions[g];
      facets.regions[name] = (facets.regions[name] || 0) + 1;
    }
  }
  return { results: items, facets, filters, ms: performance.now() - t0 };
}

export async function mapData() {
  const [ix, buf] = await Promise.all([index(), fetchBuffer('map.bin')]);
  return { buf, rows: ix.rows };
}
