"""Embed every motif and lay out the 2-D map.

    uv run python pipeline/index.py [--skip-map]

Output in data/index/: tmi.json, ids.json, emb0.npy (bge-base-en-v1.5), coords.npy, meta.json
"""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "data" / "build"
OUT = ROOT / "data" / "index"

MODEL = "BAAI/bge-base-en-v1.5"


def doc_text(m: dict) -> str:
    """What the encoder sees of a motif: its headline and explanatory note."""
    return m["title"] + (" " + m["note"] if m.get("note") else "")


def embed(motifs):
    cache = BUILD / "emb" / f"{MODEL.replace('/', '__')}__note.npy"
    if cache.exists():
        print(f"reusing {cache.name}", file=sys.stderr)
        return np.load(cache)
    import torch
    from sentence_transformers import SentenceTransformer

    device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    model = SentenceTransformer(MODEL, device=device)
    texts = [doc_text(m) for m in motifs]
    order = np.argsort([len(t) for t in texts])  # similar lengths batch faster
    t0 = time.time()
    vecs = model.encode([texts[i] for i in order], batch_size=128, normalize_embeddings=True,
                        show_progress_bar=True, convert_to_numpy=True)
    E = np.empty_like(vecs)
    E[order] = vecs
    E = E.astype(np.float16)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache, E)
    print(f"embedded {len(texts)} motifs in {time.time() - t0:.0f}s", file=sys.stderr)
    return E


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-map", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy(BUILD / "tmi.json", OUT / "tmi.json")
    data = json.load(open(OUT / "tmi.json"))
    motifs = [n for n in data["nodes"] if n["kind"] == "motif"]
    ids = [m["id"] for m in motifs]
    json.dump(ids, open(OUT / "ids.json", "w"))

    E = embed(motifs)
    np.save(OUT / "emb0.npy", E.astype(np.float16))

    if not args.skip_map:
        import umap

        t0 = time.time()
        reducer = umap.UMAP(n_neighbors=25, min_dist=0.05, metric="cosine", random_state=7)
        xy = reducer.fit_transform(E.astype(np.float32))
        xy = (xy - xy.min(0)) / (xy.max(0) - xy.min(0))
        np.save(OUT / "coords.npy", xy.astype(np.float32))
        print(f"umap in {time.time() - t0:.0f}s", file=sys.stderr)

    json.dump({"model": MODEL, "count": len(ids)}, open(OUT / "meta.json", "w"), indent=1)
    print(f"index written to {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
