"""Fine-tune the search encoder on ATU fragment-to-motif pairs.

    uv run python pipeline/finetune.py [--epochs 3 --lr 2e-5 --hard 1]

Trains bge-base-en-v1.5 so that a plot fragment ("by handing him an apple")
lands near the motif Uther cited for it (H481.1), using in-batch negatives
plus mined hard negatives. Scores the result on the development fragments and
on the two hand-made sets, to catch forgetting. Splits are by tale type, so
development and test fragments come from tale types never seen in training.
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from index import doc_text  # noqa: E402

BUILD = ROOT / "data" / "build"
MODELS = ROOT / "data" / "models"
BASE = "BAAI/bge-base-en-v1.5"
PROMPT = "Represent this sentence for searching relevant passages: "


def load(name):
    return json.load(open(BUILD / f"atu_{name}.json"))


def score(model, docs, ids, items, k=10):
    """hit@1, hit@10, MRR and lenient hit@10 of a model on a list of {q, gold, near?}."""
    D = model.encode(docs, batch_size=256, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
    Q = model.encode([PROMPT + x["q"] for x in items], batch_size=128, normalize_embeddings=True, convert_to_numpy=True)
    S = Q @ D.T
    top = np.argpartition(-S, k, axis=1)[:, :k]
    h1 = h10 = mrr = n10 = 0
    for row, x, t in zip(S, items, top):
        order = [ids[i] for i in t[np.argsort(-row[t])]]
        r = next((j for j, m in enumerate(order) if m in x["gold"]), None)
        if r is not None:
            h10 += 1
            h1 += r == 0
            mrr += 1 / (r + 1)
        if any(m in x.get("near", x["gold"]) for m in order):
            n10 += 1
    n = len(items)
    return {"hit1": h1 / n, "hit10": h10 / n, "mrr": mrr / n, "near10": n10 / n}, D


def evaluate(model, docs, ids, label):
    sets = {"atu-dev": load("dev"),
            "devset": json.load(open(ROOT / "pipeline" / "devset.json")),
            "heldout": json.load(open(ROOT / "pipeline" / "heldout.json"))}
    out = {}
    D = None
    for name, items in sets.items():
        res, D = score(model, docs, ids, items)
        out[name] = res
        print(f"  {label:10s} {name:8s} hit@1 {res['hit1']:.2f}  hit@10 {res['hit10']:.2f}  "
              f"MRR {res['mrr']:.3f}  near@10 {res['near10']:.2f}", file=sys.stderr)
    return out


def mine_hard_negatives(model, docs, ids, items, per_query, skip=5, depth=40):
    """Motifs the base model ranks high for a fragment but that are neither its
    gold nor a parent/child. The very top ranks are skipped: they are often
    acceptable answers Uther simply didn't cite."""
    D = model.encode(docs, batch_size=256, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
    Q = model.encode([PROMPT + x["q"] for x in items], batch_size=128, normalize_embeddings=True, convert_to_numpy=True)
    S = Q @ D.T
    rng = random.Random(7)
    negs = []
    for row, x in zip(S, items):
        order = np.argsort(-row)[: depth]
        cands = [ids[i] for i in order[skip:] if ids[i] not in x["near"]]
        negs.append(rng.sample(cands, min(per_query, len(cands))))
    return negs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--hard", type=int, default=1, help="hard negatives per pair (0 = in-batch only)")
    ap.add_argument("--name", default="spindle-bge-base-atu")
    ap.add_argument("--synthetic", default=None, help="readings .jsonl: add its search phrases and plain readings as training queries")
    ap.add_argument("--atu-repeat", type=int, default=1, help="repeat the ATU pairs so they keep weight among synthetic ones")
    ap.add_argument("--base", default=BASE, help="model to start from")
    args = ap.parse_args()

    import torch
    from datasets import Dataset
    from sentence_transformers import SentenceTransformer, SentenceTransformerTrainer, SentenceTransformerTrainingArguments
    from sentence_transformers.losses import CachedMultipleNegativesRankingLoss, MultipleNegativesRankingLoss
    from sentence_transformers.training_args import BatchSamplers

    device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    data = json.load(open(ROOT / "data" / "index" / "tmi.json"))
    nodes = {n["id"]: n for n in data["nodes"]}
    ids = json.load(open(ROOT / "data" / "index" / "ids.json"))
    docs = [doc_text(nodes[i]) for i in ids]

    model = SentenceTransformer(args.base, device=device)
    print("baseline:", file=sys.stderr)
    base = evaluate(model, docs, ids, "base")

    train = load("train")
    negs = mine_hard_negatives(model, docs, ids, train, args.hard) if args.hard else None
    rows = {"anchor": [], "positive": []}
    for k in range(args.hard):
        rows[f"negative_{k}"] = []
    for i, x in enumerate(train):
        for g in x["gold"]:
            if args.hard and len(negs[i]) < args.hard:
                continue
            rows["anchor"].append(PROMPT + x["q"])
            rows["positive"].append(doc_text(nodes[g]))
            for k in range(args.hard):
                rows[f"negative_{k}"].append(doc_text(nodes[negs[i][k]]))
    for k in list(rows):
        rows[k] = rows[k] * args.atu_repeat
    if args.synthetic:
        # every motif's generated phrases point at Thompson's own text; these
        # come from the motif alone, never from the ATU development or test fragments
        n_syn = 0
        neg_pool = list(range(len(ids)))
        rng = random.Random(3)
        for rec in map(json.loads, open(args.synthetic)):
            if rec["id"] not in nodes:
                continue
            target = doc_text(nodes[rec["id"]])
            for q in rec["queries"] + [rec["plain"]]:
                rows["anchor"].append(PROMPT + q)
                rows["positive"].append(target)
                for k in range(args.hard):
                    rows[f"negative_{k}"].append(doc_text(nodes[ids[rng.choice(neg_pool)]]))
                n_syn += 1
        print(f"synthetic pairs: {n_syn}", file=sys.stderr)
    ds = Dataset.from_dict(rows).shuffle(seed=7)
    print(f"training pairs: {len(ds)}", file=sys.stderr)

    loss = MultipleNegativesRankingLoss(model)
    out_dir = MODELS / args.name
    targs = SentenceTransformerTrainingArguments(
        output_dir=str(BUILD / "ft-runs" / args.name), num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch, learning_rate=args.lr, warmup_steps=0.1,
        batch_sampler=BatchSamplers.NO_DUPLICATES, logging_steps=20, save_strategy="no",
        report_to="none", seed=7, dataloader_drop_last=False,
    )
    t0 = time.time()
    trainer = SentenceTransformerTrainer(model=model, args=targs, train_dataset=ds, loss=loss)
    trainer.train()
    print(f"trained in {time.time() - t0:.0f}s", file=sys.stderr)

    print("fine-tuned:", file=sys.stderr)
    tuned = evaluate(model, docs, ids, "tuned")
    model.save(str(out_dir))
    json.dump({"args": vars(args), "base": base, "tuned": tuned}, open(out_dir / "spindle_eval.json", "w"), indent=1)
    print(f"saved {out_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
