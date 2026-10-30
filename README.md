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
- **Browse** the tree from A to Z.
- **Lists**: collect motifs while annotating a tale, one list per tale, with a note per motif; copy a list
  as numbers ("D1975; H481.1"), with headlines, or as a table or CSV, or send it as a link. Lists are kept
  in the browser's local storage (`docs/static/lists.js`).
- The **atlas** puts Thompson's traditions on a papercut world map: where his sources tell each motif,
  overall, by branch, or for the closest matches to a description. Motif pages show their own small map.

## Publishing on GitHub Pages

Everything the site needs is in `docs/` (about 44 MB). Push the repository to GitHub, then under
*Settings → Pages* choose *Deploy from a branch*, branch `main`, folder `/docs`. Routes are hashes
(`#/motif/D113.1.1`), so the site works under any sub-path.

At search time the browser fetches two things from elsewhere: transformers.js (pinned, from
jsDelivr) and Spindle's query encoder (int8 ONNX, about 110 MB, from Hugging Face, then cached by the
browser). Browsing, motif pages, the atlas and motif numbers work without them. The model is too large
for a GitHub repository (100 MB per file), and Hugging Face also carries the download traffic.

To preview locally: `cd docs && python3 -m http.server 8642`.

## Rebuilding the data

```sh
uv sync
uv run python pipeline/parse.py    # ruthenia HTML  -> data/build/motifs.raw.json
uv run python pipeline/build.py    # tree, traditions, cross-references -> data/build/tmi.json
uv run python pipeline/index.py    # stock embeddings -> data/index/
```

The search model and the plain-language readings (see below):

```sh
uv run python pipeline/atu_bench.py                         # ATU fragment benchmark -> data/build/atu_{train,dev,test}.json
source ~/.anthropic_env                                     # ANTHROPIC_API_KEY
uv run --group llm python pipeline/readings.py all          # readings for all motifs (Claude Haiku, about $2.60)
uv run --group llm python pipeline/tale_bench.py build --split train --n 0   # tale queries for training (Claude Sonnet, about $11)
uv run --group llm python pipeline/tale_bench.py check --split train          # drop passages whose motif does not fit (about $1)
uv run --group train python pipeline/finetune.py --epochs 3 --hard 3 --name spindle-bge-base-motifs \
    --tales data/build/tale_train_checked.json --tale-kinds vague,description,keywords --tale-negatives random
uv run python pipeline/compare.py data/models/spindle-bge-base-motifs --split dev   # with and without readings
```

Then convert the model for the browser (ONNX, int8), upload it to Hugging Face, and export the site:

```sh
uvx --from "optimum[onnxruntime]" optimum-cli export onnx --model data/models/spindle-bge-base-motifs \
    --task feature-extraction --opset 17 data/models/onnx/spindle-bge-base-motifs/export
# move export/model.onnx to onnx/, the tokenizer and config files up one level, then quantise:
# onnxruntime.quantization.quantize_dynamic(..., "onnx/model_quantized.onnx", weight_type=QuantType.QInt8)
uv run python pipeline/static.py --model data/models/spindle-bge-base-motifs \
    --readings data/build/readings/claude-haiku-5-5.jsonl --browser-model folgertk/spindle-bge-base-motifs \
    --browser-revision <commit on Hugging Face> --confidence 4.8,0.7
```

`--browser-revision` pins the model's commit, so a browser that cached an earlier model never pairs it
with new vectors. `--confidence` places the displayed confidence midway between the median z-scores of
the first and tenth result on the ATU development fragments; recompute it for a new model.

For a local test, copy the converted model to `docs/models/spindle-bge-base-motifs/` (git-ignored) and
pass `--browser-model local:spindle-bge-base-motifs`.

The raw sources are in `data/raw/`: the 23 ruthenia.ru pages, the old MOMFER heading index, and the
Internet Archive OCR text, which is kept only for reference. The trilogy data (`data/raw/trilogy/`),
the ATU benchmark and the trained models are not in the repository: the ATU summaries are Uther's
copyrighted text, included in trilogy (CC BY-SA 4.0) with permission. The tale benchmark and training
queries (`data/build/tale_*.json`) quote Ashliman's tale texts and also stay local. The fine-tuned model is on
Hugging Face as [folgertk/spindle-bge-base-motifs](https://huggingface.co/folgertk/spindle-bge-base-motifs),
under the same licence.

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
about 960 traditions in 14 regions. A people named under a continental group belongs to that group's
region ("Africa (Baluba)" is African, though *Alu* is a Solomon Islands people), short names match only
as whole words (Passamaquoddy is not Assam), and the end of a previous sentence that clings to a label
("Odin.) Icelandic") is dropped.

**Atlas.** `pipeline/places.py` is a gazetteer of some 480 peoples and places with the spellings
Thompson's sources use; it places 99.9% of all tradition tags. Each entry is a people or place, a broad
region ("African", "Polynesian"), or a written or religious tradition ("Jewish", "Italian Novella"),
set at its historical centre. `pipeline/atlas.py` projects Natural Earth's 1:50m land outlines (public
domain; downloaded to `data/raw/naturalearth/`) with the Natural Earth projection centred on 11°E, so
that the seam runs through the Pacific between Samoa and the Cook Islands, simplifies and softens the
coastlines, and writes `docs/data/atlas.json` (150 kB). `static.py` runs it at the end. The figures
in the sea (a serpent, a whale, a ship, a compass rose, and the mole on a far island where Tristan da
Cunha is) are drawn by `tools/artgen.py`.

**Search.** The browser embeds the query with Spindle's encoder (transformers.js), projects it onto
256 principal components, and scores all motifs at once (`docs/static/search.js`). Every motif has two
vectors, one byte per dimension (24 MB in all): one for Thompson's headline and note, one for its
plain-language reading. A motif scores its better match.

- **The encoder.** `BAAI/bge-base-en-v1.5`, fine-tuned on 1,829 plot fragments from the ATU tale-type
  summaries in Joshua Hagedorn's [trilogy](https://github.com/j-hagedorn/trilogy) datasets, each paired
  with the motif the summary cites ("...he falls into a magic sleep [D1975]"). It trains with in-batch
  negatives plus three mined hard negatives per fragment, for three epochs: about three minutes on an
  M4 Pro.
- **Plain-language readings.** For every motif, Claude Haiku wrote one or two plain sentences and three to
  five search phrases (`pipeline/readings.py`). They are shown on motif pages as *In plain words*, marked
  as generated.
- **Exact words.** For one- and two-word queries, exact word matches add a small bonus.
- **Names in the references.** If the query's word appears in no headline or note but does appear
  in the references, those motifs come first. That is how "Melusine" finds C31.1.2, the Melusine tabu.
- **Echoes and kin.** These neighbours are precomputed at full precision.

## How well it works

The main benchmark is built from the ATU summaries (`pipeline/atu_bench.py`). It has 3,130 plot fragments
of five words or more, each with the motif(s) Uther cites, split by tale type into training (1,829),
development (614) and test (687) sets. The test fragments come from tale types the encoder never saw,
and were scored once, after choosing the model on the development set. Many fragments are hard out of
context ("by handing him an apple" → H481.1), so the ceiling is well below 100%.

| ATU test fragments, browser pipeline | right motif first | in top 10 | MRR |
|---|---|---|---|
| stock bge-base | 0.24 | 0.44 | 0.30 |
| fine-tuned on summaries + readings (version 1) | 0.33 | 0.55 | 0.40 |
| fine-tuned on summaries and tales + readings (the site) | 0.33 | 0.55 | 0.40 |

At full precision the model with readings reaches 0.34 / 0.57 / 0.41. The browser's int8 model and
256-dimension vectors cost about three points.

**Tales** (`pipeline/tale_bench.py`). The ATU fragments are Uther's phrasing. Closer to how people search
are queries written from real tellings. The trilogy dataset has 1,518 tales from D. L. Ashliman's
*Folktexts*, each with its ATU type, and Uther lists the motifs of each type. Claude Sonnet reads a tale
with its type's motifs and quotes the passage where this telling expresses each one (about half are
absent: the lists belong to the type, not the telling). A second call, seeing only the passage with the
episode marked and a few sentences around it, never the motif's number or wording, writes a vague line, a
description and keywords. Their content words overlap Thompson's headline by 9–22%, against 26% for
queries written from the headline and 18% for Wikipedia sentences that cite a motif.

A telling also contains motifs Uther does not list, so one gold motif per query is too narrow. For each
passage the top ten of every compared model are pooled, and Sonnet judges each candidate against the
episode: one a folklorist would cite, broader than needed, or not fitting. Passages whose own motif is
judged not to fit (about 15%) are dropped. Results on the test split, 1,600 queries from 30 unseen tale
types, full precision with readings, top 10 / MRR:

| | listed motif | any fitting motif |
|---|---|---|
| version 1 | 0.47 / 0.28 | 0.75 / 0.50 |
| the site | 0.51 / 0.31 | 0.79 / 0.54 |

The difference is +4.3 points in the top 10 [95% interval +2.6, +6.1], resampling tale types. By kind of
query (the site, any fitting motif): passages 0.64, vague lines 0.80, descriptions 0.85, keywords 0.88.
In the browser, scored on the listed motif only: 0.49 / 0.30 against 0.44 / 0.25.

The training split's 923 tales give 4,740 queries (after `check` drops passages whose motif does not fit).
A first run on all four kinds with mined hard negatives, as for the ATU fragments, made the encoder
worse (−2 points on the listed motif). Using only the written queries, with random negatives, made it
better. The likely reason is that a passage expresses several motifs, so the encoder's near misses are
often right answers, and training against them pushes right answers away; random negatives cannot.
Doubling the weight of the ATU pairs made every score worse, ATU included.

Two small hand-made sets, run with `node tools/eval_static.mjs [file]` against the site's own search
code (install the Node dependencies first with `cd tools && npm install`):

| | | right motif first | in top 10 | MRR |
|---|---|---|---|---|
| `pipeline/devset.json` | 30 descriptions | 0.73 | 0.97 | 0.84 |
| `pipeline/heldout.json` | 40 queries written before running either system | 0.85 | 0.95 | 0.89 |

Both were also looked at while choosing among trained encoders, and some of their target motifs occur in
the ATU training fragments of other tale types, so the ATU test set is the fairer measure.

**Against the old MOMFER.** The original server is offline. `tools/momfer_legacy.py` therefore
reconstructs its search from the 2015 source: the same `tmi.json`, Whoosh schema and field boosts,
WordNet hypernym keywords, and query expansion. NLTK's WordNet 3.0 stands in for the copy bundled with
Pattern, and Whoosh-Reloaded for Whoosh. On the 40 held-out queries:

| | descriptions: first / top 10 | keywords: first / top 10 | all: MRR |
|---|---|---|---|
| Spindle | 0.90 / 1.00 | 0.80 / 0.90 | 0.89 |
| MOMFER (reconstructed) | 0.45 / 0.60 | 0.65 / 0.80 | 0.61 |

```sh
uv run --with whoosh-reloaded --with nltk python tools/momfer_legacy.py pipeline/heldout.json > data/build/heldout_momfer.json
node tools/compare.mjs pipeline/heldout.json data/build/heldout_momfer.json
```

MOMFER misses outright what it cannot match word for word: "werewolf" (Thompson wrote *werwolf*), or "a
trickster gets stuck to a figure covered in tar". The current model in turn misses two keyword
queries that version 1 found and MOMFER finds at ranks 4 and 8, "fairy ring" and "buried treasure".

**What else was tried.** Training additionally on 226,000 search phrases written by Haiku for every
motif (`--synthetic`, 40 minutes) gave no gain over the three-minute model. Neither did more epochs, a
higher learning rate, or starting from that larger model. Adding the motif's place in the index
("Magic › Magic power of prophecy › …") to its text, or scoring a motif partly by how well the query
matches its whole branch, did not help either; the readings were already written with that context.
bge-small (34 MB, trained the same way) scored about five points lower on the tale queries.

**Choosing the base model.** Before any training, `pipeline/experiment.py` compared bge-base, bge-large, bge-m3, e5-large-v2,
mxbai-embed-large, gte-modernbert and Qwen3-Embedding-0.6B on the development set. Two findings went
against expectation:

- Qwen3-Embedding and a cross-encoder reranker (bge-reranker-v2-m3) both did *worse*. Thompson's
  headlines are very short, and these models favour the shortest, most generic ones ("Magic objects.").
- Reducing stock bge-base to 256 int8 dimensions cost nothing measurable on that set.

An ensemble with bge-m3 scored about three points higher on the development set, but it is too large
to run in a browser.

**Reading whole tales.** An earlier, server-based version could also annotate a pasted tale sentence by
sentence, optionally with a local language model. It found only about a third to a half of the motifs a
folklorist would assign, so it was dropped in favour of the static site. That version is in
`archive/spindle-server-version-2026-10-29.tar.gz`.

## Layout

```
docs/       the website (GitHub Pages)
            index.html, static/app.js (views), static/store.js (data), static/search.js (search),
            static/lists.js (motif lists), static/app.css
            art/   papercut illustrations          data/  exported by pipeline/static.py
pipeline/   parse.py, build.py, index.py, static.py     build the data
            places.py, atlas.py                         the gazetteer and the world map
            readings.py, finetune.py                    plain-language readings; training the encoder
            atu_bench.py, compare.py, devset.json, heldout.json, experiment.py   benchmarks and model comparison
            tale_bench.py                               queries from real tales, judged results
            desc_bench.py, desc_wiki.json               motif descriptions from Wikipedia and generated ones
tools/      eval_static.mjs, compare.mjs   benchmarks in Node, using the site's search code
            momfer_legacy.py               the reconstructed MOMFER
            artgen.py, shoot.py            illustrations; screenshots (Playwright + system Chrome)
```
