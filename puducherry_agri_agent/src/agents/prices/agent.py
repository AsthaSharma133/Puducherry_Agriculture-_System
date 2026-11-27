"""A1 - Market Price & Arrival Agent.

S2: Department of Agriculture Puducherry 'Average Wholesale Prices' (agri.py.gov.in/mktpric.html).
One static HTML table: Sl.No | Commodity/Variety | Units | 2010-11 ... 2014-15.

Ready to run once data/raw/html/S2_mktpric_*.html exists (the host blocks the cloud build
machine; fetch it locally with scripts/fetch_corpus.py). Without the file the agent reports
PENDING. S1 (AGMARKNET) stays Pending: CAPTCHA portal + current-day-only API.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ...common.config import RAW, rel
from ...normalizer.dedup import dedupe
from ...normalizer.units import price_unit, to_number
from ..base import Agent, AgentResult, InputMissing

YEAR_COL = re.compile(r"^(20\d{2})\s*[-–]\s*(\d{2})$")
VARIETY = re.compile(r"^(.*?)[\s\-]+(I{1,3}|IV)$")
COLUMN_NUMBER = re.compile(r"^\d+\.?$")       # the live page has a '1. 2. 3. ...' column-number row
DITTO = {",,", "„", '"', "do", "-do-", "do."}   # 'same unit as the row above'


def split_label(label: str) -> tuple[str, str]:
    """'Paddy - I sort' -> ('Paddy', 'I'); 'Onion - Dindigul' -> ('Onion', 'Dindigul');
    'Paddy I' -> ('Paddy', 'I'); 'Ragi' -> ('Ragi', '')."""
    if " - " in label:
        commodity, variety = label.split(" - ", 1)
        variety = re.sub(r"\s+sort$", "", variety.strip(), flags=re.I)
        return commodity.strip(), variety
    m = VARIETY.match(label)
    return (m.group(1).strip(), m.group(2)) if m else (label, "")


class PriceAgent(Agent):
    agent_id = "A1"
    name = "Market Price & Arrival Agent"
    handles = {"S1", "S2"}

    def run(self, source: dict, prov) -> AgentResult:
        if source["source_id"] == "S1":
            raise InputMissing("S1 AGMARKNET is Pending by design: CAPTCHA-protected portal and "
                               "a current-day-only API (documented automation barrier)")
        snaps = sorted((RAW / "html").glob("S2_mktpric_*.html"))
        if not snaps:
            raise InputMissing("no data/raw/html/S2_mktpric_*.html - agri.py.gov.in blocked from "
                               "cloud host; run scripts/fetch_corpus.py from India")
        return parse_s2(snaps[-1], prov)


def parse_s2(path, prov) -> AgentResult:
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    rows, issues = [], []
    src = rel(path)
    for t_i, table in enumerate(soup.find_all("table")):
        grid = [[c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                for tr in table.find_all("tr")]
        hdr_i = next((i for i, r in enumerate(grid) if sum(bool(YEAR_COL.match(c)) for c in r) >= 2), None)
        if hdr_i is None:
            continue
        header = grid[hdr_i]
        years = {j: c for j, c in enumerate(header) if YEAR_COL.match(c)}
        name_j = next((j for j, c in enumerate(header) if re.search(r"commodit|variet", c, re.I)), 1)
        unit_j = next((j for j, c in enumerate(header) if re.search(r"unit", c, re.I)), None)
        last_unit = ""
        for r_i, r in enumerate(grid[hdr_i + 1:], start=hdr_i + 2):
            if len(r) < len(header) or not r[name_j]:
                continue
            label = r[name_j]
            if COLUMN_NUMBER.match(label):
                continue  # '1. 2. 3. ...' column-number row, not a commodity
            commodity, variety = split_label(label)
            unit_raw = r[unit_j].strip() if unit_j is not None else ""
            if unit_raw.lower() in DITTO:
                unit_raw = last_unit  # ',,' = same unit as the row above
            last_unit = unit_raw
            for j, period in years.items():
                val, note = to_number(r[j])
                where = f"table {t_i + 1} row {r_i} col {period}"
                if val == 0:
                    # Validator: a wholesale price of 0 is a missing value, not a price
                    issues.append(prov.issue("WARNING", "zero_price_as_null",
                                             f"{label} {period}: 0 stored as NULL", src, where))
                    val = None
                elif note and note != "empty":
                    issues.append(prov.issue("WARNING", "non_numeric_cell", f"{label}: {note}", src, where))
                rows.append(prov.row(src, where, period=period, market_level="UT average wholesale",
                                     region=None, commodity=commodity, variety=variety,
                                     price_value=val, price_unit=price_unit(unit_raw),
                                     unit_raw=unit_raw or None))
    rows, dropped = dedupe(rows, ["period", "commodity", "variety"])
    for d in dropped:
        issues.append(prov.issue("WARNING", "duplicate_dropped",
                                 f"{d['commodity']} {d['variety']} {d['period']}", src, d["page_or_table"]))
    status = "SUCCESS" if rows else "FAILED"
    if not rows:
        issues.append(prov.issue("ERROR", "no_price_table", "no table with year columns found", src))
    return AgentResult(status, {"market_prices": rows}, issues, inputs_found=1,
                       notes=f"{len(rows)} commodity-year prices from {path.name}")
