"""Plain-language readings of motifs, written by Claude.

For every motif: one or two plain sentences on what it is, and a few phrases
a person might search with. They are used to enrich what the search model
embeds, and are always labelled as generated, never presented as Thompson's.

    source ~/.anthropic_env && uv run --group llm python pipeline/readings.py pilot --model claude-haiku-5-5
    source ~/.anthropic_env && uv run --group llm python pipeline/readings.py pilot --model claude-sonnet-5-5

Output: data/build/readings/<model>.jsonl, one {"id", "plain", "queries"} per line.
"""

import argparse
import json
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "build" / "readings"

# USD per million tokens (input, output), before the 50% Batch API discount
PRICES = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.00, 10.00), "claude-opus-5-5": (4.00, 20.00)}

SYSTEM = """You help make Stith Thompson's Motif-Index of Folk-Literature searchable for people who do not know its terse style.

For each motif you receive its number, Thompson's headline, his explanatory note (if any), and its place in the index (branch › section › parent motifs). Write for each:

plain: one or two plain, modern English sentences saying what the motif is or what happens in it, so that a newcomer understands it. Use the place in the index to resolve terse headlines (a headline under "Lies about fruits" is a tall tale; an answer under "Riddles" is a riddle answer). Be faithful: explain, do not embellish. Never add names, cultures, tale titles, examples or details that the headline, note and place do not imply.

queries: three to five short phrases someone might type when looking for this motif: everyday paraphrases, the plot-fragment phrasing a tale summary would use, and modern spellings (werewolf for "werwolf"). No motif numbers.

Return exactly one entry per motif, with its number unchanged."""

SCHEMA = {
    "type": "object",
    "properties": {
        "motifs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "plain": {"type": "string"},
                    "queries": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "plain", "queries"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["motifs"],
    "additionalProperties": False,
}


def load_index():
    data = json.load(open(ROOT / "data" / "index" / "tmi.json"))
    return {n["id"]: n for n in data["nodes"]}, json.load(open(ROOT / "data" / "index" / "ids.json"))


def describe(nodes, mid):
    n = nodes[mid]
    place = " › ".join(nodes[p]["title"].rstrip(".") for p in n["path"])
    entry = {"id": mid, "headline": n["title"], "place": place}
    if n.get("note"):
        entry["note"] = n["note"]
    return entry


def pilot_ids(nodes, ids, n_gold=150, n_random=150):
    """Motifs cited in the ATU development fragments (so the effect can be
    measured), plus as many random ones (so they aren't the only enriched ones)."""
    dev = json.load(open(ROOT / "data" / "build" / "atu_dev.json"))
    gold = sorted({g for x in dev for g in x["gold"]})
    rng = random.Random(11)
    picked = rng.sample(gold, min(n_gold, len(gold)))
    rest = [i for i in ids if i not in set(picked)]
    return picked + rng.sample(rest, n_random)


def request(client, model, motifs):
    kw = dict(
        model=model,
        max_tokens=16000,
        system=SYSTEM,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": json.dumps(motifs, ensure_ascii=False)}],
    )
    if model.startswith("claude-sonnet") or model.startswith("claude-opus"):
        # route a declined request to Anthropic's recommended fallback model
        return client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kw)
    return client.messages.create(**kw)


def run(model, todo, nodes, group=20, workers=6):
    import anthropic

    client = anthropic.Anthropic(max_retries=4)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{model}.jsonl"
    done = set()
    if path.exists():
        done = {json.loads(line)["id"] for line in open(path)}
    todo = [m for m in todo if m not in done]
    chunks = [todo[i:i + group] for i in range(0, len(todo), group)]
    lock = threading.Lock()
    usage = {"in": 0, "out": 0, "calls": 0, "failed": 0}

    def work(chunk):
        motifs = [describe(nodes, m) for m in chunk]
        try:
            resp = request(client, model, motifs)
        except anthropic.APIStatusError as e:
            print(f"  error {e.status_code}: {e.message[:120]}", file=sys.stderr)
            with lock:
                usage["failed"] += 1
            return
        if resp.stop_reason == "refusal":
            print(f"  refusal for {chunk[0]}…", file=sys.stderr)
            with lock:
                usage["failed"] += 1
            return
        text = next((b.text for b in resp.content if b.type == "text"), "{}")
        got = {m["id"]: m for m in json.loads(text).get("motifs", [])}
        with lock:
            usage["in"] += resp.usage.input_tokens + (resp.usage.cache_read_input_tokens or 0)
            usage["out"] += resp.usage.output_tokens
            usage["calls"] += 1
            with open(path, "a") as f:
                for m in chunk:
                    if m in got:
                        rec = {"id": m, "plain": got[m]["plain"].strip(), "queries": [q.strip() for q in got[m]["queries"]]}
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    t0 = time.time()
    print(f"{model}: {len(todo)} motifs to do in {len(chunks)} requests", file=sys.stderr, flush=True)

    def tracked(chunk):
        work(chunk)
        with lock:
            n = usage["calls"] + usage["failed"]
            if n % 100 == 0:
                pin, pout = PRICES.get(model, (0, 0))
                spent = usage["in"] / 1e6 * pin + usage["out"] / 1e6 * pout
                print(f"  {n}/{len(chunks)} requests, ${spent:.2f} so far, {time.time() - t0:.0f}s", file=sys.stderr, flush=True)

    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(tracked, chunks))
    pin, pout = PRICES.get(model, (0, 0))
    cost = usage["in"] / 1e6 * pin + usage["out"] / 1e6 * pout
    print(f"{model}: {usage['calls']} calls, {usage['failed']} failed, {usage['in']:,} tokens in, "
          f"{usage['out']:,} out, ${cost:.3f} at standard prices, {time.time() - t0:.0f}s", file=sys.stderr)
    return usage, cost


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["pilot", "all"])
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    nodes, ids = load_index()
    todo = pilot_ids(nodes, ids) if args.mode == "pilot" else ids
    run(args.model, todo, nodes, workers=args.workers)


if __name__ == "__main__":
    main()
