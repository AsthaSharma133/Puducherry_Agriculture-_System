# Puducherry Agriculture Information System (Team 35, CS F/U 407)

Multi-agent pipeline that collects Puducherry agricultural data from government web pages and
PDF reports, normalizes it to LGD codes, and loads it into SQLite with full provenance.

## Quick Start

```bash
cd puducherry_agri_agent
pip install -r requirements.txt          # plus the Tesseract binary for OCR (see below)
python -m src.orchestrator --reset-db    # build db/puducherry_agri.db from data/raw/
python -m unittest discover -s tests -t . -v
```

No raw PDFs? Run `python scripts/fetch_corpus.py` first (or copy the team's Google Drive corpus
into `data/raw/s3/` and `data/raw/s8/`). Two single-page samples are in `samples/`.

OCR (needed for the 2021-22 report, whose tables have no text layer):
Linux `sudo apt install tesseract-ocr`; Windows: install Tesseract (UB Mannheim build) and add it
to PATH. Without it the pipeline still runs and logs the skipped pages.

Optional tracing: copy `.env.example` to `.env` and set `LANGSMITH_API_KEY` (with
`pip install langsmith`). With no key, tracing is off and nothing else changes.

## Layout

| Path | Purpose |
|---|---|
| `data/manifest.csv` | Source manifest (S1-S9): status, agent, volume collected |
| `data/download_list_S3_S8.csv` | The 18 PDF URLs |
| `data/aliases.csv` | LGD codes + spelling aliases (Pondicherry → Puducherry, …) |
| `data/raw/` | Raw corpus: `s3/`, `s8/` PDFs (git-ignored), `html/`, `lgd/`, `raw_inventory.csv` |
| `scripts/fetch_corpus.py` | Polite downloader (1 s delay, retries, idempotent) |
| `src/orchestrator/` | Supervisor: routes manifest sources to agents, retries, logs `pipeline_runs` |
| `src/agents/prices/` | **A1** S2 wholesale prices (S1 AGMARKNET stays Pending) |
| `src/agents/pdf_reports/` | **A2** S3 Season & Crop Reports + S8 Agromet bulletins (PyMuPDF, OCR fallback) |
| `src/agents/web_entities/` | **A3** S6 co-op societies, S5 schemes (BeautifulSoup) |
| `src/normalizer/` | Deterministic LGD codes, crop names, units, dedup ([what is rule-based vs LLM](src/normalizer/README.md)) |
| `db/schema.sql`, `db/dictionary.md` | SQLite schema and data dictionary |
| `db/puducherry_agri.db`, `db/dump` | Built database and its SQL dump |
| `docs/extraction_errors.md` | Real errors hit during extraction, with fixes (User Manual input) |
| `tests/` | Unit tests (real sample pages + synthetic HTML for blocked sources) |
| `archive/phase2_unverified/` | Phase 2 metrics that cannot be traced to any run: **do not report** |
| `tools/`, `demo.py`, `eval/` | Phase 2 code, kept for reference; evaluation is rebuilt in Sprint 3 |

## Pipeline

```
data/manifest.csv ──► Orchestrator (src/orchestrator) ──► pipeline_runs / extraction_issues
                         │  routes by source_id
        ┌────────────────┼───────────────────┬──────────────────────┐
     REF (S7)          A1 (S2)             A2 (S3, S8)            A3 (S5, S6)
     LGD exports       HTML price table    PDF text layer         HTML tables
                                            └─ no text → OCR
        └────────────────┴──── Normalizer: LGD codes · crop names · units · dedup ──┘
                                     │  validation: STATE = Σ regions, area × yield ≈ production
                                     ▼
                         SQLite db/puducherry_agri.db (every row carries provenance)
```
