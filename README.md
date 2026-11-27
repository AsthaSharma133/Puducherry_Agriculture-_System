# Puducherry Agriculture Information System - Team 35 (CS F/U 407, Phase 3)

Multi-agent Python pipeline for Puducherry agricultural data: government HTML pages and PDF
reports (including vector-outline pages that need OCR) → LGD-normalised SQLite knowledge base with
full provenance → plain-English questions answered with the exact source file, page and table.

All code lives in [`puducherry_agri_agent/`](puducherry_agri_agent/README.md) (full documentation,
verified outputs, layout). Team roles: [`CONTRIBUTIONS.md`](CONTRIBUTIONS.md).

## Quick Start

```bash
cd puducherry_agri_agent
```

```bash
pip install -r requirements.txt
```

```bash
python run.py --demo-queries
```

```bash
python -m pytest tests/ -q
```

Expected: the 10 demo queries print answers with SQL and provenance, and `41 passed`. Both work
straight after cloning (the built database is committed). To rebuild from the raw sources and
re-evaluate:

```bash
python scripts/fetch_corpus.py
```

```bash
python run.py --init-db
```

```bash
python run.py --run-all
```

```bash
python eval/run_eval.py
```

```bash
python eval/run_queries.py
```

OCR needs the Tesseract program (`sudo apt install tesseract-ocr`, or the UB Mannheim installer on
Windows). No API keys are needed; optional keys are listed in `puducherry_agri_agent/.env.example`.

## Phase 3 results at a glance (2026-11-27)

| What | Result |
|---|---|
| Database rows | 2,059 data rows: 1,650 crop statistics (5 years × 4 regions + UT), 75 market prices (S2), 44 schemes (S5), 61 co-op societies, 144 LGD units, 85 aliases; 141 logged extraction issues. S8 = 0 (host unreachable) |
| Extraction (34 hand-checked real cases, 158 fields) | P = R = F1 = 1.000 for A1, A2, A3 after fixing a bug the evaluation found (A3 was 0.875 before) |
| Provenance / tool-selection accuracy | 1.000 / 1.000 |
| Live benchmark queries | 10/10 pass with exact answers and provenance |
| Train/test overlap for QLoRA | 0 (asserted in code and in tests) |
| QLoRA base vs adapter F1 (RQ2) | produced by `notebooks/qlora_finetune_eval.ipynb` on a Colab T4 (not yet run) |

Sources S2, S5 and S8 are implemented but their hosts refuse connections from outside India, so
they are PENDING in this build; see `puducherry_agri_agent/docs/extraction_errors.md`.
