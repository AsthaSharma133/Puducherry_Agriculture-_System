# Technical Challenge & Tool Evaluation Notes (Phase 3)

## Locked research question (RQ2)

> **Does QLoRA adaptation improve structured extraction on complex, multi-layout, and
> vector-outline/OCR government PDF tables?**

* Base model: `Qwen/Qwen2.5-1.5B-Instruct`; adapter: 4-bit QLoRA, r = 16, alpha = 32
  (`notebooks/qlora_finetune_eval.ipynb`, free Colab T4).
* Training data: `eval/qlora_train.jsonl` - table-to-JSON examples from the **text-layer**
  S3 reports 2020-21, 2022-23 and 2023-24.
* Held-out test data: the S3 cases in `eval/eval_set.json` - mainly the **2021-22 report,
  whose table pages have no text layer** (glyphs are vector outlines, so OCR is the only
  way in), plus 2024-25 text-layer pages. Ground truth for 2021-22 is checked against the
  independent 5-year summary tables printed in the 2022-23 report (pp. 32-36).
* Zero overlap between training and test (source file + page + crop + region + year) is
  enforced by `eval/check_overlap.py` and by `tests/`.
* Metric: field-level Precision / Recall / F1 on the extracted numbers (base vs adapter,
  same cases), reported in `eval/adapter_comparison.csv` after the Colab run.

## 1. Primary challenges (observed on the real corpus)

* **Vector-outline PDF pages (S3 2021-22, pp. 37-72).** The pages look normal but contain
  no text and no image: each glyph is a filled path. PyMuPDF returns an empty string, so
  pages are rendered at 300 dpi and read with Tesseract after erasing the table ruling
  lines (`src/agents/pdf_reports/ocr.py`).
* **Multi-layout statistical tables.** Tables IV-A / V-A / V-B are printed as several
  column blocks per page, with group headers spanning columns and letter-spaced words
  (`R I C E`). Column meaning is recovered from x-positions, and OCR pages borrow the headers
  of the nearest year with the identical block layout.
* **Units and conventions.** `-` means nil, production is rounded to whole tonnes, and
  coconut is in nuts (yield nuts/ha, production thousand nuts). Rules live in
  `src/normalizer/units.py` and are checked with STATE = sum of regions and
  area x yield / 1000 = production.
* **LGD code alignment.** LGD has only **2 districts** (Puducherry 600, Karaikal 598) while
  every report uses **4 regions**; Mahe (5913) and Yanam (5908) are sub-districts of
  district 600. Spelling variants (`Pondicherry`, `Pondy`, `KKL`, `Mahé`) are resolved with
  `data/aliases.csv`.
* **Blocked hosts.** `agri.py.gov.in` (S2, S5) resets connections from the cloud build machine,
  so those pages were fetched from a network in India. `agritech.tnau.ac.in` (S8) timed out
  even from India, so S8 stays PENDING.
* **Language.** All Puducherry sources used are in English. No Tamil statistical tables were
  found (the Tamil `/ta/` pages of the DES site return 404), so the project makes no claim
  about Tamil table extraction.

## 2. Extraction approaches

* **HTML (S2, S5, S6):** `requests` + BeautifulSoup table parsing; no browser automation is
  needed because the pages are static.
* **PDF text layer (S3):** PyMuPDF word coordinates grouped into lines, then columns.
* **PDF without text (S3 2021-22):** PyMuPDF render + numpy line removal + Tesseract.
* **LLM (QLoRA) extractor:** evaluated as an alternative for the hardest OCR pages (RQ2);
  the production pipeline stays deterministic and logs `needs_llm_review` cases.

## 3. Tool performance summary

Measured numbers are produced by `python eval/run_eval.py` and saved in
`eval/results_summary.json` and `eval/results_by_agent.csv`. Phase 2 numbers are archived in
`archive/phase2_unverified/` and are not reported.
