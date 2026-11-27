"""Single command-line entry point for the Team 35 Puducherry agriculture system.
Run from the puducherry_agri_agent/ folder:

    python run.py --init-db                 # create an empty database from db/schema.sql
    python run.py --run-all                 # run every source through the orchestrator
    python run.py --source S3               # run one source (S2, S3, S5, S6, S7, S8 ...)
    python run.py --input samples/<file>    # extract one PDF/HTML file and print it (no DB write)
    python run.py --query "question"        # ask the knowledge base in plain English
    python run.py --demo-queries            # the 10 live benchmark queries for the demo
"""
import argparse
import json
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT))

from app.query_engine import ask, format_answer  # noqa: E402
from src.common import db  # noqa: E402
from src.common.config import load_dotenv  # noqa: E402
from src.orchestrator import run as orchestrator  # noqa: E402


def init_db():
    """Drop every table and recreate the empty schema (TELL starts from a clean KB)."""
    conn = db.connect()
    db.reset_database(conn)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY 1")]
    conn.close()
    print(f"Empty database created with {len(tables)} tables: {', '.join(tables)}")
    print("Next: python run.py --run-all")
    return 0


def preview_pdf(path):
    """Extract S3-style region tables from a PDF page by page and print them.
    Uses the same A2 code: text layer first, OCR when the page has no text."""
    from src.agents.pdf_reports import ocr, s3_tables

    year_match = re.search(r"(\d{4}-\d{2})", path.name)
    year = year_match.group(1) if year_match else "unknown"
    issues = []
    blocks, stats = s3_tables.scan_pdf(path, year, issues, ocr.available()[0])
    print(f"{path.name}: {stats['pages']} page(s), {stats['text_pages']} text-layer, "
          f"{stats['ocr_pages']} OCR; {len(blocks)} table block(s) found")
    for block in blocks:
        print(f"\nTable {block.table}, PDF page {block.page}, method {block.method}")
        print("  REGION      " + " ".join(f"({c})".rjust(8) for c in block.cols))
        for region, cells in block.rows.items():
            print(f"  {region:<11} " + " ".join(str(cells.get(c, "")).rjust(8) for c in block.cols))
        labels = {c: block.labels[c] for c in block.cols if block.labels.get(c)}
        if labels:
            print("  headers: " + "; ".join(f"({c}) {t}" for c, t in labels.items()))
    for sev, typ, detail, _src, where in issues[:10]:
        print(f"  [{sev}] {typ}: {detail} {where}")
    return 0 if blocks else 1


def preview_html(path):
    """Parse an S2 / S5 / S6 HTML snapshot with the matching agent parser and print rows."""
    from src.agents.prices.agent import parse_s2
    from src.agents.web_entities.agent import parse_s5, parse_s6
    from src.common.provenance import Provenance

    name = path.name.lower()
    if "mktpric" in name or name.startswith("s2"):
        res = parse_s2(path, Provenance("S2", "A1", "preview"))
    elif "scheme" in name or name.startswith("s5"):
        res = parse_s5(path, Provenance("S5", "A3", "preview"))
    else:
        res = parse_s6(path, Provenance("S6", "A3", "preview"))
    print(f"{path.name}: status {res.status}, {res.records_out} rows ({res.notes})")
    for table, rows in res.tables.items():
        for row in rows[:8]:
            shown = {k: v for k, v in row.items() if k not in ("run_id", "extracted_at", "agent_id")}
            print(f"  {table}: {json.dumps(shown, ensure_ascii=False)}")
    return 0 if res.records_out else 1


def run_input(file_name):
    """Extract a single input file (PDF or HTML) and print the result; nothing is saved."""
    path = Path(file_name)
    if not path.is_absolute():
        path = (Path.cwd() / path) if (Path.cwd() / path).exists() else PROJECT / path
    if not path.exists():
        print(f"File not found: {file_name}")
        return 1
    print("(preview only - the database is not changed)")
    if path.suffix.lower() == ".pdf":
        return preview_pdf(path)
    if path.suffix.lower() in (".html", ".htm"):
        return preview_html(path)
    print("Only .pdf and .html inputs are supported.")
    return 1


def demo_queries():
    """Print the 10 benchmark questions and their live answers, nicely formatted."""
    queries = json.loads((PROJECT / "eval" / "benchmark_queries.json").read_text(encoding="utf-8"))["queries"]
    for q in queries:
        print("=" * 100)
        print(f"{q['id']}  [{q['category']}]")
        print(format_answer(ask(q["question"])))
    print("=" * 100)
    print(f"{len(queries)} live queries answered from db/puducherry_agri.db")
    return 0


def main(argv=None):
    """Read the command-line option and call the matching function."""
    parser = argparse.ArgumentParser(description="Team 35 Puducherry agriculture system")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--init-db", action="store_true", help="create an empty database")
    group.add_argument("--run-all", action="store_true", help="run all sources")
    group.add_argument("--source", help="run one source id, e.g. S3")
    group.add_argument("--input", help="extract one PDF/HTML file and print it")
    group.add_argument("--query", help="ask a question in plain English")
    group.add_argument("--demo-queries", action="store_true", help="run the 10 demo queries")
    args = parser.parse_args(argv)
    load_dotenv()
    if args.init_db:
        return init_db()
    if args.run_all:
        return orchestrator.main([])
    if args.source:
        return orchestrator.main(["--sources", args.source.upper()])
    if args.input:
        return run_input(args.input)
    if args.query:
        print(format_answer(ask(args.query)))
        return 0
    return demo_queries()


if __name__ == "__main__":
    sys.exit(main())
