"""Re-check the hand-typed S3 ground truth in eval/eval_set.json against the PDFs themselves.
For every A2 case it tests two rules that do not depend on our extraction pipeline:

  1. the UT (STATE) value is printed on the report's 5-year summary page cited in the case;
  2. for additive tables (IV-A area, V-B out-turn) the 4 regions add up to the UT value.

Run (from puducherry_agri_agent/):  python eval/verify_ground_truth.py
"""
import json
import re
import sys
from pathlib import Path

import pymupdf

PROJECT = Path(__file__).resolve().parents[1]


def summary_numbers(pdf_file, page_no):
    """Return the set of whole numbers printed on one text-layer page of a PDF.
    The summary pages have a text layer, so no OCR is involved here."""
    with pymupdf.open(PROJECT / pdf_file) as doc:
        text = doc[page_no - 1].get_text()
    return {int(n) for n in re.findall(r"\b\d+\b", text.replace(",", ""))}


def check_case(case):
    """Return a list of problems found for one A2 case (an empty list means it passed).
    Checks the summary-table value and, for IV-A / V-B, the region sum."""
    problems = []
    values = case["expected"]
    ref = case["summary_check"]
    if ref["ut_value"] != values["UT"]:
        problems.append(f"UT {values['UT']} differs from cited summary value {ref['ut_value']}")
    if values["UT"] not in summary_numbers(ref["file"], ref["page"]):
        problems.append(f"UT {values['UT']} not printed on {ref['file']} p{ref['page']}")
    if case["table"] in ("IV-A", "V-B"):
        regions = values["Puducherry"] + values["Karaikal"] + values["Mahe"] + values["Yanam"]
        if regions != values["UT"]:
            problems.append(f"regions sum {regions} != UT {values['UT']}")
    return problems


def main():
    """Check every A2 case, print one line each, and exit with 1 if any case fails.
    A1/A3 cases are HTML rows and are checked by eye (see their 'verification' field)."""
    cases = json.loads((PROJECT / "eval" / "eval_set.json").read_text(encoding="utf-8"))["cases"]
    failed = 0
    for case in cases:
        if case["agent"] != "A2":
            continue
        problems = check_case(case)
        failed += bool(problems)
        status = "OK  " if not problems else "FAIL"
        print(f"{status} {case['case_id']} {case['year']} {case['table']} {case['crop']:<16} "
              f"UT={case['expected']['UT']:<7} {'; '.join(problems)}")
    print(f"{failed} failing case(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
