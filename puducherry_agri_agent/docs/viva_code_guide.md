# Viva code guide (1 page) - Team 35 Puducherry agriculture system

## What each part does (2 sentences each)

| File / folder | What it does |
|---|---|
| `run.py` | The one command-line entry point: `--init-db`, `--run-all`, `--source S3`, `--input <file>`, `--query "..."`, `--demo-queries`. It only reads the option and calls the orchestrator, a parser or the query engine. |
| `src/orchestrator/` | The **supervisor agent**: `router.py` maps each manifest source (S2…S9) to an agent with a fixed table, `run.py` runs it, retries network errors, and writes one `pipeline_runs` row per source. A failed or pending source never deletes rows that were loaded before. |
| `src/agents/prices/` (A1) | Parses the S2 wholesale-price HTML table with BeautifulSoup into `market_prices`. A printed price of 0 is stored as NULL (it means "missing"). |
| `src/agents/pdf_reports/` (A2) | Reads S3 Tables IV-A/V-A/V-B: words from the PDF text layer are grouped into lines and columns by x/y position; pages with no text (2021-22) are rendered, ruling lines erased, and read by Tesseract (`ocr.py`). It then checks STATE = sum of regions and area × yield ≈ production. |
| `src/agents/web_entities/` (A3) | Parses the S6 co-op society tables and S5 scheme rows with BeautifulSoup. The `reg_no` bug the evaluation found was fixed here (`_col(..., avoid="region")`). |
| `src/normalizer/` | Deterministic clean-up: place names → LGD codes via `data/aliases.csv`, header text → canonical crop names, Indian number formats and units, and duplicate removal by natural key. Unknown names are logged, never guessed. |
| `src/common/` | Shared paths, the SQLite helpers (schema, replace-a-source's-rows in one transaction), the 6 provenance columns, and optional LangSmith tracing. |
| `db/schema.sql` | 9 tables: 7 data tables (each with source_id, source_file_or_url, page_or_table, agent_id, run_id, extracted_at) plus `pipeline_runs` and `extraction_issues`. UNIQUE keys stop duplicates. |
| `app/query_engine.py` | Answers questions: keyword rules choose the intent (value, compare, trend, provenance, coop, lgd), `location_aliases` finds regions, and a parameterised SQL query returns the answer with its SQL and provenance. An LLM is asked only if no rule matches and a key is set. |
| `eval/` | `eval_set.json` (28 hand-checked cases), `run_eval.py` (P/R/F1, provenance, tool choice, automation, errors), `benchmark_queries.json` + `run_queries.py` (10 live queries), `qlora_train.jsonl` + `check_overlap.py` (zero train/test overlap). `verify_ground_truth.py` re-checks S3 answers against the reports' own summary tables. |
| `notebooks/qlora_finetune_eval.ipynb` | Colab T4: base Qwen2.5-1.5B vs a 4-bit QLoRA adapter (r=16, α=32) on the held-out OCR cases (RQ2). Writes `eval/adapter_comparison.csv`. |
| `tests/` | 41 pytest checks: schema and provenance, LGD/alias rules, zero overlap, real S3 text/OCR and S6 extraction, all 10 queries. |

## Deterministic code vs LLM

| Deterministic (same input → same output) | LLM / learning |
|---|---|
| Routing, PDF/HTML parsing, OCR clean-up, LGD/crop/unit normalisation, dedup, validation, SQL answers | QLoRA extractor for hard OCR tables (RQ2 experiment, notebook only) |
| Every uncertain case is logged with `needs_llm_review = 1` instead of guessed | Optional query-engine fallback that only maps a question to parameters (never writes SQL or numbers) |

## CS F407 concepts in this project

* **PEAS** (for the supervisor + agents): *Performance* = field F1, provenance accuracy, automation
  rate, query pass rate; *Environment* = government web pages and PDFs (partially observable,
  some hosts blocked, layouts change by year); *Actuators* = downloads, table parsers, OCR,
  database writes, answers; *Sensors* = HTTP responses, PDF text layer / rendered pixels, HTML DOM.
* **Agent types:** the router is a simple reflex agent (condition-action table by source_id); A2 is
  model-based (it keeps a model of the table layout: column numbers, header templates from other
  years). The **learning agent** is the QLoRA loop: *performance element* = extractor, *critic* =
  `run_eval.py` / ground truth, *learning element* = fine-tuning on `qlora_train.jsonl`, *problem
  generator* = `needs_llm_review` cases. The S6 bug was found by the critic and fixed.
* **Knowledge base TELL / ASK:** agents TELL facts (rows with provenance) into SQLite via the
  normalizer; `app/query_engine.py` ASKs and returns the answer plus the evidence (source page),
  like a KB returning a justified answer.
* **CSP constraints** (checked on every extracted table): variables = table cells; domains =
  non-negative numbers; constraints = STATE = Puducherry + Karaikal + Mahe + Yanam (additive tables),
  area × yield / 1000 ≈ production (≤ 10 % or ≤ 1 unit), UNIQUE (year, region, crop, season), every
  region must resolve to an LGD code. Violations become `extraction_issues` rows.
