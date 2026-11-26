"""All 10 live benchmark queries must give the exact expected answer with provenance."""
import pytest

from app.query_engine import ask
from eval.run_queries import check, load_queries

QUERIES = load_queries()


def test_ten_queries_in_four_categories():
    """3 spatial + 3 temporal + 2 provenance + 2 co-op/LGD."""
    cats = [q["category"] for q in QUERIES]
    assert len(QUERIES) == 10
    assert (cats.count("spatial"), cats.count("temporal"), cats.count("provenance"),
            cats.count("coop_lgd")) == (3, 3, 2, 2)


@pytest.mark.parametrize("query", QUERIES, ids=[q["id"] for q in QUERIES])
def test_benchmark_query(conn, query):
    """Intent, every expected string and the expected provenance row must all match."""
    out = ask(query["question"], conn)
    assert check(query, out) == []
    assert out["provenance"] and all(p["source_file_or_url"] and p["page_or_table"] for p in out["provenance"])
    assert out["sql"].upper().startswith("SELECT")


def test_unknown_question_is_handled(monkeypatch):
    """A question with no crop/intent gets a polite message, not a crash (offline, no LLM)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = ask("hello there")
    assert out["intent"] is None and "could not understand" in out["answer"]
