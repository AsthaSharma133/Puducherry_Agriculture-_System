"""Paths and environment settings shared by every module.

All paths are resolved from the project folder (puducherry_agri_agent/), so the
pipeline can be started from any working directory.
"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]          # .../puducherry_agri_agent
DATA = PROJECT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"                             # git-ignored caches (OCR text)
MANIFEST = DATA / "manifest.csv"
ALIASES = DATA / "aliases.csv"
DB_PATH = PROJECT / "db" / "puducherry_agri.db"
SCHEMA = PROJECT / "db" / "schema.sql"
DUMP = PROJECT / "db" / "dump" / "puducherry_agri_dump.sql"


def rel(path: Path | str) -> str:
    """Path relative to the project folder, with forward slashes (stable provenance)."""
    p = Path(path)
    try:
        return p.resolve().relative_to(PROJECT).as_posix()
    except ValueError:
        return str(p)


def load_dotenv(path: Path = PROJECT / ".env") -> None:
    """Minimal .env loader (KEY=VALUE lines). Existing environment variables win.

    Uses python-dotenv when installed, otherwise a tiny parser, so the pipeline has
    no hard dependency on it.
    """
    if not path.exists():
        return
    try:
        from dotenv import load_dotenv as _ld  # type: ignore

        _ld(path, override=False)
        return
    except ImportError:
        pass
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
