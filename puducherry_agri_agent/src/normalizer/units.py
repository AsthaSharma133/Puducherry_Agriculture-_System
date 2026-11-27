"""Number parsing and unit standardization (deterministic)."""
from __future__ import annotations

import re

ACRE_TO_HA = 0.40468564224

_NULL_TOKENS = {"", "na", "n.a", "n.a.", "nil*", "..", "...", "--", "—"}


def to_number(text) -> tuple[float | None, str | None]:
    """Parse a published table cell. Returns (value, note).

    Handles Indian digit grouping (1,20,000), stray spaces, and dash cells.
    A lone '-' / '–' is the statistical convention for nil and is returned as 0.0
    with note 'dash_as_zero' so callers can log it.
    """
    if text is None:
        return None, "empty"
    s = str(text).strip().replace("−", "-")
    if s in ("-", "–"):
        return 0.0, "dash_as_zero"
    if s.lower() in _NULL_TOKENS:
        return None, "empty"
    s = s.replace(",", "").replace(" ", "")
    if re.fullmatch(r"-?\d+(\.\d+)?", s):
        return float(s), None
    return None, f"not_numeric:{text!r}"


PRICE_UNITS = [
    (re.compile(r"1000\s*nuts|per\s*1000", re.I), "Rs/1000 nuts"),
    (re.compile(r"q(ui)?n?t(a)?l|qtl", re.I), "Rs/quintal"),
    (re.compile(r"\bkg\b|kilo", re.I), "Rs/kg"),
]


def price_unit(raw: str | None) -> str:
    """Map a printed unit ('Rs./Qtl', 'Per 1000 Nos') to a standard price unit."""
    for rx, unit in PRICE_UNITS:
        if raw and rx.search(raw):
            return unit
    return (raw or "").strip() or "unknown"


def per_hectare(amount: float, basis: str) -> float:
    """Convert a per-acre amount to per-hectare (for scheme incentives)."""
    return amount / ACRE_TO_HA if basis == "per acre" else amount
