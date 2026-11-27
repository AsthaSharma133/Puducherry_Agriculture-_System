"""Evaluate the real extraction pipeline (agents A1, A2, A3) on eval/eval_set.json.
Writes eval/results_summary.json, eval/results_by_agent.csv and eval/results_by_case.csv.

What happens:
  1. each agent runs on its real input (S3 PDFs, S2/S5/S6 saved HTML pages),
     in memory only - the database is not changed;
  2. every expected field of every case is compared with what the agent produced;
  3. we report field-level Precision / Recall / F1 per agent and macro-averaged, plus
     provenance accuracy, tool-selection accuracy, task completion, automation rate,
     retries, latency and categorised errors.
Works fully offline. LangSmith / agentevals hooks run only if installed and configured.

Run (from puducherry_agri_agent/):  python eval/run_eval.py
"""
import csv
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from eval.check_overlap import check_no_overlap  # noqa: E402
from src.agents.base import InputMissing  # noqa: E402
from src.agents.prices.agent import parse_s2  # noqa: E402
from src.agents.web_entities.agent import parse_s5  # noqa: E402
from src.common.config import DB_PATH, load_dotenv  # noqa: E402
from src.common.provenance import Provenance  # noqa: E402
from src.orchestrator.router import route  # noqa: E402

EVAL_DIR = PROJECT / "eval"
AGENTS = ["A1", "A2", "A3"]
HTML_TOOL = "bs4_html_table"          # A1 and A3 parse HTML tables with BeautifulSoup
MAX_ATTEMPTS = 2
TRANSIENT = (OSError, TimeoutError, ConnectionError)


# ----------------------------------------------------------------------------- 1. run agents
def run_with_retry(func):
    """Call func() up to MAX_ATTEMPTS times, retrying only network/file errors.
    Returns (result or None, attempts used, seconds taken, error text or '')."""
    start = time.time()
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return func(), attempt, time.time() - start, ""
        except InputMissing as error:
            return None, attempt, time.time() - start, f"input missing: {error}"
        except TRANSIENT as error:
            last = f"{type(error).__name__}: {error}"
    return None, MAX_ATTEMPTS, time.time() - start, last


def source_jobs(cases):
    """List the inputs the evaluation runs: (source_id, documents, function returning AgentResult).
    S3 and S6 go through the routed agent; S2/S5 run the same parsers on the exact saved page
    named in the cases (so a newer snapshot cannot silently change the test input)."""
    def run_routed(source_id):
        agent = route(source_id)
        return lambda: agent.run({"source_id": source_id}, Provenance(source_id, agent.agent_id, "eval"))

    def case_file(source_id):
        return PROJECT / next(c["input_file"] for c in cases if c["source_id"] == source_id)

    s3_docs = len(list((PROJECT / "data" / "raw" / "s3").glob("S3_SCR_*.pdf")))
    s2_page, s5_page = case_file("S2"), case_file("S5")
    return [
        ("S3", s3_docs, run_routed("S3")),
        ("S6", 1, run_routed("S6")),
        ("S2", 1, lambda: parse_s2(s2_page, Provenance("S2", "A1", "eval"))),
        ("S5", 1, lambda: parse_s5(s5_page, Provenance("S5", "A3", "eval"))),
    ]


def run_all_sources(cases):
    """Run every job once and keep its rows, issues, timing and retry count.
    Returns {source_id: info dict}; a failed source simply has no rows."""
    outputs = {}
    for source_id, docs, func in source_jobs(cases):
        result, attempts, seconds, error = run_with_retry(func)
        rows = []
        issues = []
        if result is not None:
            for table_rows in result.tables.values():
                rows += table_rows
            issues = result.issues
        errors = [i for i in issues if i["severity"] == "ERROR"]
        outputs[source_id] = {"rows": rows, "issues": issues, "documents": docs,
                              "attempts": attempts, "seconds": round(seconds, 3),
                              "error": error, "automatic": result is not None and not errors}
        print(f"  ran {source_id}: {len(rows)} rows from {docs} document(s) in {seconds:.2f} s "
              f"(attempts={attempts}) {error}")
    return outputs


# ----------------------------------------------------------------------------- 2. predictions
def find_rows(case, rows):
    """Return {expected field name: matching output row or None} for one case.
    A2 cases match one crop_statistics row per region; other cases match one row."""
    if case["agent"] == "A2":
        found = {}
        for region in case["expected"]:
            found[region] = next((r for r in rows if r.get("crop_year") == case["year"]
                                  and r.get("region") == region and r.get("crop") == case["crop"]
                                  and r.get("season") == case["season"]), None)
        return found
    match = case["match"]
    hit = None
    for r in rows:
        if "name" in match and r.get("name") == match["name"]:
            hit = r
        elif "scheme_name_contains" in match and match["scheme_name_contains"] in r.get("scheme_name", ""):
            hit = r
        elif "period" in match and all(r.get(k) == v for k, v in match.items()):
            hit = r
        if hit:
            break
    return {field: hit for field in case["expected"]}


def predicted_value(case, field, row):
    """Return what the pipeline produced for one expected field (None if no row)."""
    if row is None:
        return None
    if case["agent"] == "A2":
        return row.get(case["metric"])
    return row.get(field)


def same(expected, predicted):
    """True if two values match: numbers compared as floats, text compared exactly.
    None only matches None (used for the 0 -> NULL price rule)."""
    if expected is None or predicted is None:
        return expected is None and predicted is None
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        try:
            return abs(float(expected) - float(predicted)) < 1e-6
        except (TypeError, ValueError):
            return False
    return str(expected) == str(predicted)


# ----------------------------------------------------------------------------- 3. scoring
def score_case(case, rows, routed_agent):
    """Score one case: field TP/FP/FN, provenance, tool choice, completion and error notes.
    Returns a flat dict that becomes one line of results_by_case.csv."""
    found = find_rows(case, rows)
    tp = fp = fn = 0
    wrong = []
    for field, expected in case["expected"].items():
        row = found[field]
        pred = predicted_value(case, field, row)
        if row is not None and same(expected, pred):
            tp += 1
            continue
        fn += 1
        if row is not None and pred is not None:
            fp += 1
        wrong.append(f"{field}: expected {expected!r} got {pred!r}")
    used_rows = [r for r in found.values() if r is not None]
    exp = case["expected_provenance"]
    prov_ok = bool(used_rows) and len(used_rows) == len(found) and all(
        r["source_file_or_url"] == exp["source_file_or_url"] and exp["page_or_table"] in r["page_or_table"]
        for r in used_rows)
    tools = {r.get("extraction_method", HTML_TOOL) for r in used_rows}
    tool_ok = routed_agent == case["agent"] and tools == {case["expected_tool"]}
    return {"case_id": case["case_id"], "agent": case["agent"], "source_id": case["source_id"],
            "synthetic": case["synthetic"], "fields": len(case["expected"]), "tp": tp, "fp": fp,
            "fn": fn, "exact_match": not wrong, "provenance_ok": prov_ok, "tool_ok": tool_ok,
            "completed": len(used_rows) == len(found) and all(r.get("page_or_table") for r in used_rows),
            "errors": "; ".join(wrong), "error_category": classify_errors(case, wrong, found)}


def classify_errors(case, wrong, found):
    """Put a wrong case into one error category (empty string if the case is correct).
    A number that is not in the input text at all counts as a hallucination."""
    if not wrong:
        return ""
    if all(r is None for r in found.values()):
        return "network_geo_block" if case["source_id"] in ("S2", "S5", "S8") else "layout"
    if case["agent"] == "A2":
        text = case.get("model_input", "")
        for item in wrong:
            got = item.rsplit("got ", 1)[-1]
            number = got.replace(".0", "")
            if number not in ("None",) and number not in text:
                return "hallucination"
        return "OCR" if case["expected_tool"] == "ocr_tesseract" else "layout"
    if any(w.startswith(("region", "lgd_")) for w in wrong):
        return "location_name"
    if any(w.startswith(("price_unit", "amount_basis")) for w in wrong):
        return "unit"
    return "layout"


def prf(tp, fp, fn):
    """Precision, recall and F1 from counts (0.0 when undefined), rounded to 4 places."""
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return round(p, 4), round(r, 4), round(f, 4)


def agent_table(case_results, outputs):
    """Aggregate case results per agent and add the macro average row.
    Returns a list of dicts (one per agent + 'MACRO') for results_by_agent.csv."""
    table = []
    for agent in AGENTS:
        rows = [c for c in case_results if c["agent"] == agent]
        tp, fp, fn = (sum(c[k] for c in rows) for k in ("tp", "fp", "fn"))
        p, r, f = prf(tp, fp, fn)
        sources = {c["source_id"] for c in rows}
        secs = sum(outputs[s]["seconds"] for s in sources)
        docs = sum(outputs[s]["documents"] for s in sources)
        n = len(rows)
        table.append({"agent": agent, "n_cases": n, "n_fields": sum(c["fields"] for c in rows),
                      "tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f,
                      "exact_match_rate": round(sum(c["exact_match"] for c in rows) / n, 4),
                      "provenance_accuracy": round(sum(c["provenance_ok"] for c in rows) / n, 4),
                      "tool_selection_accuracy": round(sum(c["tool_ok"] for c in rows) / n, 4),
                      "task_completion_rate": round(sum(c["completed"] for c in rows) / n, 4),
                      "documents": docs, "avg_latency_s_per_document": round(secs / docs, 3)})
    macro = {"agent": "MACRO", "n_cases": sum(t["n_cases"] for t in table),
             "n_fields": sum(t["n_fields"] for t in table)}
    for key in ("precision", "recall", "f1", "exact_match_rate", "provenance_accuracy",
                "tool_selection_accuracy", "task_completion_rate", "avg_latency_s_per_document"):
        macro[key] = round(sum(t[key] for t in table) / len(table), 4)
    return table + [macro]


# ----------------------------------------------------------------------------- 4. extra metrics
ISSUE_CATEGORY = {
    "OCR": ["ocr_column_count_mismatch", "ocr_char_fix", "no_text_layer_ocr_unavailable"],
    "layout": ["row_value_count_mismatch", "cell_collision", "unmapped_header", "template_disagreement",
               "duplicate_crop_column", "state_sum_mismatch", "no_header_template", "unexpected_table"],
    "unit": ["area_yield_mismatch", "non_numeric_cell", "zero_price_as_null"],
    "location_name": ["unknown_region", "alias_key_collision"],
}


def issue_categories(outputs):
    """Count the issues the agents logged during this eval run, by error category.
    INFO-level notes that need no action (e.g. dash_as_zero) are not counted."""
    counts = {"OCR": 0, "layout": 0, "unit": 0, "location_name": 0}
    for info in outputs.values():
        for issue in info["issues"]:
            for category, types in ISSUE_CATEGORY.items():
                if issue["issue_type"] in types:
                    counts[category] += 1
    return counts


def blocked_fetches():
    """Count corpus downloads that failed because the host refused the connection.
    Read from data/raw/raw_inventory.csv (written by scripts/fetch_corpus.py)."""
    path = PROJECT / "data" / "raw" / "raw_inventory.csv"
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    failed = [r for r in rows if r["status"] == "FAILED" and re.search(r"Connect|Connection", r["error"])]
    return len(failed), len(rows), sum(r["status"].startswith("OK") for r in rows)


def pipeline_retries():
    """Return retries (attempts - 1) recorded in the latest pipeline run in the database.
    Returns None if the database has not been built yet."""
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT run_id FROM pipeline_runs ORDER BY run_step_id DESC LIMIT 1").fetchone()
    if row is None:
        return None
    total = conn.execute("SELECT SUM(MAX(attempts - 1, 0)) FROM pipeline_runs WHERE run_id = ? "
                         "AND source_id != 'ALL'", row).fetchone()[0]
    conn.close()
    return {"run_id": row[0], "retries": total or 0}


def failure_snippets():
    """Return two real before/after failure examples (B2, B3) from docs/extraction_errors.md.
    Reading them from the doc keeps one single source of truth."""
    text = (PROJECT / "docs" / "extraction_errors.md").read_text(encoding="utf-8")
    snippets = []
    for line in text.splitlines():
        if line.startswith(("| B2 |", "| B3 |")):
            cells = [c.strip() for c in line.strip("|").split("|")]
            snippets.append({"id": cells[0], "before_error": cells[1], "cause": cells[2],
                             "after_fix": cells[3]})
    return snippets


# ----------------------------------------------------------------------------- 5. optional hooks
def optional_hooks(summary):
    """Run LangSmith / agentevals hooks only when available; record what ran and what was skipped.
    Never fails the evaluation: every hook error is stored as text."""
    ran = ["field_prf_local", "provenance_local", "tool_selection_local", "overlap_assert_local"]
    skipped = []
    if not os.environ.get("LANGSMITH_API_KEY"):
        skipped.append({"name": "langsmith_upload", "reason": "LANGSMITH_API_KEY not set"})
    else:
        try:
            from langsmith import Client
            Client().create_run(name="team35_phase3_eval", run_type="chain",
                                inputs={"eval_set": "eval/eval_set.json"}, outputs=summary["by_agent"])
            ran.append("langsmith_upload")
        except Exception as error:  # noqa: BLE001 - optional hook must never break the eval
            skipped.append({"name": "langsmith_upload", "reason": f"{type(error).__name__}: {error}"})
    try:
        from agentevals.trajectory.match import create_trajectory_match_evaluator
        evaluator = create_trajectory_match_evaluator(trajectory_match_mode="strict")
        trajectory = routing_trajectory()
        result = evaluator(outputs=trajectory, reference_outputs=trajectory)
        ran.append("agentevals_trajectory_match")
        summary["agentevals_routing"] = result
    except ImportError:
        skipped.append({"name": "agentevals_trajectory_match", "reason": "agentevals not installed"})
    except Exception as error:  # noqa: BLE001
        skipped.append({"name": "agentevals_trajectory_match", "reason": f"{type(error).__name__}: {error}"})
    skipped.append({"name": "llm_as_judge", "reason": "not used: every field has an exact numeric/text answer"})
    return ran, skipped


def routing_trajectory():
    """Describe the supervisor's routing decisions as OpenAI-style messages for agentevals.
    One assistant message calls the agent chosen for each source."""
    calls = [{"function": {"name": route(s).agent_id, "arguments": json.dumps({"source_id": s})}}
             for s in ("S3", "S6", "S2", "S5")]
    return [{"role": "user", "content": "extract all sources"},
            {"role": "assistant", "content": "", "tool_calls": calls}]


# ----------------------------------------------------------------------------- 6. main
def write_csv(path, rows):
    """Write a list of dicts to CSV with the keys of the first row as header."""
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build_summary(cases, case_results, outputs, by_agent):
    """Collect every reported number into one dictionary for results_summary.json."""
    blocked, attempted_fetch, ok_fetch = blocked_fetches()
    eval_inputs = sum(o["documents"] for o in outputs.values())
    auto_inputs = sum(o["documents"] for o in outputs.values() if o["automatic"])
    eval_cats = {}
    for c in case_results:
        if c["error_category"]:
            eval_cats[c["error_category"]] = eval_cats.get(c["error_category"], 0) + 1
    logged = issue_categories(outputs)
    return {
        "eval_set": "eval/eval_set.json", "n_cases": len(cases),
        "n_real_cases": sum(not c["synthetic"] for c in cases),
        "n_synthetic_cases": sum(c["synthetic"] for c in cases),
        "train_test_overlap": check_no_overlap(),
        "by_agent": by_agent,
        "automation": {
            "eval_inputs_attempted": eval_inputs, "eval_inputs_fully_automatic": auto_inputs,
            "automation_rate_eval_inputs": round(auto_inputs / eval_inputs, 4),
            "corpus_fetch_attempted": attempted_fetch, "corpus_fetch_ok": ok_fetch,
            "automation_rate_corpus_fetch": round(ok_fetch / attempted_fetch, 4),
            "note": "all corpus fetch failures are S8: agritech.tnau.ac.in was unreachable "
                    "(TCP connect timeout) even from India on 2026-11-27 - HOST_UNREACHABLE"},
        "retries": {"eval_run": sum(o["attempts"] - 1 for o in outputs.values()),
                    "latest_pipeline_run": pipeline_retries()},
        "latency_s_per_document": {s: round(o["seconds"] / o["documents"], 3) for s, o in outputs.items()},
        "latency_note": "S3 OCR results are cached in data/interim/ocr; a cold first run OCRs "
                        "54 pages (~2 minutes)",
        "error_counts": {
            "eval_wrong_cases": {k: eval_cats.get(k, 0) for k in
                                 ("OCR", "layout", "unit", "location_name", "hallucination", "network_geo_block")},
            "issues_logged_during_eval": logged,
            "network_geo_block_fetch_failures": blocked},
        "failure_snippets": failure_snippets(),
    }


def main():
    """Run the evaluation end to end and print a short report."""
    load_dotenv()
    if not list((PROJECT / "data" / "raw" / "s3").glob("S3_SCR_*.pdf")):
        print("The S3 PDFs are not in data/raw/s3/ (they are git-ignored, 30 MB).\n"
              "Download them first:  python scripts/fetch_corpus.py   then run this again.")
        return 1
    cases = json.loads((EVAL_DIR / "eval_set.json").read_text(encoding="utf-8"))["cases"]
    print(f"Evaluating {len(cases)} cases")
    outputs = run_all_sources(cases)
    case_results = [score_case(c, outputs[c["source_id"]]["rows"], route(c["source_id"]).agent_id)
                    for c in cases]
    by_agent = agent_table(case_results, outputs)
    summary = build_summary(cases, case_results, outputs, by_agent)
    ran, skipped = optional_hooks(summary)
    summary["evaluators_run"], summary["evaluators_skipped"] = ran, skipped
    (EVAL_DIR / "results_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_csv(EVAL_DIR / "results_by_agent.csv", by_agent)
    write_csv(EVAL_DIR / "results_by_case.csv", case_results)
    for t in by_agent:
        print(f"  {t['agent']:<5} n={t['n_cases']:<3} fields={t['n_fields']:<4} P={t['precision']:.3f} "
              f"R={t['recall']:.3f} F1={t['f1']:.3f} prov={t['provenance_accuracy']:.3f} "
              f"tool={t['tool_selection_accuracy']:.3f} done={t['task_completion_rate']:.3f}")
    for c in case_results:
        if c["errors"]:
            print(f"  WRONG {c['case_id']}: {c['errors'][:150]}")
    print(f"  automation (eval inputs): {summary['automation']['automation_rate_eval_inputs']}  "
          f"skipped hooks: {[s['name'] for s in skipped]}")
    print("wrote eval/results_summary.json, eval/results_by_agent.csv, eval/results_by_case.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
