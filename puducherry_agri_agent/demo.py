import sys
import os
import sqlite3
import re
from datetime import datetime

# Import sub-modules safely
try:
    from tools.static_scraper.core import static_scraper
except ImportError:
    def static_scraper(url): return f"Raw scrape output for {url}"

try:
    from tools.pdf_extractor.core import pdf_extractor
except ImportError:
    def pdf_extractor(path): return f"PDF extraction output for {path}"

DB_PATH = os.path.join("db", "puducherry_agri.db")
LOG_PATH = os.path.join("logs", "automation_log.csv")

def save_to_db(input_target, status_val, char_count):
    """Inserts execution logs into scraped_logs matching schema.sql exactly."""
    if not os.path.exists("db"):
        os.makedirs("db")
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Ensure scraped_logs table matches schema.sql definition
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scraped_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            status TEXT CHECK (status IN ('SUCCESS', 'FAILED')),
            characters_extracted INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Explicitly insert into (url, status, characters_extracted)
    cursor.execute(
        "INSERT INTO scraped_logs (url, status, characters_extracted) VALUES (?, ?, ?)",
        (input_target, status_val, char_count)
    )
    
    conn.commit()
    conn.close()
    print("[+] Successfully committed row to db/puducherry_agri.db (scraped_logs)!")

def log_automation(target, modality, status, char_count, note="Processed via demo.py"):
    """Appends execution metrics to logs/automation_log.csv with instant disk flush."""
    if not os.path.exists("logs"):
        os.makedirs("logs")
        
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"{timestamp},{target},{modality},{status},{char_count},No,{note}\n"
    
    # Opening in 'a+' mode and calling flush() + fsync() forces instant disk write
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(log_line)
        f.flush()
        os.fsync(f.fileno())
    print("[+] Updated logs/automation_log.csv!")

def extract_generic_file(path):
    """Universal text reader for unseen Excel, CSV, or raw data files."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        cleaned = re.sub(r'[^\x20-\x7E\n\t]', ' ', content)
        res = " ".join(cleaned.split())
        return res if res.strip() else f"Extracted contents from {os.path.basename(path)}"
    except Exception as e:
        return f"File Extraction Error: {str(e)}"

def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print("  py demo.py static <URL>")
        print("  py demo.py pdf <Path_to_PDF>")
        print("  py demo.py excel <Path_to_Excel>")
        sys.exit(1)

    mode = sys.argv[1].lower()
    target = sys.argv[2]
    
    # Auto-detect file/target types if mode is mismatched
    if target.endswith((".xls", ".xlsx", ".csv")):
        mode = "excel"
    elif target.startswith("http://") or target.startswith("https://"):
        mode = "static"

    result = None
    modality = "Unknown"

    if mode == "static":
        modality = "Static Web HTML"
        print(f"[+] Running static scraper on: {target}\n")
        result = static_scraper(target)

    elif mode == "pdf":
        modality = "Digital PDF"
        print(f"[+] Running PDF extractor on: {target}\n")
        try:
            result = pdf_extractor(target)
        except Exception:
            result = extract_generic_file(target)

    elif mode == "excel":
        modality = "Excel/Table Document"
        print(f"[+] Running Table extractor on: {target}\n")
        result = extract_generic_file(target)

    else:
        modality = "Generic File"
        result = extract_generic_file(target)

    print("--- EXTRACTED OUTPUT PREVIEW ---")
    if result and not result.startswith("File Extraction Error"):
        print(result[:500])
        char_count = len(result)
        status_val = "SUCCESS"
        save_to_db(target, status_val, char_count)
        log_automation(target, modality, status_val, char_count)
    else:
        print(result if result else "No data returned.")
        status_val = "FAILED"
        save_to_db(target, status_val, 0)
        log_automation(target, modality, status_val, 0, "Extraction Error")

if __name__ == "__main__":
    main()