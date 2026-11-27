"""Phase 3 corpus fetcher - Team 35 (Puducherry).

Run from the puducherry_agri_agent/ folder:
    python scripts/fetch_corpus.py

What it does
  1. Downloads every PDF listed in data/download_list_S3_S8.csv into
     data/raw/s3/ and data/raw/s8/ (1 s polite delay, 3 retries).
     Files that already exist and open as valid PDFs are skipped, so the
     script can be re-run (e.g. from a different network) to fill gaps.
  2. Inspects the cover of the S3 "2020-21" file to confirm its real year.
  3. Saves raw HTML snapshots of S2, S5, S6 into data/raw/html/.
  4. Builds data/aliases.csv from the official LGD exports in data/raw/lgd/.
  5. Writes data/raw/raw_inventory.csv (one row per raw file: status, bytes,
     sha256, pages, image-only pages) and updates volume_collected in
     data/manifest.csv.
"""
from __future__ import annotations

import csv
import hashlib
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import requests

try:
    import pymupdf as fitz  # PyMuPDF >= 1.24
except ImportError:  # pragma: no cover
    try:
        import fitz  # older PyMuPDF
    except ImportError:
        sys.exit("PyMuPDF missing: pip install pymupdf")

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    BeautifulSoup = None

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
MANIFEST = DATA / "manifest.csv"
DOWNLOAD_LIST = DATA / "download_list_S3_S8.csv"
INVENTORY = RAW / "raw_inventory.csv"
ALIASES = DATA / "aliases.csv"
LGD_DIR = RAW / "lgd"

DELAY_S = 1.0
RETRIES = 3
TIMEOUT_S = 90
HEADERS = {"User-Agent": "Team35-CSF407-academic-corpus-fetcher/1.0 (python-requests)"}
TODAY = date.today().isoformat()

HTML_SOURCES = {  # source_id -> short name used in the snapshot filename
    "S2": "mktpric",
    "S5": "schemes",
    "S6": "credit_coop_societies",
}
REGION_CODE = {"Puducherry": "PY", "Karaikal": "KKL"}
IMAGE_ONLY_CHARS = 30  # a page with less text than this (and an image) is treated as scanned

session = requests.Session()
session.headers.update(HEADERS)


# --------------------------------------------------------------------------- helpers
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, dest: Path, expect_pdf: bool) -> tuple[bool, str, int | None]:
    """Download url to dest atomically. Returns (ok, error_message, http_status)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    last_err, status = "", None
    for attempt in range(1, RETRIES + 1):
        try:
            with session.get(url, timeout=TIMEOUT_S, stream=True) as r:
                status = r.status_code
                r.raise_for_status()
                with tmp.open("wb") as f:
                    for chunk in r.iter_content(1 << 16):
                        f.write(chunk)
            if expect_pdf and not tmp.read_bytes()[:5].startswith(b"%PDF"):
                raise ValueError("response is not a PDF (missing %PDF header)")
            tmp.replace(dest)
            return True, "", status
        except Exception as e:  # noqa: BLE001 - we log every failure type
            last_err = f"{type(e).__name__}: {e}"[:300]
            tmp.unlink(missing_ok=True)
            if attempt < RETRIES:
                time.sleep(2 * attempt)
    return False, last_err, status


def pdf_stats(path: Path) -> dict:
    """Pages, text pages, image-only (likely scanned) pages."""
    with fitz.open(path) as doc:
        pages = doc.page_count
        image_only = 0
        for page in doc:
            if len(page.get_text().strip()) < IMAGE_ONLY_CHARS and page.get_images():
                image_only += 1
    return {"pages": pages, "image_only_pages": image_only}


def valid_pdf(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        with fitz.open(path) as doc:
            return doc.page_count > 0
    except Exception:  # noqa: BLE001
        return False


def pdf_filename(row: dict) -> Path:
    sid = row["source_id"].strip()
    period = row["period_or_date"].strip()
    if sid == "S3":
        return RAW / "s3" / f"S3_SCR_{period}.pdf"
    region = REGION_CODE.get(row["region"].strip(), re.sub(r"\W+", "_", row["region"].strip()))
    return RAW / "s8" / f"S8_AAB_{region}_{period}.pdf"


# --------------------------------------------------------------------------- step 1: PDFs
def download_pdfs() -> list[dict]:
    rows = list(csv.DictReader(DOWNLOAD_LIST.open(encoding="utf-8-sig")))
    inventory = []
    first_request = True
    for row in rows:
        url = row["url"].strip()
        dest = pdf_filename(row)
        rec = {
            "source_id": row["source_id"].strip(), "item": row["period_or_date"].strip(),
            "region": row["region"].strip(), "url": url, "local_path": dest.relative_to(ROOT).as_posix(),
            "status": "", "http_status": "", "bytes": "", "sha256": "", "pages": "",
            "image_only_pages": "", "error": "", "fetched_at": "",
        }
        if valid_pdf(dest):
            rec["status"] = "OK (already present)"
        else:
            if not first_request:
                time.sleep(DELAY_S)
            first_request = False
            ok, err, status = fetch(url, dest, expect_pdf=True)
            rec["http_status"] = status or ""
            rec["fetched_at"] = datetime.now().isoformat(timespec="seconds")
            if ok and valid_pdf(dest):
                rec["status"] = "OK"
            else:
                rec["status"] = "FAILED"
                rec["error"] = err or "downloaded file is not a readable PDF"
                dest.unlink(missing_ok=True)
        if rec["status"].startswith("OK"):
            rec.update(bytes=dest.stat().st_size, sha256=sha256(dest), **pdf_stats(dest))
        print(f"  [{rec['status']:<20}] {rec['source_id']} {rec['item']:<10} {rec['region']:<16} "
              f"pages={rec['pages']!s:<4} {rec['error']}")
        inventory.append(rec)
    return inventory


# --------------------------------------------------------------------------- step 2: S3 cover check
YEAR_RE = re.compile(r"\b(20\d\d)\s*[-–/]\s*(20)?(\d\d)\b")


def check_s3_cover(inventory: list[dict]) -> str:
    target = next((r for r in inventory if r["source_id"] == "S3" and r["item"] == "2020-21"), None)
    if not target or not target["status"].startswith("OK"):
        return "S3 2020-21 file not available - cover not checked."
    path = ROOT / target["local_path"]
    with fitz.open(path) as doc:
        cover = doc[0].get_text()
        first_pages = "\n".join(doc[i].get_text() for i in range(min(4, doc.page_count)))
    years = Counter(f"{m.group(1)}-{m.group(3)}" for m in YEAR_RE.finditer(first_pages))
    cover_years = [f"{m.group(1)}-{m.group(3)}" for m in YEAR_RE.finditer(cover)]
    same_as = [r["item"] for r in inventory
               if r is not target and r["sha256"] and r["sha256"] == target["sha256"]]
    lines = [
        f"S3 cover check - {target['local_path']} (listed as 2020-21)",
        f"URL: {target['url']}",
        f"Year strings on cover page (p.1): {cover_years or 'none found (cover may be an image)'}",
        f"Year strings on pp.1-4 (count): {dict(years.most_common(6))}",
        f"Byte-identical to other S3 files: {same_as or 'none'}",
        "--- cover page text (first 1500 chars) ---",
        cover.strip()[:1500] or "(no extractable text on cover)",
    ]
    report = "\n".join(lines)
    (RAW / "s3" / "cover_check_2020-21.txt").write_text(report + "\n", encoding="utf-8")
    pix = fitz.open(path)[0].get_pixmap(dpi=60)
    pix.save(RAW / "s3" / "cover_check_2020-21.png")
    return report


# --------------------------------------------------------------------------- step 3: HTML snapshots
def snapshot_html(manifest_rows: list[dict]) -> list[dict]:
    by_id = {r["source_id"]: r for r in manifest_rows}
    inventory = []
    for sid, short in HTML_SOURCES.items():
        url = by_id[sid]["url"].strip()
        dest = RAW / "html" / f"{sid}_{short}_{TODAY}.html"
        time.sleep(DELAY_S)
        ok, err, status = fetch(url, dest, expect_pdf=False)
        rec = {
            "source_id": sid, "item": f"snapshot {TODAY}", "region": "UT", "url": url,
            "local_path": dest.relative_to(ROOT).as_posix(), "status": "OK" if ok else "FAILED",
            "http_status": status or "", "bytes": "", "sha256": "", "pages": "", "image_only_pages": "",
            "error": err, "fetched_at": datetime.now().isoformat(timespec="seconds"),
        }
        if ok:
            rec.update(bytes=dest.stat().st_size, sha256=sha256(dest))
            if BeautifulSoup is not None:
                soup = BeautifulSoup(dest.read_text(encoding="utf-8", errors="replace"), "html.parser")
                tables = soup.find_all("table")
                rec["tables"] = len(tables)
                rec["table_rows"] = sum(len(t.find_all("tr")) for t in tables)
        else:
            # keep an older snapshot if one exists, so the corpus is never emptied by a bad run
            older = sorted((RAW / "html").glob(f"{sid}_{short}_*.html"))
            if older:
                rec["error"] += f" | older snapshot kept: {older[-1].name}"
        print(f"  [{rec['status']:<20}] {sid} {short:<22} bytes={rec['bytes']!s:<7} "
              f"tables={rec.get('tables', '')} rows={rec.get('table_rows', '')} {rec['error']}")
        inventory.append(rec)
    return inventory


# --------------------------------------------------------------------------- step 4: aliases
SS = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}


def read_spreadsheetml(path: Path) -> list[list[str]]:
    rows = []
    for r in ET.parse(path).iterfind(".//ss:Row", SS):
        cells = []
        for c in r.iterfind("ss:Cell", SS):
            d = c.find("ss:Data", SS)
            cells.append((d.text or "").strip() if d is not None and d.text else "")
        rows.append(cells)
    return rows


def lgd_tables() -> tuple[list[dict], list[dict], int]:
    def latest(prefix: str) -> Path:
        files = sorted(LGD_DIR.glob(f"{prefix}*.xls"))
        if not files:
            raise FileNotFoundError(f"no {prefix}*.xls in {LGD_DIR}")
        return files[-1]

    districts = [
        {"code": r[1], "name": r[3], "local": r[4], "census2011": r[6]}
        for r in read_spreadsheetml(latest("districtofSpecificState"))
        if len(r) >= 7 and r[1].isdigit()
    ]
    subdistricts = [
        {"district_code": r[1], "district": r[2], "code": r[3], "name": r[5], "local": r[6],
         "census2011": r[8]}
        for r in read_spreadsheetml(latest("subDistrictofSpecificState"))
        if len(r) >= 9 and r[3].isdigit()
    ]
    villages = sum(1 for r in read_spreadsheetml(latest("villageofSpecificState"))
                   if r and re.fullmatch(r"\d+(\.0)?", r[0] or ""))
    return districts, subdistricts, villages


# Spelling variants seen in our sources (S1 uses "Pondicherry", S8 file names use PY/KKL, etc.)
SPELLINGS = {
    "Puducherry": ["Pondicherry", "Pondichery", "Pondichéry", "Pondy", "Puduchery", "Puducheri",
                   "Puduvai", "Puthuvai", "PY", "PDY", "Puducherry Region", "Pondicherry Region"],
    "Karaikal": ["Karikal", "Karaikkal", "Karaical", "KKL", "Karaikal Region"],
    "Mahe": ["Mahé", "Mayyazhi", "Mayyali", "Mahe Region"],
    "Yanam": ["Yanaon", "Yenam", "Yanam Region"],
    "Oulgaret": ["Ozhukarai", "Uzhavarkarai", "Olgaret"],
    "Villianur": ["Villenour", "Villiyanur"],
    "Bahour": ["Bahur", "Bahoor"],
    "Thirunallar": ["Tirunallar", "Thirunallaru", "Tirunallaru"],
}


def build_aliases() -> tuple[int, int, int, int]:
    districts, subdistricts, villages = lgd_tables()
    dist = {d["name"]: d for d in districts}
    sub = {s["name"]: s for s in subdistricts}
    src = "LGD export 2026-11-04 (data/raw/lgd/)"
    out: list[dict] = []

    def add(alias, canonical, etype, dcode, dname, scode="", census="", note=""):
        out.append({"alias": alias, "canonical_name": canonical, "entity_type": etype,
                    "lgd_state_code": "34", "lgd_district_code": dcode, "lgd_district_name": dname,
                    "lgd_subdistrict_code": scode, "census2011_code": census, "source": src,
                    "notes": note})

    # State / UT
    for a in ["Puducherry", "Pondicherry", "Pondy", "U.T. of Puducherry", "Puducherry UT",
              "Union Territory of Puducherry", "Puduvai"]:
        add(a, "Puducherry", "state", "", "", note="UT, LGD state code 34")

    # Four reporting regions used by S3 / S8 / S2. LGD now has only 2 districts:
    # Mahe and Yanam are LGD sub-districts of Puducherry district (600).
    region_map = {
        "Puducherry": (dist["Puducherry"], "", "Region = LGD district 600 minus Mahe & Yanam "
                       "(taluks Puducherry, Oulgaret, Villianur, Bahour)"),
        "Karaikal": (dist["Karaikal"], "", "Region = LGD district 598 (taluks Karaikal, Thirunallar)"),
        "Mahe": (dist[sub["Mahe"]["district"]], sub["Mahe"]["code"],
                 "Not an LGD district in this export: LGD sub-district 5913 under district 600"),
        "Yanam": (dist[sub["Yanam"]["district"]], sub["Yanam"]["code"],
                  "Not an LGD district in this export: LGD sub-district 5908 under district 600"),
    }
    for region, (d, scode, note) in region_map.items():
        census = d["census2011"] if not scode else sub[region]["census2011"]
        local = sub[region]["local"] if scode else d["local"]
        for a in [region, local, *SPELLINGS[region]]:
            add(a, region, "region", d["code"], d["name"], scode, census, note)

    # Sub-districts (taluks) with their LGD codes
    for s in subdistricts:
        for a in [s["name"], s["local"], *SPELLINGS.get(s["name"], [])]:
            add(a, s["name"], "subdistrict", s["district_code"], s["district"], s["code"],
                s["census2011"])

    seen, rows = set(), []
    for r in out:
        key = (r["alias"].casefold(), r["entity_type"], r["canonical_name"])
        if r["alias"] and key not in seen:
            seen.add(key)
            rows.append(r)
    with ALIASES.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return len(rows), len(districts), len(subdistricts), villages


# --------------------------------------------------------------------------- step 5: inventory + manifest
INV_FIELDS = ["source_id", "item", "region", "url", "local_path", "status", "http_status", "bytes",
              "sha256", "pages", "image_only_pages", "tables", "table_rows", "error", "fetched_at"]


def write_inventory(rows: list[dict]) -> None:
    with INVENTORY.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=INV_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def pdf_volume(rows: list[dict], sid: str) -> str:
    sel = [r for r in rows if r["source_id"] == sid]
    ok = [r for r in sel if r["status"].startswith("OK")]
    pages = sum(int(r["pages"]) for r in ok)
    img = sum(int(r["image_only_pages"]) for r in ok)
    mb = sum(int(r["bytes"]) for r in ok) / 1e6
    txt = f"{len(ok)}/{len(sel)} PDFs, {pages} pages ({img} image-only), {mb:.1f} MB [{TODAY}]"
    if len(ok) < len(sel):
        txt += f"; {len(sel) - len(ok)} failed - see data/raw/raw_inventory.csv"
    return txt


def html_volume(rows: list[dict], sid: str) -> str:
    r = next(r for r in rows if r["source_id"] == sid)
    if r["status"] != "OK":
        return f"0 HTML snapshots - fetch failed {TODAY} ({r['error'][:80]})"
    extra = f", {r['tables']} table(s), {r['table_rows']} rows" if "tables" in r else ""
    return f"1 HTML snapshot ({int(r['bytes']) / 1024:.0f} KB{extra}) [{TODAY}]"


def update_manifest(rows: list[dict], lgd_counts: tuple[int, int, int]) -> dict:
    with MANIFEST.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields, mrows = reader.fieldnames, list(reader)
    n_d, n_s, n_v = lgd_counts
    volumes = {
        "S2": html_volume(rows, "S2"),
        "S3": pdf_volume(rows, "S3"),
        "S5": html_volume(rows, "S5"),
        "S6": html_volume(rows, "S6"),
        "S7": f"3 LGD SpreadsheetML exports (2026-11-04): {n_d} districts, {n_s} sub-districts, "
              f"{n_v} villages",
        "S8": pdf_volume(rows, "S8"),
        "S9": soi_volume(),
    }
    for r in mrows:
        if r["source_id"] in volumes:
            r["volume_collected"] = volumes[r["source_id"]]
    with MANIFEST.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(mrows)
    return volumes


def soi_volume() -> str:
    """S9 boundary files present in data/raw/soi/ (downloaded by scripts/plot_soi_map.py --download)."""
    shps = sorted((RAW / "soi").glob("*.shp"))
    if not shps:
        return "0 files - run: python scripts/plot_soi_map.py --download (SOI index maps, DataMeet mirror)"
    mb = sum(f.stat().st_size for f in (RAW / "soi").iterdir() if f.is_file()) / 1e6
    return f"{len(shps)} shapefiles ({', '.join(s.stem for s in shps)}) - {mb:.1f} MB [{TODAY}]"


# --------------------------------------------------------------------------- main
def main() -> int:
    manifest_rows = list(csv.DictReader(MANIFEST.open(encoding="utf-8-sig")))

    print("[1/5] Downloading PDFs from", DOWNLOAD_LIST.relative_to(ROOT))
    pdf_rows = download_pdfs()

    print("\n[2/5] Checking cover of S3 '2020-21' file")
    print("  " + check_s3_cover(pdf_rows).replace("\n", "\n  "))

    print("\n[3/5] Saving HTML snapshots")
    html_rows = snapshot_html(manifest_rows)

    print("\n[4/5] Building data/aliases.csv from LGD exports")
    n_alias, n_d, n_s, n_v = build_aliases()
    print(f"  {n_alias} alias rows  (LGD: {n_d} districts, {n_s} sub-districts, {n_v} villages)")

    print("\n[5/5] Writing raw_inventory.csv and updating manifest volume_collected")
    all_rows = pdf_rows + html_rows
    write_inventory(all_rows)
    for sid, vol in update_manifest(all_rows, (n_d, n_s, n_v)).items():
        print(f"  {sid}: {vol}")

    failed = [r for r in all_rows if r["status"] == "FAILED"]
    print(f"\nDone: {len(all_rows) - len(failed)}/{len(all_rows)} items OK, {len(failed)} failed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
