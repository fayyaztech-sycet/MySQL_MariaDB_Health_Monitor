"""Index / EXPLAIN analyzer (README section 5).

For the top slow digests, attempts EXPLAIN FORMAT=JSON and flags:
  - full table scan            (access_type == "ALL")
  - missing usable index       (empty possible_keys)
  - temporary table            (using_temporary_table)
  - filesort                   (using_filesort)

EXPLAIN requires a valid executable statement; digest templates contain `?`
placeholders, so many fail cleanly and are skipped (best-effort). Findings are
returned as structured dicts for the recommendation engine.
"""
from __future__ import annotations

import json
import logging
import re

from app.mysql_connection import query_all

logger = logging.getLogger(__name__)

_SELECT_RE = re.compile(r"^\s*select\b", re.IGNORECASE)
_FORBIDDEN_PREFIXES = ("insert", "update", "delete", "replace", "call",
                       "show", "set", "create", "alter", "drop", "grant",
                       "commit", "rollback", "explain", "analyze", "describe")


def _collect_tables(node: dict, findings: list[dict], table: str | None = None):
    """Recursively walk an EXPLAIN JSON query_block, collecting per-table flags."""
    atype = node.get("access_type")
    table_name = node.get("table_name") or table or "?"

    if atype == "ALL":
        findings.append(
            {"table": table_name, "type": "full_table_scan", "detail": "Full table scan detected"}
        )
    elif atype and atype not in ("const", "eq_ref", "ref", "range", "index"):
        pass

    if atype and not node.get("possible_keys") and atype in ("ALL", "index"):
        findings.append(
            {"table": table_name, "type": "missing_index", "detail": "No usable index"}
        )

    attached = node.get("attached_subqueries") or []
    for sub in attached:
        for qb in sub.get("query_block", []):
            _collect_tables(qb, findings, table_name)

    nested = node.get("nested_loop") or []
    for nl in nested:
        for tbl in nl:
            _collect_tables(tbl, findings)


def _flags_from_json(data: dict) -> list[dict]:
    findings: list[dict] = []
    qb = data.get("query_block", {})
    _collect_tables(qb, findings)
    if qb.get("using_temporary_table"):
        findings.append({"type": "temporary_table", "detail": "Temporary table used"})
    if qb.get("using_filesort"):
        findings.append({"type": "filesort", "detail": "Filesort used"})
    return findings


def _explain_one(conn, query: str) -> list[dict]:
    if not _SELECT_RE.match(query):
        return []
    for prefix in _FORBIDDEN_PREFIXES:
        if query.lower().startswith(prefix):
            return []
    try:
        rows = query_all(conn, f"EXPLAIN FORMAT=JSON {query}")
    except Exception as exc:
        logger.debug("EXPLAIN failed for query (skipping): %s", exc)
        return []
    if not rows:
        return []
    try:
        data = json.loads(rows[0].get("EXPLAIN") or rows[0].get("JSON") or "{}")
    except (json.JSONDecodeError, KeyError):
        data = rows[0] if isinstance(rows[0], dict) else {}
    return _flags_from_json(data)


def analyze_queries(session, conn, queries: list[dict], limit: int = 5) -> list[dict]:
    """Run EXPLAIN analysis over the given query dicts (from query_analyzer)."""
    all_findings: list[dict] = []
    for q in queries[:limit]:
        flags = _explain_one(conn, q["query"])
        for f in flags:
            all_findings.append({**f, "query": q["query"]})
    return all_findings
