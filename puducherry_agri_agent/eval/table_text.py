"""Turn one block of an S3 region table into plain text lines for the QLoRA model.
Used by build_eval_set.py and build_qlora_train.py so train and test inputs look the same.

A "block" is the column-number row "(1) (2) ... (16)" plus the 5 region rows
(PUDUCHERRY, KARAIKAL, MAHE, YANAM, STATE). Text-layer pages are read with PyMuPDF;
pages without a text layer (2021-22) are read from the Tesseract OCR output.
"""
import sys
from pathlib import Path

import pymupdf

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from src.agents.pdf_reports import ocr, s3_tables  # noqa: E402

REGION_KEYS = {"PUDUCHERRY": "Puducherry", "KARAIKAL": "Karaikal", "MAHE": "Mahe",
               "YANAM": "Yanam", "STATE": "UT"}
TABLE_TITLES = {"IV-A": "Region-wise area under all crops (hectares)",
                "V-A": "Region-wise yield rate of principal crops (kg per hectare)",
                "V-B": "Total out-turn of principal crops in each region (metric tonnes)"}


def page_lines(pdf_path, page_no):
    """Return the printed lines of one PDF page (1-based page number) and the method used.
    Text-layer pages give 'text_layer'; empty pages are OCR-ed and give 'ocr_tesseract'."""
    with pymupdf.open(pdf_path) as doc:
        page = doc[page_no - 1]
        if len(page.get_text().strip()) >= 30:
            lines = s3_tables._lines(page.get_text("words"))
            return [" ".join(word[4] for word in line) for line in lines], "text_layer"
        text = ocr.ocr_page(Path(pdf_path), page, page_no)
        return text.splitlines(), "ocr_tesseract"


def find_region(line):
    """Return the region word (PUDUCHERRY ... STATE) a line starts with, or None.
    OCR lines may start with junk such as '|' or '—', so the first 3 tokens are checked."""
    for token in line.split()[:3]:
        region = s3_tables._region_of(token)
        if region:
            return region
    return None


def block_text(pdf_path, page_no, first_col):
    """Return the text of the block whose column-number row starts at (first_col).
    The result is the number row plus the 5 region rows, exactly as printed or OCR-ed."""
    lines, method = page_lines(pdf_path, page_no)
    start = None
    for i, line in enumerate(lines):
        if "(1)" in line and f"({first_col})" in line:
            start = i
            break
    if start is None:
        raise ValueError(f"block starting at column ({first_col}) not found on p{page_no}")
    picked = [lines[start].strip()]
    for line in lines[start + 1:]:
        if find_region(line):
            picked.append(line.strip())
        if len(picked) == 6:
            break
    return "\n".join(picked), method


def instruction(year, table, column, label):
    """Return the task instruction given to the model for one table column.
    The same wording is used for training and for the held-out evaluation."""
    return (f"Season & Crop Report {year}, Table {table}: {TABLE_TITLES[table]}. "
            f"Column ({column}) is '{label}'. Read column ({column}) in every region row and "
            f"return only JSON with the keys Puducherry, Karaikal, Mahe, Yanam, UT "
            f"(UT is the STATE row). Use numbers; a '-' cell means 0.")
