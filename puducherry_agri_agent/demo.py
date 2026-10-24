import sys
from tools.static_scraper.core import static_scraper
from tools.pdf_extractor.core import pdf_extractor

def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print("  py demo.py static <URL>")
        print("  py demo.py pdf <URL_or_Path>")
        sys.exit(1)

    command = sys.argv[1].lower()
    target = sys.argv[2]

    if command == "static":
        print(f"[+] Running static scraper on: {target}\n")
        result = static_scraper(target)
        print("--- EXTRACTED OUTPUT PREVIEW ---")
        print(result[:500] if result else "No data returned.")

    elif command == "pdf":
        print(f"[+] Running PDF extractor on: {target}\n")
        result = pdf_extractor(target)
        print("--- EXTRACTED OUTPUT PREVIEW ---")
        print(result[:500] if result else "No data returned.")

    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()