// Benchmark the static site's search code with the browser model, in Node.
//   node tools/eval_static.mjs [queries.json] [--dtype q8] [--lex 0.6] [--data path/to/exported/data/]
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
const ROOT = fileURLToPath(new URL('..', import.meta.url));
import { pipeline, env } from '@huggingface/transformers';
import { Index } from '../docs/static/search.js';

const args = process.argv.slice(2);
const opt = (name, dflt) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : dflt; };
const file = (f => f.startsWith('/') ? f : ROOT + f)(args.find((a) => a.endsWith('.json')) || 'pipeline/devset.json');
const dtype = opt('--dtype', 'q8');
const lexes = opt('--lex', 'auto').split(',').map((x) => (x === 'auto' ? null : +x));

const D = (d => d.startsWith('/') ? d : ROOT + d)(opt('--data', 'docs/data/').replace(/\/?$/, '/'));
const json = (f) => JSON.parse(readFileSync(D + f, 'utf8'));
const buf = (f) => { const b = readFileSync(D + f); return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength); };
const index = new Index({
  meta: json('meta.json'), motifs: json('motifs.json'), tree: json('tree.json'),
  vectors: new Int8Array(buf('vectors.i8')), projection: new Float32Array(buf('projection.f32')),
});
let modelName = opt('--model', index.meta.model);
if (modelName.startsWith('local:')) { modelName = modelName.slice(6); env.localModelPath = ROOT + 'docs/models/'; env.allowRemoteModels = false; }
const extractor = await pipeline('feature-extraction', modelName, { dtype, revision: index.meta.model_revision || 'main' });
const embed = async (t) => (await extractor(t, { pooling: 'cls', normalize: true })).data;

const queries = JSON.parse(readFileSync(file, 'utf8'));
for (const lexWeight of lexes) {
  let h1 = 0, h10 = 0, mrr = 0, ms = 0, n10 = 0;
  const misses = [];
  for (const { q, gold, near } of queries) {
    const t0 = performance.now();
    const { results } = await index.search(q, embed, { k: 10, lexWeight });
    ms += performance.now() - t0;
    const ids = results.map((r) => index.rows[r.row][0]);
    const r = ids.findIndex((id) => gold.includes(id));
    if (r >= 0) { h10++; if (r === 0) h1++; mrr += 1 / (r + 1); } else misses.push(q);
    if (near && ids.some((id) => near.includes(id))) n10++;
  }
  const n = queries.length;
  const lenient = queries[0].near ? `  (top 10 incl. parent/child ${(n10 / n).toFixed(2)})` : '';
  console.log(`${dtype} lex=${lexWeight ?? 'auto'} n=${n}: hit@1 ${(h1 / n).toFixed(2)} hit@10 ${(h10 / n).toFixed(2)} mrr ${(mrr / n).toFixed(3)}${lenient}  [${(ms / n).toFixed(0)} ms/query]`);
}
