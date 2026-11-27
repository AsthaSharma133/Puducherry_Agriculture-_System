"""S3 Season & Crop Report: region-wise crop tables IV-A (area), V-A (yield), V-B (out-turn).

Layout facts (verified on 2020-21 .. 2024-25):
  * Each table is printed in blocks. A block has a column-number row "(1) (2) ... (16)",
    header text above it, and 5 data rows: PUDUCHERRY, KARAIKAL, MAHE, YANAM, STATE.
  * Header text in the PDF text layer is scattered (group labels span columns, letters are
    spaced: "R I C E"), so we map header words to columns by x-position, not reading order.
  * 2021-22 pp.37-72 have no text layer (vector outlines): we OCR them and reuse the column
    headers of the nearest year with an identical block layout (header_source='template:YYYY').

Deterministic validation:
  * IV-A and V-B are additive: STATE must equal the sum of the 4 regions, column by column.
  * Cross-table: production ~= area * yield / 1000 (tonnes, or thousand nuts for coconut).
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from ...common.config import rel
from ...normalizer.crops import canonical_crop, product_form, season_only
from ...normalizer.units import to_number
from . import ocr

REGIONS = ["PUDUCHERRY", "KARAIKAL", "MAHE", "YANAM", "STATE"]
REGION_RX = re.compile(r"^(PUDUCHERRY|KARAIKAL|MAHE|YANAM|STATE)$", re.I)
NUM_RX = re.compile(r"^\((\d+)\)$")
TABLE_UNITS = {"IV-A": ("area_ha", "ha"), "V-A": ("yield_value", "kg/ha"),
               "V-B": ("production_value", "tonnes")}
ADDITIVE = {"IV-A", "V-B"}
TITLE_RX = re.compile(r"OUT\s*TURN|REGION\s*-?\s*WISE|UNDER\s+ALL\s+CROPS|YIELD\s+RATE|contd", re.I)


@dataclass
class Block:
    year: str
    table: str
    page: int
    cols: list[int]                                   # column numbers, excluding (1) REGION
    labels: dict[int, str] = field(default_factory=dict)
    rows: dict[str, dict[int, str]] = field(default_factory=dict)   # REGION -> col -> raw cell
    method: str = "text_layer"
    header_source: str = "page"


def classify(text: str) -> str | None:
    u = re.sub(r"[^A-Z0-9]", "", text.upper())
    if "IVAREGIONWISEAREAUNDERALLCROPS" in u:
        return "IV-A"
    if "VAREGIONWISEYIELD" in u:
        return "V-A"
    if "VBTOTALOUTTURN" in u:
        return "V-B"
    return None


# ----------------------------------------------------------------------------- text layer
def _lines(words, tol=3.0):
    """Group PyMuPDF words into visual lines by vertical centre."""
    ws = sorted(words, key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    lines, cur, cy = [], [], None
    for w in ws:
        yc = (w[1] + w[3]) / 2
        if cy is None or abs(yc - cy) <= tol:
            cur.append(w)
            cy = yc if cy is None else (cy + yc) / 2
        else:
            lines.append(sorted(cur, key=lambda x: x[0]))
            cur, cy = [w], yc
    if cur:
        lines.append(sorted(cur, key=lambda x: x[0]))
    return lines


def _drop_spaced_letters(line):
    """Remove runs of >=3 single letters ('F O O D  C R O P S', 'R I C E')."""
    out, run = [], []
    for w in line + [None]:
        if w is not None and len(w[4]) == 1 and w[4].isalpha():
            run.append(w)
            continue
        if len(run) < 3:
            out.extend(run)
        run = []
        if w is not None:
            out.append(w)
    return out


def blocks_from_text(page, year: str, table: str, issues: list, src: str) -> list[Block]:
    lines = _lines(page.get_text("words"))
    num_idx = [i for i, ln in enumerate(lines) if sum(bool(NUM_RX.match(w[4])) for w in ln) >= 5]
    blocks, prev_end = [], 0
    for b, li in enumerate(num_idx):
        ln = lines[li]
        cols = [(int(NUM_RX.match(w[4]).group(1)), (w[0] + w[2]) / 2) for w in ln if NUM_RX.match(w[4])]
        cols.sort(key=lambda c: c[1])
        centers = [c[1] for c in cols]
        bounds = [-1e9] + [(centers[i] + centers[i + 1]) / 2 for i in range(len(centers) - 1)] + [1e9]

        def col_of(xc):
            for i in range(len(cols)):
                if bounds[i] <= xc < bounds[i + 1]:
                    return cols[i][0]

        blk = Block(year, table, page.number + 1, [c[0] for c in cols if c[0] != 1])
        nxt = num_idx[b + 1] if b + 1 < len(num_idx) else len(lines)
        last_data = li
        for j in range(li + 1, nxt):
            words = lines[j]
            if not words or not REGION_RX.match(words[0][4]):
                continue
            region = words[0][4].upper()
            vals = [w for w in words[1:]]
            cells: dict[int, str] = {}
            if len(vals) == len(blk.cols):
                # one value per column: assign in order (numbers are right-aligned in their
                # cells while column labels are centred, so x-position alone can misplace them)
                blk.rows[region] = {c: w[4] for c, w in zip(blk.cols, vals)}
                last_data = j
                continue
            issues.append(("WARNING", "row_value_count_mismatch",
                           f"{table} {region}: {len(vals)} values for {len(blk.cols)} columns; "
                           f"assigned by x-position", f"p{blk.page} {table}"))
            for w in vals:
                c = col_of((w[0] + w[2]) / 2)
                if c in (None, 1):
                    continue
                if c in cells:
                    issues.append(("WARNING", "cell_collision",
                                   f"{table} {region}: two values map to col ({c}): "
                                   f"{cells[c]!r} and {w[4]!r}", f"p{blk.page} {table}"))
                cells[c] = w[4]
            blk.rows[region] = cells
            last_data = j
        # header words: between previous block's last data line and this number line
        for j in range(prev_end, li):
            joined = " ".join(w[4] for w in lines[j])
            if TITLE_RX.search(joined):          # table title / 'contd.' line, not a header
                continue
            for w in _drop_spaced_letters(lines[j]):
                c = col_of((w[0] + w[2]) / 2)
                if c and c != 1:
                    blk.labels[c] = (blk.labels.get(c, "") + " " + w[4]).strip()
        prev_end = last_data + 1
        if blk.rows:
            blocks.append(blk)
    return blocks


# ----------------------------------------------------------------------------- OCR pages
_OCR_FIX = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1", "|": "1", "S": "5", "B": "8"})


def _region_of(token: str) -> str | None:
    word = re.sub(r"[^A-Za-z]", "", token).upper()
    if len(word) < 4:
        return None
    m = difflib.get_close_matches(word, REGIONS, n=1, cutoff=0.75)
    return m[0] if m else None


def blocks_from_ocr(text: str, year: str, table: str, page_no: int, issues: list) -> list[Block]:
    blocks: list[Block] = []
    cur: Block | None = None
    for raw in text.splitlines():
        nums = re.findall(r"\((\d+)\)", raw)
        if len(nums) >= 5:
            cur = Block(year, table, page_no, [int(n) for n in nums if n != "1"],
                        method="ocr_tesseract")
            blocks.append(cur)
            continue
        toks = raw.replace("=", " ").split()
        if not toks or cur is None:
            continue
        # region word may be preceded by OCR junk like '—' or '|'
        k = next((i for i, t in enumerate(toks[:3]) if _region_of(t)), None)
        if k is None:
            continue
        region = _region_of(toks[k])
        vals = []
        for t in toks[k + 1:]:
            # a printed '0' comes back as '0)', '()', ')' ... and on Tesseract 5.4 (Windows)
            # also as 'f°)' or '¢)': any token ending in ')' with no digit 1-9 is a zero
            if t in ("(", "(0", "(0)") or (t.endswith(")") and not re.search(r"[1-9]", t)):
                issues.append(("INFO", "ocr_char_fix", f"{table} {region}: {t!r} read as '0'",
                               f"p{page_no} {table}"))
                vals.append("0")
                continue
            t2 = t.strip(".,;:_|()")
            if not t2:
                continue
            if re.fullmatch(r"\d+[-–]\d+", t2):
                # two cells glued by a left-over ruling line, e.g. '33-895' -> 33, 895
                # (a nil cell is a lone '-', so a dash between digits is never a value)
                parts = re.split(r"[-–]", t2)
                issues.append(("INFO", "ocr_char_fix", f"{table} {region}: {t2!r} split into {parts}",
                               f"p{page_no} {table}"))
                vals += parts
                continue
            if not re.fullmatch(r"[\d,.\-–]+", t2) and re.search(r"\d", t2):
                fixed = t2.translate(_OCR_FIX)
                if re.fullmatch(r"[\d,.]+", fixed):
                    issues.append(("INFO", "ocr_char_fix", f"{table} {region}: {t2!r} read as {fixed!r}",
                                   f"p{page_no} {table}"))
                    t2 = fixed
            if re.fullmatch(r"[\d,.]+|[-–]", t2):
                vals.append(t2)
        if len(vals) != len(cur.cols):
            issues.append(("ERROR", "ocr_column_count_mismatch",
                           f"{table} {region}: {len(vals)} numbers for {len(cur.cols)} columns "
                           f"in OCR line {raw.strip()[:120]!r}; row skipped", f"p{page_no} {table}"))
            continue
        cur.rows[region] = dict(zip(cur.cols, vals))
    return [b for b in blocks if b.rows]


# ----------------------------------------------------------------------------- per-file scan
def scan_pdf(pdf: Path, year: str, issues_out: list, ocr_ok: bool) -> tuple[list[Block], dict]:
    """Return target-table blocks of one report plus page statistics."""
    stats = {"pages": 0, "text_pages": 0, "ocr_pages": 0, "no_text_pages_skipped": 0}
    blocks: list[Block] = []
    src = rel(pdf)
    with pymupdf.open(pdf) as doc:
        stats["pages"] = doc.page_count
        last_kind = None
        for page in doc:
            pno = page.number + 1
            text = page.get_text()
            local: list = []
            if len(text.strip()) >= 30:
                stats["text_pages"] += 1
                kind = classify(text)
                if kind:
                    found = blocks_from_text(page, year, kind, local, src)
                    if found and year.replace("-", "") not in re.sub(r"\D", "", text):
                        local.append(("WARNING", "title_year_mismatch",
                                      f"{kind} page p{pno} does not mention {year}", f"p{pno}"))
                    blocks += found
                last_kind = kind
            else:
                kind_hint = "image" if page.get_images() else "vector-outline"
                if not ocr_ok:
                    stats["no_text_pages_skipped"] += 1
                    local.append(("WARNING", "no_text_layer_ocr_unavailable",
                                  f"p{pno} has no text layer ({kind_hint}); OCR not available",
                                  f"p{pno}"))
                else:
                    stats["ocr_pages"] += 1
                    otext = ocr.ocr_page(pdf, page, pno)
                    kind = classify(otext)
                    local.append(("INFO", "no_text_layer_ocr_used",
                                  f"p{pno} has no text layer ({kind_hint}); OCR -> "
                                  f"{kind or 'not a target table'}", f"p{pno}"))
                    if kind:
                        blocks += blocks_from_ocr(otext, year, kind, pno, local)
            for sev, typ, detail, where in local:
                issues_out.append((sev, typ, detail, src, where))
    return blocks, stats


# ----------------------------------------------------------------------------- header mapping
def column_meaning(blk: Block, col: int, label: str) -> tuple[str, str, bool] | None:
    """(crop, season, is_aggregate) for one column label, or None if unmapped."""
    so = season_only(label)
    first_block = min(blk.cols) == 2
    if so and first_block and col <= 5:
        return "Paddy", so, False
    hit = canonical_crop(label)
    if not hit:
        return None
    crop, agg = hit
    season = "All"
    if crop == "Paddy":
        toks = re.findall(r"[a-z]+", label.lower())
        romans = [t for t in toks if t in ("i", "ii", "iii", "total", "average")]
        season = {"i": "I", "ii": "II", "iii": "III"}.get(romans[-1], "All") if romans else "All"
    return crop, season, agg


def apply_templates(blocks: list[Block], issues_out: list) -> None:
    """Give OCR blocks the header labels of the nearest text-layer year with the same layout."""
    text_blocks = [b for b in blocks if b.method == "text_layer"]
    for b in blocks:
        if b.method != "ocr_tesseract":
            continue
        cands = [t for t in text_blocks if t.table == b.table and t.cols == b.cols]
        if not cands:
            issues_out.append(("ERROR", "no_header_template",
                               f"{b.year} {b.table} p{b.page}: no text-layer block with columns "
                               f"{b.cols[0]}..{b.cols[-1]} to borrow headers from", "", f"p{b.page}"))
            continue
        y0 = int(b.year[:4])
        cands.sort(key=lambda t: (abs(int(t.year[:4]) - y0), int(t.year[:4]) > y0))
        best = cands[0]
        b.labels = dict(best.labels)
        b.header_source = f"template:{best.year}"
        # do the two nearest years agree on what each column means?
        if len(cands) > 1:
            other = cands[1]
            diff = [c for c in b.cols
                    if column_meaning(best, c, best.labels.get(c, "")) !=
                    column_meaning(other, c, other.labels.get(c, ""))]
            if diff:
                issues_out.append(("WARNING", "template_disagreement",
                                   f"{b.year} {b.table} p{b.page}: templates {best.year} and "
                                   f"{other.year} disagree on columns {diff}", "", f"p{b.page}"))


def validate_state_sums(blocks: list[Block], issues_out: list, src_of: dict) -> set:
    """Return {(year, table, col)} where STATE != sum of regions (beyond +-2 rounding)."""
    bad = set()
    for b in blocks:
        if b.table not in ADDITIVE or "STATE" not in b.rows:
            continue
        for c in b.cols:
            vals = [to_number(b.rows.get(r, {}).get(c))[0] for r in REGIONS[:4]]
            state = to_number(b.rows["STATE"].get(c))[0]
            if state is None or any(v is None for v in vals):
                continue
            diff = abs(sum(vals) - state)
            where = f"p{b.page} {b.table} col ({c})"
            if diff == 0:
                continue
            if diff <= 2:
                issues_out.append(("INFO", "state_sum_rounding",
                                   f"{b.year} {b.table} col ({c}) {b.labels.get(c, '')!r}: "
                                   f"regions sum {sum(vals):g} vs STATE {state:g}", src_of[b.year], where))
            else:
                bad.add((b.year, b.table, c))
                issues_out.append(("WARNING", "state_sum_mismatch",
                                   f"{b.year} {b.table} col ({c}) {b.labels.get(c, '')!r} [{b.method}]: "
                                   f"regions sum {sum(vals):g} vs STATE {state:g}", src_of[b.year], where))
    return bad
