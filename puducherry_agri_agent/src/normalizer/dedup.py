"""Natural-key deduplication (deterministic, keeps the first occurrence)."""
from __future__ import annotations

from typing import Iterable


def dedupe(rows: Iterable[dict], key_fields: list[str]) -> tuple[list[dict], list[dict]]:
    """Return (unique_rows, dropped_duplicates). Keys are compared case-insensitively."""
    seen, keep, dropped = set(), [], []
    for r in rows:
        key = tuple(str(r.get(k) or "").strip().casefold() for k in key_fields)
        if key in seen:
            dropped.append(r)
        else:
            seen.add(key)
            keep.append(r)
    return keep, dropped
