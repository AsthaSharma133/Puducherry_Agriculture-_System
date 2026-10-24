import sys
import os

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import csv
from tools.static_scraper.core import static_scraper
from tools.pdf_extractor.core import pdf_extractor

def run_evaluation():
    print("=== Starting Puducherry Agriculture System Benchmark Evaluation ===")
    
    map_path = os.path.join("docs", "source_agent_map.csv")
    if not os.path.exists(map_path):
        print(f"[!] Error: Map file not found at {map_path}")
        return

    with open(map_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [name.strip().lower() for name in reader.fieldnames if name]
        sources = list(reader)

    print(f"[+] Loaded {len(sources)} sources from {map_path}\n")
    
    passed = 0
    total = 0

    for idx, source in enumerate(sources, 1):
        url = source.get("url") or source.get("urls") or source.get("source_url") or ""
        modality = source.get("modality") or source.get("modalities") or ""

        url = url.strip()
        modality = modality.strip()

        if not url:
            continue

        total += 1
        print(f"[{idx}] Testing: {url} ({modality})")
        
        # Route execution based on modality
        if "PDF" in modality.upper():
            res = pdf_extractor(url)
        else:
            # Both Static and Dynamic URLs route to HTTP scraper
            res = static_scraper(url)

        if res and not res.startswith("Error"):
            print(f"    -> SUCCESS ({len(res)} characters extracted)")
            passed += 1
        else:
            print(f"    -> FAILED: {res[:100]}")

    print("\n=== Benchmark Summary ===")
    print(f"Passed: {passed}/{total} tests")
    print("==========================")

if __name__ == "__main__":
    run_evaluation()