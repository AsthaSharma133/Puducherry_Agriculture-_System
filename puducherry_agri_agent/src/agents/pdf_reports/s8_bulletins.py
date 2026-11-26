"""S8 PAJANCOA&RI / IMD Agromet Advisory Bulletins (Puducherry 'AAB PY', Karaikal 'AAB KKL').

Status: written against the bulletin layout described in the manifest (past-week weather
table, 5-day forecast table, crop advisory table) but NOT yet run on real files: the
bulletin host (agritech.tnau.ac.in) refused connections from the cloud build machine.
Run scripts/fetch_corpus.py from India, then `python -m src.orchestrator --sources S8`.

Approach: PyMuPDF find_tables(); a table whose first column holds weather parameters
(Rainfall, Tmax, Tmin, RH, Wind, Cloud) becomes long-format weather rows (one per
parameter x date column); a table with a 'Crop' column becomes advisory rows.
Pages without a text layer fall back to OCR text stored as one 'other' row for review.
"""
from __future__ import annotations

import re
from pathlib import Path

import pymupdf

from ...common.config import rel
from ...normalizer.lgd import AliasResolver
from ...normalizer.units import to_number
from ..base import AgentResult, InputMissing
from . import ocr

NAME_RX = re.compile(r"S8_AAB_(PY|KKL)_(\d{4}-\d{2}-\d{2})\.pdf$")
PARAMS = [("rain", "Rainfall", "mm"), ("tmax", "Max temperature", "°C"),
          ("max", "Max temperature", "°C"), ("tmin", "Min temperature", "°C"),
          ("min", "Min temperature", "°C"), ("rh", "Relative humidity", "%"),
          ("humid", "Relative humidity", "%"), ("wind speed", "Wind speed", "km/h"),
          ("wind dir", "Wind direction", "deg"), ("cloud", "Cloud cover", "okta")]


def _param(label: str):
    lab = label.lower()
    for key, name, unit in PARAMS:
        if key in lab:
            return name, unit
    return None


def parse_bulletins(pdfs: list[Path], prov) -> AgentResult:
    if not pdfs:
        raise InputMissing("no data/raw/s8/*.pdf - agritech.tnau.ac.in blocked from cloud host; "
                           "run scripts/fetch_corpus.py from India")
    resolver = AliasResolver()
    rows, issues = [], []
    for pdf in pdfs:
        m = NAME_RX.search(pdf.name)
        if not m:
            issues.append(prov.issue("WARNING", "s8_unrecognised_filename", pdf.name, rel(pdf)))
            continue
        region = "Puducherry" if m.group(1) == "PY" else "Karaikal"
        lgd = resolver.resolve(region, "region")
        base = dict(bulletin_date=m.group(2), region=region,
                    lgd_district_code=lgd["lgd_district_code"] if lgd else None)
        with pymupdf.open(pdf) as doc:
            for page in doc:
                pno = page.number + 1
                text = page.get_text()
                if len(text.strip()) < 30:
                    ok, _ = ocr.available()
                    otext = ocr.ocr_page(pdf, page, pno) if ok else ""
                    rows.append(prov.row(rel(pdf), f"p{pno} OCR", **base, section="other",
                                         target_date=None, parameter=None, value_text=None,
                                         value_num=None, unit=None, crop=None,
                                         advisory_text=otext.strip()[:4000] or None))
                    issues.append(prov.issue("INFO", "no_text_layer_ocr_used", f"p{pno}", rel(pdf),
                                             f"p{pno}", needs_llm_review=True))
                    continue
                lower = text.lower()
                for t_i, tab in enumerate(page.find_tables()):
                    grid = [[(c or "").replace("\n", " ").strip() for c in r] for r in tab.extract()]
                    if len(grid) < 2:
                        continue
                    header = grid[0]
                    where = f"p{pno} table {t_i + 1}"
                    if any("crop" in h.lower() for h in header):
                        ci = next(i for i, h in enumerate(header) if "crop" in h.lower())
                        for r in grid[1:]:
                            adv = " ".join(x for i, x in enumerate(r) if i != ci and x)
                            if r[ci] or adv:
                                rows.append(prov.row(rel(pdf), where, **base, section="advisory",
                                                     target_date=None, parameter=None,
                                                     value_text=None, value_num=None, unit=None,
                                                     crop=r[ci] or None, advisory_text=adv or None))
                        continue
                    weather = [r for r in grid[1:] if r and _param(r[0])]
                    if not weather:
                        continue
                    section = "forecast" if "forecast" in lower and t_i > 0 else "past_weather"
                    for r in weather:
                        pname, unit = _param(r[0])
                        for j, cell in enumerate(r[1:], start=1):
                            if not cell:
                                continue
                            num, _ = to_number(cell)
                            rows.append(prov.row(rel(pdf), where, **base, section=section,
                                                 target_date=header[j] if j < len(header) else None,
                                                 parameter=pname, value_text=cell, value_num=num,
                                                 unit=unit, crop=None, advisory_text=None))
    status = "SUCCESS" if rows else "FAILED"
    return AgentResult(status, {"agromet_advisories": rows}, issues, inputs_found=len(pdfs),
                       notes=f"{len(pdfs)} bulletins parsed (parser not yet validated on real files)")
