"""Build a large fragment-to-motif benchmark from the ATU tale-type summaries.

Uther's summaries in the trilogy dataset (github.com/j-hagedorn/trilogy) cite
Thompson motifs inline: "...he falls into a magic sleep [D1975]". Each cited
fragment becomes a query whose gold answer is the cited motif(s).

    uv run python pipeline/atu_bench.py

The summaries are copyrighted (Uther 2004); the downloaded data and the
benchmark stay out of the published repository (data/raw/trilogy and
data/build are git-ignored). Splits are by tale type, so a model trained on
'train' is judged on tale types it has never seen:

    data/build/atu_{train,dev,test}.json   [{q, gold, near, atu}, ...]

'near' adds the gold motifs' parents and children, for a lenient score.
"""

import csv
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "trilogy"
OUT = ROOT / "data" / "build"
URL = "https://raw.githubusercontent.com/j-hagedorn/trilogy/master/data/"

MIN_WORDS = 5


def fetch():
    RAW.mkdir(parents=True, exist_ok=True)
    for f in ("atu_df.csv", "aft.csv"):
        if not (RAW / f).exists():
            urllib.request.urlretrieve(URL + f, RAW / f)


def split_of(atu_id: str) -> str:
    h = int(hashlib.sha1(atu_id.encode()).hexdigest(), 16) % 10
    return "train" if h < 6 else ("dev" if h < 8 else "test")


def clean(fragment: str) -> str:
    # keep the clause that ends at the citation
    frag = re.split(r"(?<=[.;:!?])\s+", fragment.strip())[-1]
    frag = re.sub(r"^\(?(?:cf\.|e\.g\.|i\.e\.)\s*", "", frag, flags=re.I)
    frag = frag.strip(" ,;:(")
    # balance a dangling opening parenthesis
    if frag.count("(") > frag.count(")"):
        frag = frag[: frag.rfind("(")].strip(" ,;:")
    return frag


def main():
    fetch()
    csv.field_size_limit(10 ** 9)
    data = json.load(open(ROOT / "data" / "index" / "tmi.json"))
    nodes = {n["id"]: n for n in data["nodes"]}
    motifs = {i for i, n in nodes.items() if n["kind"] == "motif"}

    rows = list(csv.DictReader(open(RAW / "atu_df.csv", encoding="utf-8")))
    out = {"train": [], "dev": [], "test": []}
    seen = set()
    for r in rows:
        text, prev = r["tale_type"], 0
        for m in re.finditer(r"\[([^\]]+)\]", text):
            frag = clean(text[prev:m.start()])
            prev = m.end()
            refs = [x.strip().rstrip(".") for x in re.split(r"[,;]", m.group(1))]
            gold = [x for x in refs if x in motifs]
            if not gold or len(frag.split()) < MIN_WORDS:
                continue
            key = (frag.lower(), tuple(sorted(gold)))
            if key in seen:
                continue
            seen.add(key)
            near = set(gold)
            for g in gold:
                if nodes[g]["parent"] in motifs:
                    near.add(nodes[g]["parent"])
                near.update(c for c in nodes[g]["children"] if c in motifs)
            out[split_of(r["atu_id"])].append(
                {"q": frag, "gold": gold, "near": sorted(near), "atu": r["atu_id"], "kind": "fragment"})

    OUT.mkdir(parents=True, exist_ok=True)
    for name, items in out.items():
        json.dump(items, open(OUT / f"atu_{name}.json", "w"), ensure_ascii=False, indent=0)
        print(f"{name}: {len(items)} fragments from {len({i['atu'] for i in items})} tale types", file=sys.stderr)


if __name__ == "__main__":
    main()
