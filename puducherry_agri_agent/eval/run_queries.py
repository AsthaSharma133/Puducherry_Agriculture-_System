"""Run the 10 live benchmark queries against db/puducherry_agri.db and check every answer.
A query passes only if its intent, every expected answer string and its provenance all match.
Writes eval/query_results.csv.

Run (from puducherry_agri_agent/):  python eval/run_queries.py
"""
import csv
import json
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from app.query_engine import ask  # noqa: E402

BENCHMARK = PROJECT / "eval" / "benchmark_queries.json"
RESULTS = PROJECT / "eval" / "query_results.csv"


def load_queries():
    """Return the list of benchmark query dicts."""
    return json.loads(BENCHMARK.read_text(encoding="utf-8"))["queries"]


def check(query, out):
    """Return a list of failed checks for one query (empty list = pass).
    Checks intent, each expected answer string, and the expected provenance row."""
    problems = []
    if out["intent"] != query["expected_intent"]:
        problems.append(f"intent {out['intent']} != {query['expected_intent']}")
    for text in query["expect_in_answer"]:
        if text not in out["answer"]:
            problems.append(f"missing '{text}'")
    if not out["provenance"]:
        problems.append("no provenance")
    exp = query["expect_provenance"]
    if not any(p["source_file_or_url"] == exp["source_file_or_url"]
               and exp["page_or_table_contains"] in p["page_or_table"] for p in out["provenance"]):
        problems.append(f"provenance {exp} not found")
    return problems


def run_one(query):
    """Ask one benchmark question and return a result row for the CSV."""
    start = time.time()
    out = ask(query["question"])
    seconds = time.time() - start
    problems = check(query, out)
    return {"id": query["id"], "category": query["category"], "question": query["question"],
            "intent": out["intent"], "passed": not problems, "answer": out["answer"],
            "sql": out["sql"], "sql_params": json.dumps(out["sql_params"]),
            "provenance": " || ".join(f"{p['source_id']} | {p['source_file_or_url']} | {p['page_or_table']}"
                                      for p in out["provenance"]),
            "latency_ms": round(seconds * 1000, 1), "problems": "; ".join(problems)}


def main():
    """Run all queries, print PASS/FAIL lines, write the CSV, exit 1 unless all pass."""
    rows = [run_one(q) for q in load_queries()]
    for r in rows:
        print(f"{'PASS' if r['passed'] else 'FAIL'} {r['id']} [{r['category']}] {r['answer'][:110]}"
              + (f"\n     -> {r['problems']}" if r["problems"] else ""))
    with RESULTS.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    passed = sum(r["passed"] for r in rows)
    print(f"{passed}/{len(rows)} queries passed with exact answers and provenance -> {RESULTS.name}")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
