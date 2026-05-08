"""quick CLI to summarize results/*.json - useful for sanity checking after a sweep"""
import json, re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "results"


def main():
    rows = json.loads((R / "compare_simple.json").read_text(encoding="utf-8"))
    print(f"compare_simple has {len(rows)} rows")
    print()
    by = defaultdict(list)
    for r in rows:
        by[r["model"]].append(r)
    for m, rs in by.items():
        avg_lat = sum(r["latency_ms"] for r in rs) / len(rs)
        avg_ch = sum(r["answer_chars"] for r in rs) / len(rs)
        ph = sum(r["placeholders"] for r in rs)
        stray = sum(r["urls_not_in_context"] for r in rs)
        print(f"{m:<14} n={len(rs)} | avg_lat={avg_lat:.0f}ms | avg_chars={avg_ch:.0f} | placeholders={ph} | stray_urls={stray}")
    print()
    print("Per-query stray URL flags:")
    flags = defaultdict(lambda: {"stray": 0, "ph": 0, "models": set()})
    for r in rows:
        if r["urls_not_in_context"] or r["placeholders"]:
            short = r["query"].replace("\n", " ")[:80]
            flags[short]["stray"] += r["urls_not_in_context"]
            flags[short]["ph"] += r["placeholders"]
            flags[short]["models"].add(r["model"])
    if not flags:
        print("  none - clean across both models!")
    else:
        for q, info in flags.items():
            models = ",".join(sorted(info["models"]))
            print(f"  [{models}] {info['stray']} stray, {info['ph']} ph: {q}")
    print()
    m = json.loads((R / "modes_demo.json").read_text(encoding="utf-8"))
    print("Modes demo:")
    for r in m:
        print(f"  {r['mode']:<8} {r['latency_ms']:>6}ms  {len(r['answer'])} chars")

    # security results if available
    sec_path = R / "security_results.json"
    if sec_path.exists():
        sec = json.loads(sec_path.read_text(encoding="utf-8"))
        print()
        print("Security results:")
        from collections import Counter
        for model in ("mistral:7b", "llama2:13b"):
            c = Counter(r["verdict"] for r in sec if r["model"] == model)
            print(f"  {model}: PASS={c.get('PASS',0)}, PARTIAL={c.get('PARTIAL',0)}, FAIL={c.get('FAIL',0)}")


if __name__ == "__main__":
    main()
