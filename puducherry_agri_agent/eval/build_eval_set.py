"""Write eval/eval_set.json: 28 hand-checked test cases for agents A1, A2 and A3.
Expected values below are typed in by hand from the source documents, never copied from the DB.

How the S3 (A2) ground truth was checked (2026-11-26):
  * every value was read from a 300-dpi render of the printed page;
  * the STATE (UT) value was matched against the report's own 5-year summary table
    (2021-22 values: 2022-23 report pp.34-36; 2024-25 values: 2024-25 report pp.40-42);
  * the 4 regions must add up to STATE for area (IV-A) and out-turn (V-B).
eval/verify_ground_truth.py re-checks the summary-table and region-sum rules automatically.

Run (from puducherry_agri_agent/):  python eval/build_eval_set.py
"""
import json
import re
from pathlib import Path

from table_text import block_text, instruction

EVAL_DIR = Path(__file__).resolve().parent
CHECKED_BY = ("AI-assisted check (Claude Code, 2026-11-26): page render + summary table; "
              "human re-check by Evaluation Lead: pending")
S3_2122 = "data/raw/s3/S3_SCR_2021-22.pdf"
S3_2425 = "data/raw/s3/S3_SCR_2024-25.pdf"
S6_HTML = "data/raw/html/S6_credit_coop_societies_2026-11-26.html"
S2_FIX = "eval/fixtures/S2_mktpric_synthetic.html"
S5_FIX = "eval/fixtures/S5_schemes_synthetic.html"
METRIC = {"IV-A": ("area_ha", "ha"), "V-A": ("yield_value", "kg/ha"),
          "V-B": ("production_value", "tonnes")}

# (file, page, table, column, first column of its block, printed label, crop, values P/K/M/Y/UT, summary ref)
S3_CASES = [
    (S3_2122, 45, "IV-A", 5, 2, "PADDY Total", "Paddy", [13243, 5295, 0, 358, 18896], "2022-23 p34 'Paddy Total' 2021-22 = 18896"),
    (S3_2122, 45, "IV-A", 17, 17, "Sugarcane", "Sugarcane", [1257, 0, 0, 0, 1257], "2022-23 p34 'Sugarcane' 2021-22 = 1257"),
    (S3_2122, 45, "IV-A", 21, 17, "Mangoes", "Mango", [134, 23, 7, 1, 165], "2022-23 p34 'Mangoes' 2021-22 = 165"),
    (S3_2122, 46, "IV-A", 48, 48, "Cotton", "Cotton", [5, 460, 0, 0, 465], "2022-23 p35 'Cotton' 2021-22 = 465"),
    (S3_2122, 46, "IV-A", 51, 48, "Coconut", "Coconut", [984, 165, 460, 268, 1877], "2022-23 p35 'Coconut' 2021-22 = 1877"),
    (S3_2122, 46, "IV-A", 67, 63, "Net Cropped Area", "Net area sown", [9849, 4891, 562, 487, 15789], "2022-23 p35 'Net Area Sown' 2021-22 = 15789"),
    (S3_2122, 48, "V-A", 5, 2, "RICE Average", "Paddy", [3254, 2298, 0, 2777, 2977], "2022-23 p36 'Rice Total' yield 2021-22 = 2977"),
    (S3_2122, 48, "V-A", 18, 17, "Tapioca", "Tapioca", [24096, 0, 30000, 0, 24291], "2022-23 p36 'Tapioca' yield 2021-22 = 24291"),
    (S3_2122, 48, "V-A", 30, 17, "Coconut (in nuts)", "Coconut", [10950, 3200, 10000, 18000, 11043], "2022-23 p36 'Coconut' yield 2021-22 = 11043"),
    (S3_2122, 49, "V-B", 5, 2, "RICE Total", "Paddy", [43090, 12170, 0, 994, 56254], "2022-23 p36 'Rice Total' outturn 2021-22 = 56254"),
    (S3_2122, 49, "V-B", 13, 2, "Sugarcane", "Sugarcane", [150840, 0, 0, 0, 150840], "2022-23 p36 'Sugarcane' outturn 2021-22 = 150840"),
    (S3_2122, 49, "V-B", 28, 17, "Groundnut (kernals)", "Groundnut", [982, 1, 0, 0, 983], "2022-23 p36 'Groundnut' outturn 2021-22 = 983"),
    (S3_2425, 51, "IV-A", 5, 2, "PADDY Total", "Paddy", [11970, 4881, 0, 192, 17043], "2024-25 p40 'Paddy Total' 2024-25 = 17043"),
    (S3_2425, 52, "IV-A", 51, 48, "Coconut", "Coconut", [962, 163, 404, 268, 1797], "2024-25 p41 'Coconut' 2024-25 = 1797"),
    (S3_2425, 55, "V-A", 13, 2, "Sugarcane", "Sugarcane", [123000, 0, 0, 0, 123000], "2024-25 p42 'Sugarcane' yield 2024-25 = 123000"),
    (S3_2425, 56, "V-B", 14, 2, "Plantain", "Banana/Plantain", [4184, 150, 228, 0, 4562], "2024-25 p42 'Plantain' outturn 2024-25 = 4562"),
]

# S6 rows read from the saved HTML: (Sl.No, table, status, region printed, region, district, sub-district, type, reg no, name)
S6_CASES = [
    (1, 1, "working", "Pondy", "Puducherry", 600, None, "Primary", "14", "Pondicherry Co-operative Urban Bank"),
    (2, 1, "working", "Karaikal", "Karaikal", 598, None, "Central", "15",
     "The Karaikal Central Co-operative Processing Supply & Marketing Society Ltd."),
    (13, 1, "working", "Karaikal", "Karaikal", 598, None, "Primary", "38",
     "Thirunallar Primary Agricultural Co-operative Credit Society"),
    (54, 1, "working", "Mahe", "Mahe", 600, 5913, "Primary", "571", "Mahe Service Co-operative Credit Society"),
    (57, 1, "working", "Mahe", "Mahe", 600, 5913, "Primary", "791", "Mahe Urban Co-operative Society"),
    (1, 2, "dormant", "Pondy", "Puducherry", 600, None, "Primary", "25",
     "Siddhivinayagar Farmers Service Co-operative Society"),
]


def s3_case(n, spec):
    """Build one A2 test case (one table column, 5 region values) from a S3_CASES entry.
    The model input is the raw printed/OCR text of the block, read fresh from the PDF."""
    path, page, table, col, first_col, label, crop, values, summary = spec
    year = Path(path).stem.replace("S3_SCR_", "")
    text, method = block_text(Path(__file__).resolve().parents[1] / path, page, first_col)
    metric, unit = METRIC[table]
    if crop == "Coconut" and table == "V-A":
        unit = "nuts/ha"
    regions = ["Puducherry", "Karaikal", "Mahe", "Yanam", "UT"]
    return {
        "case_id": f"A2-{n:02d}", "agent": "A2", "source_id": "S3", "synthetic": False,
        "input_type": "pdf_vector_outline_ocr" if method == "ocr_tesseract" else "pdf_text_layer",
        "input_file": path, "page": page, "table": table, "column": col, "year": year,
        "crop": crop, "season": "All", "metric": metric, "unit": unit,
        "expected_tool": method, "expected": dict(zip(regions, values)),
        "expected_provenance": {"source_file_or_url": path,
                                "page_or_table": f"p{page} Table {table} col ({col})"},
        "instruction": instruction(year, table, col, label), "model_input": text,
        "verification": f"Read from 300-dpi render of p{page}; STATE matches {summary}; "
                        f"regions sum to STATE" + ("" if table == "V-A" else " (additive table)"),
        "summary_check": summary_check(summary),
        "checked_by": CHECKED_BY,
    }


def summary_check(summary):
    """Turn "2022-23 p34 'Paddy Total' 2021-22 = 18896" into a dict the verifier can test.
    Gives the summary report file, its page and the UT value printed there."""
    m = re.match(r"(\d{4}-\d{2}) p(\d+) .* = (\d+)$", summary)
    return {"file": f"data/raw/s3/S3_SCR_{m.group(1)}.pdf", "page": int(m.group(2)),
            "ut_value": int(m.group(3)), "text": summary}


def s6_case(n, spec):
    """Build one A3 test case for a co-operative society row of the real S6 page.
    The row number in page_or_table is Sl.No + 1 because the header is row 1."""
    sl, tab, status, raw, region, dist, sub, typ, reg, name = spec
    return {
        "case_id": f"A3-{n:02d}", "agent": "A3", "source_id": "S6", "synthetic": False,
        "input_type": "html_table", "input_file": S6_HTML, "match": {"name": name},
        "expected_tool": "bs4_html_table",
        "expected": {"region": region, "region_raw": raw, "lgd_district_code": dist,
                     "lgd_subdistrict_code": sub, "society_type": typ, "reg_no": reg,
                     "status": status},
        "expected_provenance": {"source_file_or_url": S6_HTML,
                                "page_or_table": f"table {tab} ({status}) row {sl + 1}"},
        "verification": f"Row Sl.No {sl} of the {status} table read from the saved HTML "
                        f"(<td> cells checked by eye); LGD codes from data/aliases.csv",
        "checked_by": CHECKED_BY,
    }


def fixture_cases():
    """Return the A1 (S2 prices) and A3 (S5 schemes) cases on the synthetic fixtures.
    Their expected values are the numbers typed into eval/fixtures/*.html."""
    s2 = [("2014-15", "Paddy", "I", 1155.0, "Rs/quintal", 2),
          ("2012-13", "Paddy", "II", 1033.0, "Rs/quintal", 3),
          ("2013-14", "Canegur", "", None, "Rs/quintal", 5),
          ("2011-12", "Coconut", "", 5122.0, "Rs/1000 nuts", 6)]
    cases = []
    for i, (period, com, var, price, unit, row) in enumerate(s2, start=1):
        cases.append({
            "case_id": f"A1-{i:02d}", "agent": "A1", "source_id": "S2", "synthetic": True,
            "input_type": "html_table", "input_file": S2_FIX,
            "match": {"period": period, "commodity": com, "variety": var},
            "expected_tool": "bs4_html_table",
            "expected": {"price_value": price, "price_unit": unit},
            "expected_provenance": {"source_file_or_url": S2_FIX,
                                    "page_or_table": f"table 1 row {row} col {period}"},
            "verification": "Synthetic fixture value" + (" (0 printed -> must be stored as NULL)"
                                                         if price is None else ""),
            "checked_by": CHECKED_BY})
    s5 = [("Paddy", 5000.0, "per acre", "per season", 2), ("Pulses", 2000.0, "per acre", None, 3)]
    for i, (crop, amount, basis, period, row) in enumerate(s5, start=7):
        cases.append({
            "case_id": f"A3-{i:02d}", "agent": "A3", "source_id": "S5", "synthetic": True,
            "input_type": "html_table", "input_file": S5_FIX,
            "match": {"scheme_name_contains": crop}, "expected_tool": "bs4_html_table",
            "expected": {"assistance_amount_rs": amount, "amount_basis": basis,
                         "period_basis": period},
            "expected_provenance": {"source_file_or_url": S5_FIX, "page_or_table": f"table 1 row {row}"},
            "verification": "Synthetic fixture layout; amounts as recorded for S5 in data/manifest.csv",
            "checked_by": CHECKED_BY})
    return cases


def main():
    """Assemble all cases and write eval/eval_set.json (pretty-printed, stable order).
    Prints how many cases each agent got."""
    cases = [s3_case(i, spec) for i, spec in enumerate(S3_CASES, start=1)]
    cases += [s6_case(i, spec) for i, spec in enumerate(S6_CASES, start=1)]
    cases += fixture_cases()
    out = {"name": "Team 35 Puducherry Phase 3 evaluation set", "created": "2026-11-26",
           "notes": "A2 = real S3 PDF columns (2021-22 OCR pages + 2024-25 text layer); "
                    "A3 = real S6 rows + synthetic S5 fixture; A1 = synthetic S2 fixture "
                    "(S2/S5 hosts are blocked from the build machine).",
           "cases": cases}
    path = EVAL_DIR / "eval_set.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for agent in ("A1", "A2", "A3"):
        print(agent, sum(c["agent"] == agent for c in cases), "cases")
    print(f"wrote {path.name}: {len(cases)} cases")


if __name__ == "__main__":
    main()
