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

# 'Rs.5000/acre', 'Rs.2000/- acre', 'Rs12,500/- per ha', 'Rs.6,250/-- per ha', 'Rs.1.50 lakhs per Tube well'
AMOUNT_RX = re.compile(r"(?:Rs\.?|₹)\s*([\d,]+(?:\.\d+)?)\s*(lakhs?)?\s*(?:/-+)?\s*(?:per\s+|/)?\s*"
                       r"(acre|hectare|ha|cent|palm|tube\s*well|demonstration|group|block|"
                       r"farm\s*school|unit|no)?\b", re.I)
BASIS = {"acre": "per acre", "ha": "per ha", "hectare": "per ha", "unit": "per unit", "no": "per unit"}
# 'Subsidy for Paddy production', 'for new area under cashew cultivation', 'cultivation of Water melons @'
CROP_RX = re.compile(r"for (?:new area under )?([A-Za-z ]+?) (?:production|cultivation)\b"
                     r"|cultivation of ([A-Za-z ]+?)(?:\s*@|\s+like|\s+in\b)", re.I)


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


def _col(header: list[str], word: str, avoid: str | None = None) -> int:
    """Index of the first header cell containing `word` (and not containing `avoid`).
    Bug fixed 2026-11-26: 'reg' also matched 'region', so reg_no got the region text."""
    for i, h in enumerate(header):
        if word in h and not (avoid and avoid in h):
            return i
    raise ValueError(f"no header cell with {word!r} in {header}")


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
        ix = {"region": _col(header, "region"), "type": _col(header, "type"),
              "reg": _col(header, "reg", avoid="region"), "name": _col(header, "name")}
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


def scheme_items(soup):
    """Yield (where, category, name, text) for every candidate scheme on the page.
    The live page (checked 2026-11-27) has NO <table>: schemes are <li> items inside <ol>,
    each list starting with a <label><strong>Category</strong></label>. Older layouts and
    the test fixture use table rows, so both are read."""
    for t_i, table in enumerate(soup.find_all("table")):
        category = _section_heading(table)
        for r_i, tr in enumerate(table.find_all("tr"), start=1):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            text = " | ".join(c for c in cells if c)
            name = next((c for c in cells if c and not re.fullmatch(r"\d+\.?", c)), text)
            yield f"table {t_i + 1} row {r_i}", category, name, text
    for l_i, ol in enumerate(soup.find_all("ol"), start=1):
        label = ol.find("label")
        category = label.get_text(" ", strip=True) if label else ""
        for i_i, li in enumerate(ol.find_all("li"), start=1):
            lines = [x.strip() for x in li.get_text("\n").split("\n") if x.strip()]
            text = " ".join(" ".join(lines).split()).lstrip("> ")   # one item starts with a stray '>'
            name = re.split(r"\s*Eligibility\s*[–-]", lines[0].lstrip("> ") if lines else text)[0]
            yield f"list {l_i} item {i_i}", category, name.strip(), text


def parse_s5(path, prov) -> AgentResult:
    """Each scheme (list item or table row) with a rupee amount becomes a scheme row.
    The page is undated, so the snapshot date is stored as valid_from."""
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    snapshot_date = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
    valid_from = snapshot_date.group(1) if snapshot_date else datetime.now().date().isoformat()
    rows, issues, src = [], [], rel(path)
    for where, category, name, text in scheme_items(soup):
        m = AMOUNT_RX.search(text)
        if not m:
            continue
        amount, _ = to_number(m.group(1))
        if amount is not None and m.group(2):          # 'Rs.1.50 lakhs' -> 150000
            amount = round(amount * 100000, 2)
        word = re.sub(r"\s+", " ", (m.group(3) or "").lower())
        basis = BASIS.get(word, f"per {word}" if word else "unspecified")
        period = "per season" if re.search(r"season", text, re.I) else (
            "per year" if re.search(r"per\s+(year|annum)", text, re.I) else None)
        c = CROP_RX.search(name)
        crop = (c.group(1) or c.group(2)).strip().capitalize() if c else None
        rows.append(prov.row(src, where, scheme_name=name[:200], category=category or None,
                             crop=crop, assistance_amount_rs=amount, amount_basis=basis,
                             period_basis=period, description=text[:1000], valid_from=valid_from))
    rows, dropped = dedupe(rows, ["scheme_name", "description"])
    for d in dropped:
        issues.append(prov.issue("INFO", "duplicate_dropped", d["scheme_name"], src, d["page_or_table"]))
    if rows:
        issues.append(prov.issue("INFO", "llm_structuring_candidate",
                                 "Scheme rows keep the full item text (with eligibility) in "
                                 "`description`; only the first rupee amount is structured", src,
                                 needs_llm_review=True))
    return AgentResult("SUCCESS" if rows else "FAILED", {"schemes": rows}, issues, inputs_found=1,
                       notes=f"{len(rows)} scheme rows")
