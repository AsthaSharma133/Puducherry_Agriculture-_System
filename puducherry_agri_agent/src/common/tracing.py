"""Optional LangSmith tracing.

If LANGSMITH_API_KEY is set (and LANGSMITH_TRACING is not 'false') and the `langsmith`
package is installed, agent runs are wrapped with `langsmith.traceable`. Otherwise
`traced` is a no-op decorator, so the pipeline runs identically without a key.
"""
from __future__ import annotations

import functools
import os


def backend() -> str:
    if not os.environ.get("LANGSMITH_API_KEY"):
        return "none"
    if os.environ.get("LANGSMITH_TRACING", "true").lower() in ("0", "false", "no"):
        return "none"
    try:
        import langsmith  # noqa: F401
    except ImportError:
        return "none"
    return "langsmith"


def traced(name: str):
    """Decorator: trace with LangSmith when available, else call through unchanged."""
    def deco(fn):
        if backend() == "langsmith":
            from langsmith import traceable

            return traceable(name=name, run_type="chain")(fn)

        @functools.wraps(fn)
        def wrapper(*a, **k):
            return fn(*a, **k)

        return wrapper

    return deco
