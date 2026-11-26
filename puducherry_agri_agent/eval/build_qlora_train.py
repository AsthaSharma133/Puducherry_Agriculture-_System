"""Write eval/qlora_train.jsonl: table-to-JSON training examples for the QLoRA notebook.
Examples come ONLY from the text-layer S3 reports 2020-21, 2022-23 and 2023-24, so they never
share a year (or page) with the held-out test cases (2021-22 OCR pages and 2024-25).

Labels are read from the PDF text layer by the A2 table parser and kept only if the
column passes the STATE = sum of regions check (for additive tables IV-A and V-B).
Every third example gets light OCR-style noise ("0" -> "0)", stray "|") so the model
also sees inputs that look like the Tesseract output it is tested on.

Run (from puducherry_agri_agent/):  python eval/build_qlora_train.py
"""
import json
import random
from pathlib import Path

from table_text import PROJECT, block_text, instruction
from src.agents.pdf_reports import s3_tables
from src.normalizer.units import to_number

TRAIN_YEARS = ["2020-21", "2022-23", "2023-24"]
REGION_KEYS = {"PUDUCHERRY": "Puducherry", "KARAIKAL": "Karaikal", "MAHE": "Mahe",
               "YANAM": "Yanam", "STATE": "UT"}
NOISE_SEED = 35


def pick_columns(block):
    """Choose which columns of a block become examples: first, middle and (for V-A/V-B) last.
    A fixed rule keeps the training set reproducible."""
    cols = block.cols
    picks = [cols[0], cols[len(cols) // 2]]
    if block.table in ("V-A", "V-B"):
        picks.append(cols[-1])
    return sorted(set(picks))


def column_values(block, col):
    """Return {region: number} for one column, or None if a cell is not a number.
    '-' is read as 0 by the shared to_number rule."""
    values = {}
    for printed, key in REGION_KEYS.items():
        number, _note = to_number(block.rows.get(printed, {}).get(col))
        if number is None:
            return None
        values[key] = int(number) if number == int(number) else number
    return values


def sums_ok(block, values):
    """True if the 4 regions add up to UT (within 2 for rounding) or the table is not additive.
    Yield tables (V-A) are averages, so they are not checked."""
    if block.table not in ("IV-A", "V-B"):
        return True
    regions = values["Puducherry"] + values["Karaikal"] + values["Mahe"] + values["Yanam"]
    return abs(regions - values["UT"]) <= 2


def add_ocr_noise(text, rng):
    """Make a clean text block look a little like Tesseract output.
    Some zeros become '0)' and some separators become ' | ' (numbers are never changed)."""
    out_lines = []
    for line in text.splitlines():
        tokens = []
        for token in line.split():
            if token == "0" and rng.random() < 0.3:
                token = "0)"
            tokens.append(token)
            if rng.random() < 0.08:
                tokens.append("|")
        out_lines.append(" ".join(tokens))
    return "\n".join(out_lines)


def examples_for_year(year, rng, start_id):
    """Build all training examples for one report year.
    Returns a list of dicts ready to be written as JSON lines."""
    pdf = PROJECT / "data" / "raw" / "s3" / f"S3_SCR_{year}.pdf"
    blocks, _stats = s3_tables.scan_pdf(pdf, year, [], ocr_ok=False)
    examples = []
    for block in blocks:
        for col in pick_columns(block):
            label = block.labels.get(col, "")
            meaning = s3_tables.column_meaning(block, col, label)
            values = column_values(block, col)
            if meaning is None or values is None or not sums_ok(block, values):
                continue
            text, _method = block_text(pdf, block.page, block.cols[0])
            noisy = (start_id + len(examples)) % 3 == 2
            examples.append({
                "id": f"train-{start_id + len(examples):03d}",
                "source_file": f"data/raw/s3/S3_SCR_{year}.pdf", "page": block.page,
                "table": block.table, "column": col, "year": year, "crop": meaning[0],
                "season": meaning[1], "regions": list(values),
                "instruction": instruction(year, block.table, col, label),
                "input": add_ocr_noise(text, rng) if noisy else text,
                "output": json.dumps(values), "ocr_noise_added": noisy,
            })
    return examples


def main():
    """Build examples for the 3 training years and write eval/qlora_train.jsonl.
    Prints the number of examples per year."""
    rng = random.Random(NOISE_SEED)
    rows = []
    for year in TRAIN_YEARS:
        new = examples_for_year(year, rng, len(rows) + 1)
        print(year, len(new), "examples")
        rows += new
    path = PROJECT / "eval" / "qlora_train.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {path.name}: {len(rows)} examples")


if __name__ == "__main__":
    main()
