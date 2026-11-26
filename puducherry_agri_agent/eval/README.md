# Evaluation (Phase 3, Sprint 3)

| File | What it is |
|---|---|
| `eval_set.json` | 28 hand-checked test cases: A2 = 16 real S3 table columns (12 from the 2021-22 vector-outline/OCR pages, 4 from 2024-25), A3 = 6 real S6 society rows + 2 synthetic S5 rows, A1 = 4 synthetic S2 rows. Each case has `expected`, `expected_provenance`, `expected_tool`, `verification` and `checked_by`. |
| `build_eval_set.py` | Writes `eval_set.json`. Expected values are typed in by hand (from page renders + summary tables); only the model input text is read from the PDF. |
| `verify_ground_truth.py` | Re-checks every S3 expected value against the report's own 5-year summary page and the region-sum rule. |
| `qlora_train.jsonl` | 66 table-to-JSON training examples from the text-layer reports 2020-21, 2022-23, 2023-24 (QLoRA notebook). |
| `build_qlora_train.py` | Writes `qlora_train.jsonl` (every 3rd example gets light OCR-style noise). |
| `check_overlap.py` | `assert`s zero overlap (source file + page + crop + region + year) between train and test. |
| `run_eval.py` | Runs the real agents on the case inputs and writes `results_summary.json`, `results_by_agent.csv`, `results_by_case.csv`. |
| `fixtures/` | Synthetic S2 / S5 HTML in the real page layouts (those hosts are blocked from the build machine). Values are invented and must not be reported as real data. |
| `adapter_comparison.csv` | Written by `notebooks/qlora_finetune_eval.ipynb` after the Colab run (not produced here: no GPU). |

```bash
python eval/verify_ground_truth.py   # 16 OK, 0 failing
python eval/check_overlap.py         # OK: zero overlap
python eval/run_eval.py              # metrics -> eval/results_*.{json,csv}
```

Honest reading of the numbers: the deterministic pipeline scores F1 = 1.000 on these 28 cases
after the S6 `reg_no` fix (it was 0.875 for A3 before the fix, see
`docs/extraction_errors.md` E1). n is small (136 fields); A1 and the S5 part of A3 use synthetic
fixtures, so they prove parser logic, not live-page coverage.
