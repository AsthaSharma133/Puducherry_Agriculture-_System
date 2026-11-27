"""Supervisor routing table: manifest source_id -> agent (or a documented non-run status).

Routing is deterministic: it is driven by data/manifest.csv `source_id` and the agent
each source is assigned to (`agent_id` column). No LLM decides the route.
"""
from __future__ import annotations

from ..agents.pdf_reports.agent import PdfReportAgent
from ..agents.prices.agent import PriceAgent
from ..agents.web_entities.agent import WebEntityAgent
from ..normalizer.reference import LgdReferenceLoader

AGENTS = [LgdReferenceLoader(), PriceAgent(), PdfReportAgent(), WebEntityAgent()]
ROUTES = {sid: a for a in AGENTS for sid in a.handles}

# Sources that are deliberately not executed, with the reason logged to pipeline_runs.
NOT_RUN = {
    "S4": ("SKIPPED", "Weekly report archive (2016-2018) is outside Phase 3 scope; S8 replaces it"),
    "S9": ("SKIPPED", "Survey of India boundaries are a map layer, not extracted into the DB: "
                      "data/raw/soi/ (SOI index maps via DataMeet mirror), drawn by "
                      "scripts/plot_soi_map.py"),
}

# Run order: reference data first, then sources that use it.
ORDER = ["S7", "S1", "S2", "S3", "S5", "S6", "S8", "S4", "S9"]


def route(source_id: str):
    return ROUTES.get(source_id)
