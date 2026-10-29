"""Export everything the static site needs into docs/data/.

    uv run python pipeline/static.py [--dims 256]

The browser embeds a query with the same encoder (bge-base-en-v1.5, run by
transformers.js), projects it onto the principal components below and scores
it against int8 motif vectors. Files:

  vectors.i8        n × dims int8, PCA-projected, normalised and quantised motif embeddings
  projection.f32    768 mean, then 768 × dims components, then dims dequantisation scales
  motifs.json       per motif: id, title, note, parent, cultures, regions, types, cross-references
  tree.json         categories and sections: id, title, parent; plus every node's children in order
  refs/X.json       references and precomputed neighbours ('echoes' and 'kin') per branch letter
  map.bin           per motif: uint16 x, uint16 y, uint8 branch (the 2-D map)
  meta.json         counts, traditions, regions, model, calibration
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

MODEL = "Xenova/bge-base-en-v1.5"
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dims", type=int, default=256)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "refs").mkdir(exist_ok=True)

    data = json.load(open(INDEX / "tmi.json"))
    ids = json.load(open(INDEX / "ids.json"))
    nodes = {n["id"]: n for n in data["nodes"]}
    motifs = [nodes[i] for i in ids]
    row = {mid: i for i, mid in enumerate(ids)}
    meta_idx = json.load(open(INDEX / "meta.json"))
    assert meta_idx["model"] == "BAAI/bge-base-en-v1.5"

    # ------------------------------------------------------------- vectors
    E = np.load(INDEX / "emb0.npy").astype(np.float32)
    mean = E.mean(0)
    _, _, Vt = np.linalg.svd(E - mean, full_matrices=False)
    P = Vt[: args.dims].T.astype(np.float32)  # 768 × dims
    X = (E - mean) @ P
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
        per_letter[m["id"][0]][m["id"]] = rec
    for L, recs in per_letter.items():
        json.dump(recs, open(OUT / "refs" / f"{L}.json", "w"), ensure_ascii=False, separators=(",", ":"))

    # ----------------------------------------------------------------- map
    letters = list(data["categories"])
    xy = np.clip(np.load(INDEX / "coords.npy") * 65535, 0, 65535).astype("<u2")
    rec = np.zeros(len(ids), dtype=[("x", "<u2"), ("y", "<u2"), ("c", "u1")])
    rec["x"], rec["y"] = xy[:, 0], xy[:, 1]
    rec["c"] = [letters.index(mid[0]) for mid in ids]
    rec.tofile(OUT / "map.bin")

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
        "count": len(ids), "dims": args.dims, "model": MODEL, "query_prompt": QUERY_PROMPT,
        "cultures": cultures, "culture_counts": [n for _, n in data["cultures"]],
        "regions": regions, "notable": notable,
    }, open(OUT / "meta.json", "w"), ensure_ascii=False, separators=(",", ":"))

    total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"wrote {OUT} ({total / 1e6:.1f} MB)", file=sys.stderr)


if __name__ == "__main__":
    main()
