# Team 35 contributions (CS F/U 407, Phase 3)

**Solo submission.** Every role below was carried out by **Astha Sharma** (100 % of the work).
"Main files" lists what each role covers in `puducherry_agri_agent/`, for viva questions.

| Role | Name | ID number | Share | Responsibilities | Main files |
|---|---|---|---|---|---|
| Source Lead | Astha Sharma | F20231242 | 100 % | Source discovery and verification, manifest, corpus download (S3 PDFs, live S2/S5/S6 pages, LGD exports, SOI boundaries), unreachable-host handling (S8) | `data/manifest.csv`, `data/download_list_S3_S8.csv`, `scripts/fetch_corpus.py`, `data/aliases.csv`, `scripts/plot_soi_map.py` |
| Model Lead | Astha Sharma | F20231242 | 100 % | RQ2 design, QLoRA training set, Colab T4 fine-tuning (Qwen2.5-1.5B, r=16) and base-vs-adapter evaluation | `docs/challenge.md`, `eval/build_qlora_train.py`, `eval/qlora_train.jsonl`, `notebooks/qlora_finetune_eval.ipynb`, `eval/adapter_comparison.csv`, `eval/qlora_train_log.json` |
| Data Engineering Lead | Astha Sharma | F20231242 | 100 % | Agents A1/A2/A3, OCR fallback, normalizer, orchestrator, SQLite schema and dump, query engine | `src/`, `app/query_engine.py`, `run.py`, `db/schema.sql`, `db/dictionary.md` |
| Evaluation Lead | Astha Sharma | F20231242 | 100 % | Hand-checked evaluation set (`checked_by`), metrics, benchmark queries, tests, figures, error log | `eval/eval_set.json`, `eval/run_eval.py`, `eval/run_queries.py`, `tests/`, `scripts/generate_figures.py`, `docs/extraction_errors.md` |

AI assistance: parts of the code and documentation were drafted with an AI coding assistant
(Claude Code). Every number reported comes from the scripts in this repository, and the
evaluation ground truth was checked by Astha Sharma (`checked_by` in `eval/eval_set.json`).
