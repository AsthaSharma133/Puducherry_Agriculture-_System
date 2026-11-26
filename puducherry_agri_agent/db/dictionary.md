# Data Dictionary: Puducherry Agricultural Intelligence System (Team 35, Phase 3)

Database: `db/puducherry_agri.db` (SQLite 3). Schema: `db/schema.sql`. Full SQL dump: `db/dump/puducherry_agri_dump.sql`.
Built by `python -m src.orchestrator` (see `README.md`).

## Provenance columns (on every data table)

| Column | Type | Meaning |
|---|---|---|
| `source_id` | TEXT | Manifest id (`S3`, `S6`, `S7`, …), see `data/manifest.csv` |
| `source_file_or_url` | TEXT | Raw file the value came from, relative to `puducherry_agri_agent/` (URL mapping in `data/raw/raw_inventory.csv`) |
| `page_or_table` | TEXT | Exact location, e.g. `p46 Table IV-A col (5); p49 Table V-A col (5); p50 Table V-B col (5)` or `table 1 (working) row 12` |
| `agent_id` | TEXT | `A1` prices, `A2` PDF reports, `A3` web entities, `REF` LGD lookup loader |
| `run_id` | TEXT | Pipeline run that wrote the row → `pipeline_runs.run_id` |
| `extracted_at` | TEXT | ISO-8601 UTC timestamp |

A re-run replaces a source's rows only when that source succeeds; FAILED/PENDING runs never delete data.

## `lgd_locations` (S7, REF)
Administrative units from the LGD exports plus the 4 reporting regions.

| Column | Type | Notes |
|---|---|---|
| `location_id` | INTEGER PK | |
| `entity_type` | TEXT | `state`, `district`, `subdistrict`, `village`, `region` |
| `lgd_code` | INTEGER | LGD code (NULL for `region`, which is not an LGD unit) |
| `name`, `local_name` | TEXT | English and local-script name as published by LGD |
| `lgd_state_code` | INTEGER | Always 34 |
| `lgd_district_code`, `lgd_subdistrict_code` | INTEGER | Parent codes |
| `region` | TEXT | Puducherry / Karaikal / Mahe / Yanam |
| `census2011_code` | TEXT | NULL where LGD publishes `000000` |
| `status` | TEXT | LGD village status (`Inhabitant`, …) |

**Note:** LGD lists only 2 districts: Karaikal (598) and Puducherry (600). Mahe (5913) and Yanam (5908) are sub-districts of district 600.

## `location_aliases` (S7, REF)
Spelling variants from `data/aliases.csv` (`Pondicherry`, `Pondy`, `PY` → Puducherry, …).
Columns: `alias`, `alias_key` (normalized lookup key), `canonical_name`, `entity_type`, `lgd_district_code`, `lgd_subdistrict_code`, `notes`. Unique on (`alias_key`, `entity_type`, `canonical_name`).

## `crop_statistics` (S3, A2)
One row per agricultural year × region × crop × season, merged from Season & Crop Report Tables IV-A (area), V-A (yield) and V-B (out-turn).

| Column | Type | Notes |
|---|---|---|
| `crop_year` | TEXT | Agricultural year July–June, `2020-21` … `2024-25` |
| `region` | TEXT | Puducherry / Karaikal / Mahe / Yanam / `UT` (the report's STATE row) |
| `lgd_district_code`, `lgd_subdistrict_code` | INTEGER | From `AliasResolver` |
| `crop` | TEXT | Canonical name (`src/normalizer/crops.py`) |
| `season` | TEXT | `I`, `II`, `III` (paddy crop seasons) or `All` |
| `is_aggregate` | INTEGER | 1 for totals (Total cereals, Gross cropped area, Net area sown, …) |
| `crop_label_raw` | TEXT | Header text extracted from the PDF |
| `area_ha` | REAL | Table IV-A, hectares |
| `yield_value`, `yield_unit` | REAL, TEXT | Table V-A: kg/ha (coconut: nuts/ha) |
| `production_value`, `production_unit` | REAL, TEXT | Table V-B: tonnes (coconut: thousand nuts, verified as area × yield / 1000) |
| `product_form` | TEXT | `rice (milled)` for paddy yield/production, `kapas` cotton, `kernels` groundnut, `nuts` coconut |
| `extraction_method` | TEXT | `text_layer` (PyMuPDF) or `ocr_tesseract` (2021-22 vector-outline pages) |
| `header_source` | TEXT | `page`, or `template:2020-21` when OCR column headers were taken from the nearest year with an identical layout |
| `validation_status` | TEXT | `ok`, `state_sum_mismatch` (STATE ≠ sum of regions), `area_yield_mismatch` |
| `area_yield_rel_error` | REAL | abs(area × yield / 1000 − production) / production |

Yield and production exist only for the ~30 principal crops in Tables V-A/V-B; IV-A covers all crops, so `area_ha` is filled for every row.

## `coop_societies` (S6, A3)
| Column | Type | Notes |
|---|---|---|
| `region` / `region_raw` | TEXT | Canonical region / as printed (`Pondy`) |
| `lgd_district_code`, `lgd_subdistrict_code` | INTEGER | |
| `society_type` | TEXT | Primary / Central / Apex |
| `reg_no`, `name` | TEXT | Registration number and society name (unique pair) |
| `status` | TEXT | `working` or `dormant` (from the table heading) |

The source page has no warehouse locations or capacities; none are claimed.

## `market_prices` (S2, A1; schema ready)
`period` (e.g. `2013-14`), `market_level` (`UT average wholesale`), `region` (NULL = UT), `commodity`, `variety` (`I`/`II` split from labels like *Paddy I*), `price_value` (0 in the source → NULL, logged), `price_unit` (`Rs/quintal`, `Rs/1000 nuts`), `unit_raw`.

## `schemes` (S5, A3; schema ready)
`scheme_name`, `category` (section heading), `crop`, `assistance_amount_rs`, `amount_basis` (per acre / per ha / per unit), `period_basis` (per season / per year), `description` (full row text), `valid_from` (snapshot date: the page is undated).

## `agromet_advisories` (S8, A2; schema ready)
Long format: `bulletin_date`, `region` (Puducherry / Karaikal), `lgd_district_code`, `section` (`past_weather`, `forecast`, `advisory`, `other`), `target_date`, `parameter`, `value_text`, `value_num`, `unit`, `crop`, `advisory_text`.

## `pipeline_runs` (orchestrator)
One row per source step and one `source_id = 'ALL'` summary row per run: `run_id`, `source_id`, `agent_id`, `status` (SUCCESS / PARTIAL / FAILED / PENDING / SKIPPED), `attempts`, `inputs_found`, `records_out`, `issues_logged`, `started_at`, `finished_at`, `duration_s`, `error_message`, `notes`, `trace_backend` (`langsmith` or `none`).

## `extraction_issues` (all agents)
Every problem found during extraction: `severity` (INFO / WARNING / ERROR), `issue_type`, `detail`, `needs_llm_review` (1 = a rule could not resolve it), plus the six provenance columns.
