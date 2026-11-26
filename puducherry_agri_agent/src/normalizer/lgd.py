"""LGD code resolution (deterministic).

- AliasResolver: maps any spelling in data/aliases.csv (Pondicherry, Pondy, KKL, Mahé, ...)
  to the canonical name and its LGD district / sub-district codes.
- load_lgd_locations(): builds lgd_locations rows from the S7 LGD SpreadsheetML exports.
"""
from __future__ import annotations

import csv
import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

from ..common.config import ALIASES, RAW, rel

SS = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}
LGD_DIR = RAW / "lgd"

# LGD has 2 districts; the 4 reporting regions map onto them like this (see aliases.csv notes).
SUBDISTRICT_REGION = {5913: "Mahe", 5908: "Yanam"}
DISTRICT_REGION = {598: "Karaikal", 600: "Puducherry"}


def alias_key(text: str) -> str:
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode() or str(text)
    return re.sub(r"[^0-9a-z\u0080-￿]+", "", t.casefold())


class AliasResolver:
    def __init__(self, path: Path = ALIASES):
        self.path = path
        with path.open(encoding="utf-8") as f:
            self.rows = list(csv.DictReader(f))
        self.index: dict[tuple[str, str], dict] = {}
        for r in self.rows:
            for key in {alias_key(r["alias"]), r["alias"].strip().casefold()}:
                self.index.setdefault((key, r["entity_type"]), r)

    def resolve(self, name: str, entity_type: str = "region") -> dict | None:
        """Canonical record for `name`, or None if unknown (caller logs an issue)."""
        r = self.index.get((alias_key(name), entity_type)) or \
            self.index.get((str(name).strip().casefold(), entity_type))
        if not r:
            return None
        return {"canonical": r["canonical_name"],
                "lgd_district_code": int(r["lgd_district_code"]) if r["lgd_district_code"] else None,
                "lgd_subdistrict_code": int(r["lgd_subdistrict_code"]) if r["lgd_subdistrict_code"] else None}


def read_spreadsheetml(path: Path) -> list[list[str]]:
    rows = []
    for r in ET.parse(path).iterfind(".//ss:Row", SS):
        cells = []
        for c in r.iterfind("ss:Cell", SS):
            d = c.find("ss:Data", SS)
            cells.append((d.text or "").strip() if d is not None and d.text else "")
        rows.append(cells)
    return rows


def _latest(prefix: str) -> Path:
    files = sorted(LGD_DIR.glob(f"{prefix}*.xls"))
    if not files:
        raise FileNotFoundError(f"No LGD export {prefix}*.xls in {rel(LGD_DIR)}")
    return files[-1]


def region_for(district_code: int | None, subdistrict_code: int | None) -> str | None:
    if subdistrict_code in SUBDISTRICT_REGION:
        return SUBDISTRICT_REGION[subdistrict_code]
    return DISTRICT_REGION.get(district_code)


def load_lgd_locations(prov) -> tuple[list[dict], list[dict]]:
    """Return (lgd_locations rows, issues) from the LGD exports."""
    rows, issues = [], []
    f_d, f_s, f_v = _latest("districtofSpecificState"), _latest("subDistrictofSpecificState"), \
        _latest("villageofSpecificState")

    rows.append(prov.row(rel(f_d), "state header", entity_type="state", lgd_code=34,
                         name="Puducherry", local_name="புதுச்சேரி", lgd_district_code=None,
                         lgd_subdistrict_code=None, region=None, census2011_code=None, status=None))
    for i, r in enumerate(read_spreadsheetml(f_d)):
        if len(r) >= 7 and r[1].isdigit():
            code = int(r[1])
            rows.append(prov.row(rel(f_d), f"row {i + 1}", entity_type="district", lgd_code=code,
                                 name=r[3], local_name=r[4], lgd_district_code=code,
                                 lgd_subdistrict_code=None, region=None, census2011_code=r[6],
                                 status=None))
    for i, r in enumerate(read_spreadsheetml(f_s)):
        if len(r) >= 9 and r[3].isdigit():
            d, s = int(r[1]), int(r[3])
            rows.append(prov.row(rel(f_s), f"row {i + 1}", entity_type="subdistrict", lgd_code=s,
                                 name=r[5], local_name=r[6], lgd_district_code=d,
                                 lgd_subdistrict_code=s, region=region_for(d, s),
                                 census2011_code=r[8], status=None))
    for i, r in enumerate(read_spreadsheetml(f_v)):
        if len(r) >= 12 and r[5].isdigit():
            d, s, v = int(r[1]), int(r[3]), int(r[5])
            census = r[11] if r[11] and r[11].strip("0") else None
            rows.append(prov.row(rel(f_v), f"row {i + 1}", entity_type="village", lgd_code=v,
                                 name=r[7], local_name=r[8], lgd_district_code=d,
                                 lgd_subdistrict_code=s, region=region_for(d, s),
                                 census2011_code=census, status=r[9] or None))
            if not census:
                issues.append(prov.issue("INFO", "lgd_missing_census_code",
                                         f"Village {r[7]} ({v}) has Census 2011 code '{r[11]}'",
                                         rel(f_v), f"row {i + 1}"))
    # The 4 reporting regions used by S3/S6/S8 (not LGD units themselves)
    for region, (d, s) in {"Puducherry": (600, None), "Karaikal": (598, None),
                           "Mahe": (600, 5913), "Yanam": (600, 5908)}.items():
        rows.append(prov.row(rel(ALIASES), "region rows", entity_type="region", lgd_code=None,
                             name=region, local_name=None, lgd_district_code=d,
                             lgd_subdistrict_code=s, region=region, census2011_code=None,
                             status=None))
    return rows, issues


def load_alias_rows(prov) -> list[dict]:
    out = []
    with ALIASES.open(encoding="utf-8") as f:
        alias_rows = list(csv.DictReader(f))
    for i, r in enumerate(alias_rows):
        out.append(prov.row(rel(ALIASES), f"row {i + 2}", alias=r["alias"],
                            alias_key=alias_key(r["alias"]), canonical_name=r["canonical_name"],
                            entity_type=r["entity_type"],
                            lgd_district_code=int(r["lgd_district_code"]) if r["lgd_district_code"] else None,
                            lgd_subdistrict_code=int(r["lgd_subdistrict_code"]) if r["lgd_subdistrict_code"] else None,
                            notes=r["notes"] or None))
    return out
