"""Run: python -m unittest discover -s tests -v   (from puducherry_agri_agent/)

S3 tests use the real sample pages in samples/. S2/S5 parsers are exercised with small
SYNTHETIC HTML (their real pages could not be fetched from the cloud build host), so those
tests only prove the parser logic, not coverage of the live page layout.
"""
import tempfile
import unittest
from pathlib import Path

import pymupdf

from src.agents.pdf_reports import ocr, s3_tables as T
from src.agents.prices.agent import parse_s2
from src.agents.web_entities.agent import parse_s5
from src.common.provenance import Provenance
from src.normalizer.crops import canonical_crop
from src.normalizer.lgd import AliasResolver
from src.normalizer.units import to_number

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
PROV = Provenance("TEST", "T", "test-run")


class NormalizerTests(unittest.TestCase):
    def test_aliases(self):
        r = AliasResolver()
        self.assertEqual(r.resolve("Pondicherry")["canonical"], "Puducherry")
        self.assertEqual(r.resolve("Pondy")["lgd_district_code"], 600)
        self.assertEqual(r.resolve("KKL")["lgd_district_code"], 598)
        self.assertEqual(r.resolve("Mahé")["lgd_subdistrict_code"], 5913)
        self.assertIsNone(r.resolve("Chennai"))

    def test_crops(self):
        self.assertEqual(canonical_crop("Plantain"), ("Banana/Plantain", False))
        self.assertEqual(canonical_crop("PUDUCHERRY Cereals Total"), ("Total cereals", True))
        self.assertEqual(canonical_crop("Other Pulsus"), ("Other pulses", False))
        self.assertIsNone(canonical_crop("Quinoa"))

    def test_numbers(self):
        self.assertEqual(to_number("1,20,000"), (120000.0, None))
        self.assertEqual(to_number("-"), (0.0, "dash_as_zero"))


class S3SampleTests(unittest.TestCase):
    def test_text_layer_sample(self):
        with pymupdf.open(SAMPLES / "S3_SCR_2020-21_p50_tableVB_text_layer.pdf") as doc:
            blocks = T.blocks_from_text(doc[0], "2020-21", "V-B", [], "sample")
        self.assertEqual(len(blocks), 2)
        b = blocks[0]
        self.assertEqual(b.rows["STATE"][5], "50149")              # total rice out-turn
        self.assertEqual(T.column_meaning(b, 13, b.labels[13])[0], "Sugarcane")
        self.assertEqual(b.rows["PUDUCHERRY"][13], "160080")

    @unittest.skipUnless(ocr.available()[0], "tesseract not installed")
    def test_vector_page_needs_ocr(self):
        with pymupdf.open(SAMPLES / "S3_SCR_2021-22_p49_tableVB_vector_needs_OCR.pdf") as doc:
            self.assertLess(len(doc[0].get_text().strip()), 30)        # no text layer
            with tempfile.TemporaryDirectory() as tmp:
                old, ocr.CACHE = ocr.CACHE, Path(tmp)
                try:
                    text = ocr.ocr_page(Path("sample.pdf"), doc[0], 1)
                finally:
                    ocr.CACHE = old
        issues = []
        blocks = T.blocks_from_ocr(text, "2021-22", T.classify(text), 49, issues)
        self.assertEqual(T.classify(text), "V-B")
        self.assertEqual([len(b.rows) for b in blocks], [5, 5])
        b = blocks[0]
        regions = sum(float(b.rows[r][5]) for r in ("PUDUCHERRY", "KARAIKAL", "MAHE", "YANAM"))
        self.assertEqual(regions, float(b.rows["STATE"][5]))         # 56254 t rice


SYNTHETIC_S2 = """<table><tr><th>Sl.No</th><th>Commodity/Variety</th><th>Units</th>
<th>2012-13</th><th>2013-14</th></tr>
<tr><td>1</td><td>Paddy I</td><td>Rs./Qtl</td><td>1,250</td><td>1,310</td></tr>
<tr><td>2</td><td>Canegur</td><td>Rs./Qtl</td><td>3,100</td><td>0</td></tr>
<tr><td>3</td><td>Coconut</td><td>Per 1000 nuts</td><td>9,000</td><td>9,500</td></tr></table>"""

SYNTHETIC_S5 = """<h3>Crop Incentives</h3><table>
<tr><td>1</td><td>Paddy production incentive</td><td>Rs.5,000 per acre per season</td></tr>
<tr><td>2</td><td>Pulses incentive</td><td>Rs.2,000/acre</td></tr></table>"""


class HtmlParserTests(unittest.TestCase):
    def _write(self, html, name):
        d = Path(tempfile.mkdtemp())
        p = d / name
        p.write_text(html, encoding="utf-8")
        return p

    def test_s2_parser_synthetic(self):
        res = parse_s2(self._write(SYNTHETIC_S2, "S2_mktpric_2026-01-01.html"), PROV)
        rows = res.tables["market_prices"]
        self.assertEqual(len(rows), 6)
        paddy = [r for r in rows if r["commodity"] == "Paddy" and r["period"] == "2012-13"][0]
        self.assertEqual((paddy["variety"], paddy["price_value"], paddy["price_unit"]),
                         ("I", 1250.0, "Rs/quintal"))
        cane = [r for r in rows if r["commodity"] == "Canegur" and r["period"] == "2013-14"][0]
        self.assertIsNone(cane["price_value"])                        # 0 -> NULL
        self.assertTrue(any(i["issue_type"] == "zero_price_as_null" for i in res.issues))

    def test_s5_parser_synthetic(self):
        res = parse_s5(self._write(SYNTHETIC_S5, "S5_schemes_2026-01-01.html"), PROV)
        rows = res.tables["schemes"]
        self.assertEqual([r["assistance_amount_rs"] for r in rows], [5000.0, 2000.0])
        self.assertEqual(rows[0]["period_basis"], "per season")
        self.assertEqual(rows[1]["amount_basis"], "per acre")
        self.assertEqual(rows[0]["valid_from"], "2026-01-01")


if __name__ == "__main__":
    unittest.main()
