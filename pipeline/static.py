"""Export everything the static site needs into docs/data/.

    uv run python pipeline/static.py [--dims 256]

The browser embeds a query with the same encoder (run by transformers.js),
projects it onto the principal components below and scores it against int8
motif vectors. With --readings, every motif also gets a second vector for its
plain-language reading, and scores its better match. Files:

  vectors.i8        n (or 2n) × dims int8, PCA-projected, normalised and quantised embeddings:
                    Thompson's text for every motif, then (with readings) every reading
  projection.f32    768 mean, then 768 × dims components, then dims dequantisation scales
  motifs.json       per motif: id, title, note, parent, cultures, regions, types, cross-references
  tree.json         categories and sections: id, title, parent; plus every node's children in order
  refs/X.json       references and precomputed neighbours ('echoes' and 'kin') per branch letter
  meta.json         counts, traditions, regions, model, calibration
  atlas.json        the world map and where each tradition is (see atlas.py)
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "data" / "index"
OUT = ROOT / "docs" / "data"

BASE = "BAAI/bge-base-en-v1.5"
BROWSER_MODEL = "Xenova/bge-base-en-v1.5"
QUERY_PROMPT = "Represent this sentence for searching relevant passages: "


def neighbours(E, motifs, ids, k_echo=8, k_kin=5, chunk=2048):
    """For every motif, the most similar motifs in other second-level branches
    (echoes) and in the same branch (kin), excluding its parent and children."""
    n = len(ids)
    branch = [m["path"][1] if len(m["path"]) > 1 else m["path"][0] for m in motifs]
    row = {mid: i for i, mid in enumerate(ids)}
    echoes, kin = [None] * n, [None] * n
    for start in range(0, n, chunk):
        S = E[start:start + chunk] @ E.T
        top = np.argpartition(-S, 300, axis=1)[:, :300]
        for r in range(S.shape[0]):
            i = start + r
            order = top[r][np.argsort(-S[r, top[r]])]
            m = motifs[i]
            skip = {i, row.get(m["parent"], -1), *(row[c] for c in m["children"] if c in row)}
            e, s = [], []
            for j in order:
                if j in skip:
                    continue
                if branch[j] != branch[i]:
                    if len(e) < k_echo:
                        e.append(int(j))
                elif len(s) < k_kin:
                    s.append(int(j))
                if len(e) >= k_echo and len(s) >= k_kin:
                    break
            echoes[i], kin[i] = e, s
        print(f"  neighbours {min(start + chunk, n)}/{n}", file=sys.stderr, end="\r")
    print(file=sys.stderr)
    return echoes, kin


def embed(model_name, texts, cache):
    """Embed with a sentence-transformers model, caching the result."""
    if cache.exists():
        return np.load(cache).astype(np.float32)
    import torch
    from sentence_transformers import SentenceTransformer

    device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    model = SentenceTransformer(model_name, device=device)
    order = np.argsort([len(t) for t in texts])
    vecs = model.encode([texts[i] for i in order], batch_size=128, normalize_embeddings=True,
                        convert_to_numpy=True, show_progress_bar=True)
    E = np.empty_like(vecs)
    E[order] = vecs
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache, E.astype(np.float16))
    return E.astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dims", type=int, default=256)
    ap.add_argument("--model", default=BASE, help="encoder for the motif vectors (a local path or a model name)")
    ap.add_argument("--browser-model", default=BROWSER_MODEL,
                    help="the ONNX version of the same encoder that the browser loads (Hugging Face id)")
    ap.add_argument("--readings", default=None, help="plain-language readings (.jsonl) to add as second vectors")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "refs").mkdir(exist_ok=True)

    data = json.load(open(INDEX / "tmi.json"))
    ids = json.load(open(INDEX / "ids.json"))
    nodes = {n["id"]: n for n in data["nodes"]}
    motifs = [nodes[i] for i in ids]
    row = {mid: i for i, mid in enumerate(ids)}
    sys.path.insert(0, str(ROOT / "pipeline"))
    from index import doc_text

    # ------------------------------------------------------------- vectors
    emb_dir = ROOT / "data" / "build" / "emb"
    tag = Path(args.model).name if Path(args.model).exists() else args.model.replace("/", "__")
    if args.model == BASE:
        E = np.load(INDEX / "emb0.npy").astype(np.float32)
    else:
        E = embed(args.model, [doc_text(m) for m in motifs], emb_dir / f"{tag}__note.npy")
    readings = {}
    if args.readings:
        readings = {r["id"]: r for r in map(json.loads, open(args.readings))}
        assert all(i in readings for i in ids), "every motif needs a reading"
        R = embed(args.model, [readings[i]["plain"] + " " + "; ".join(readings[i]["queries"]) for i in ids],
                  emb_dir / f"{tag}__reading__{Path(args.readings).stem}.npy")
        V = np.vstack([E, R])
    else:
        V = E
    mean = V.mean(0)
    _, _, Vt = np.linalg.svd(V - mean, full_matrices=False)
    P = Vt[: args.dims].T.astype(np.float32)  # 768 × dims
    X = (V - mean) @ P
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    scale = np.abs(X).max(0).astype(np.float32)
    Xq = np.clip(np.round(X / scale * 127), -127, 127).astype(np.int8)
    Xq.tofile(OUT / "vectors.i8")
    np.concatenate([mean, P.ravel(), scale / 127]).astype("<f4").tofile(OUT / "projection.f32")
    print(f"vectors: {Xq.nbytes / 1e6:.1f} MB, projection {(mean.size + P.size + scale.size) * 4 / 1e6:.1f} MB",
          file=sys.stderr)

    # -------------------------------------------------------------- motifs
    cultures = [c for c, _ in data["cultures"]]
    regions = [r for r, _ in data["regions"]]
    cidx = {c: i for i, c in enumerate(cultures)}
    ridx = {r: i for i, r in enumerate(regions)}
    rows = []
    for m in motifs:
        rec = [m["id"], m["title"], m.get("note", ""), m["parent"],
               [cidx[c] for c in m.get("cultures", [])], [ridx[r] for r in m.get("regions", [])],
               m.get("types", []), [row[c] for c in m.get("cf", []) if c in row]]
        if m.get("alt_titles"):
            rec.append(m["alt_titles"])
        rows.append(rec)
    json.dump({"fields": ["id", "title", "note", "parent", "cultures", "regions", "types", "cf", "alt"],
               "rows": rows}, open(OUT / "motifs.json", "w"), ensure_ascii=False, separators=(",", ":"))

    # ---------------------------------------------------------------- tree
    tree = {"categories": data["categories"], "nodes": [], "children": {}}
    for n in data["nodes"]:
        if n["kind"] != "motif":
            tree["nodes"].append([n["id"], 0 if n["kind"] == "category" else 1, n["title"], n["parent"]])
        if n["children"]:
            tree["children"][n["id"]] = n["children"]
    json.dump(tree, open(OUT / "tree.json", "w"), ensure_ascii=False, separators=(",", ":"))

    # ---------------------------------------------- references, neighbours
    echoes, kin = neighbours(E, motifs, ids)
    per_letter = defaultdict(dict)
    for i, m in enumerate(motifs):
        rec = {"e": echoes[i], "k": kin[i]}
        if m.get("refs"):
            rec["r"] = m["refs"]
        if m["id"] in readings:
            rec["p"] = readings[m["id"]]["plain"]
        per_letter[m["id"][0]][m["id"]] = rec
    for L, recs in per_letter.items():
        json.dump(recs, open(OUT / "refs" / f"{L}.json", "w"), ensure_ascii=False, separators=(",", ":"))

    # notable motifs for the 'at random' card
    notable = [i for i, m in enumerate(motifs)
               if m.get("note") and len(m.get("cultures", [])) >= 2 and len(m["title"]) < 90]

    # the region each tradition belongs to, recomputed with build.py's own rules
    sys.path.insert(0, str(ROOT / "pipeline"))
    from build import canon_culture

    region_of = {}
    for m in motifs:
        for c in m.get("cultures", []):
            if c not in region_of:
                hit = canon_culture(c)
                region_of[c] = hit[1] if hit else None
    # traditions whose canonical name no longer maps on its own: majority over the motifs citing them
    votes = defaultdict(lambda: defaultdict(float))
    for m in motifs:
        for c in m.get("cultures", []):
            for r in m.get("regions", []):
                votes[c][r] += 1 / len(m["regions"])
    culture_regions = []
    for c in cultures:
        r = region_of.get(c) or (max(votes[c], key=votes[c].get) if votes[c] else None)
        culture_regions.append(ridx[r] if r in ridx else -1)
    print(f"traditions without a region: {culture_regions.count(-1)}", file=sys.stderr)

    json.dump({
        "culture_regions": culture_regions,
        "count": len(ids), "dims": args.dims, "model": args.browser_model, "query_prompt": QUERY_PROMPT,
        "second_vectors": bool(readings),
        "cultures": cultures, "culture_counts": [n for _, n in data["cultures"]],
        "regions": regions, "notable": notable,
    }, open(OUT / "meta.json", "w"), ensure_ascii=False, separators=(",", ":"))

    from atlas import export as export_atlas

    export_atlas(cultures, OUT)

    total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"wrote {OUT} ({total / 1e6:.1f} MB)", file=sys.stderr)


if __name__ == "__main__":
    main()
