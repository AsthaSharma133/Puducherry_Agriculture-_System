# Puducherry Agriculture Information System (Team 35, CS F/U 407, Phase 3)

A multi-agent Python pipeline that collects Puducherry agricultural data from government web
pages and PDF reports, normalises place names to LGD codes, stores everything in SQLite with full
provenance, and answers plain-English questions with the exact source page of every number.

**RQ2 (locked):** *Does QLoRA adaptation improve structured extraction on complex, multi-layout,
and vector-outline/OCR government PDF tables?* (see `docs/challenge.md`,
`notebooks/qlora_finetune_eval.ipynb`).

## Quick Start (copy-paste; outputs below were produced by these exact commands on 2026-11-27)

All commands run from this folder (`puducherry_agri_agent/`), Python 3.11+.

```bash
pip install -r requirements.txt
```

OCR for the 2021-22 report also needs the Tesseract program: Linux `sudo apt install tesseract-ocr`;
Windows: install the UB Mannheim build and add it to PATH. Without it the pipeline still runs and
logs the skipped pages.

**1. Ask the knowledge base** (works straight after cloning: the built database is in git)

```bash
python run.py --query "Which region had the highest paddy production in 2023-24?"
```
```
Q: Which region had the highest paddy production in 2023-24?
A: 2023-24 Paddy production (tonnes): Puducherry 46,970, Karaikal 13,821, Yanam 515, Mahe 0. Highest: Puducherry; lowest: Mahe.
   intent: compare
   SQL: SELECT crop_year, region, crop, production_value AS value, extraction_method, source_id, source_file_or_url, page_or_table FROM crop_statistics WHERE crop = ? AND season = 'All' AND region IN (?,?,?,?) AND crop_year IN (?) ORDER BY crop_year, region
   params: ['Paddy', 'Puducherry', 'Karaikal', 'Mahe', 'Yanam', '2023-24']
   provenance: S3 | data/raw/s3/S3_SCR_2023-24.pdf | p46 Table IV-A col (5); p50 Table V-A col (5); p51 Table V-B col (5)
```

```bash
python run.py --demo-queries
```
Prints the 10 presentation queries (3 spatial, 3 temporal, 2 provenance, 2 co-op/LGD), each with
answer, SQL and provenance.

**2. Run the tests** (no downloads needed)

```bash
python -m pytest tests/ -q
```
```
.........................................                                [100%]
41 passed in 3.98s
```

**3. Rebuild the database from the raw sources**

```bash
python scripts/fetch_corpus.py
```
Downloads the 5 S3 PDFs (30 MB, git-ignored) and the S8 bulletins; re-runnable, skips files already
present. `agri.py.gov.in` (S2, S5) refuses connections from non-Indian cloud hosts: run it from a
network in India. `agritech.tnau.ac.in` (S8) was unreachable even from India on 2026-11-27, so S8 stays
PENDING.

```bash
python run.py --init-db
```
```
Empty database created with 9 tables: agromet_advisories, coop_societies, crop_statistics, extraction_issues, lgd_locations, location_aliases, market_prices, pipeline_runs, schemes
Next: python run.py --run-all
```

```bash
python run.py --run-all
```
```
run 20261127T055617Z-0bf98d  db=db/puducherry_agri.db  tracing=none
  S7  REF  SUCCESS  rows=229   issues=39   1 state, 2 district, 8 subdistrict, 129 village, 4 region; 85 aliases
  S1  A1   PENDING  rows=0     issues=0    S1 AGMARKNET is Pending by design: CAPTCHA-protected portal and a current-day-only API (documented automation 
  S2  A1   SUCCESS  rows=75    issues=1    75 commodity-year prices from S2_mktpric_2026-11-27.html
  S3  A2   SUCCESS  rows=1650  issues=98   5 PDFs, 440 pages (386 text-layer, 54 OCR, 0 skipped); 45 table blocks; years 2020-21, 2021-22, 2022-23, 2023-
  S5  A3   SUCCESS  rows=44    issues=2    44 scheme rows
  S6  A3   SUCCESS  rows=61    issues=0    58 working + 3 dormant societies; 0 duplicate rows dropped
  S8  A2   PENDING  rows=0     issues=1    HOST_UNREACHABLE: agritech.tnau.ac.in refused/timed out TCP connections for 13 S8 bulletin downloads (also fro
  S4  A2   SKIPPED  rows=0     issues=0    Weekly report archive (2016-2018) is outside Phase 3 scope; S8 replaces it
  S9  REF  SKIPPED  rows=0     issues=0    Survey of India boundaries are a map layer, not extracted into the DB: data/raw/soi/ (SOI index maps via DataM
overall PARTIAL: 2059 rows, 141 issues, 4.29 s
```
(The first run on a new machine OCRs 54 pages and takes about 2 minutes; results are cached in
`data/interim/ocr/`.) One source only: `python run.py --source S3`.

**4. Evaluate**

Needs the S3 PDFs from step 3: run `python scripts/fetch_corpus.py` first, otherwise
`run_eval.py` stops with "The S3 PDFs are not in data/raw/s3/".

```bash
python eval/run_eval.py
```
```
  A1    n=6   fields=12   P=1.000 R=1.000 F1=1.000 prov=1.000 tool=1.000 done=1.000
  A2    n=16  fields=80   P=1.000 R=1.000 F1=1.000 prov=1.000 tool=1.000 done=1.000
  A3    n=12  fields=66   P=1.000 R=1.000 F1=1.000 prov=1.000 tool=1.000 done=1.000
  MACRO n=34  fields=158  P=1.000 R=1.000 F1=1.000 prov=1.000 tool=1.000 done=1.000
  automation (eval inputs): 1.0  skipped hooks: ['langsmith_upload', 'agentevals_trajectory_match', 'llm_as_judge']
```

```bash
python eval/run_queries.py
```
```
10/10 queries passed with exact answers and provenance -> query_results.csv
```

**5. Look at one input file without touching the database**

```bash
python run.py --input samples/S3_SCR_2021-22_p49_tableVB_vector_needs_OCR.pdf
```
Prints the OCR-read table (PUDUCHERRY 10725 15414 16951 43090 ... STATE 12697 26440 17117 56254 ...).

**6. Figures** (300 dpi, `docs/figures/`)

```bash
python scripts/generate_figures.py
```
Writes `fig_extraction_f1.png`, `fig_spatiotemporal_crop_trends.png`, `fig_architecture.png`,
`fig_er_diagram.png`, `fig_qlora_base_vs_adapter.png`. The SOI map:
```bash
python scripts/plot_soi_map.py --download   # once: 8 boundary files into data/raw/soi/ (git-ignored, 16 MB)
python scripts/plot_soi_map.py              # -> docs/figures/fig_puducherry_soi_map.png
```
Boundaries: Survey of India index maps (2011 Census districts), digitised by the DataMeet India
community, https://github.com/datameet/maps (`Survey-of-India-Index-Maps/Boundaries/`, CC BY 4.0).
The SOI Online Maps portal download was not available, so this SOI-derived mirror is used; every
map credits Survey of India and DataMeet.

Optional keys (`cp .env.example .env`): `LANGSMITH_API_KEY` turns on tracing and the eval upload,
`ANTHROPIC_API_KEY` turns on the query engine's LLM fallback. With no keys everything above runs
offline and gives the same results.

## What the numbers mean (honest reading)

* **Evaluation set** (`eval/eval_set.json`): 34 cases, 158 fields, all real (12 columns from the
  2021-22 vector-outline pages read by OCR, 4 from 2024-25, 6 S6 co-op rows, 6 S2 price cells and
  6 S5 scheme items from the live pages saved from India on 2026-11-27). S3 ground truth was read from
  page renders and re-checked against each report's own 5-year summary table
  (`python eval/verify_ground_truth.py`).
* The evaluation **found a real bug**: A3 stored the region text in `coop_societies.reg_no`
  (A3 F1 0.875 before the fix, 1.000 after; `docs/extraction_errors.md` E1).
* F1 = 1.000 is for the deterministic parsers on this small set. S8 is not covered: its host
  (`agritech.tnau.ac.in`) was unreachable even from India (`HOST_UNREACHABLE`). Automation: 8/8
  evaluation inputs fully automatic; 8/21 corpus downloads succeed (the 13 failures are all S8).
* QLoRA (RQ2): on the 16 held-out S3 columns (80 fields), field-level F1 goes from 0.0247 for the
  base Qwen2.5-1.5B-Instruct to 0.6625 with the 4-bit QLoRA adapter (+0.6378; OCR pages 0.0328 →
  0.6167, text-layer pages 0.0 → 0.8). Produced by the Colab notebook on a T4 and saved to
  `eval/adapter_comparison.csv` and `eval/qlora_train_log.json`. The rule-based A2 parser still
  scores 1.000 on the same cases, so the adapter is a fallback for rows flagged `needs_llm_review`.
* **Adapter weights** (`qlora_adapter_team35.zip`, not stored in git), in the Drive folder: https://drive.google.com/drive/folders/1CoDbHaUQMSki3i939j3LgqV4uNe_yicc

## Layout

| Path | Purpose |
|---|---|
| `run.py` | Single CLI entry point (`--init-db`, `--run-all`, `--source`, `--input`, `--query`, `--demo-queries`) |
| `src/orchestrator/` | Supervisor: routes manifest sources to agents, retries, logs `pipeline_runs` |
| `src/agents/prices/` | **A1** S2 wholesale prices (S1 AGMARKNET stays Pending) |
| `src/agents/pdf_reports/` | **A2** S3 Season & Crop Reports + S8 bulletins (PyMuPDF, Tesseract OCR fallback) |
| `src/agents/web_entities/` | **A3** S6 co-op societies, S5 schemes (BeautifulSoup) |
| `src/normalizer/` | Deterministic LGD codes, crop names, units, dedup ([rules vs LLM](src/normalizer/README.md)) |
| `app/query_engine.py` | Knowledge-base ASK: keyword intents + aliases + parameterised SQL + provenance |
| `db/schema.sql`, `db/dictionary.md` | SQLite schema and data dictionary |
| `db/puducherry_agri.db`, `db/dump/puducherry_agri_dump.sql` | Built database and its SQL dump |
| `eval/` | Evaluation set, QLoRA training set, overlap check, `run_eval.py`, `run_queries.py` ([details](eval/README.md)) |
| `notebooks/qlora_finetune_eval.ipynb` | Colab T4 notebook: base vs QLoRA adapter on the held-out OCR cases |
| `scripts/` | `fetch_corpus.py`, `generate_figures.py`, `plot_soi_map.py` |
| `docs/` | `challenge.md` (RQ2), `extraction_errors.md` (User Manual section 7), `viva_code_guide.md`, `figures/` |
| `data/` | Manifest, LGD aliases, raw corpus (`s3/`, `s8/` PDFs git-ignored) |
| `samples/` | Two single PDF pages (text layer and vector-outline) for quick tests |
| `tests/` | pytest suite (schema, provenance, normalisation, overlap, extraction, 10 queries) |
| `archive/` | Phase 2 files that cannot be verified or are no longer used: **do not report** |
| `demo.py` | Phase 2 preview tool, now print-only (never writes the DB) |

## Pipeline

```
data/manifest.csv ──► Supervisor (src/orchestrator) ──► pipeline_runs / extraction_issues
                         │  routes by source_id (rule-based)
        ┌────────────────┼───────────────────┬──────────────────────┐
     REF (S7)          A1 (S2)             A2 (S3, S8)            A3 (S5, S6)
     LGD exports       HTML price table    PDF text layer         HTML tables
                                            └─ no text → OCR
        └────────────────┴──── Normalizer: LGD codes · crop names · units · dedup ──┘
                                     │  validation: STATE = Σ regions, area × yield ≈ production
                                     ▼
                  SQLite db/puducherry_agri.db (TELL; every row carries 6 provenance columns)
                                     ▼
                  app/query_engine.py (ASK) ──► answer + SQL + source file/page/table
```

Team roles: see [`../CONTRIBUTIONS.md`](../CONTRIBUTIONS.md). Viva cheat sheet:
[`docs/viva_code_guide.md`](docs/viva_code_guide.md).
