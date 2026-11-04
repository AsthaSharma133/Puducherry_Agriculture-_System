# Technical Challenge & Tool Evaluation Notes

## 1. Primary Challenges
* **Heterogeneous Web Portals:** Puducherry agricultural data is split across dynamic portals (AGMARKNET) and static departmental HTML tables, requiring distinct extraction strategies.
* **Non-Standard PDF Layouts:** DES seasonal crop reports contain multi-column bilingual tables (Tamil & English) that standard parsers fail to slice accurately without structural coordinate boundaries.
* **LGD Code Alignment:** Resolving localized village/taluk names against standardized LGD codes (State Code 34) required explicit lookup normalization to prevent primary key mismatches.

## 2. Extraction Approaches & Literature Context
* **DOM vs. Rendered Parsing:** Evaluated direct HTML parsing vs. browser automation. BeautifulSoup4 proved optimal for lightweight static scheme pages, while dynamic AGMARKNET endpoints required DOM table target parsing.
* **PDF Structural Slicing:** Compared `pypdf` against `PyMuPDF` (`fitz`). PyMuPDF offered vastly superior bounding-box text line extraction for tabular layout reconstruction.

## 3. Tool Performance Summary
* **Static Scraper (`tools/static_scraper`):** 100% success rate on clean scheme pages; stripped inline CSS/JS cleanly.
* **PDF Extractor (`tools/pdf_extractor`):** Successfully parsed target report pages with baseline layout preservation.