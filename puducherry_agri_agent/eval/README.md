# Evaluation (Phase 3, Sprint 3)

| File | What it is |
|---|---|
| `eval_set.json` | 34 hand-checked test cases, all real: A2 = 16 S3 table columns (12 from the 2021-22 vector-outline/OCR pages, 4 from 2024-25), A3 = 6 S6 society rows + 6 S5 scheme items, A1 = 6 S2 price cells (S2/S5 pages saved from India on 2026-11-27). Each case has `expected`, `expected_provenance`, `expected_tool`, `verification` and `checked_by`. |
| `build_eval_set.py` | Writes `eval_set.json`. Expected values are typed in by hand (from page renders + summary tables); only the model input text is read from the PDF. |
| `verify_ground_truth.py` | Re-checks every S3 expected value against the report's own 5-year summary page and the region-sum rule. |
| `qlora_train.jsonl` | 66 table-to-JSON training examples from the text-layer reports 2020-21, 2022-23, 2023-24 (QLoRA notebook). |
| `build_qlora_train.py` | Writes `qlora_train.jsonl` (every 3rd example gets light OCR-style noise). |
| `check_overlap.py` | `assert`s zero overlap (source file + page + crop + region + year) between train and test. |
| `run_eval.py` | Runs the real agents on the case inputs and writes `results_summary.json`, `results_by_agent.csv`, `results_by_case.csv`. |
| `fixtures/` | Synthetic S2 / S5 HTML in the real page layouts (those hosts are blocked from the build machine). Values are invented and must not be reported as real data. |
| `adapter_comparison.csv` | Written by `notebooks/qlora_finetune_eval.ipynb` on a Colab T4: base vs QLoRA adapter P/R/F1 per subset and per case (overall F1 0.0247 → 0.6625). |
| `qlora_train_log.json` | Training settings and run log of that Colab run (Qwen2.5-1.5B-Instruct, r=16, alpha=32, 4 epochs, 66 examples, 147 s). |

```bash
python eval/verify_ground_truth.py   # 16 OK, 0 failing
python eval/check_overlap.py         # OK: zero overlap
python eval/run_eval.py              # metrics -> eval/results_*.{json,csv}
```

Honest reading of the numbers: the deterministic pipeline scores F1 = 1.000 on these 34 cases
(158 fields) after the S6 `reg_no` fix (A3 was 0.875 before it, `docs/extraction_errors.md` E1) and
the S2/S5 live-page fixes (F1-F11; S5 loaded 0 rows before them). n is still small. The A2 `model_input`
texts are frozen from the first (Linux) OCR run so the QLoRA notebook results stay comparable.
S8 has no cases: its host was unreachable when the corpus was fetched (A3 in the errors doc).
`fixtures/` is kept for the unit tests only.
