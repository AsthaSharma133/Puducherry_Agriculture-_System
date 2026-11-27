"""Phase 2 quick-look demo, kept so old instructions still work.
It only PRINTS a text preview of a PDF, HTML page or file; it never writes to the database.

Usage (from puducherry_agri_agent/):
    python demo.py pdf samples/S3_SCR_2020-21_p50_tableVB_text_layer.pdf
    python demo.py static https://cooperative.py.gov.in/credit-co-operative-societies
    python demo.py file data/aliases.csv

For the real Phase 3 pipeline use run.py (python run.py --run-all / --input / --query).
The old version also created a legacy `scraped_logs` table in db/puducherry_agri.db; that
table is not part of db/schema.sql, so this demo no longer touches the database at all.
"""
import sys
from pathlib import Path

PREVIEW_CHARS = 500


def preview_pdf(path):
    """Return the text layer of every page of a PDF (empty pages are marked).
    Uses PyMuPDF, the same library Agent A2 uses."""
    import pymupdf

    parts = []
    with pymupdf.open(path) as doc:
        for page in doc:
            text = page.get_text().strip()
            if not text:
                text = "[no text layer: this page needs OCR - see src/agents/pdf_reports/ocr.py]"
            parts.append(f"--- Page {page.number + 1} ---\n{text}")
    return "\n".join(parts)


def preview_url(url):
    """Download a web page and return its visible text (scripts and styles removed).
    Uses requests + BeautifulSoup, the same libraries Agents A1 and A3 use."""
    import requests
    from bs4 import BeautifulSoup

    response = requests.get(url, timeout=15, headers={"User-Agent": "Team35-CSF407-demo/1.0"})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)


def preview_file(path):
    """Return the readable text of any local file (CSV, HTML, TXT ...).
    Non-printable bytes are replaced by spaces."""
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    return " ".join(text.split())


def main():
    """Pick the preview function from the mode argument and print the first characters.
    Returns 0 on success and 1 on error (nothing is saved anywhere)."""
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    mode, target = sys.argv[1].lower(), sys.argv[2]
    try:
        if mode == "pdf":
            text = preview_pdf(target)
        elif mode == "static" or target.startswith("http"):
            text = preview_url(target)
        else:
            text = preview_file(target)
    except Exception as error:  # show the error instead of a traceback in a live demo
        print(f"[!] Could not read {target}: {error}")
        return 1
    print("--- EXTRACTED OUTPUT PREVIEW (not saved) ---")
    print(text[:PREVIEW_CHARS])
    print(f"\n[{len(text)} characters read. Nothing was written to the database.]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
