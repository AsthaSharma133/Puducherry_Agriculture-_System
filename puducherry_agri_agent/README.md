# Puducherry Agriculture Information System

A standardized data scraping and extraction agent designed for the Puducherry Department of Agriculture and Farmers Welfare web portals.

## Project Structure
- `Data/raw/manifest.csv`: Raw data tracking manifest.
- `db/`: Database schema (`schema.sql`) and data dictionary (`dictionary.md`).
- `docs/`: Source agent registry (`source_agent_map.csv`) and agent specifications.
- `eval/`: Evaluation metrics and runner script (`run_eval.py`).
- `logs/`: Execution logs (`automation_log.csv`).
- `tools/`: Extraction modules (`static_scraper` and `pdf_extractor`).
- `demo.py`: Command line interface for running tools.

## Setup & Execution

### 1. Requirements
Ensure required Python packages are installed:
```bash
pip install beautifulsoup4 requests PyMuPDF tabulate