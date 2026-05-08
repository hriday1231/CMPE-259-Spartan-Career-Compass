"""run the full proposal query set across models and prompting modes

records answer text, end-to-end latency, retrieved context length, and a
couple of cheap grounding heuristics (placeholder count, stray-URL count)
so the report can compare mistral 7B against llama2 13B without an
LLM-as-judge pass
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import OLLAMA_LARGE_MODEL, OLLAMA_SMALL_MODEL
from src.agent import run_agent
from src.tool_router import run_tools


# 20 functional user queries derived from the project proposal
# the two queries that need a JD body to make sense (#9 compare-listings
# and #17 summarize-JD) include a short fake job description inline
# the 5 security probes live in scripts/security_tests.py as ATTACKS
PROPOSAL_QUERIES = [
    "What career events are happening this week?",
    "Are there any STEM career fairs this month?",
    "Find resume workshops in the next 7 days.",
    "Who is the counselor for engineering students?",
    "Summarize the Resume Guide into a checklist.",
    "What should I bring to a career fair?",
    "Find remote data science internships paying over $20/hr.",
    "Show entry-level software roles in California.",
    (
        "I am comparing two job listings and want to know which is a better "
        "fit for someone strong in Python and SQL.\n"
        "Listing A - Data Analyst at FinPulse Analytics (Remote): "
        "build SQL pipelines on Snowflake, write Python ETL scripts with pandas, "
        "produce Tableau dashboards for the product team, 2+ years experience required.\n"
        "Listing B - Backend Engineer at MeshHealth (Hybrid, San Jose): "
        "design Java microservices on Spring Boot, deploy to AWS via Docker / "
        "Kubernetes, 3+ years experience required, Python optional.\n"
        "Compare the two for fit based on Python and SQL skills."
    ),
    "Generate a networking email to a recruiter.",
    "What workshops help with interview prep?",
    "When is the next headshots event?",
    "Give me 3 behavioral interview tips from Career Center guides.",
    "Find internships suitable for international students.",
    "What employers are hiring robotics majors?",
    "Create a 2-week job search plan.",
    (
        "Here is a job description, summarize it into the key required skills:\n"
        "Machine Learning Engineer at Acme AI (San Francisco, hybrid). Build and "
        "deploy production ML models that power our recommendation product. "
        "Requirements: 3+ years of Python, strong PyTorch or TensorFlow, "
        "experience with MLOps tooling (MLflow or Kubeflow), familiarity with "
        "AWS or GCP, comfortable with Docker and Kubernetes. Nice to have: "
        "experience with LLMs, experience leading a small team, MS or PhD in "
        "CS or a related field."
    ),
    "What Career Center services can I access without an appointment?",
    "Prepare 5 mock interview questions for a product management role.",
    "How do I negotiate a job offer salary at SJSU career resources?",
]


PLACEHOLDER_PATTERNS = [
    re.compile(r"\[insert [^\]]+\]", re.I),
    re.compile(r"\[TBD\]", re.I),
    re.compile(r"\[your \w+ here\]", re.I),
]
REAL_DOMAINS = ("careercenter.sjsu.edu", "sjsu.edu")


def heuristic_grounding(answer: str, context: str) -> dict:
    placeholders = sum(len(p.findall(answer)) for p in PLACEHOLDER_PATTERNS)

    answer_urls = set(re.findall(r"https?://[^\s)\]]+", answer))
    context_urls = set(re.findall(r"https?://[^\s)\]]+", context))
    # normalize trailing punctuation so "https://x.com." matches "https://x.com"
    def _norm(u): return u.rstrip(".,")
    answer_urls = {_norm(u) for u in answer_urls}
    context_urls = {_norm(u) for u in context_urls}
    not_in_context = [u for u in answer_urls if u not in context_urls and not u.startswith("https://careercenter.sjsu.edu")]

    cited_real = any(d in answer for d in REAL_DOMAINS)

    return {
        "placeholders_count": placeholders,
        "urls_in_answer": len(answer_urls),
        "urls_not_in_context": len(not_in_context),
        "cited_real_domain": cited_real,
    }


def run_one(query: str, model: str, mode: str) -> dict:
    context = run_tools(query)
    t0 = time.time()
    try:
        answer = run_agent(query, model_name=model, mode=mode, use_cache=False)
        err = None
    except Exception as e:
        answer = ""
        err = str(e)
    latency_ms = int((time.time() - t0) * 1000)

    g = heuristic_grounding(answer, context)
    return {
        "model": model,
        "mode": mode,
        "query": query,
        "latency_ms": latency_ms,
        "context_chars": len(context),
        "answer_chars": len(answer),
        "answer": answer,
        "error": err,
        **g,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=f"{OLLAMA_LARGE_MODEL},{OLLAMA_SMALL_MODEL}")
    ap.add_argument("--modes", default="simple,chain,reflect")
    ap.add_argument("--queries", default="",
                    help="comma-separated 1-based indices, empty means all")
    ap.add_argument("--out-json", default=str(ROOT / "results" / "compare_results.json"))
    ap.add_argument("--out-csv", default=str(ROOT / "results" / "compare_results.csv"))
    args = ap.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]

    if args.queries:
        idx = [int(i) - 1 for i in args.queries.split(",")]
        queries = [PROPOSAL_QUERIES[i] for i in idx]
    else:
        queries = PROPOSAL_QUERIES

    rows = []
    for model in models:
        for mode in modes:
            for q in queries:
                print(f"[{model} | {mode}] {q[:70]}")
                rows.append(run_one(q, model, mode))
                print(f"  latency {rows[-1]['latency_ms']}ms | placeholders={rows[-1]['placeholders_count']} | stray_urls={rows[-1]['urls_not_in_context']}")

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(rows, indent=2))

    # answer is truncated for the CSV so it stays openable in a spreadsheet
    out_csv = Path(args.out_csv)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "model", "mode", "query", "latency_ms", "context_chars", "answer_chars",
            "placeholders_count", "urls_in_answer", "urls_not_in_context",
            "cited_real_domain", "error", "answer_preview",
        ])
        writer.writeheader()
        for r in rows:
            row = {k: r.get(k) for k in writer.fieldnames if k != "answer_preview"}
            row["answer_preview"] = (r.get("answer") or "")[:500].replace("\n", " ")
            writer.writerow(row)

    print(f"\nWrote {len(rows)} rows to {out_json} and {out_csv}")


if __name__ == "__main__":
    main()
