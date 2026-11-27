"""Prove that the QLoRA training set and the evaluation set share no table cell.
A cell is identified by (source file, page, crop, region, year); the check uses plain asserts.

Run (from puducherry_agri_agent/):  python eval/check_overlap.py
"""
import json
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
REGIONS = ["Puducherry", "Karaikal", "Mahe", "Yanam", "UT"]


def train_keys(path=EVAL_DIR / "qlora_train.jsonl"):
    """Return the set of (file, page, crop, region, year) keys used by the training examples.
    Each example covers one column, i.e. one crop in 5 regions."""
    keys = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        for region in row["regions"]:
            keys.add((row["source_file"], row["page"], row["crop"], region, row["year"]))
    return keys


def eval_keys(path=EVAL_DIR / "eval_set.json"):
    """Return the same kind of keys for every PDF test case in eval_set.json.
    HTML cases (S2, S5, S6) have no page or crop, so they cannot overlap with PDF training rows."""
    keys = set()
    cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
    for case in cases:
        if case["agent"] != "A2":
            continue
        for region in case["expected"]:
            keys.add((case["input_file"], case["page"], case["crop"], region, case["year"]))
    return keys


def check_no_overlap():
    """Assert that the two key sets are disjoint and that no test year is used for training.
    Returns a small summary dict (used by run_eval.py and the tests)."""
    train, test = train_keys(), eval_keys()
    shared = train & test
    assert not shared, f"{len(shared)} train/test overlaps, e.g. {sorted(shared)[:3]}"
    train_years = {k[4] for k in train}
    test_years = {k[4] for k in test}
    assert not (train_years & test_years), f"years used in both: {train_years & test_years}"
    train_pages = {(k[0], k[1]) for k in train}
    test_pages = {(k[0], k[1]) for k in test}
    assert not (train_pages & test_pages), f"pages used in both: {train_pages & test_pages}"
    # HTML / bulletin test files (S2, S5, S6, S8) must never appear in training at all
    train_files = {k[0] for k in train}
    cases = json.loads((EVAL_DIR / "eval_set.json").read_text(encoding="utf-8"))["cases"]
    html_files = {c["input_file"] for c in cases if c["agent"] != "A2"}
    assert not (train_files & html_files), f"files used in both: {train_files & html_files}"
    return {"train_keys": len(train), "test_keys": len(test), "overlap": 0,
            "train_years": sorted(train_years), "test_years": sorted(test_years)}


if __name__ == "__main__":
    summary = check_no_overlap()
    print(f"OK: zero overlap. train cells={summary['train_keys']} (years {summary['train_years']}), "
          f"test cells={summary['test_keys']} (years {summary['test_years']})")
