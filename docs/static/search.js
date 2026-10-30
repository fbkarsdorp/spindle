// Spindle's search, in the browser (and in Node, for the benchmark).
//
// A query is embedded by bge-base-en-v1.5 (transformers.js), projected onto the
// principal components the motif vectors were reduced to, and scored against
// all 46,220 int8 motif vectors. Scores are standardised (z-scores) and a small
// literal-match nudge is added. Pure functions over loaded data; no DOM.

export const LETTERS = 'ABCDEFGHJKLMNPQRSTUVWXZ'.split('');

const STOP = new Set(('a an and are as at be but by for from has have he her his how i in into is it its of on or ' +
  'she so that the their them then there they this to was were what when where which who why will with whose ' +
  'one someone something person people man men').split(' '));
const ID_RE = /^\s*([A-Za-z])\s?(\d+(?:\.\d+)*)\.?\s*$/;
const FILTER_RE = /\b(culture|region|in|type):(?:"([^"]+)"|(\S+))/gi;

export const fold = (s) => s.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase();
const stem = (w) => w.replace(/(?:ies)$/, 'y').replace(/(?:es|s|ing|ed)$/, '').slice(0, 7);
const words = (s) => fold(s).match(/[a-z0-9]+/g) || [];

export function parseQuery(q) {
  const f = { cultures: [], regions: [], within: [], types: [] };
  q.replace(FILTER_RE, (_, key, a, b) => {
    const v = a || b;
    key = key.toLowerCase();
    if (key === 'culture') f.cultures.push(v);
    else if (key === 'region') f.regions.push(v);
    else if (key === 'in') f.within.push(v.length === 1 ? v.toUpperCase() : v);
    else if (key === 'type') f.types.push(v.toUpperCase());
    return ' ';
  });
  return { text: q.replace(FILTER_RE, ' ').replace(/\s+/g, ' ').trim(), filters: f };
}

// a display confidence from a z-score, calibrated per model on ATU development
// fragments (meta.confidence: midway between the median first and tenth result)
export const confidence = (z, centre = 5.0, scale = 0.8) => 1 / (1 + Math.exp(-(z - centre) / scale));

export class Index {
  constructor({ meta, motifs, tree, vectors = null, projection = null }) {
    this.meta = meta;
    this.dims = meta.dims;
    this.n = meta.count;
    this.fields = motifs.fields;
    this.rows = motifs.rows; // [id, title, note, parent, cultures, regions, types, cf, alt?]
    if (vectors) this.setVectors(vectors, projection);
    this.categories = tree.categories;
    this.children = tree.children;
    this.row = new Map(this.rows.map((r, i) => [r[0], i]));
    this.sections = new Map(tree.nodes.map(([id, kind, title, parent]) => [id, { id, kind: kind === 0 ? 'category' : 'section', title, parent }]));
    this._lex = null;
  }

  setVectors(vectors, projection) {
    // the encoder's width (768 for bge-base, 384 for bge-small), from the projection's length:
    // a mean of d0, then d0 × dims components, then dims scales
    const d0 = (projection.length - this.dims) / (1 + this.dims);
    this.vectors = vectors; // Int8Array n × dims
    this.mean = projection.subarray(0, d0);
    this.P = projection.subarray(d0, d0 + d0 * this.dims); // d0 × dims, row-major
    this.scale = projection.subarray(d0 + d0 * this.dims);
  }

  // ---------------------------------------------------------------- nodes

  node(id) {
    const i = this.row.get(id);
    if (i !== undefined) {
      const r = this.rows[i];
      return { id, kind: 'motif', title: r[1], parent: r[3], row: i };
    }
    return this.sections.get(id) || null;
  }

  path(id) {
    const out = [];
    let p = this.node(id)?.parent;
    while (p) {
      const n = this.node(p);
      if (!n) break;
      out.unshift(n);
      p = n.parent;
    }
    return out;
  }

  // -------------------------------------------------------------- scoring

  project(q) {
    // (q - mean) · P, normalised; then folded with the dequantisation scales
    const d = this.dims, out = new Float32Array(d);
    for (let j = 0; j < this.mean.length; j++) {
      const x = q[j] - this.mean[j];
      if (x === 0) continue;
      const base = j * d;
      for (let k = 0; k < d; k++) out[k] += x * this.P[base + k];
    }
    let norm = 0;
    for (let k = 0; k < d; k++) norm += out[k] * out[k];
    norm = Math.sqrt(norm) || 1;
    for (let k = 0; k < d; k++) out[k] = (out[k] / norm) * this.scale[k];
    return out;
  }

  zscores(q) {
    // with second vectors, rows n..2n-1 hold the plain-language readings and a
    // motif scores the better of its two matches
    const v = this.project(q), d = this.dims, n = this.n, V = this.vectors;
    const second = !!this.meta.second_vectors;
    const s = new Float32Array(n);
    let sum = 0, sq = 0;
    for (let i = 0; i < n; i++) {
      let acc = 0;
      const base = i * d;
      for (let k = 0; k < d; k++) acc += v[k] * V[base + k];
      if (second) {
        let acc2 = 0;
        const base2 = (n + i) * d;
        for (let k = 0; k < d; k++) acc2 += v[k] * V[base2 + k];
        if (acc2 > acc) acc = acc2;
      }
      s[i] = acc;
      sum += acc;
      sq += acc * acc;
    }
    const mu = sum / n, sd = Math.sqrt(Math.max(sq / n - mu * mu, 1e-12));
    for (let i = 0; i < n; i++) s[i] = (s[i] - mu) / sd;
    return s;
  }

  get lexicon() {
    // inverted index over headline + note: stem -> rows
    if (!this._lex) {
      const inv = new Map();
      this.rows.forEach((r, i) => {
        for (const w of new Set(words(r[1] + ' ' + r[2]).map(stem))) {
          if (w.length < 3 || STOP.has(w)) continue;
          let a = inv.get(w);
          if (!a) inv.set(w, (a = []));
          a.push(i);
        }
      });
      this._lex = inv;
    }
    return this._lex;
  }

  lexical(text) {
    // idf-weighted share of the query's words found in a motif's headline or note
    const terms = [...new Set(words(text).map(stem))].filter((w) => w.length >= 3 && !STOP.has(w));
    const out = new Float32Array(this.n);
    let total = 0;
    for (const t of terms) {
      const rows = this.lexicon.get(t);
      if (!rows) continue;
      const idf = Math.log(1 + this.n / rows.length);
      total += idf;
      for (const i of rows) out[i] += idf;
    }
    if (total > 0) for (let i = 0; i < this.n; i++) out[i] /= total;
    return out;
  }

  // -------------------------------------------------------------- filters

  mask(f) {
    if (!f || !(f.cultures.length || f.regions.length || f.within.length || f.types.length)) return null;
    const n = this.n, m = new Uint8Array(n).fill(1);
    const pick = (names, wanted) => {
      const want = wanted.map((w) => w.toLowerCase());
      return new Set(names.map((c, i) => [c.toLowerCase(), i])
        .filter(([c]) => want.some((w) => c === w || c.startsWith(w + ' ')))
        .map(([, i]) => i));
    };
    if (f.cultures.length) {
      const ok = pick(this.meta.cultures, f.cultures);
      for (let i = 0; i < n; i++) if (!this.rows[i][4].some((c) => ok.has(c))) m[i] = 0;
    }
    if (f.regions.length) {
      const ok = pick(this.meta.regions, f.regions);
      for (let i = 0; i < n; i++) if (!this.rows[i][5].some((r) => ok.has(r))) m[i] = 0;
    }
    if (f.types.length) {
      const match = (t) => f.types.some((w) => t === w || (t.startsWith(w) && !/^\d/.test(t.slice(w.length))));
      for (let i = 0; i < n; i++) if (!this.rows[i][6].some(match)) m[i] = 0;
    }
    if (f.within.length) {
      for (let i = 0; i < n; i++) {
        if (!m[i]) continue;
        const id = this.rows[i][0];
        if (f.within.includes(id)) continue;
        let p = this.rows[i][3], inside = false;
        while (p && !inside) {
          if (f.within.includes(p)) inside = true;
          p = this.node(p)?.parent;
        }
        if (!inside) m[i] = 0;
      }
    }
    return m;
  }

  // --------------------------------------------------------------- search

  lookupId(text) {
    const m = text.match(ID_RE);
    if (!m) return null;
    const id = m[1].toUpperCase() + m[2];
    return this.node(id) ? id : null;
  }

  /**
   * @param {string} query   free text, optionally with culture:/region:/in:/type: filters
   * @param {(text: string) => Promise<Float32Array>} embed   query -> normalised vector
   * @returns {Promise<{results: {row, score, via}[], filters}>}
   */
  async search(query, embed, { k = 60, lexWeight = null, refs = null } = {}) {
    const { text, filters } = parseQuery(query);
    const mask = this.mask(filters);
    const exact = text && this.lookupId(text);
    if (exact) {
      const out = [];
      if (this.row.has(exact)) out.push({ row: this.row.get(exact), score: 1, via: 'id' });
      for (const c of this.children[exact] || []) if (this.row.has(c)) out.push({ row: this.row.get(c), score: 0.9, via: 'child' });
      return { results: out.slice(0, k), filters };
    }
    if (!text) {
      const out = [];
      if (mask) for (let i = 0; i < this.n && out.length < k; i++) if (mask[i]) out.push({ row: i, score: 0, via: 'filter' });
      return { results: out, filters };
    }
    const z = this.zscores(await embed(this.meta.query_prompt + text));
    const lex = this.lexical(text);
    let lexMax = 0;
    for (let i = 0; i < this.n; i++) if (lex[i] > lexMax) lexMax = lex[i];
    const nWords = text.split(/\s+/).length;
    const w = lexWeight ?? (nWords <= 2 ? 1.5 : 0);
    for (let i = 0; i < this.n; i++) z[i] += w * lex[i];
    const top = topK(z, k, mask);
    let results = top.map((i) => ({ row: i, score: confidence(z[i], ...(this.meta.confidence || [])), via: 'meaning' }));

    // A name that occurs in no headline or note may still occur in the
    // references ('Melusine' only in Köhler's Melusinensage): look there first.
    if (refs && nWords <= 3 && text.length >= 4 && lexMax === 0) {
      const needle = fold(text);
      const all = await refs();
      const hits = [];
      for (const [id, r] of all) {
        const i = this.row.get(id);
        if (r && (!mask || mask[i])) {
          const c = fold(r).split(needle).length - 1;
          if (c) hits.push([i, c]);
        }
      }
      hits.sort((a, b) => b[1] - a[1] || z[b[0]] - z[a[0]]);
      const seen = new Set(hits.map(([i]) => i));
      results = hits.slice(0, k).map(([i]) => ({ row: i, score: 0.5, via: 'refs' }))
        .concat(results.filter((r) => !seen.has(r.row))).slice(0, k);
    }
    return { results, filters };
  }
}

function topK(s, k, mask) {
  // simple partial selection: keep a sorted buffer of the best k
  const idx = [], val = [];
  for (let i = 0; i < s.length; i++) {
    if (mask && !mask[i]) continue;
    const v = s[i];
    if (idx.length === k && v <= val[k - 1]) continue;
    let j = idx.length === k ? k - 1 : idx.length;
    while (j > 0 && val[j - 1] < v) { val[j] = val[j - 1]; idx[j] = idx[j - 1]; j--; }
    val[j] = v; idx[j] = i;
    if (idx.length > k) { idx.length = k; val.length = k; }
  }
  return idx;
}
