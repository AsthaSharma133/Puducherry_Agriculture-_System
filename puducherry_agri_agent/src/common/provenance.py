"""Run ids, timestamps and the provenance columns shared by all data tables."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

PROVENANCE_COLS = ["source_id", "source_file_or_url", "page_or_table", "agent_id", "run_id",
                   "extracted_at"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)


class Provenance:
    """Stamps rows/issues with the six provenance fields for one agent step."""

    def __init__(self, source_id: str, agent_id: str, run_id: str):
        self.source_id, self.agent_id, self.run_id = source_id, agent_id, run_id

    def row(self, source_file_or_url: str, page_or_table: str, **fields) -> dict:
        return {**fields, "source_id": self.source_id, "source_file_or_url": source_file_or_url,
                "page_or_table": page_or_table, "agent_id": self.agent_id, "run_id": self.run_id,
                "extracted_at": now_iso()}

    def issue(self, severity: str, issue_type: str, detail: str, source_file_or_url: str = "",
              page_or_table: str = "", needs_llm_review: bool = False) -> dict:
        return {"severity": severity, "issue_type": issue_type, "detail": detail,
                "needs_llm_review": int(needs_llm_review), "source_id": self.source_id,
                "source_file_or_url": source_file_or_url, "page_or_table": page_or_table,
                "agent_id": self.agent_id, "run_id": self.run_id, "extracted_at": now_iso()}
