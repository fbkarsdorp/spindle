// Score Spindle (the static site's search) and the reconstructed MOMFER on the held-out set.
//   node tools/compare.mjs pipeline/heldout.json data/build/heldout_momfer.json [--data path/to/exported/data/]
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { pipeline, env } from '@huggingface/transformers';
import { Index } from '../docs/static/search.js';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const args = process.argv.slice(2);
const [qfile, mfile] = args.filter((a) => a.endsWith('.json')).map((f) => ROOT + f);
const di = args.indexOf('--data');
const D = ROOT + (di >= 0 ? args[di + 1] : 'docs/data').replace(/\/?$/, '/');
const json = (f) => JSON.parse(readFileSync(D + f, 'utf8'));
const buf = (f) => { const b = readFileSync(D + f); return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength); };
const ix = new Index({ meta: json('meta.json'), motifs: json('motifs.json'), tree: json('tree.json'),
  vectors: new Int8Array(buf('vectors.i8')), projection: new Float32Array(buf('projection.f32')) });
let modelName = ix.meta.model;
if (modelName.startsWith('local:')) { modelName = modelName.slice(6); env.localModelPath = ROOT + 'docs/models/'; env.allowRemoteModels = false; }
const ex = await pipeline('feature-extraction', modelName, { dtype: 'q8', revision: ix.meta.model_revision || 'main' });
const embed = async (t) => (await ex(t, { pooling: 'cls', normalize: true })).data;

const queries = JSON.parse(readFileSync(qfile, 'utf8'));
const momfer = JSON.parse(readFileSync(mfile, 'utf8')).results;
const allRefs = async () => {
  const out = [];
  for (const L of 'ABCDEFGHJKLMNPQRSTUVWXZ') for (const [id, r] of Object.entries(json(`refs/${L}.json`))) out.push([id, r.r || '']);
  return out;
};
const rank = (ids, gold) => { const r = ids.slice(0, 10).findIndex((id) => gold.includes(id)); return r < 0 ? null : r + 1; };
const rows = [];
let ms = 0;
for (const q of queries) {
  const t0 = performance.now();
  const { results } = await ix.search(q.q, embed, { k: 10, refs: allRefs });
  ms += performance.now() - t0;
  rows.push({ ...q, spindle: rank(results.map((r) => ix.rows[r.row][0]), q.gold), momfer: rank(momfer[q.q] || [], q.gold) });
}
const summary = (sel, sys) => {
  const n = sel.length, ranks = sel.map((r) => r[sys]);
  const h1 = ranks.filter((r) => r === 1).length, h10 = ranks.filter((r) => r).length;
  const mrr = ranks.reduce((a, r) => a + (r ? 1 / r : 0), 0) / n;
  return `hit@1 ${(h1 / n).toFixed(2)}  hit@10 ${(h10 / n).toFixed(2)}  MRR ${mrr.toFixed(2)}`;
};
for (const kind of ['description', 'keyword', null]) {
  const sel = rows.filter((r) => !kind || r.kind === kind);
  console.log(`\n${kind || 'all'} (${sel.length})`);
  console.log(`  Spindle  ${summary(sel, 'spindle')}`);
  console.log(`  MOMFER   ${summary(sel, 'momfer')}`);
}
console.log(`\nSpindle ${(ms / queries.length).toFixed(0)} ms/query (Node, CPU)\n`);
for (const r of rows) console.log(`${String(r.spindle ?? '–').padStart(3)} ${String(r.momfer ?? '–').padStart(3)}  ${r.kind[0]}  ${r.q}`);
