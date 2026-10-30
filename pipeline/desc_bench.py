"""A benchmark of motif *descriptions*: how people put a motif in words when they look for it.

    uv run --with mwparserfromhell python pipeline/desc_bench.py wiki   # candidate sentences from English Wikipedia
    source ~/.anthropic_env && uv run --group llm python pipeline/desc_bench.py curate
    source ~/.anthropic_env && uv run --group llm python pipeline/desc_bench.py synth --n 1000

wiki: articles that cite Thompson motif numbers in their prose ("the motif of the
substituted caps, K1611"); every sentence naming a motif in the index becomes a
candidate, the number removed.

curate: a language model proposes, per candidate, whether to keep it and which
span of the sentence carries the description, by deleting words only (never
adding or changing any); spans that are not in the sentence, still hold a motif
number or copy the headline are dropped by the script. The result
(data/build/desc_wiki_curated.json) was then reviewed by hand into
pipeline/desc_wiki.json: sentences that do not describe the cited motif, or
whose citation is wrong, were removed. Wikipedia text is CC BY-SA 4.0; each
query keeps its article title and revision.

synth: for motifs sampled evenly across the 23 branches, a language model (not the
one that wrote the readings) writes what a folklorist or student might type when
half-remembering the motif: a few keywords, and a sentence. Queries that copy the
headline are dropped. Output: data/build/desc_synth.json.
"""

import argparse
import json
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "wikipedia"
BUILD = ROOT / "data" / "build"
UA = "spindle-research/0.1 (https://github.com/fbkarsdorp/spindle)"
API = "https://en.wikipedia.org/w/api.php"

SEARCHES = [
    'insource:"Motif-Index"',
    'insource:"Folk-Literature"',
    'insource:"Thompson motif"',
    'motif insource:/[Mm]otifs? [A-HJ-NP-Z][0-9]{1,4}/',
    'tale insource:/\\([A-HJ-NP-Z][0-9]{1,4}(\\.[0-9]+)*[,;)]/ Thompson',
    'myth insource:/\\([A-HJ-NP-Z][0-9]{1,4}(\\.[0-9]+)*[,;)]/ Thompson',
]
MOTIF = re.compile(r"(?<![A-Za-z0-9])([A-HJ-NP-Z]\d{1,4}(?:\.\d+)*)(?![\d.]*\d)")


def api(**params):
    params = {"format": "json", "formatversion": "2", **params}
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(params), headers={"User-Agent": UA})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.load(r)
            # Wikipedia limits how many regex searches run at once: wait and try again
            if d.get("error", {}).get("code") == "cirrussearch-regex-too-busy-error":
                raise RuntimeError("busy")
            return d
        except Exception:
            time.sleep(3 * 2 ** attempt)
    raise RuntimeError(f"Wikipedia API failed for {params}")


def titles():
    out = []
    for q in SEARCHES:
        offset = 0
        while offset is not None:
            d = api(action="query", list="search", srsearch=q, srlimit=500, sroffset=offset, srnamespace=0)
            out += [x["title"] for x in d["query"]["search"]]
            offset = d.get("continue", {}).get("sroffset")
    return sorted(set(out))


def wikitext(titles):
    """Articles' wiki source (cached), fetched fifty at a time."""
    RAW.mkdir(parents=True, exist_ok=True)
    fname = lambda t: RAW / (re.sub(r"[^\w.-]+", "_", t)[:150] + ".json")
    todo = [t for t in titles if not fname(t).exists()]
    for i in range(0, len(todo), 50):
        d = api(action="query", prop="revisions", rvprop="ids|content", rvslots="main", titles="|".join(todo[i:i + 50]))
        for page in d["query"]["pages"]:
            rev = (page.get("revisions") or [{}])[0]
            rec = {"title": page["title"], "revid": rev.get("revid"), "wikitext": rev.get("slots", {}).get("main", {}).get("content", "")}
            json.dump(rec, open(fname(page["title"]), "w"), ensure_ascii=False)
        time.sleep(0.5)
    return [json.load(open(fname(t))) for t in titles if fname(t).exists()]


def cited_sentences(wikitext, motifs):
    """(sentence, motif ids) for motifs cited in the prose ("the motif K1611") or in a
    footnote that names the Motif-Index or Thompson, credited to the sentence the
    footnote is attached to."""
    import mwparserfromhell as mw

    text, marks = [], []  # plain prose so far; (offset, ids) of each citation
    def walk(nodes):
        for node in nodes:
            # a footnote: <ref>…</ref>, or a note template such as {{efn|…}} or {{Refn|…}}
            note = (isinstance(node, mw.nodes.Tag) and str(node.tag).lower() == "ref") or (
                isinstance(node, mw.nodes.Template) and re.match(r"(?i)\s*(refn|efn(-[a-z]+)?|note)\s*$", str(node.name)))
            if note:
                inner = str(node.contents or "") if isinstance(node, mw.nodes.Tag) else " ".join(str(p.value) for p in node.params)
                if re.search(r"[Mm]otif|Thompson", inner):
                    ids = [m for m in MOTIF.findall(inner) if m in motifs]
                    if ids:
                        marks.append((sum(map(len, text)), ids))
            elif isinstance(node, mw.nodes.Tag) and str(node.tag).lower() in ("b", "i", "span", "small", "sup", "sub"):
                walk(node.contents.nodes if node.contents else [])
            elif isinstance(node, mw.nodes.Tag):
                continue
            elif isinstance(node, mw.nodes.Wikilink):
                t = str(node.text if node.text is not None else node.title)
                if not re.match(r"(?i)(file|image|category):", str(node.title)):
                    text.append(t)
            elif isinstance(node, (mw.nodes.Template, mw.nodes.Comment, mw.nodes.ExternalLink)):
                if isinstance(node, mw.nodes.ExternalLink) and node.title:
                    text.append(str(node.title))
            elif isinstance(node, mw.nodes.Heading):
                text.append("\n\n")
            elif isinstance(node, mw.nodes.HTMLEntity):
                text.append(node.normalize())
            else:
                text.append(str(node).replace("'''", "").replace("''", ""))
    walk(mw.parse(wikitext).nodes)
    prose = "".join(text)
    # sentence spans
    spans, start = [], 0
    for m in re.finditer(r"(?<=[a-z\)”\"'][.!?])\s+(?=[A-Z“\"(])|\n+", prose):
        spans.append((start, m.start()))
        start = m.end()
    spans.append((start, len(prose)))
    out = {}
    for off, ids in marks:
        for a, b in spans:
            if a < off <= b + 1:
                out.setdefault(prose[a:b].strip(), set()).update(ids)
                break
    for a, b in spans:
        s = prose[a:b].strip()
        if re.search(r"[Mm]otif", s):
            ids = [m for m in MOTIF.findall(s) if m in motifs]
            if ids:
                out.setdefault(s, set()).update(ids)
    return [(s, sorted(ids)) for s, ids in out.items() if 20 <= len(s) <= 700]


def wiki():
    data = json.load(open(ROOT / "data" / "index" / "tmi.json"))
    motifs = {n["id"]: n for n in data["nodes"] if n["kind"] == "motif"}
    ts = titles()
    print(f"{len(ts)} articles", file=sys.stderr)
    cands = []
    for rec in wikitext(ts):
        for s, ids in cited_sentences(rec["wikitext"], motifs):
            cands.append({"title": rec["title"], "revid": rec["revid"], "sentence": s, "ids": ids,
                          "headlines": {m: motifs[m]["title"] for m in ids}})
    BUILD.mkdir(parents=True, exist_ok=True)
    json.dump(cands, open(BUILD / "desc_wiki_candidates.json", "w"), ensure_ascii=False, indent=1)
    print(f"{len(cands)} candidate sentences from {len({c['title'] for c in cands})} articles", file=sys.stderr)


# ------------------------------------------------------------------ synthetic

SYSTEM = """You help build a test of a search engine for Stith Thompson's Motif-Index of Folk-Literature. People search it by describing a motif in their own words.

For each motif you receive (number, Thompson's headline, his note if any, and its place in the index), write two search queries that a folklorist, a student, or a curious reader might type when they half-remember this motif and do not know Thompson's wording:

keywords: 2 to 5 words, the way people type into a search box.
description: one plain sentence of 6 to 16 words describing what happens or what the motif is.

Rules:
- Use everyday words. Avoid the distinctive words of Thompson's headline whenever an ordinary paraphrase exists (write "werewolf" for "werwolf", "a giant" for "an ogre" only if natural, "turned into a stone" for "transformation to stone" and so on).
- Describe only what the headline, note and place imply. Do not add names, cultures, tale titles, or details.
- No motif numbers, no quotation marks, no mention of Thompson or the index.
- Vary the phrasing across motifs, as different people would.

Return exactly one entry per motif, with its number unchanged."""

SCHEMA = {
    "type": "object",
    "properties": {"motifs": {"type": "array", "items": {
        "type": "object",
        "properties": {"id": {"type": "string"}, "keywords": {"type": "string"}, "description": {"type": "string"}},
        "required": ["id", "keywords", "description"], "additionalProperties": False}}},
    "required": ["motifs"], "additionalProperties": False,
}

STOP = set("a an the of to in on and or by for with from as at is be his her its their who which that this into out off up "
           "own one two man woman men women person people thing things".split())


def content(s):
    return {w[:6] for w in re.findall(r"[a-z]+", s.lower()) if w not in STOP and len(w) > 2}


def copies_headline(q, headline):
    """True when most of a query's content words come straight from the headline."""
    c, h = content(q), content(headline)
    return bool(c) and len(c & h) / len(c) >= 0.6


def sample(nodes, ids, n, seed=5):
    """Motifs drawn evenly from the 23 branches."""
    rng = random.Random(seed)
    by = {}
    for i in ids:
        by.setdefault(i[0], []).append(i)
    per = -(-n // len(by))
    out = []
    for L in sorted(by):
        out += rng.sample(by[L], min(per, len(by[L])))
    return out


def synth(n, model, workers):
    sys.path.insert(0, str(ROOT / "pipeline"))
    from readings import describe, load_index  # the same description of a motif as the readings get

    import anthropic
    from concurrent.futures import ThreadPoolExecutor

    nodes, ids = load_index()
    todo = sample(nodes, ids, n)
    client = anthropic.Anthropic(max_retries=4)
    usage = {"in": 0, "out": 0}

    def work(chunk):
        kw = dict(model=model, max_tokens=8000, system=SYSTEM,
                  output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
                  messages=[{"role": "user", "content": json.dumps([describe(nodes, m) for m in chunk], ensure_ascii=False)}])
        resp = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kw)
        usage["in"] += resp.usage.input_tokens
        usage["out"] += resp.usage.output_tokens
        text = next((b.text for b in resp.content if b.type == "text"), "{}")
        return json.loads(text).get("motifs", [])

    chunks = [todo[i:i + 20] for i in range(0, len(todo), 20)]
    with ThreadPoolExecutor(workers) as ex:
        got = [m for part in ex.map(work, chunks) for m in part]
    out, dropped = [], 0
    for m in got:
        if m["id"] not in nodes:
            continue
        for kind in ("keywords", "description"):
            q = m[kind].strip()
            if copies_headline(q, nodes[m["id"]]["title"]):
                dropped += 1
                continue
            out.append({"q": q, "gold": [m["id"]], "kind": kind, "motif": m["id"]})
    json.dump(out, open(BUILD / "desc_synth.json", "w"), ensure_ascii=False, indent=0)
    pin, pout = {"claude-sonnet-5-5": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0)}.get(model, (0, 0))
    print(f"{len(out)} queries for {len({x['motif'] for x in out})} motifs, {dropped} dropped as copies of the headline; "
          f"{usage['in']:,} tokens in, {usage['out']:,} out, ${usage['in'] / 1e6 * pin + usage['out'] / 1e6 * pout:.2f}",
          file=sys.stderr)


# ------------------------------------------------------------------ curation

CURATE = """You curate a test set for a search engine over Stith Thompson's Motif-Index. Each item is a sentence from an English Wikipedia article that cites a motif (its number and Thompson's headline are given). We want to know how people describe motifs in their own words.

For each item decide:
keep: true only if the sentence, or one contiguous part of it, says in the writer's own words what the motif is or what happens in it, clearly enough that a reader could recognise the cited motif without the number. False if it only names the motif by quoting Thompson's headline, only cites a number, or is about something else (genes, weapons, editions).
span: if kept, the shortest contiguous stretch of the sentence, copied character for character, that carries the description. Cut the citation, the motif number, phrases such as "is motif ... in the Motif-Index", and any quotation of Thompson's headline. Never add, change or reorder words.
kind: "description" if the span characterises the motif in general ("a girl must not look back"); "plot" if it narrates an event in one particular tale ("the cat spreads the oil on her fur and becomes a princess").

Return one entry per item, with its number unchanged."""

CURATE_SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {
        "type": "object",
        "properties": {"i": {"type": "integer"}, "keep": {"type": "boolean"}, "span": {"type": "string"},
                       "kind": {"type": "string", "enum": ["description", "plot"]}},
        "required": ["i", "keep", "span", "kind"], "additionalProperties": False}}},
    "required": ["items"], "additionalProperties": False,
}


def curate(model):
    import anthropic

    cands = json.load(open(BUILD / "desc_wiki_candidates.json"))
    client = anthropic.Anthropic(max_retries=4)
    decisions, tokens = {}, [0, 0]
    for start in range(0, len(cands), 25):
        batch = [{"i": start + k, "sentence": c["sentence"], "cited": c["headlines"]} for k, c in enumerate(cands[start:start + 25])]
        resp = client.beta.messages.create(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", model=model, max_tokens=8000, system=CURATE,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": CURATE_SCHEMA}},
            messages=[{"role": "user", "content": json.dumps(batch, ensure_ascii=False)}])
        tokens[0] += resp.usage.input_tokens
        tokens[1] += resp.usage.output_tokens
        text = next((b.text for b in resp.content if b.type == "text"), "{}")
        for d in json.loads(text).get("items", []):
            decisions[d["i"]] = d
    out, why = [], {"not kept": 0, "not in the sentence": 0, "has a number": 0, "copies the headline": 0, "too short": 0}
    for i, c in enumerate(cands):
        d = decisions.get(i)
        span = (d or {}).get("span", "").strip(" ,;:.")
        if not d or not d["keep"]:
            why["not kept"] += 1
        elif span not in c["sentence"]:           # delete-only: the span must be in the sentence as it stands
            why["not in the sentence"] += 1
        elif MOTIF.search(span):
            why["has a number"] += 1
        elif any(copies_headline(span, h) for h in c["headlines"].values()):
            why["copies the headline"] += 1
        elif len(span.split()) < 4:
            why["too short"] += 1
        else:
            out.append({"q": span, "gold": c["ids"], "kind": d["kind"], "source": f"en.wikipedia.org: {c['title']} (revision {c['revid']})"})
    json.dump(out, open(BUILD / "desc_wiki_curated.json", "w"), ensure_ascii=False, indent=1)
    pin, pout = {"claude-sonnet-5-5": (2.0, 10.0)}.get(model, (0, 0))
    print(f"kept {len(out)} of {len(cands)}; dropped: {why}; ${tokens[0] / 1e6 * pin + tokens[1] / 1e6 * pout:.2f}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["wiki", "curate", "synth"])
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--model", default="claude-sonnet-5-5")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    if args.mode == "wiki":
        wiki()
    elif args.mode == "curate":
        curate(args.model)
    else:
        synth(args.n, args.model, args.workers)


if __name__ == "__main__":
    main()
