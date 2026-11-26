"""The QLoRA training set must never share a table cell with the evaluation set."""
import json

from eval.check_overlap import EVAL_DIR, check_no_overlap, eval_keys, train_keys


def test_zero_overlap():
    """check_no_overlap() asserts disjoint (file, page, crop, region, year) keys, years and pages."""
    summary = check_no_overlap()
    assert summary["overlap"] == 0
    assert set(summary["train_years"]).isdisjoint(summary["test_years"])


def test_sizes_match_the_plan():
    """60-80 training examples and 25-30 evaluation cases, every case with checked_by."""
    lines = (EVAL_DIR / "qlora_train.jsonl").read_text(encoding="utf-8").splitlines()
    cases = json.loads((EVAL_DIR / "eval_set.json").read_text(encoding="utf-8"))["cases"]
    assert 60 <= len(lines) <= 80
    assert 25 <= len(cases) <= 30
    assert all(c.get("checked_by") for c in cases)


def test_keys_are_not_empty():
    """Guard against a vacuous pass: both key sets must actually contain cells."""
    assert len(train_keys()) > 0 and len(eval_keys()) > 0
