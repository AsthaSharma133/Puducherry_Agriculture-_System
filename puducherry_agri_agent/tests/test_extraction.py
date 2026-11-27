"""Extraction tests on real inputs: S3 text-layer page, S3 vector-outline (OCR) page, S6 HTML."""
import tempfile
from pathlib import Path

import pymupdf
import pytest

from src.agents.pdf_reports import ocr, s3_tables
from src.agents.web_entities.agent import parse_s6
from src.common.provenance import Provenance

PROJECT = Path(__file__).resolve().parents[1]
SAMPLES = PROJECT / "samples"


def test_s3_text_layer_sample():
    """2020-21 p50 (Table V-B) is read from the text layer: rice total and sugarcane values."""
    with pymupdf.open(SAMPLES / "S3_SCR_2020-21_p50_tableVB_text_layer.pdf") as doc:
        blocks = s3_tables.blocks_from_text(doc[0], "2020-21", "V-B", [], "sample")
    first = blocks[0]
    assert first.rows["STATE"][5] == "50149"
    assert first.rows["PUDUCHERRY"][13] == "160080"
    assert s3_tables.column_meaning(first, 13, first.labels[13])[0] == "Sugarcane"


@pytest.mark.skipif(not ocr.available()[0], reason="tesseract not installed")
def test_s3_vector_outline_sample_needs_ocr():
    """2021-22 p49 has no text layer; OCR gives 5 region rows that add up (56254 t rice)."""
    with pymupdf.open(SAMPLES / "S3_SCR_2021-22_p49_tableVB_vector_needs_OCR.pdf") as doc:
        assert len(doc[0].get_text().strip()) < 30
        with tempfile.TemporaryDirectory() as tmp:
            old, ocr.CACHE = ocr.CACHE, Path(tmp)
            try:
                text = ocr.ocr_page(Path("sample.pdf"), doc[0], 1)
            finally:
                ocr.CACHE = old
    blocks = s3_tables.blocks_from_ocr(text, "2021-22", s3_tables.classify(text), 49, [])
    rice = blocks[0].rows
    assert rice["STATE"][5] == "56254" and rice["KARAIKAL"][5] == "12170"
    assert rice["PUDUCHERRY"][13] == "150840"


def test_s6_coop_societies():
    """The saved S6 page gives 58 working + 3 dormant societies with real registration numbers."""
    html = sorted((PROJECT / "data" / "raw" / "html").glob("S6_credit_coop_societies_*.html"))[-1]
    res = parse_s6(html, Provenance("S6", "A3", "test"))
    rows = res.tables["coop_societies"]
    assert len(rows) == 61
    assert sum(r["status"] == "dormant" for r in rows) == 3
    bank = next(r for r in rows if r["name"] == "Pondicherry Co-operative Urban Bank")
    assert (bank["reg_no"], bank["region"], bank["region_raw"]) == ("14", "Puducherry", "Pondy")
    assert all(r["reg_no"].isdigit() for r in rows), "reg_no must not hold the region text (bug E1)"
    mahe = next(r for r in rows if r["name"] == "Mahe Urban Co-operative Society")
    assert (mahe["lgd_district_code"], mahe["lgd_subdistrict_code"]) == (600, 5913)
