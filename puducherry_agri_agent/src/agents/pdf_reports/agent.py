"""A2 - PDF Report & Table Extraction Agent (S3 Season & Crop Reports, S8 Agromet bulletins).

Pipeline per PDF page:  PyMuPDF text layer -> word-position table parser
                        no text layer      -> render + grid-line removal + Tesseract OCR
then deterministic normalization (crop dictionary, LGD region codes, units) and validation.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from ...common.config import RAW, rel
from ...normalizer.crops import product_form
from ...normalizer.dedup import dedupe
from ...normalizer.lgd import AliasResolver
from ...normalizer.units import to_number
from ..base import Agent, AgentResult, InputMissing
from . import ocr, s3_tables as T
from .s8_bulletins import parse_bulletins

YEAR_RX = re.compile(r"S3_SCR_(\d{4}-\d{2})\.pdf$")
AREA_YIELD_TOL = 0.10          # >10 % gap between area*yield/1000 and production is flagged ...
ROUNDING_ABS = 1.0             # ... unless the gap is within 1 unit (published values are whole numbers)


class PdfReportAgent(Agent):
    agent_id = "A2"
    name = "PDF Report & Table Extraction Agent"
    handles = {"S3", "S8"}

    def run(self, source: dict, prov) -> AgentResult:
        if source["source_id"] == "S3":
            return self._run_s3(prov)
        return parse_bulletins(sorted((RAW / "s8").glob("*.pdf")), prov)

    # ------------------------------------------------------------------ S3
    def _run_s3(self, prov) -> AgentResult:
        pdfs = sorted(p for p in (RAW / "s3").glob("S3_SCR_*.pdf") if YEAR_RX.search(p.name))
        if not pdfs:
            raise InputMissing("no data/raw/s3/S3_SCR_*.pdf - run scripts/fetch_corpus.py")
        ocr_ok, ocr_msg = ocr.available()
        raw_issues: list[tuple] = []
        if not ocr_ok:
            raw_issues.append(("WARNING", "ocr_unavailable", ocr_msg, "", ""))
        blocks, stats = [], defaultdict(int)
        src_of = {}
        for pdf in pdfs:
            year = YEAR_RX.search(pdf.name).group(1)
            src_of[year] = rel(pdf)
            b, st = T.scan_pdf(pdf, year, raw_issues, ocr_ok)
            blocks += b
            for k, v in st.items():
                stats[k] += v
            if not b:
                raw_issues.append(("ERROR", "no_target_tables",
                                   f"{year}: tables IV-A/V-A/V-B not found", rel(pdf), ""))
        T.apply_templates(blocks, raw_issues)
        bad_cols = T.validate_state_sums(blocks, raw_issues, src_of)
        rows, issues = self._to_rows(blocks, bad_cols, src_of, prov, raw_issues)
        issues = [prov.issue(sev, typ, det, src, where, needs_llm_review=(
                  typ in ("unmapped_header", "ocr_column_count_mismatch", "no_header_template")))
                  for sev, typ, det, src, where in raw_issues] + issues
        years_done = sorted({r["crop_year"] for r in rows})
        status = "SUCCESS" if len(years_done) == len(pdfs) and not any(
            i["severity"] == "ERROR" for i in issues) else ("PARTIAL" if rows else "FAILED")
        notes = (f"{len(pdfs)} PDFs, {stats['pages']} pages ({stats['text_pages']} text-layer, "
                 f"{stats['ocr_pages']} OCR, {stats['no_text_pages_skipped']} skipped); "
                 f"{len(blocks)} table blocks; years {', '.join(years_done)}")
        return AgentResult(status, {"crop_statistics": rows}, issues, inputs_found=len(pdfs),
                           notes=notes)

    def _to_rows(self, blocks, bad_cols, src_of, prov, raw_issues):
        resolver = AliasResolver()
        merged: dict[tuple, dict] = {}
        issues = []
        for b in blocks:
            metric, unit = T.TABLE_UNITS[b.table]
            for c in b.cols:
                label = b.labels.get(c, "")
                meaning = T.column_meaning(b, c, label)
                where = f"p{b.page} Table {b.table} col ({c})"
                if meaning is None:
                    raw_issues.append(("WARNING", "unmapped_header",
                                       f"{b.year} {b.table} col ({c}) header {label!r} matches no "
                                       f"crop rule; column skipped", src_of[b.year], where))
                    continue
                crop, season, agg = meaning
                for region_raw, cells in b.rows.items():
                    if region_raw == "STATE":
                        region, d, s = "UT", None, None
                    else:
                        hit = resolver.resolve(region_raw.title(), "region")
                        if not hit:
                            raw_issues.append(("ERROR", "unknown_region", region_raw,
                                               src_of[b.year], where))
                            continue
                        region, d, s = hit["canonical"], hit["lgd_district_code"], hit["lgd_subdistrict_code"]
                    val, note = to_number(cells.get(c))
                    if note == "dash_as_zero":
                        raw_issues.append(("INFO", "dash_as_zero", f"{region_raw} {label!r}: '-' stored as 0",
                                           src_of[b.year], where))
                    elif note and note != "empty":
                        raw_issues.append(("WARNING", "non_numeric_cell", f"{region_raw} {label!r}: {note}",
                                           src_of[b.year], where))
                    key = (b.year, region, crop, season)
                    row = merged.get(key)
                    if row is None:
                        row = merged[key] = prov.row(
                            src_of[b.year], "", crop_year=b.year, region=region, lgd_district_code=d,
                            lgd_subdistrict_code=s, crop=crop, season=season, is_aggregate=int(agg),
                            crop_label_raw=label, area_ha=None, yield_value=None, yield_unit=None,
                            production_value=None, production_unit=None, product_form=None,
                            extraction_method=b.method, header_source=b.header_source,
                            validation_status="ok", area_yield_rel_error=None)
                        row["_pages"] = []
                    elif row.get(metric) is not None:
                        raw_issues.append(("WARNING", "duplicate_crop_column",
                                           f"{b.year} {region} {crop}/{season}: {b.table} has two "
                                           f"columns for it; kept the first", src_of[b.year], where))
                        continue
                    row[metric] = val
                    if b.table == "V-A":
                        row["yield_unit"] = "nuts/ha" if crop == "Coconut" else "kg/ha"
                    if b.table == "V-B":
                        row["production_unit"] = "thousand nuts" if crop == "Coconut" else "tonnes"
                    row["product_form"] = row["product_form"] or product_form(crop, label, b.table)
                    if b.method != "text_layer":
                        row["extraction_method"] = b.method
                        row["header_source"] = b.header_source
                    if (b.year, b.table, c) in bad_cols:
                        row["validation_status"] = "state_sum_mismatch"
                    row["_pages"].append(where)
        rows = []
        for row in merged.values():
            row["page_or_table"] = "; ".join(row.pop("_pages"))
            a, y, p = row["area_ha"], row["yield_value"], row["production_value"]
            if a and y and p:
                err = abs(a * y / 1000 - p) / p
                row["area_yield_rel_error"] = round(err, 4)
                if (err > AREA_YIELD_TOL and abs(a * y / 1000 - p) > ROUNDING_ABS
                        and row["validation_status"] == "ok"):
                    row["validation_status"] = "area_yield_mismatch"
                    issues.append(prov.issue(
                        "WARNING", "area_yield_mismatch",
                        f"{row['crop_year']} {row['region']} {row['crop']}/{row['season']}: "
                        f"area {a:g} ha x yield {y:g} {row['yield_unit']} / 1000 = {a * y / 1000:,.1f} "
                        f"vs published production {p:g} {row['production_unit']} ({err:.0%} gap)",
                        row["source_file_or_url"], row["page_or_table"]))
            rows.append(row)
        rows, dropped = dedupe(rows, ["crop_year", "region", "crop", "season"])
        for d in dropped:
            issues.append(prov.issue("WARNING", "duplicate_dropped",
                                     f"{d['crop_year']} {d['region']} {d['crop']}/{d['season']}",
                                     d["source_file_or_url"], d["page_or_table"]))
        return rows, issues
