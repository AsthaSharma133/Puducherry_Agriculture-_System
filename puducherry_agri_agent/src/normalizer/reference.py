"""S7 reference loader (non-agent lookup): LGD units + spelling aliases -> DB."""
from __future__ import annotations

from ..agents.base import Agent, AgentResult, InputMissing
from .dedup import dedupe
from .lgd import LGD_DIR, load_alias_rows, load_lgd_locations


class LgdReferenceLoader(Agent):
    agent_id = "REF"
    name = "Entity Normalization Pipeline (LGD lookup)"
    handles = {"S7"}

    def run(self, source: dict, prov) -> AgentResult:
        if not list(LGD_DIR.glob("*.xls")):
            raise InputMissing("no LGD exports in data/raw/lgd/")
        locs, issues = load_lgd_locations(prov)
        aliases, dropped = dedupe(load_alias_rows(prov), ["alias_key", "entity_type", "canonical_name"])
        for d in dropped:
            issues.append(prov.issue("INFO", "alias_key_collision",
                                     f"alias {d['alias']!r} has the same lookup key as an earlier "
                                     f"alias of {d['canonical_name']} ({d['entity_type']})",
                                     d["source_file_or_url"], d["page_or_table"]))
        counts = {t: sum(r["entity_type"] == t for r in locs)
                  for t in ("state", "district", "subdistrict", "village", "region")}
        return AgentResult("SUCCESS", {"lgd_locations": locs, "location_aliases": aliases}, issues,
                           inputs_found=len(list(LGD_DIR.glob("*.xls"))),
                           notes=", ".join(f"{v} {k}" for k, v in counts.items()) +
                                 f"; {len(aliases)} aliases")
