"""A faithful Python 3 reconstruction of MOMFER's search (2015), for comparison.

The original runs on Python 2 with the Pattern library; this mirrors its
indexer.py and app/expand.py: the old tmi.json, the same Whoosh schema and
field boosts, WordNet hypernyms of every lemma in a 'wn' keyword field, and
queries expanded with the first hypernym of each term. Differences: NLTK's
WordNet 3.0 instead of Pattern's bundled copy, and Whoosh-Reloaded.

    uv run --with whoosh-reloaded --with nltk python tools/momfer_legacy.py pipeline/heldout.json
"""

import copy
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("NLTK_DATA", str(ROOT / "data" / "build" / "nltk_data"))

import nltk  # noqa: E402

try:
    from nltk.corpus import wordnet as WN

    WN.synsets("dog")
except LookupError:
    nltk.download("wordnet", download_dir=os.environ["NLTK_DATA"], quiet=True)
    from nltk.corpus import wordnet as WN

from whoosh import index, qparser  # noqa: E402
from whoosh.analysis import SimpleAnalyzer  # noqa: E402
from whoosh.fields import ID, KEYWORD, TEXT, Schema  # noqa: E402
from whoosh.qparser import QueryParser, syntax  # noqa: E402
from whoosh.qparser.plugins import Plugin  # noqa: E402

OLD_JSON = ROOT.parent / "tmi" / "data" / "tmi.json"
INDEX_DIR = ROOT / "data" / "build" / "momfer_index"

# indexer.py
SCHEMA = Schema(motif=ID(stored=True, unique=True),
                description=TEXT(analyzer=SimpleAnalyzer(), field_boost=2.0, stored=True, phrase=True),
                additional=TEXT(analyzer=SimpleAnalyzer(), field_boost=1.5, stored=True, phrase=True),
                wn=KEYWORD(field_boost=1.0, stored=True, lowercase=True, scorable=True, commas=True),
                references=TEXT(analyzer=SimpleAnalyzer(), field_boost=0.5, stored=True, phrase=True),
                location=KEYWORD(field_boost=0.5, stored=True, lowercase=True, scorable=True, commas=True))


def senses(synset):
    return {l.replace("_", " ") for l in synset.lemma_names()}


def hypernyms(synset):
    """All ancestors, nearest first (Pattern's hypernyms(recursive=True))."""
    return list(synset.closure(lambda s: s.hypernyms()))


def build():
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    ix = index.create_in(str(INDEX_DIR), schema=SCHEMA, indexname="tmi")
    w = ix.writer()
    for item in json.load(open(OLD_JSON)):
        keywords = set()
        for lemma in item["lemmas"]:
            if not lemma:
                continue
            syn_id = 0 if lemma != "white" else 1
            try:
                for h in hypernyms(WN.synsets(lemma, "n")[syn_id]):
                    keywords |= senses(h)
            except (IndexError, ValueError):
                pass
        w.add_document(motif=item["motif"].rstrip("."), description=item["description"],
                       additional=item["additional_description"], wn=", ".join(keywords),
                       references=item["references"], location=", ".join(item["locations"]))
    w.commit()
    return ix


# app/expand.py
def expand(term, limit=1):
    try:
        hs = hypernyms(WN.synsets(term, "n")[0])
        # Pattern's w.senses[0]: the first lemma of each hypernym synset
        return {h.lemma_names()[0].replace("_", " ") for h in hs[:limit]} | {term}
    except IndexError:
        return set()


class WordnetPlugin(Plugin):
    def __init__(self, fieldnames, fieldboosts=None, expansion=1, group=syntax.OrGroup.factory(0.9)):
        self.fieldnames, self.boosts, self.expansion, self.group = fieldnames, fieldboosts or {}, expansion, group

    def filters(self, parser):
        return [(self.do_multifield, 110)]

    def do_multifield(self, parser, group):
        for i, node in enumerate(group):
            if isinstance(node, syntax.GroupNode):
                group[i] = self.do_multifield(parser, node)
            elif node.has_fieldname and node.fieldname is None:
                newnodes = []
                for fname in self.fieldnames:
                    n = copy.copy(node)
                    n.set_fieldname(fname)
                    n.set_boost(self.boosts.get(fname, 1.0))
                    newnodes.append(n)
                for hyp in expand(node.text, self.expansion):
                    n = copy.copy(node)
                    n.set_fieldname("wn")
                    n.text = hyp
                    n.set_boost(self.boosts.get("wn", 1.0))
                    newnodes.append(n)
                group[i] = self.group(newnodes)
        return group


def parser(schema):
    p = QueryParser(None, schema, group=qparser.OrGroup.factory(0.9))
    p.add_plugin(WordnetPlugin(["description", "additional"], fieldboosts={"description": 3.0, "additional": 1.0}))
    return p


def main():
    queries = json.load(open(sys.argv[1] if len(sys.argv) > 1 else ROOT / "pipeline" / "heldout.json"))
    ix = index.open_dir(str(INDEX_DIR), indexname="tmi") if index.exists_in(str(INDEX_DIR), indexname="tmi") else build()
    p = parser(ix.schema)
    out = {}
    with ix.searcher() as s:
        t0 = time.time()
        for q in queries:
            hits = s.search(p.parse(q["q"]), limit=10)
            out[q["q"]] = [h["motif"] for h in hits]
        ms = (time.time() - t0) / len(queries) * 1000
    json.dump({"system": "MOMFER (reconstructed)", "ms_per_query": ms, "results": out}, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
