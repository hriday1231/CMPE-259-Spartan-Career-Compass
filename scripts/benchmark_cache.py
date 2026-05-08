"""benchmark response time with and without the application-level prompt cache

runs a fixed suite of proposal queries against the configured Ollama model,
measures the cold (no cache) call vs the warm (cache hit) call, and writes
the timings into results/cache_benchmark.json for the eval notebook
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import OLLAMA_LARGE_MODEL
from src.agent import run_agent
from src import prompt_cache


DEFAULT_QUERIES = [
    "What career events are happening this week?",
    "Who is the counselor for engineering students?",
    "Summarize the Resume Guide into a checklist.",
    "What should I bring to a career fair?",
    "Find remote data science internships paying over $20/hr.",
    "What employers are hiring robotics majors?",
]


def timed(fn):
    t0 = time.time()
    result = fn()
    return result, int((time.time() - t0) * 1000)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=OLLAMA_LARGE_MODEL)
    ap.add_argument("--mode", default="simple", choices=["simple", "chain", "reflect"])
    ap.add_argument("--out", default=str(ROOT / "results" / "cache_benchmark.json"))
    ap.add_argument("--clear-cache", action="store_true",
                    help="clear cache before running (gives clean cold numbers)")
    args = ap.parse_args()

    if args.clear_cache:
        n = prompt_cache.clear()
        print(f"Cleared {n} cache entries.")

    rows = []
    for q in DEFAULT_QUERIES:
        # cold timing - clear the cache first so the call really hits the model
        prompt_cache.clear()
        _, cold_ms = timed(lambda: run_agent(q, model_name=args.model, mode=args.mode, use_cache=False))
        # warm-store: populate the cache
        _ = run_agent(q, model_name=args.model, mode=args.mode, use_cache=True)
        # warm timing - this call is the cache hit we want to measure
        _, hit_ms = timed(lambda: run_agent(q, model_name=args.model, mode=args.mode, use_cache=True))

        rows.append({
            "query": q,
            "model": args.model,
            "mode": args.mode,
            "no_cache_ms": cold_ms,
            "cached_hit_ms": hit_ms,
            "speedup_x": round(cold_ms / max(hit_ms, 1), 1),
        })
        print(f"{q[:60]:<62} | cold {cold_ms:>6}ms | hit {hit_ms:>5}ms | x{rows[-1]['speedup_x']}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rows, indent=2))
    print(f"\nWrote {len(rows)} rows -> {out_path}")

    avg_cold = sum(r["no_cache_ms"] for r in rows) / len(rows)
    avg_hit = sum(r["cached_hit_ms"] for r in rows) / len(rows)
    print(f"Average cold: {avg_cold:.0f}ms  |  Average cached: {avg_hit:.0f}ms  |  Average speedup: x{avg_cold/max(avg_hit,1):.1f}")


if __name__ == "__main__":
    main()
