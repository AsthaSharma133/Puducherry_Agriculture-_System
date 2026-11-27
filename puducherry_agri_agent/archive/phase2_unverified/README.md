# Phase 2 artifacts - UNVERIFIED, DO NOT REPORT

Archived on 2026-11-26 (Phase 3 audit). These numbers cannot be traced to any code run or data
in this repository and must not be quoted in the Phase 3 report, poster or presentation.

| File | Why it is unverified |
|---|---|
| `phase2_metrics.csv` | Claims e.g. 150 SQL-checked rows, LangSmith traces and "bilingual Tamil/English PDF tables"; the Phase 2 DB had 0 data rows and no Tamil sources exist for Puducherry. |
| `adapter_comparison.csv` | Base vs QLoRA F1 (0.740 / 0.825) with no training run, adapter, or evaluation script behind it. |
| `automation_log.csv` | First 7 rows were hand-written (incl. "SUCCESS" for AGMARKNET, which is CAPTCHA-blocked and Pending). |

Phase 3 replacements: `pipeline_runs` and `extraction_issues` tables in `db/puducherry_agri.db`
(written by `python -m src.orchestrator`), and real evaluation results produced in Sprint 3.
| `source_agent_map.csv` | Phase 2 source list; claims "warehouse locations, storage capacities" for S6, which the real page does not contain (it lists credit co-op societies only). Replaced by `data/manifest.csv`. |

`archive/phase2_code/` holds the Phase 2 `tools/` scrapers and agent note. Nothing in Phase 3 imports them;
they are kept only so the Phase 2 history stays readable. The live code is `run.py`, `src/`, `app/`, `eval/`.
