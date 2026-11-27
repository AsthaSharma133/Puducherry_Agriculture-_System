# Real extraction errors (Sprints 2-3, 2026-11-26) - for the User Manual (Section 7)

Every error below was hit while building and running the pipeline on the real corpus.
Messages are copied from the pipeline output or `extraction_issues`. "Status" says how it is
handled now. Query current issues with:

```sql
SELECT source_id, severity, issue_type, COUNT(*) FROM extraction_issues
WHERE run_id = (SELECT run_id FROM pipeline_runs ORDER BY run_step_id DESC LIMIT 1)
GROUP BY 1, 2, 3;
```

## A. Acquisition (scripts/fetch_corpus.py)

| # | Error | Cause | Status / user action |
|---|---|---|---|
| A1 | `ConnectionError: ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))` for all 13 S8 PDFs and the S2/S5 pages | `agri.py.gov.in` and `agritech.tnau.ac.in` drop connections from the cloud build host (other `.py.gov.in` hosts work); probably IP/geo filtering | Re-run `python scripts/fetch_corpus.py` from a network in India; it skips files already present. Agents then report PENDING → SUCCESS. |
| A2 | S3 file for "2020-21" is named `season-crop-report-2021-22.pdf` | Mislabelled upload on the DES site | Cover page checked automatically: reads "SEASON AND CROP REPORT 2020-21" (`data/raw/s3/cover_check_2020-21.txt`). |
| A3 | `HOST_UNREACHABLE` - `ConnectTimeout: HTTPSConnectionPool(host='agritech.tnau.ac.in', port=443)` for all 13 S8 bulletins, **also from a home network in India** (2026-11-27). `curl` to ports 443 and 80 times out after ~21 s although DNS resolves (14.139.187.9) and `tnau.ac.in` itself answers | Host-side outage or firewall on `agritech.tnau.ac.in`, not a client or code problem. (S2/S5 on `agri.py.gov.in` now download fine from India, so A1 above is resolved for them.) | S8 is recorded as `pipeline_runs.status = PENDING`, `error_message = HOST_UNREACHABLE` plus one `host_unreachable` ERROR in `extraction_issues` (count read from `raw_inventory.csv`). The S8 parser is still **unvalidated on real bulletins**. Re-run `python scripts/fetch_corpus.py` when the host is back, then `python run.py --source S8`. |

## B. S3 PDF tables (Agent A2)

| # | Error (as logged) | Cause | Status |
|---|---|---|---|
| B1 | `p37..p72 has no text layer (vector-outline)` - 36 pages of the 2021-22 report | Glyphs drawn as filled vector paths: no text, no embedded image. PyMuPDF returns empty text. | Render at 300 dpi → Tesseract OCR (`no_text_layer_ocr_used`, INFO). |
| B2 | OCR rows came out as `PUDUCHERRY \|__3365\| _s067\|__4814\|_13243\| 40, ta]_— a]` | Ruled grid lines break Tesseract's line segmentation | Fixed: long horizontal/vertical dark runs are erased before OCR (`ocr.strip_ruling_lines`). Rows now read cleanly. |
| B3 | `ocr_column_count_mismatch: IV-A KARAIKAL: 9 numbers for 16 columns in OCR line 'KARAIKAL ) 0) 0) 0 0) 0) 5 5 0 ...'; row skipped` (7 rows on 2021-22 p46) | Tesseract reads the digit 0 as `0)`, `()` or `)` | Fixed: those tokens map to `0` (`ocr_char_fix`, INFO, 43 cases). All repaired values pass the STATE = sum of regions check. Rows that still mismatch are skipped and flagged `needs_llm_review`. |
| B4 | `ocr_column_count_mismatch: V-B MAHE: 0 numbers for 15 columns in OCR line 'Cashew . . a Betelnuts/ ...'` | Fuzzy region matching (cutoff 0.6) accepted "Cashew" as "MAHE" | Fixed: cutoff 0.75, minimum 4 letters. |
| B5 | `cell_collision: IV-A PUDUCHERRY: two values map to col (39): '52' and '377'` (20 warnings; 2023-24 p47, 2024-25 p52) | Numbers are right-aligned in their cells while column labels are centred, so a value near a boundary was assigned to the next column | Fixed: when a row has exactly one value per column, values are assigned in order; x-position is only a fallback (`row_value_count_mismatch` warning). |
| B6 | `unmapped_header: col (49) header 'Ground nut'`, `'Betalvines'`, `'Bamboos'`, `'Eucalyptus'`, `'oil seeds Total'`, `'Net Cropped Area'` … | Spelling variants, typos in the source ("Betalvines", "Pulsus"), and the land-use summary block (cols 63-67) | Fixed by adding dictionary rules. Any new unmatched header is logged with `needs_llm_review = 1` and the column is skipped (never guessed). |
| B7 | `template_disagreement: 2021-22 IV-A p46: templates 2020-21 and 2022-23 disagree on columns [49]` | Knock-on effect of B6 (one year's label unmapped) | Resolved with B6. The check stays: OCR pages borrow headers from the nearest year only when both neighbouring years agree. |
| B8 | `duplicate_crop_column: 2020-21 Puducherry Cucumber & pumpkin/All: IV-A has two columns for it` (25 warnings) | Dictionary merged two separate columns (35 Cucumber, 36 Pumpkin) into one name | Fixed: separate crops. |
| B9 | `area_yield_mismatch: 2022-23 Karaikal Groundnut/All: area 1 ha x yield 540 kg/ha / 1000 = 0.5 vs published production 1 tonnes (46% gap)` (21 warnings) | Not a parsing error: the report rounds production to whole tonnes, so tiny crops show big relative gaps | Tolerance now requires > 10 % **and** > 1 unit. For production ≥ 10 the max gap is 3.85 % (mean 0.14 %) over 353 rows. |
| B10 | `title_year_mismatch: IV-A title on p5 does not mention 2022-23` | The CONTENTS page contains "Region wise Area under All Crops" | Fixed: the check only runs on pages where table blocks were found. |
| B11 | `ocr_column_count_mismatch` on 5 rows of 2021-22 p46 (S3 dropped from 1650 to 1600 rows) when the pipeline was first run on Windows with Tesseract 5.4.0 (UB Mannheim): `KARAIKAL f°) 0 0 f°) ...`, `MAHE ... ¢) ...`, `PUDUCHERRY ... 3 3 33-895 4053` | A different Tesseract build reads the printed `0` as `f°)` / `¢)`, and one left-over ruling line glued two cells (Eucalyptus 33, Casuarina 895) into `33-895` | Fixed: any token ending in `)` with no digit 1-9 is a zero, and `<digits>-<digits>` is split into two cells (both logged as `ocr_char_fix`). S3 is back to 1650 rows, identical to the earlier Linux run, and every repaired row passes STATE = sum of regions. |

## C. Reference data (S7, REF)

| # | Issue | Status |
|---|---|---|
| C1 | `lgd_missing_census_code` (35 villages): LGD publishes Census 2011 code `000000` | Stored as NULL (INFO). |
| C2 | `alias_key_collision` (4): `Mahe`/`Mahé` etc. normalize to the same key | Duplicate dropped (INFO). |
| C3 | LGD has only 2 districts (Karaikal 598, Puducherry 600); Mahe and Yanam are sub-districts | Region rows carry district + sub-district codes; no district codes invented. |

## D. Environment

| # | Error | Fix |
|---|---|---|
| D1 | `ModuleNotFoundError: No module named 'fitz'` | `pip install pymupdf` (see `requirements.txt`) |
| D2 | `tesseract binary not found` | Install Tesseract (`apt install tesseract-ocr`; Windows: UB Mannheim installer, add to PATH). Without it, A2 logs `no_text_layer_ocr_unavailable` and 2021-22 is skipped (PARTIAL). |
| D3 | LGD `.xls` files are SpreadsheetML (XML), not binary Excel | Parsed with `xml.etree`; no `xlrd` needed. |

## E. Found by the Phase 3 evaluation (eval/run_eval.py, Sprint 3)

| # | Error (as measured) | Cause | Status |
|---|---|---|---|
| E1 | `WRONG A3-01: reg_no: expected '14' got 'Pondy'` - all 6 S6 cases had the region text in `coop_societies.reg_no` (A3 F1 0.875 on 48 fields; 61/61 DB rows affected) | `parse_s6` picked the first header containing `"reg"`, and `"region"` contains `"reg"`, so the Region column was read twice | Fixed: `_col(header, "reg", avoid="region")` in `src/agents/web_entities/agent.py`. After the fix A3 F1 = 1.000 and `coop_societies` has 61 distinct registration numbers. |
| E2 | 2022-23 report p32 gives 2021-22 Mango area **3 ha**, but the region table (2021-22 p45) prints **165 ha** | p32 is table "C. AREA OF CROPS IRRIGATED", not total area. Using it as ground truth would have marked correct extractions as wrong | Ground truth uses p34-35 "D. AREA UNDER ALL CROPS" (Mango 165) and p36 "E. AVERAGE YIELD ... AND TOTAL OUTTURN". The cited page is stored per case and re-checked by `eval/verify_ground_truth.py`. |
| E3 | Gross cropped area 2021-22: region table total **27993** ha vs 5-year summary **27994** ha | Two printed tables in the official reports disagree by 1 (rounding in the source) | Not an extraction error: the pipeline stores the value printed on the page it read; the provenance column says which page. |
| E4 | Rice total out-turn 2023-24: the 2023-24 region table (p51 Table V-B col (5)) prints STATE **61306** t (= 46970 + 13821 + 0 + 515), while the 2024-25 report's 5-year summary (p42) prints **61299** t for 2023-24 (and 13024 vs 13022 for rice I crop) | The later report revised or mistyped the earlier year's total | Not an extraction error. The KB keeps the value of the page it read (61306) with that page in `page_or_table`; benchmark query Q01 documents the discrepancy. |

## F. Live S2 / S5 files (fetched from India, 2026-11-27; S8 unreachable, see A3)

The S2/S5 parsers had only been run on synthetic fixtures. Running them on the real files
showed these problems. Each one was fixed in plain Python and is covered by `eval/eval_set.json`.

| # | Error (as seen on the real file) | Cause | Status |
|---|---|---|---|
| F1 | S2: a fake commodity `2.` with prices `4.0, 5.0, 6.0, 7.0, 8.0` would have been loaded | The live table has a second row `1. 2. 3. 4. 5. 6. 7. 8.` (column numbers) under the header, and every cell parses as a number | Fixed: rows whose commodity cell is only a number (`COLUMN_NUMBER`) are skipped in `parse_s2`. |
| F2 | S2: `price_unit = ',,'` for 13 of 15 commodities (65 of 75 prices) | The page prints the unit only once (`Qtl`) and uses the ditto mark `,,` for "same as above" | Fixed: a ditto unit is replaced by the previous row's unit (`DITTO` set). All 75 prices now have `Rs/quintal` or `Rs/1000 nuts`. |
| F3 | S2: `commodity = 'Paddy - I sort'`, `'Onion - Dindigul'`, `'Cumbu - T.'` with empty variety | Live labels use `Commodity - Variety`; the old regex only knew `Paddy I` / `Paddy II` | Fixed: `split_label` splits on `' - '` and drops the word `sort` (`Paddy - I sort` → Paddy / I). The old `Paddy I` form still works. |
| F4 | S2: `Canegur - I` 2013-14 printed as `0` | Missing value in the source, not a price | Already handled: stored as NULL with a `zero_price_as_null` warning (`price_value > 0` CHECK in the schema). |
| F5 | S5: `status FAILED, 0 scheme rows` | The live schemes page has **no `<table>`**. Schemes are `<li>` items in four `<ol>` lists, each list starting with `<label><strong>Category</strong></label>`; the parser only read tables | Fixed: `scheme_items` reads both table rows and `<ol><li>` items; category = the list's `<label>`. 44 schemes load. |
| F6 | S5: amounts written six different ways: `Rs.5000/acre`, `Rs.2000/- acre`, `Rs12,500/-` (no dot), `Rs.6,250/--`, `Rs.1.50 lakhs`, `Rs. 1.25 lakhs` | Free text typed by hand on the page | Fixed: one regex (`AMOUNT_RX`) handles all of them; `lakh(s)` is multiplied by 1,00,000 (Tube well → Rs 150000). |
| F7 | S5: `amount_basis = 'unspecified'` for per-palm, per-tube-well, per-group, per-block, per-demonstration, per-farm-school and per-cent schemes | The old regex only knew acre / ha / unit | Fixed: these bases are recognised and stored as `per <word>`. Only items with no basis at all (e.g. a lump-sum tour grant) stay `unspecified`. |
| F8 | S5: the Mango (high density) item appears twice, the second time with a stray `>` before it | HTML typo on the page (`>Subsidy for Mango ...`) | Fixed: the leading `>` is stripped, so the duplicate is caught by `dedupe` (`duplicate_dropped`, INFO). Same for the ATMA `>Scheme for exposure visits` item (not a duplicate, kept). |
| F9 | S5: two different Guava "High density planting" items (Rs 21,100 and Rs 12,668 per acre) | Probably a typo on the page (the second is likely "Ordinary planting", as for Acid lime) | Not changed: both rows are kept exactly as printed; the description column shows the full text. |
| F10 | S5: `crop` was always NULL | The parser never tried to read it | Simple rule added: `for <X> production / cultivation` or `cultivation of <X>` → crop (Paddy, Millets, Banana, Cashew, ...). 22 of 44 schemes get a crop; the rest (pump sets, groups, training) have none. |
| F11 | S5: Paddy item gives two amounts (Rs 5000 per acre per season, Rs 10,000 per acre per year) | Free text | Only the first amount is structured (5000, per acre, per season); the full sentence is kept in `description` and flagged `llm_structuring_candidate`. |
