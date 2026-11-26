"""SQLite helpers: schema creation, per-source replace, issue logging."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterable

from .config import DB_PATH, SCHEMA

DATA_TABLES = ["lgd_locations", "location_aliases", "crop_statistics", "coop_societies",
               "market_prices", "schemes", "agromet_advisories"]


def connect(path=DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    conn.commit()


def reset_database(conn: sqlite3.Connection) -> None:
    """Drop every table (including legacy Phase 2 tables) and recreate the Phase 3 schema."""
    names = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    for n in names:
        conn.execute(f'DROP TABLE IF EXISTS "{n}"')
    conn.commit()
    init_schema(conn)
    conn.execute("VACUUM")


@contextmanager
def transaction(conn: sqlite3.Connection):
    try:
        conn.execute("BEGIN")
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def replace_source_rows(conn: sqlite3.Connection, table: str, source_id: str,
                        rows: Iterable[dict]) -> int:
    """Delete this source's previous rows in `table`, then insert `rows` (caller holds the txn)."""
    rows = list(rows)
    conn.execute(f"DELETE FROM {table} WHERE source_id = ?", (source_id,))
    if not rows:
        return 0
    cols = list(rows[0].keys())
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    conn.executemany(sql, [tuple(r.get(c) for c in cols) for r in rows])
    return len(rows)


def insert_issues(conn: sqlite3.Connection, issues: Iterable[dict]) -> int:
    issues = list(issues)
    if not issues:
        return 0
    cols = ["severity", "issue_type", "detail", "needs_llm_review", "source_id",
            "source_file_or_url", "page_or_table", "agent_id", "run_id", "extracted_at"]
    conn.executemany(
        f"INSERT INTO extraction_issues ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
        [tuple(i.get(c) for c in cols) for i in issues])
    return len(issues)


def dump_sql(conn: sqlite3.Connection, path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("-- Puducherry Agriculture DB dump (SQLite). Regenerate: python -m src.orchestrator --dump\n")
        for line in conn.iterdump():
            f.write(line + "\n")
