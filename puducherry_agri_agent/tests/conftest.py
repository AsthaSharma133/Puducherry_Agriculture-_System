"""Shared pytest setup: make the project folder importable and open the built database.
Run all tests from puducherry_agri_agent/ with:  python -m pytest tests/ -q
"""
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))


@pytest.fixture(scope="session")
def conn():
    """One read connection to db/puducherry_agri.db for the whole test session."""
    db = PROJECT / "db" / "puducherry_agri.db"
    if not db.exists():
        pytest.skip("db/puducherry_agri.db missing - run: python run.py --run-all")
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    yield connection
    connection.close()
