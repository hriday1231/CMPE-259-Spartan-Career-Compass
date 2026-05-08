"""driver that produces the three eval JSONs the notebook reads

writes:
  results/cache_benchmark.json  cold vs warm cache timings (mistral 7B)
  results/compare_simple.json   2 models x 8 proposal queries x simple mode
  results/modes_demo.json       1 query x mistral 7B x {simple, chain, reflect}
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.agent import run_agent
from src.tool_router import run_tools
from src import prompt_cache

RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)


CACHE_QUERIES = [
    "What career events are happening this week?",
    "Who is the counselor for engineering students?",
    "Summarize the Resume Guide into a checklist.",
    "When is the next headshots event?",
    "What should I bring to a career fair?",
    "Find resume workshops in the next 7 days.",
]


def run_cache_benchmark(model: str = "mistral:7b"):
    rows = []
    for q in CACHE_QUERIES:
        prompt_cache.clear()
        t0 = time.time()
        _ = run_agent(q, model_name=model, mode="simple", use_cache=False)
        cold_ms = int((time.time() - t0) * 1000)
        _ = run_agent(q, model_name=model, mode="simple", use_cache=True)
        t0 = time.time()
        _ = run_agent(q, model_name=model, mode="simple", use_cache=True)
        hit_ms = int((time.time() - t0) * 1000)
        row = {
            "query": q, "model": model,
            "no_cache_ms": cold_ms, "cached_hit_ms": hit_ms,
            "speedup_x": round(cold_ms / max(hit_ms, 1), 1),
        }
        rows.append(row)
        print(f"  {q[:50]:<52} cold {cold_ms:>6}ms | hit {hit_ms:>5}ms | x{row['speedup_x']}")
    (RESULTS / "cache_benchmark.json").write_text(json.dumps(rows, indent=2))
    return rows


# the 20 functional proposal queries live in compare_models.py to avoid drift
# (the two queries with embedded JDs are part of that list)
sys.path.insert(0, str(ROOT / "scripts"))
from compare_models import PROPOSAL_QUERIES  # noqa: E402

COMPARE_QUERIES = PROPOSAL_QUERIES


def run_model_compare(models=("mistral:7b", "llama2:13b")):
    import re
    PLACEHOLDERS = [re.compile(r"\[insert [^\]]+\]", re.I),
                    re.compile(r"\[TBD\]", re.I),
                    re.compile(r"\[your \w+ here\]", re.I)]

    rows = []
    for q in COMPARE_QUERIES:
        context = run_tools(q)
        ctx_urls = set(re.findall(r"https?://[^\s)\]]+", context))
        ctx_urls = {u.rstrip(".,") for u in ctx_urls}
        for model in models:
            t0 = time.time()
            ans = run_agent(q, model_name=model, mode="simple", use_cache=False)
            latency_ms = int((time.time() - t0) * 1000)
            ph = sum(len(p.findall(ans)) for p in PLACEHOLDERS)
            ans_urls = {u.rstrip(".,") for u in re.findall(r"https?://[^\s)\]]+", ans)}
            stray = [u for u in ans_urls if u not in ctx_urls
                     and not u.startswith("https://careercenter.sjsu.edu")]
            rows.append({
                "query": q, "model": model, "latency_ms": latency_ms,
                "answer_chars": len(ans), "placeholders": ph,
                "urls_in_answer": len(ans_urls),
                "urls_not_in_context": len(stray),
                "answer": ans,
                "context_preview": context[:400],
            })
            print(f"  {model:<12} | {q[:50]:<52} | {latency_ms/1000:>5.1f}s | ph={ph} stray_urls={len(stray)}")
    (RESULTS / "compare_simple.json").write_text(json.dumps(rows, indent=2))
    return rows


MODES_QUERY = "Create a 2-week job search plan."


def run_modes_demo(model="mistral:7b"):
    rows = []
    for mode in ["simple", "chain", "reflect"]:
        t0 = time.time()
        ans = run_agent(MODES_QUERY, model_name=model, mode=mode, use_cache=False)
        latency_ms = int((time.time() - t0) * 1000)
        rows.append({
            "mode": mode, "model": model, "query": MODES_QUERY,
            "latency_ms": latency_ms, "answer": ans,
        })
        print(f"  {mode:<8} {latency_ms/1000:>5.1f}s  {len(ans)} chars")
    (RESULTS / "modes_demo.json").write_text(json.dumps(rows, indent=2))
    return rows


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="cache,compare,modes",
                    help="comma-separated subset of {cache,compare,modes}")
    args = ap.parse_args()
    parts = {p.strip() for p in args.parts.split(",")}

    if "cache" in parts:
        print("\n=== A. Cache benchmark (mistral:7b) ===")
        run_cache_benchmark()
    if "compare" in parts:
        print("\n=== B. Model comparison (simple mode) ===")
        run_model_compare()
    if "modes" in parts:
        print("\n=== C. Prompting modes demo (mistral:7b) ===")
        run_modes_demo()
    print("\nDone.")
