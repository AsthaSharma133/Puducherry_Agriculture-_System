# Normalizer: what deterministic code does vs. what an LLM handles

Everything in this folder is **deterministic Python**: the same input always gives the same
output, and every rule is listed here. No LLM is called anywhere in the Phase 3 pipeline;
places where an LLM *would* help are logged as `extraction_issues.needs_llm_review = 1`.

| Task | Module | Rule (deterministic) |
|---|---|---|
| Region / LGD codes | `lgd.py` (`AliasResolver`) | Exact lookup of a casefolded, accent- and punctuation-stripped key in `data/aliases.csv`. `Pondicherry`, `Pondy`, `PY` → Puducherry (LGD district 600); `Karikal`, `KKL` → Karaikal (598); `Mahé`, `Mayyazhi` → Mahe (sub-district 5913 of district 600); `Yanaon` → Yanam (5908 of 600). Unknown names are **not guessed**: they raise an `unknown_region` issue. |
| LGD reference load | `lgd.py`, `reference.py` | Parses the LGD SpreadsheetML exports (state 34, 2 districts, 8 sub-districts, 129 villages) and assigns each unit to one of the 4 reporting regions by its codes. |
| Crop names | `crops.py` | Tokenise the header text, drop title/unit noise words, match ordered keyword rules (e.g. `plantain`/`banana` → *Banana/Plantain*; `sesamum`/`gingelly` → *Sesamum (gingelly)*; `total`+`cereals` → aggregate *Total cereals*). Unmatched header → `unmapped_header` issue, column skipped. |
| Numbers & units | `units.py` | Indian digit grouping (`1,20,000`), `-` = nil → 0 (logged `dash_as_zero`), price units → `Rs/quintal` / `Rs/1000 nuts`, acre → ha factor 0.40468564224. S3 units fixed per table: IV-A ha, V-A kg/ha (coconut nuts/ha), V-B tonnes (coconut thousand nuts: verified as area × yield / 1000). |
| Deduplication | `dedup.py` | Natural keys, first occurrence wins, every dropped row logged (`duplicate_dropped`). Keys: crop stats (year, region, crop, season); co-ops (reg_no, name); prices (period, commodity, variety). The DB also enforces them with UNIQUE constraints. |
| Validation (in A2) | `agents/pdf_reports/s3_tables.py` | STATE row = sum of the 4 regions for additive tables (IV-A, V-B); cross-table area × yield / 1000 ≈ production (flag if > 10 % **and** > 1 unit). |

## Where an LLM is (or will be) used

| Situation | Why rules are not enough | Status |
|---|---|---|
| Header text no rule matches (`unmapped_header`) | New crop names / layouts in future editions | Logged for review; candidate input for the QLoRA extractor (RQ2, Sprint 3) |
| OCR row with the wrong number of values (`ocr_column_count_mismatch`) | Merged/lost cells in noisy scans | Row skipped and logged; QLoRA reconstruction is the RQ2 experiment |
| Scheme rows (S5) | Free text: eligibility, crop, per-season vs per-year | Full row text stored in `schemes.description`; structuring left to the LLM |
| Agromet advisories (S8) | Free-text crop advice | Stored verbatim in `agromet_advisories.advisory_text` |

The orchestrator's routing (which agent handles which source) is also deterministic: it
follows `data/manifest.csv` and `src/orchestrator/router.py`.
