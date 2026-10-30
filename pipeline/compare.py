"""Compare search models, with and without plain-language readings.

    uv run python pipeline/compare.py MODEL [MODEL ...] [--readings data/build/readings/claude-haiku-5-5.jsonl] [--split dev]

For each model: Thompson's text only, and Thompson's text plus the reading as
a second vector per motif (a motif scores its better match). Scores on the ATU
fragments of the chosen split and on the two hand-made sets. Full-precision
vectors; the browser's compressed version is checked separately.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from index import doc_text  # noqa: E402

PROMPT = "Represent this sentence for searching relevant passages: "


def reading_text(r):
    return r["plain"] + " " + "; ".join(r["queries"])


def metrics(S, items, ids, k=10):
    h1 = h10 = mrr = 0
    for row, x in zip(S, items):
        top = np.argpartition(-row, k)[:k]
        order = [ids[i] for i in top[np.argsort(-row[top])]]
        r = next((j for j, m in enumerate(order) if m in x["gold"]), None)
        if r is not None:
            h10 += 1
            h1 += r == 0
            mrr += 1 / (r + 1)
    n = len(items)
    return h1 / n, h10 / n, mrr / n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="+")
    ap.add_argument("--readings", default=str(ROOT / "data" / "build" / "readings" / "claude-haiku-5-5.jsonl"))
    ap.add_argument("--split", default="dev")
    args = ap.parse_args()
    import torch
    from sentence_transformers import SentenceTransformer

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    data = json.load(open(ROOT / "data" / "index" / "tmi.json"))
    nodes = {n["id"]: n for n in data["nodes"]}
    ids = json.load(open(ROOT / "data" / "index" / "ids.json"))
    readings = {r["id"]: r for r in map(json.loads, open(args.readings))} if Path(args.readings).exists() else {}
    have = [i for i, m in enumerate(ids) if m in readings]
    print(f"readings for {len(have)} of {len(ids)} motifs", file=sys.stderr)

    sets = {f"atu-{args.split}": json.load(open(ROOT / "data" / "build" / f"atu_{args.split}.json")),
            "devset": json.load(open(ROOT / "pipeline" / "devset.json")),
            "heldout": json.load(open(ROOT / "pipeline" / "heldout.json"))}
    print(f"{'model':38s} {'variant':9s} " + "  ".join(f"{s:>22s}" for s in sets))
    for name in args.models:
        model = SentenceTransformer(name, device=device)
        enc = lambda t: model.encode(t, batch_size=256, normalize_embeddings=True, convert_to_numpy=True,
                                     show_progress_bar=False)
        D = enc([doc_text(nodes[m]) for m in ids])
        R = enc([reading_text(readings[ids[i]]) for i in have]) if have else None
        res = {"thompson": [], "+reading": []}
        for items in sets.values():
            Q = enc([PROMPT + x["q"] for x in items])
            S = Q @ D.T
            res["thompson"].append(metrics(S, items, ids))
            if R is not None:
                S2 = S.copy()
                S2[:, have] = np.maximum(S[:, have], Q @ R.T)
                res["+reading"].append(metrics(S2, items, ids))
        short = Path(name).name if Path(name).exists() else name
        for variant, rows in res.items():
            if rows:
                cells = "  ".join(f"{h1:.2f} / {h10:.2f} / {mrr:.3f}" for h1, h10, mrr in rows)
                print(f"{short:38s} {variant:9s} {cells}")
    print("(cells: first / top 10 / MRR)")


if __name__ == "__main__":
    main()
