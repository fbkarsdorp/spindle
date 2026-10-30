"""A benchmark from real tales: passages of Ashliman's folktexts that express a
motif, and search queries written blind from those passages.

    source ~/.anthropic_env && uv run --group llm python pipeline/tale_bench.py build --split dev --n 20
    source ~/.anthropic_env && uv run --group train --group llm python pipeline/tale_bench.py judge --split dev
    source ~/.anthropic_env && uv run --group llm python pipeline/tale_bench.py check --split train

Each tale in the trilogy dataset (data/raw/trilogy/aft.csv) has an ATU type, and
Uther's summary of that type cites Thompson motifs; so we know, per tale, which
motifs it probably contains, but not where. Two steps close that gap, in the
manner of Alyami & Finlayson (2026) for the Arabian Nights:

locate: a language model reads the tale and its type's motifs and quotes, for
    each motif, the passage that expresses it (or says it is absent). Quotes that
    are not in the tale verbatim are dropped. The passage itself becomes a query
    ("passage"), its gold the motif.

write: a second call sees only the passage, with the words that carry the
    episode marked, never the motif's number or Thompson's wording, and writes
    what someone half-remembering the episode would type: a vague line, a fuller
    description, and keywords.

judge: Uther's motifs belong to the tale *type*: a telling lacks some of them
    (dropped by locate) and contains others he does not list. So one cited motif
    is too narrow an answer key. For each passage, the motifs the encoders rank
    highest for any of its queries are pooled, and a language model judges each
    against the marked episode: "cite" (a folklorist annotating this telling
    would cite it here), "broader" (true of the episode but more general than
    needed) or "no". A passage whose own gold motif is judged "no" was located
    wrongly and is dropped. Judgments are kept per passage and motif, so a new
    model only needs its unseen candidates judged.

check: the cheap version of judge, for training data: only each passage's own
    motif is judged, ten passages to a call, and passages whose motif does not
    fit are dropped. Output: data/build/tale_{split}_checked.json.

Splits follow the ATU fragments (pipeline/atu_bench.py, by tale type), so test
tales are of types the encoder never saw. The tales are not ours to publish;
output stays in data/build (git-ignored):

    data/build/tale_{split}.json        [{q, gold, near, kind, atu, tale, focus?}, ...]
    data/build/tale_{split}_judgments.json   {tale|focus: {motif: cite|broader|no}}
"""

import argparse
import csv
import json
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "trilogy"
BUILD = ROOT / "data" / "build"
sys.path.insert(0, str(ROOT / "pipeline"))
from atu_bench import clean, split_of  # noqa: E402
from desc_bench import content  # noqa: E402

PRICE = {"claude-sonnet-5-5": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0)}


def type_motifs(motifs):
    """Per ATU type: the motifs Uther cites, each with the summary fragment that cites it."""
    csv.field_size_limit(10 ** 9)
    out = {}
    for r in csv.DictReader(open(RAW / "atu_df.csv", encoding="utf-8")):
        text, prev, got = r["tale_type"], 0, {}
        for m in re.finditer(r"\[([^\]]+)\]", text):
            frag = clean(text[prev:m.start()])
            prev = m.end()
            for x in re.split(r"[,;]", m.group(1)):
                x = x.strip().rstrip(".")
                if x in motifs and x not in got:
                    got[x] = frag
        out[r["atu_id"]] = got
    return out


def tales(split, n, seed=3):
    nodes = {n["id"]: n for n in json.load(open(ROOT / "data" / "index" / "tmi.json"))["nodes"]}
    motifs = {i for i, x in nodes.items() if x["kind"] == "motif"}
    tm = type_motifs(motifs)
    csv.field_size_limit(10 ** 9)
    rows = [dict(r, i=k) for k, r in enumerate(csv.DictReader(open(RAW / "aft.csv", encoding="utf-8")))]
    rows = [r for r in rows if split_of(r["atu_id"]) == split and tm.get(r["atu_id"])]
    if n:
        rows = random.Random(seed).sample(rows, min(n, len(rows)))
    return nodes, tm, rows


# --------------------------------------------------------------------- locate

LOCATE = """You help build a test set for a search engine over Stith Thompson's Motif-Index of Folk-Literature. You get one folktale and the motifs that the tale type it belongs to usually contains. A particular telling often lacks some of them.

For each motif decide whether this telling expresses it. If it does, quote the passage where it happens: a stretch of the tale, copied character for character, from which a reader could recognise the motif without knowing the rest of the story (usually one or two sentences, at most three; include the sentence that makes it clear, for instance that the meat is the hero's own son, or that the rescue happens at the gallows). Then mark, inside that passage, the focus: the few consecutive words, again copied exactly, where the motif's event or element itself is told.

Be strict: the motif must actually happen or appear in this telling, not merely be similar in spirit. If it is absent, set present to false and leave passage and focus empty."""

LOCATE_SCHEMA = {
    "type": "object",
    "properties": {"motifs": {"type": "array", "items": {
        "type": "object",
        "properties": {"id": {"type": "string"}, "present": {"type": "boolean"},
                       "passage": {"type": "string"}, "focus": {"type": "string"}},
        "required": ["id", "present", "passage", "focus"], "additionalProperties": False}}},
    "required": ["motifs"], "additionalProperties": False,
}

# --------------------------------------------------------------------- write

WRITE = """Someone once read or heard a folktale and now wants to find the motif behind one of its episodes in a motif index. They do not know how the index words things, nor the motif's number. You get a passage from a tale with the episode's key words marked between ⟦ and ⟧, and a little of the story before and after it.

Write what they might type into the search box, in three forms:
vague: a half-remembered line, 4 to 10 words, the way a person recalls a story element weeks later.
description: one sentence, 10 to 25 words, describing the episode as a recurring kind of event rather than this telling, so no names of people or places.
keywords: 2 to 5 words.

Describe what is marked, not the rest of the passage. Use everyday words."""

WRITE_SCHEMA = {
    "type": "object",
    "properties": {"queries": {"type": "array", "items": {
        "type": "object",
        "properties": {"k": {"type": "integer"}, "vague": {"type": "string"},
                       "description": {"type": "string"}, "keywords": {"type": "string"}},
        "required": ["k", "vague", "description", "keywords"], "additionalProperties": False}}},
    "required": ["queries"], "additionalProperties": False,
}


JUDGE = """You judge search results for a search engine over Stith Thompson's Motif-Index of Folk-Literature. You get a passage from a folktale with one episode marked between ⟦ and ⟧, and candidate motifs (number, headline, sometimes a note).

A little of the story before and after the passage is given for context. List the candidates that fit the marked episode, in two groups:
cite: a folklorist annotating this telling would cite this motif for the marked episode. One episode often instances several motifs (an actor, an object, an incident), so several candidates can fit. Folklorists cite motifs across the usual variation between tellings: a fox where the headline has a wolf, bones hidden where it has buried, a dog where it has a genie, still count.
broader: true of the episode, but so general that a folklorist would cite a more specific motif instead (for example "Helpful animal" for an episode with a helpful cat).
Leave out every other candidate: motifs that do not fit, that fit only another part of the story, or whose central point the episode lacks.

Judge each candidate by its headline and note, not by its number."""

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {"cite": {"type": "array", "items": {"type": "string"}},
                   "broader": {"type": "array", "items": {"type": "string"}}},
    "required": ["cite", "broader"], "additionalProperties": False,
}


CHECK = """You check a training set for a search engine over Stith Thompson's Motif-Index of Folk-Literature. Each item is a passage from a folktale with one episode marked between ⟦ and ⟧ (a little of the story before and after is given for context), and one motif.

List the items whose motif fits the marked episode: a folklorist annotating this telling would cite it there, or it is true of the episode though general. Folklorists cite motifs across the usual variation between tellings (a fox where the headline has a wolf, bones hidden where it has buried). Leave out items whose motif does not fit, fits only another part of the story, or whose central point the episode lacks."""

CHECK_SCHEMA = {
    "type": "object",
    "properties": {"fits": {"type": "array", "items": {"type": "integer"}}},
    "required": ["fits"], "additionalProperties": False,
}


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def around(text, passage, n=2):
    """The n sentences before and after a passage in a tale."""
    text = norm(text)
    i = text.find(passage)
    if i < 0:
        return "", ""
    split = lambda t: re.split(r"""(?<=[.!?'"’”])\s+(?=[A-Z'"‘“])""", t)
    before = [x for x in split(text[:i].strip()) if x][-n:]
    after = [x for x in split(text[i + len(passage):].strip()) if x][:n]
    return " ".join(before), " ".join(after)


def marked(text, passage, focus):
    before, after = around(text, passage)
    return {"before": before, "passage": passage.replace(focus, "⟦" + focus + "⟧", 1), "after": after}


class Claude:
    def __init__(self, model):
        import anthropic

        self.client, self.model, self.usage = anthropic.Anthropic(max_retries=4), model, [0, 0]

    def __call__(self, system, schema, payload, effort):
        resp = self.client.beta.messages.create(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", model=self.model, max_tokens=16000,
            system=system, output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}])
        self.usage[0] += resp.usage.input_tokens
        self.usage[1] += resp.usage.output_tokens
        return json.loads(next((b.text for b in resp.content if b.type == "text"), "{}"))

    def cost(self):
        pin, pout = PRICE.get(self.model, (0, 0))
        return f"{self.usage[0]:,} tokens in, {self.usage[1]:,} out, ${self.usage[0] / 1e6 * pin + self.usage[1] / 1e6 * pout:.2f}"


def build(args):
    nodes, tm, rows = tales(args.split, args.n)
    call = Claude(args.model)

    def locate(r):
        ms = tm[r["atu_id"]]
        payload = {"tale": {"title": r["tale_title"], "text": r["text"]},
                   "motifs": [{"id": m, "headline": nodes[m]["title"], "in the type summary": ms[m]} for m in ms]}
        got = call(LOCATE, LOCATE_SCHEMA, payload, "medium").get("motifs", [])
        text = norm(r["text"])
        found, why = [], {"absent": 0, "not verbatim": 0}
        for g in got:
            if g["id"] not in ms:
                continue
            p, f = norm(g["passage"]), norm(g["focus"])
            if not g["present"]:
                why["absent"] += 1
            elif not p or p not in text or (f and f not in p):
                why["not verbatim"] += 1
            else:
                found.append({"motif": g["id"], "passage": p, "focus": f or p})
        return r, found, why

    with ThreadPoolExecutor(args.workers) as ex:
        located = list(ex.map(locate, rows))
    stats = {"pairs": sum(len(tm[r["atu_id"]]) for r in rows), "found": 0, "absent": 0, "not verbatim": 0}
    for _, found, why in located:
        stats["found"] += len(found)
        stats["absent"] += why["absent"]
        stats["not verbatim"] += why["not verbatim"]

    def write(item):
        r, found = item
        if not found:
            return r, found, []
        ps = [{"k": k, **marked(r["text"], f["passage"], f["focus"])} for k, f in enumerate(found)]
        return r, found, call(WRITE, WRITE_SCHEMA, {"passages": ps}, "low").get("queries", [])

    with ThreadPoolExecutor(args.workers) as ex:
        written = list(ex.map(write, [(r, f) for r, f, _ in located]))

    out = []
    for r, found, qs in written:
        by = {q["k"]: q for q in qs}
        for k, f in enumerate(found):
            m = f["motif"]
            near = {m} | ({nodes[m]["parent"]} if nodes.get(nodes[m]["parent"], {}).get("kind") == "motif" else set())
            near |= {c for c in nodes[m]["children"] if nodes[c]["kind"] == "motif"}
            base = {"gold": [m], "near": sorted(near), "atu": r["atu_id"], "tale": r["i"],
                    "passage": f["passage"], "focus": f["focus"]}
            out.append({"q": f["passage"], "kind": "passage", **base})
            for kind in ("vague", "description", "keywords"):
                if by.get(k, {}).get(kind, "").strip():
                    out.append({"q": by[k][kind].strip(), "kind": kind, **base})

    path = Path(args.out) if args.out else BUILD / f"tale_{args.split}.json"
    json.dump(out, open(path, "w"), ensure_ascii=False, indent=1)
    print(f"{len(rows)} tales: {stats['found']} of {stats['pairs']} tale-motif pairs found "
          f"({stats['absent']} absent, {stats['not verbatim']} not verbatim) -> {len(out)} queries in {path.name}; "
          f"{call.cost()}", file=sys.stderr)


def pools(items, encoders, depth):
    """Per item, the motifs each encoder ranks in its top `depth` (headline and
    reading vectors, the higher score counting, as on the site)."""
    import numpy as np
    from sentence_transformers import SentenceTransformer

    from finetune import PROMPT

    ids = json.load(open(ROOT / "data" / "index" / "ids.json"))
    out = [set() for _ in items]
    for tag in encoders:
        E = np.load(BUILD / "emb" / f"{tag}__note.npy").astype(np.float32)
        R = np.load(BUILD / "emb" / f"{tag}__reading__claude-haiku-5-5.npy").astype(np.float32)
        model = SentenceTransformer(str(ROOT / "data" / "models" / tag), device="mps")
        Q = model.encode([PROMPT + x["q"] for x in items], batch_size=64, normalize_embeddings=True, convert_to_numpy=True)
        S = np.maximum(Q @ E.T, Q @ R.T)
        for k, s in enumerate(S):
            out[k].update(ids[i] for i in np.argpartition(-s, depth)[:depth])
    return out


def judge(args):
    nodes = {n["id"]: n for n in json.load(open(ROOT / "data" / "index" / "tmi.json"))["nodes"]}
    path = Path(args.out) if args.out else BUILD / f"tale_{args.split}.json"
    items = json.load(open(path))
    # the episode each query was written from: older files keep the passage only on the passage query
    ep = {(x["tale"], x["gold"][0]): (x["q"], x["focus"]) for x in items if x["kind"] == "passage"}
    key = lambda x: f"{x['tale']}|{ep[(x['tale'], x['gold'][0])][1]}"
    cand = {}
    for x, pool in zip(items, pools(items, args.encoders, args.depth)):
        cand.setdefault(key(x), set()).update(pool | set(x["gold"]))

    jpath = path.with_name(path.stem + "_judgments.json")
    csv.field_size_limit(10 ** 9)
    texts = [r["text"] for r in csv.DictReader(open(RAW / "aft.csv", encoding="utf-8"))]
    J = json.load(open(jpath)) if jpath.exists() else {}
    call = Claude(args.model)
    rng = random.Random(1)

    def work(k):
        tale, focus = k.split("|", 1)
        x = next(y for y in items if key(y) == k)
        passage = ep[(x["tale"], x["gold"][0])][0]
        todo = sorted(cand[k] - set(J.get(k, {})))
        if not todo:
            return k, {}
        rng.shuffle(todo)
        payload = {**marked(texts[x["tale"]], passage, focus),
                   "candidates": [{"id": m, "headline": nodes[m]["title"], **({"note": nodes[m]["note"][:300]} if nodes[m].get("note") else {})}
                                  for m in todo]}
        got = call(JUDGE, JUDGE_SCHEMA, payload, "medium")
        v = {m: "no" for m in todo}
        v.update({m: "broader" for m in got.get("broader", []) if m in v})
        v.update({m: "cite" for m in got.get("cite", []) if m in v})
        return k, v

    with ThreadPoolExecutor(args.workers) as ex:
        for k, v in ex.map(work, sorted(cand)):
            J.setdefault(k, {}).update(v)
    json.dump(J, open(jpath, "w"), ensure_ascii=False, indent=0)

    kept, dropped = [], set()
    for x in items:
        v = J.get(key(x), {})
        if v.get(x["gold"][0]) == "no":
            dropped.add(key(x))
            continue
        kept.append({**x, "cite": sorted(m for m, w in v.items() if w == "cite"),
                     "broader": sorted(m for m, w in v.items() if w == "broader")})
    out = path.with_name(path.stem + "_judged.json")
    json.dump(kept, open(out, "w"), ensure_ascii=False, indent=1)
    n = sum(len(v) for k, v in J.items() if k in cand)
    cites = sum(w == "cite" for k, v in J.items() if k in cand for w in v.values())
    print(f"{len(cand)} passages, {n} judgments ({cites} cite); {len(dropped)} passages dropped as wrongly located; "
          f"{len(kept)} queries in {out.name}; {call.cost()}", file=sys.stderr)


def check(args):
    nodes = {n["id"]: n for n in json.load(open(ROOT / "data" / "index" / "tmi.json"))["nodes"]}
    path = Path(args.out) if args.out else BUILD / f"tale_{args.split}.json"
    items = json.load(open(path))
    csv.field_size_limit(10 ** 9)
    texts = [r["text"] for r in csv.DictReader(open(RAW / "aft.csv", encoding="utf-8"))]
    passages = [x for x in items if x["kind"] == "passage"]
    call = Claude(args.model)

    def work(start):
        batch = passages[start:start + 10]
        payload = [{"k": start + j, **marked(texts[x["tale"]], x["q"], x["focus"]),
                    "motif": {"headline": nodes[x["gold"][0]]["title"],
                              **({"note": nodes[x["gold"][0]]["note"][:300]} if nodes[x["gold"][0]].get("note") else {})}}
                   for j, x in enumerate(batch)]
        return set(call(CHECK, CHECK_SCHEMA, {"items": payload}, "low").get("fits", []))

    with ThreadPoolExecutor(args.workers) as ex:
        fits = set().union(*ex.map(work, range(0, len(passages), 10)))
    ok = {(passages[k]["tale"], passages[k]["focus"], passages[k]["gold"][0]) for k in fits if k < len(passages)}
    kept = [x for x in items if (x["tale"], x["focus"], x["gold"][0]) in ok]
    out = path.with_name(path.stem + "_checked.json")
    json.dump(kept, open(out, "w"), ensure_ascii=False, indent=1)
    print(f"{len(ok)} of {len(passages)} passages fit their motif; {len(kept)} queries in {out.name}; {call.cost()}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["build", "judge", "check"])
    ap.add_argument("--split", default="dev", choices=["train", "dev", "test"])
    ap.add_argument("--n", type=int, default=20, help="build: tales to sample (0 = all)")
    ap.add_argument("--model", default="claude-sonnet-5-5")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", default=None, help="the queries file (default data/build/tale_{split}.json)")
    ap.add_argument("--encoders", nargs="+", default=["spindle-bge-base-motifs", "spindle-bge-small-sm-lr5"],
                    help="judge: fine-tuned models in data/models whose top results are pooled")
    ap.add_argument("--depth", type=int, default=10, help="judge: how many of each encoder's results to pool")
    args = ap.parse_args()
    {"build": build, "judge": judge, "check": check}[args.mode](args)


if __name__ == "__main__":
    main()
