"""A3 - Schemes & Infrastructure Agent (BeautifulSoup structured table parser).

S6  Co-operative Department: credit co-operative societies (working + dormant tables).
S5  Department of Agriculture schemes page (ready; the host blocks the cloud build machine,
    so it reports PENDING until data/raw/html/S5_schemes_*.html is fetched locally).
"""
from __future__ import annotations

import re
from datetime import datetime

from bs4 import BeautifulSoup

from ...common.config import RAW, rel
from ...normalizer.dedup import dedupe
from ...normalizer.lgd import AliasResolver
from ...normalizer.units import to_number
from ..base import Agent, AgentResult, InputMissing

AMOUNT_RX = re.compile(r"(?:Rs\.?|₹)\s*([\d,]+(?:\.\d+)?)\s*(?:/-)?\s*(?:per|/)?\s*(acre|ha|hectare|unit|no)?",
                       re.I)


class WebEntityAgent(Agent):
    agent_id = "A3"
    name = "Schemes & Infrastructure Agent"
    handles = {"S5", "S6"}

    def run(self, source: dict, prov) -> AgentResult:
        sid = source["source_id"]
        pattern = {"S5": "S5_schemes_*.html", "S6": "S6_credit_coop_societies_*.html"}[sid]
        snaps = sorted((RAW / "html").glob(pattern))
        if not snaps:
            raise InputMissing(f"no data/raw/html/{pattern} - run scripts/fetch_corpus.py "
                               f"(agri.py.gov.in is blocked from the cloud host)")
        return parse_s6(snaps[-1], prov) if sid == "S6" else parse_s5(snaps[-1], prov)


def _section_heading(table) -> str:
    h = table.find_previous(["h1", "h2", "h3", "h4", "h5", "strong", "p"])
    return h.get_text(" ", strip=True) if h else ""


def parse_s6(path, prov) -> AgentResult:
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    resolver = AliasResolver()
    rows, issues, src = [], [], rel(path)
    for t_i, table in enumerate(soup.find_all("table")):
        heading = _section_heading(table)
        status = "dormant" if "dormant" in heading.lower() else "working"
        grid = [[c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                for tr in table.find_all("tr")]
        header = [h.lower() for h in grid[0]] if grid else []
        if not any("reg" in h for h in header):
            issues.append(prov.issue("WARNING", "unexpected_table", f"table {t_i + 1}: header {grid[:1]}", src))
            continue
        ix = {k: next(i for i, h in enumerate(header) if k in h) for k in ("region", "type", "reg", "name")}
        for r_i, r in enumerate(grid[1:], start=2):
            if len(r) < len(header):
                continue
            where = f"table {t_i + 1} ({status}) row {r_i}"
            hit = resolver.resolve(r[ix["region"]], "region")
            if not hit:
                issues.append(prov.issue("ERROR", "unknown_region", r[ix["region"]], src, where))
                continue
            rows.append(prov.row(src, where, region=hit["canonical"], region_raw=r[ix["region"]],
                                 lgd_district_code=hit["lgd_district_code"],
                                 lgd_subdistrict_code=hit["lgd_subdistrict_code"],
                                 society_type=r[ix["type"]] or None, reg_no=r[ix["reg"]],
                                 name=re.sub(r"\s+", " ", r[ix["name"]]).strip(), status=status))
    rows, dropped = dedupe(rows, ["reg_no", "name"])
    for d in dropped:
        issues.append(prov.issue("INFO", "duplicate_dropped",
                                 f"Reg.No {d['reg_no']} {d['name']!r} repeated in the page "
                                 f"({d['status']} table)", src, d["page_or_table"]))
    working = sum(r["status"] == "working" for r in rows)
    return AgentResult("SUCCESS" if rows else "FAILED", {"coop_societies": rows}, issues,
                       inputs_found=1, notes=f"{working} working + {len(rows) - working} dormant "
                                             f"societies; {len(dropped)} duplicate rows dropped")


def parse_s5(path, prov) -> AgentResult:
    """Each table row with a rupee amount becomes a scheme row (page is undated -> valid_from)."""
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    snapshot_date = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
    valid_from = snapshot_date.group(1) if snapshot_date else datetime.now().date().isoformat()
    rows, issues, src = [], [], rel(path)
    for t_i, table in enumerate(soup.find_all("table")):
        category = _section_heading(table)
        for r_i, tr in enumerate(table.find_all("tr"), start=1):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            text = " | ".join(c for c in cells if c)
            m = AMOUNT_RX.search(text)
            if not m:
                continue
            amount, _ = to_number(m.group(1))
            basis = {"acre": "per acre", "ha": "per ha", "hectare": "per ha", "unit": "per unit",
                     "no": "per unit"}.get((m.group(2) or "").lower(), "unspecified")
            period = "per season" if re.search(r"season", text, re.I) else (
                "per year" if re.search(r"year|annum", text, re.I) else None)
            name = next((c for c in cells if c and not re.fullmatch(r"\d+\.?", c)), text)[:200]
            rows.append(prov.row(src, f"table {t_i + 1} row {r_i}", scheme_name=name,
                                 category=category or None, crop=None,
                                 assistance_amount_rs=amount, amount_basis=basis,
                                 period_basis=period, description=text[:1000],
                                 valid_from=valid_from))
    rows, dropped = dedupe(rows, ["scheme_name", "description"])
    for d in dropped:
        issues.append(prov.issue("INFO", "duplicate_dropped", d["scheme_name"], src, d["page_or_table"]))
    if rows:
        issues.append(prov.issue("INFO", "llm_structuring_candidate",
                                 "Scheme rows keep the full row text in `description`; crop and "
                                 "eligibility fields are left for the LLM structurer", src,
                                 needs_llm_review=True))
    return AgentResult("SUCCESS" if rows else "FAILED", {"schemes": rows}, issues, inputs_found=1,
                       notes=f"{len(rows)} scheme rows")
