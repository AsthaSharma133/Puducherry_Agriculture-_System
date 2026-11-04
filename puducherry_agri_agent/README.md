# Puducherry Agriculture Information System

A standardized data scraping and extraction agent designed for the Puducherry Department of Agriculture and Farmers Welfare web portals.

## Project Structure
- `data/raw/manifest.csv`: Raw data source tracking manifest.
- `db/`: Database schema (`schema.sql`) and data dictionary (`dictionary.md`).
- `docs/`: Data source map (`source_agent_map.csv`) and agent notes.
- `eval/`: Evaluation runner (`run_eval.py`) and benchmark test cases.
- `logs/`: Pipeline execution logs (`automation_log.csv`).
- `tools/`: Scraper implementations (`static_scraper`, `pdf_extractor`).
- `demo.py`: Command line interface for running tools.

## Setup & Execution

### 1. Requirements
Ensure required Python packages are installed:
```bash
pip install beautifulsoup4 requests PyMuPDF tabulate




## System Flowchart & Data Architecture


+-----------------------------------+
             |        1. RAW DATA SOURCES        |
             |  - Static Web Pages (HTML)        |
             |  - PDF Advisories & Reports       |
             |  - Dynamic Web Portals (AGMARKNET)|
             |  - LGD Administrative Registry    |
             +-----------------------------------+
                               |
                               v
             +-----------------------------------+
             |        2. EXTRACTION LAYER        |
             |  - tools/static_scraper/core.py   |
             |  - tools/pdf_extractor/core.py    |
             +-----------------------------------+
                               |
                               v
             +-----------------------------------+
             |        3. DATA STORAGE (db/)      |
             |  - Schema Definitions (schema.sql)|
             |  - Seed Dump (db/dump)            |
             |  - SQLite Database (.db)          |
             +-----------------------------------+
                               |
                               v
             +-----------------------------------+
             |     4. EXECUTION & BENCHMARK      |
             |  - CLI Interface (demo.py)        |
             |  - Eval Suite (eval/run_eval.py)  |
             |  - System Logs (automation_log)   |
             +-----------------------------------+