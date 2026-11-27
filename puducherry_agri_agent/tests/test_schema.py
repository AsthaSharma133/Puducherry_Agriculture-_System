"""Database schema tests: every table exists and every data table carries full provenance."""
from src.common.db import DATA_TABLES
from src.common.provenance import PROVENANCE_COLS

EXPECTED_TABLES = set(DATA_TABLES) | {"pipeline_runs", "extraction_issues"}


def columns(conn, table):
    """Return the column names of one table."""
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def test_all_tables_exist_and_no_legacy_tables(conn):
    """The DB has exactly the schema.sql tables (no Phase 2 scraped_logs table)."""
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    assert names == EXPECTED_TABLES


def test_six_provenance_columns_on_every_data_table(conn):
    """source_id, source_file_or_url, page_or_table, agent_id, run_id, extracted_at everywhere."""
    assert len(PROVENANCE_COLS) == 6
    for table in DATA_TABLES:
        missing = set(PROVENANCE_COLS) - set(columns(conn, table))
        assert not missing, f"{table} lacks {missing}"


def test_loaded_rows_have_non_empty_provenance(conn):
    """No loaded row may have an empty source file, agent or run id."""
    for table in DATA_TABLES:
        bad = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE source_file_or_url IS NULL OR "
                           f"source_file_or_url = '' OR agent_id = '' OR run_id = ''").fetchone()[0]
        assert bad == 0, f"{table}: {bad} rows without provenance"


def test_expected_row_counts(conn):
    """The real corpus loads 1,650 crop rows, 61 co-ops, 144 LGD units and 85 aliases."""
    counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in DATA_TABLES}
    assert counts["crop_statistics"] == 1650
    assert counts["coop_societies"] == 61
    assert counts["lgd_locations"] == 144
    assert counts["location_aliases"] == 85


def test_every_run_id_is_logged(conn):
    """Every data row points to a run recorded in pipeline_runs (the logical FK)."""
    for table in DATA_TABLES:
        orphans = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE run_id NOT IN "
                               f"(SELECT run_id FROM pipeline_runs)").fetchone()[0]
        assert orphans == 0, f"{table}: {orphans} rows with an unknown run_id"
