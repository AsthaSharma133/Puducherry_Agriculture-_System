"""OCR fallback for PDF pages without a usable text layer.

Two kinds of 'no text' pages occur in the Season & Crop Reports:
  * raster scans (an embedded image), e.g. covers and some rainfall tables;
  * vector-outline pages (2021-22 pp.37-72): glyphs are drawn as filled paths, so there is
    neither text nor an image. Rendering the page and OCR-ing it is the only option.

Ruled table grid lines wreck Tesseract's line segmentation (rows come out as '__s067|_13243|'),
so before OCR we erase long horizontal/vertical dark runs with numpy (no OpenCV needed).
Results are cached in data/interim/ocr/ so re-runs are fast.
"""
from __future__ import annotations

import io
import shutil
from pathlib import Path

import numpy as np

from ...common.config import INTERIM

try:
    import pytesseract
    from PIL import Image
except ImportError:  # pragma: no cover
    pytesseract = None
    Image = None

OCR_DPI = 300
LINE_MIN_PX = 60          # a dark run this long (at 300 dpi = 5 mm) is treated as a ruling line
CACHE = INTERIM / "ocr"


def available() -> tuple[bool, str]:
    if pytesseract is None or Image is None:
        return False, "pytesseract/Pillow not installed (pip install pytesseract pillow)"
    if not shutil.which("tesseract"):
        return False, "tesseract binary not found (apt install tesseract-ocr / choco install tesseract)"
    return True, "tesseract " + str(pytesseract.get_tesseract_version())


def _runs(dark: np.ndarray, axis: int, k: int) -> np.ndarray:
    """Boolean mask of pixels that belong to a run of >= k dark pixels along `axis`."""
    c = np.cumsum(dark, axis=axis, dtype=np.int32)
    zero = np.zeros_like(c[:1]) if axis == 0 else np.zeros_like(c[:, :1])
    c = np.concatenate([zero, c], axis=axis)
    if axis == 1:
        full = (c[:, k:] - c[:, :-k]) == k            # window starting at column j is all dark
        out = np.zeros_like(dark, dtype=bool)
        for o in range(k):
            out[:, o:o + full.shape[1]] |= full
    else:
        full = (c[k:, :] - c[:-k, :]) == k
        out = np.zeros_like(dark, dtype=bool)
        for o in range(k):
            out[o:o + full.shape[0], :] |= full
    return out


def strip_ruling_lines(gray: np.ndarray, k: int = LINE_MIN_PX) -> np.ndarray:
    dark = gray < 160
    mask = _runs(dark, 1, k) | _runs(dark, 0, k)
    mask[1:, :] |= mask[:-1, :].copy()
    mask[:-1, :] |= mask[1:, :].copy()
    mask[:, 1:] |= mask[:, :-1].copy()
    mask[:, :-1] |= mask[:, 1:].copy()
    out = gray.copy()
    out[mask] = 255
    return out


def ocr_page(pdf_path: Path, page, page_no: int) -> str:
    """OCR one PyMuPDF page (1-based page_no for the cache key). Returns plain text."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cache = CACHE / f"{pdf_path.stem}_p{page_no:03d}.txt"
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    pix = page.get_pixmap(dpi=OCR_DPI)
    gray = np.array(Image.open(io.BytesIO(pix.tobytes("png"))).convert("L"))
    text = pytesseract.image_to_string(Image.fromarray(strip_ruling_lines(gray)),
                                       config="--psm 6")
    cache.write_text(text, encoding="utf-8")
    return text
