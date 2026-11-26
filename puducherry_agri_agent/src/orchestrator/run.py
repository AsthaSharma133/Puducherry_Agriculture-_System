"""Pipeline supervisor.

    python -m src.orchestrator                    # all sources in data/manifest.csv
    python -m src.orchestrator --sources S3,S6    # selected sources
    python -m src.orchestrator --reset-db         # drop all tables, recreate schema, then run
    python -m src.orchestrator --dump-only        # rewrite db/dump from the current DB

Per source: route -> run agent (retry transient errors) -> validate status ->
replace that source's rows in one transaction -> log issues -> log pipeline_runs.
A failed or pending source never deletes previously loaded rows.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
import traceback

from ..agents.base import InputMissing
from ..common import db
from ..common.config import DB_PATH, DUMP, MANIFEST, load_dotenv, rel
from ..common.provenance import Provenance, new_run_id, now_iso
from ..common.tracing import backend, traced
from .router import NOT_RUN, ORDER, route

TRANSIENT = (OSError, TimeoutError, ConnectionError)


def load_manifest() -> dict[str, dict]:
    with MANIFEST.open(encoding="utf-8-sig") as f:
        return {r["source_id"]: r for r in csv.DictReader(f) if r.get("source_id")}


def run_source(conn, run_id: str, source: dict, max_attempts: int) -> dict:
    sid = source["source_id"]
    started, t0 = now_iso(), time.time()
    log = dict(run_id=run_id, source_id=sid, agent_id=None, status="FAILED", attempts=0,
               inputs_found=0, records_out=0, issues_logged=0, started_at=started,
               finished_at=None, duration_s=None, error_message=None, notes=None,
               trace_backend=backend())
    if sid in NOT_RUN:
        log["status"], log["notes"] = NOT_RUN[sid]
        log["agent_id"] = source.get("agent_id")
        return _finish(conn, log, t0, [], {})
    agent = route(sid)
    if agent is None:
        log["status"], log["error_message"] = "SKIPPED", f"no agent registered for {sid}"
        return _finish(conn, log, t0, [], {})
    log["agent_id"] = agent.agent_id
    prov = Provenance(sid, agent.agent_id, run_id)
    result, issues = None, []
    traced_run = traced(f"{agent.agent_id}:{sid}")(agent.run)
    for attempt in range(1, max_attempts + 1):
        log["attempts"] = attempt
        try:
            result = traced_run(source, prov)
            break
        except InputMissing as e:
            log["status"], log["notes"] = "PENDING", str(e)
            break
        except TRANSIENT as e:
            log["error_message"] = f"{type(e).__name__}: {e}"
            issues.append(prov.issue("WARNING", "transient_error_retry",
                                     f"attempt {attempt}: {log['error_message']}"))
            time.sleep(attempt)
        except Exception as e:  # noqa: BLE001 - any agent bug must be logged, not crash the run
            tb = traceback.format_exc(limit=3)
            log["error_message"] = f"{type(e).__name__}: {e}"
            issues.append(prov.issue("ERROR", "agent_exception", tb[-1500:]))
            break
    tables = {}
    if result is not None:
        log["status"], log["notes"] = result.status, result.notes
        log["inputs_found"] = result.inputs_found
        issues = issues + result.issues
        if result.status in ("SUCCESS", "PARTIAL"):
            tables = result.tables
    return _finish(conn, log, t0, issues, tables)


def _finish(conn, log, t0, issues, tables) -> dict:
    with db.transaction(conn):
        for table, rows in tables.items():
            log["records_out"] += db.replace_source_rows(conn, table, log["source_id"], rows)
        log["issues_logged"] = db.insert_issues(conn, issues)
        log["finished_at"] = now_iso()
        log["duration_s"] = round(time.time() - t0, 2)
        cols = list(log)
        conn.execute(f"INSERT INTO pipeline_runs ({', '.join(cols)}) VALUES "
                     f"({', '.join('?' for _ in cols)})", [log[c] for c in cols])
    return log


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Team 35 Puducherry agri pipeline supervisor")
    ap.add_argument("--sources", help="comma-separated source ids (default: all in manifest)")
    ap.add_argument("--reset-db", action="store_true", help="drop all tables and recreate schema")
    ap.add_argument("--max-attempts", type=int, default=2)
    ap.add_argument("--no-dump", action="store_true", help="do not rewrite db/dump")
    ap.add_argument("--dump-only", action="store_true")
    args = ap.parse_args(argv)

    load_dotenv()
    conn = db.connect()
    if args.dump_only:
        db.dump_sql(conn, DUMP)
        print(f"wrote {rel(DUMP)}")
        return 0
    if args.reset_db:
        db.reset_database(conn)
    else:
        db.init_schema(conn)

    manifest = load_manifest()
    wanted = [s.strip() for s in args.sources.split(",")] if args.sources else list(manifest)
    unknown = [s for s in wanted if s not in manifest]
    if unknown:
        print(f"unknown source ids: {unknown}", file=sys.stderr)
        return 2
    order = [s for s in ORDER if s in wanted] + [s for s in wanted if s not in ORDER]

    run_id = new_run_id()
    print(f"run {run_id}  db={rel(DB_PATH)}  tracing={backend()}")
    t0, started = time.time(), now_iso()
    logs = []

    @traced("pipeline_run")
    def _run_all():
        for sid in order:
            log = run_source(conn, run_id, manifest[sid], args.max_attempts)
            logs.append(log)
            print(f"  {sid:<3} {log['agent_id'] or '-':<4} {log['status']:<8} "
                  f"rows={log['records_out']:<5} issues={log['issues_logged']:<4} "
                  f"{(log['notes'] or log['error_message'] or '')[:110]}")

    _run_all()
    statuses = [l["status"] for l in logs]
    overall = "FAILED" if "FAILED" in statuses else (
        "PARTIAL" if any(s in ("PARTIAL", "PENDING") for s in statuses) else "SUCCESS")
    summary = dict(run_id=run_id, source_id="ALL", agent_id="ORCH", status=overall, attempts=1,
                   inputs_found=sum(l["inputs_found"] or 0 for l in logs),
                   records_out=sum(l["records_out"] for l in logs),
                   issues_logged=sum(l["issues_logged"] for l in logs), started_at=started,
                   finished_at=now_iso(), duration_s=round(time.time() - t0, 2),
                   error_message=None,
                   notes=", ".join(f"{l['source_id']}={l['status']}" for l in logs),
                   trace_backend=backend())
    with db.transaction(conn):
        cols = list(summary)
        conn.execute(f"INSERT INTO pipeline_runs ({', '.join(cols)}) VALUES "
                     f"({', '.join('?' for _ in cols)})", [summary[c] for c in cols])
    if not args.no_dump:
        db.dump_sql(conn, DUMP)
    print(f"overall {overall}: {summary['records_out']} rows, {summary['issues_logged']} issues, "
          f"{summary['duration_s']} s")
    conn.close()
    return 0 if overall != "FAILED" else 1
