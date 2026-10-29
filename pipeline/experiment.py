"""Compare embedding models and document representations on the development set
(pipeline/devset.json). Used to choose the encoder; see README.

    uv run python pipeline/experiment.py --model Qwen/Qwen3-Embedding-0.6B --variant context
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
DESCRIPTIONS = [(d["q"], d["gold"]) for d in json.load(open(ROOT / "pipeline" / "devset.json"))]
BUILD = ROOT / "data" / "build"
EMB = BUILD / "emb"

TASK = "Given a description or passage from a folktale, myth or legend, retrieve the folk-literature motifs it contains"

PROMPTS = {
    "qwen": (f"Instruct: {TASK}\nQuery:", ""),
    "bge": ("Represent this sentence for searching relevant passages: ", ""),
    "e5": ("query: ", "passage: "),
    "none": ("", ""),
}


def prompt_style(model_name):
    n = model_name.lower()
    if "qwen" in n:
        return "qwen"
    if "bge-m3" in n:
        return "none"
    if "bge" in n:
        return "bge"
    if "e5" in n:
        return "e5"
    return "none"


def load_motifs():
    d = json.load(open(BUILD / "tmi.json"))
    return [n for n in d["nodes"] if n["kind"] == "motif"]


def doc_text(m, variant):
    if variant == "title":
        return m["title"]
    t = m["title"] + (" " + m["note"] if m["note"] else "")
    if variant == "note":
        return t
    if variant == "context":
        return f"{t}\n({m['category']} › {m['context']})" if m["context"] else f"{t}\n({m['category']})"
    raise ValueError(variant)


def load_model(name):
    from sentence_transformers import SentenceTransformer
    import torch

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    kw = {}
    if "qwen" in name.lower():
        kw["model_kwargs"] = {"torch_dtype": torch.float16}
    return SentenceTransformer(name, device=device, **kw)


def embed_docs(model, name, motifs, variant):
    EMB.mkdir(parents=True, exist_ok=True)
    path = EMB / f"{name.replace('/', '__')}__{variant}.npy"
    if path.exists():
        return np.load(path)
    _, dprompt = PROMPTS[prompt_style(name)]
    texts = [dprompt + doc_text(m, variant) for m in motifs]
    # sort by length for efficient batching
    order = np.argsort([len(t) for t in texts])
    t0 = time.time()
    vecs = model.encode([texts[i] for i in order], batch_size=128, normalize_embeddings=True,
                        show_progress_bar=True, convert_to_numpy=True)
    out = np.empty_like(vecs)
    out[order] = vecs
    print(f"embedded {len(texts)} docs in {time.time() - t0:.0f}s", file=sys.stderr)
    np.save(path, out.astype(np.float16))
    return out.astype(np.float16)


def evaluate(model, name, motifs, D):
    qprompt, _ = PROMPTS[prompt_style(name)]
    ids = [m["id"] for m in motifs]
    idx = {m: i for i, m in enumerate(ids)}
    Df = D.astype(np.float32)

    # descriptions
    qs = [q for q, _ in DESCRIPTIONS]
    Q = model.encode([qprompt + q for q in qs], normalize_embeddings=True, convert_to_numpy=True)
    S = Q @ Df.T
    h1 = h10 = mrr = 0
    for (q, gold), row in zip(DESCRIPTIONS, S):
        top = np.argsort(-row)[:50]
        gold = {g for g in gold if g in idx}
        ranks = [r for r, i in enumerate(top) if ids[i] in gold]
        if ranks:
            r = ranks[0]
            h1 += r == 0
            h10 += r < 10
            mrr += 1 / (r + 1) if r < 10 else 0
        else:
            print(f"   MISS: {q[:60]} -> {[ids[i] for i in top[:3]]}", file=sys.stderr)
    n = len(DESCRIPTIONS)
    print(f"descriptions: hit@1 {h1/n:.2f} hit@10 {h10/n:.2f} mrr@10 {mrr/n:.3f}")



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-Embedding-0.6B")
    ap.add_argument("--variant", default="context", choices=["title", "note", "context"])
    ap.add_argument("--task", default=None, help="override the Qwen instruction ('' for none)")
    args = ap.parse_args()
    if args.task is not None:
        PROMPTS["qwen"] = (f"Instruct: {args.task}\nQuery:" if args.task else "", "")
    motifs = load_motifs()
    missing = sorted({g for _, gs in DESCRIPTIONS for g in gs} - {m["id"] for m in motifs})
    if missing:
        print("gold ids not in index:", missing, file=sys.stderr)
    model = load_model(args.model)
    D = embed_docs(model, args.model, motifs, args.variant)
    print(f"== {args.model} [{args.variant}]")
    evaluate(model, args.model, motifs, D)


if __name__ == "__main__":
    main()
