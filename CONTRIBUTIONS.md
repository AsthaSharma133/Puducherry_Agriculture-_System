# Team 35 contributions (CS F/U 407, Phase 3)

Fill in the names and ID numbers. "Main files" lists what each role owns in
`puducherry_agri_agent/`, so each member can answer viva questions on those parts.

| Role | Name | ID number | Responsibilities | Main files |
|---|---|---|---|---|
| Source Lead | _(name)_ | _(ID)_ | Source discovery and verification, manifest, corpus download, LGD exports, blocked-host workarounds | `data/manifest.csv`, `data/download_list_S3_S8.csv`, `scripts/fetch_corpus.py`, `data/aliases.csv` |
| Model Lead | _(name)_ | _(ID)_ | RQ2 design, QLoRA training set, Colab fine-tuning and base-vs-adapter evaluation | `docs/challenge.md`, `eval/build_qlora_train.py`, `eval/qlora_train.jsonl`, `notebooks/qlora_finetune_eval.ipynb` |
| Data Engineering Lead | _(name)_ | _(ID)_ | Agents A1/A2/A3, OCR fallback, normalizer, orchestrator, SQLite schema and dump, query engine | `src/`, `app/query_engine.py`, `run.py`, `db/schema.sql`, `db/dictionary.md` |
| Evaluation Lead | _(name)_ | _(ID)_ | Hand-checked evaluation set (re-check the `checked_by` field), metrics, benchmark queries, tests, figures, error log | `eval/eval_set.json`, `eval/run_eval.py`, `eval/run_queries.py`, `tests/`, `scripts/generate_figures.py`, `docs/extraction_errors.md` |

AI assistance: parts of the code and documentation were drafted with an AI coding assistant
(Claude Code); every number reported comes from the scripts in this repository, and the
evaluation ground truth still needs the Evaluation Lead's human re-check (see `checked_by`).
