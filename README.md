# Spindle

A search engine for Stith Thompson's *Motif-Index of Folk-Literature* (revised edition, 1955–58),
and a successor to [MOMFER](https://doi.org/10.1080/0015587X.2015.1006954). It is a static
website: the search runs entirely in the visitor's browser, so it can be served from GitHub Pages
with no server.

- **Describe** a motif in your own words ("a girl must not look back", "why the bear has a short tail")
  and get the motifs that mean it, however Thompson worded them. Filters: `in:B`, `culture:Irish`,
  `region:"South Asia"`, `type:510`; motif numbers (`D1960.3`) open directly.
- **Motif pages** show the place in Thompson's tree, the traditions a motif is attested in (grouped by
  region), tale types, references with clickable cross-references, subdivisions, and **echoes**: similar
  motifs Thompson filed under other headings.
- **Browse** the tree from A to Z, or wander a **map** on which motifs alike in meaning lie together.

## Publishing on GitHub Pages

Everything the site needs is in `docs/` (about 27 MB). Push the repository to GitHub, then under
*Settings → Pages* choose *Deploy from a branch*, branch `main`, folder `/docs`. Routes are hashes
(`#/motif/D113.1.1`), so the site works under any sub-path.

At search time the browser fetches two things from elsewhere: transformers.js (pinned, from
jsDelivr) and the query encoder `Xenova/bge-base-en-v1.5` (int8, about 110 MB, from Hugging Face,
then cached by the browser). Browsing, motif pages, the map and motif numbers work without them.

To preview locally: `cd docs && python3 -m http.server 8642`.

## Rebuilding the data

```sh
uv sync
uv run python pipeline/parse.py    # ruthenia HTML  -> data/build/motifs.raw.json
uv run python pipeline/build.py    # tree, traditions, cross-references -> data/build/tmi.json
uv run python pipeline/index.py    # embeddings and 2-D map -> data/index/   (minutes on an M-series Mac)
uv run python pipeline/static.py   # everything the site needs -> docs/data/
```

The raw sources are in `data/raw/`: the 23 ruthenia.ru pages, the old MOMFER heading index, and the
Internet Archive OCR text, which is kept only for reference.

## How it works

**Text.** `pipeline/parse.py` re-parses the HTML edition at ruthenia.ru, the fullest digital
transcription of the revised edition. Its italics separate the headline from the explanatory note and
the references, so all three are kept apart. (The old `tmi.json` in the MOMFER repository had lost many
notes and references, and its accented characters.) The ruthenia text had once been decoded as
Windows-1251 instead of Latin-1, turning *Métraux* into *Mйtraux*; that mapping is a bijection and is
reversed character by character. Headlines whose italics stop short are completed to the end of their
sentence, and the handful the transcription garbles beyond repair are patched in `build.py`.

**Tree.** `pipeline/build.py` places every motif under its parent: dotted motifs under their stems,
numbered motifs under the decade headings and ranges of Thompson's synopses. For A and B, whose
synopses are missing from ruthenia, the headings come from the old MOMFER index.

**Traditions.** Reference labels ("Irish myth:", "Icel.:", "N. A. Indian (Zuñi):") are normalised into
about 1,100 traditions in 14 regions.

**Search.** Each motif's headline and note are embedded with `BAAI/bge-base-en-v1.5`, reduced to
256 principal components and stored as one byte per dimension: 12 MB for all 46,220 motifs.
The browser embeds the query with the same encoder (transformers.js), projects it, and scores all
motifs in a few milliseconds (`docs/static/search.js`).

- **Exact words.** For one- and two-word queries, exact word matches add a small bonus.
- **Names in the references.** If the query's word appears in no headline or note but does appear
  in the references, those motifs come first. That is how "Melusine" finds C31.1.2, the Melusine tabu.
- **Echoes and kin.** These neighbours are precomputed at full precision.

## How well it works

There are two benchmarks, both run with `node tools/eval_static.mjs [file]` against the site's own search code.
Install the Node dependencies first with `cd tools && npm install`.

| | | right motif first | in top 10 | MRR |
|---|---|---|---|---|
| `pipeline/devset.json` | 30 descriptions, used while building | 0.50 | 0.80 | 0.61 |
| `pipeline/heldout.json` | 40 queries written before running either system | 0.60 | 0.97 | 0.73 |

**Against the old MOMFER.** The original server is offline. `tools/momfer_legacy.py` therefore
reconstructs its search from the 2015 source: the same `tmi.json`, Whoosh schema and field boosts,
WordNet hypernym keywords, and query expansion. NLTK's WordNet 3.0 stands in for the copy bundled with
Pattern, and Whoosh-Reloaded for Whoosh. On the held-out set:

| | descriptions: first / top 10 | keywords: first / top 10 | all: MRR |
|---|---|---|---|
| Spindle | 0.50 / 0.95 | 0.70 / 1.00 | 0.73 |
| MOMFER (reconstructed) | 0.45 / 0.60 | 0.65 / 0.80 | 0.61 |

```sh
uv run --with whoosh-reloaded --with nltk python tools/momfer_legacy.py pipeline/heldout.json > data/build/heldout_momfer.json
node tools/compare.mjs pipeline/heldout.json data/build/heldout_momfer.json
```

When both systems find a motif, they often both put it first. The difference is in how rarely Spindle
misses altogether. MOMFER finds nothing for "werewolf", because Thompson wrote *werwolf*, or for "a
trickster gets stuck to a figure covered in tar". Forty queries is a small sample.

**Choosing the model.** `pipeline/experiment.py` compared bge-base, bge-large, bge-m3, e5-large-v2,
mxbai-embed-large, gte-modernbert and Qwen3-Embedding-0.6B on the development set. Two findings went
against expectation:

- Qwen3-Embedding and a cross-encoder reranker (bge-reranker-v2-m3) both did *worse*. Thompson's
  headlines are very short, and these models favour the shortest, most generic ones ("Magic objects.").
- Reducing bge-base to 256 int8 dimensions cost nothing measurable.

An ensemble with bge-m3 scored about three points higher on the development set, but it is too large
to run in a browser.

**Reading whole tales.** An earlier, server-based version could also annotate a pasted tale sentence by
sentence, optionally with a local language model. It found only about a third to a half of the motifs a
folklorist would assign, so it was dropped in favour of the static site. That version is in
`archive/spindle-server-version-2026-10-29.tar.gz`.

## Layout

```
docs/       the website (GitHub Pages)
            index.html, static/app.js (views), static/store.js (data), static/search.js (search), static/app.css
            art/   papercut illustrations          data/  exported by pipeline/static.py
pipeline/   parse.py, build.py, index.py, static.py     build the data
            devset.json, heldout.json, experiment.py    benchmarks and model comparison
tools/      eval_static.mjs, compare.mjs   benchmarks in Node, using the site's search code
            momfer_legacy.py               the reconstructed MOMFER
            artgen.py, shoot.py            illustrations; screenshots (Playwright + system Chrome)
```
