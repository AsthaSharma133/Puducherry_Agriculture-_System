"""Agent interface used by the orchestrator."""
from __future__ import annotations

from dataclasses import dataclass, field


class InputMissing(Exception):
    """Raised when an agent's raw input is not on disk (-> status PENDING, not FAILED)."""


@dataclass
class AgentResult:
    status: str                                   # SUCCESS | PARTIAL | FAILED | PENDING
    tables: dict[str, list[dict]] = field(default_factory=dict)   # table -> rows for this source
    issues: list[dict] = field(default_factory=list)
    inputs_found: int = 0
    notes: str = ""

    @property
    def records_out(self) -> int:
        return sum(len(v) for v in self.tables.values())


class Agent:
    agent_id = "?"
    name = "?"
    handles: set[str] = set()                     # manifest source_ids this agent can process

    def run(self, source: dict, prov) -> AgentResult:  # pragma: no cover - interface
        raise NotImplementedError
