from __future__ import annotations

import json
import sqlite3
from typing import Any


def _snapshot_rule(rule: dict[str, Any]) -> dict[str, Any]:
    """快照行转成规则引擎可消费的规则字典（含 enabled=1）。"""
    return {
        "id": rule["source_rule_id"],
        "name": rule["name"],
        "field": rule["field"],
        "rule_type": rule["rule_type"],
        "severity": rule["severity"],
        "params_json": rule["params_json"],
        "params": json.loads(rule["params_json"] or "{}"),
        "enabled": 1,
    }


def next_version(conn: sqlite3.Connection, dataset_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(version), 0) + 1 AS v FROM rule_packs WHERE dataset_id=?",
        (dataset_id,),
    ).fetchone()
    return int(row["v"])


def create_pack(
    conn: sqlite3.Connection,
    *,
    dataset_id: int,
    note: str | None,
    now: str,
) -> dict[str, Any]:
    """把数据集当前启用的规则打成不可变快照并发布为新版本。

    快照只写独立表，之后 rules 表的启停/改字段都不会回写到已发布版本。
    """
    ds = conn.execute("SELECT id FROM datasets WHERE id=?", (dataset_id,)).fetchone()
    if not ds:
        raise ValueError(f"dataset {dataset_id} not found")

    enabled_rules = conn.execute(
        """
        SELECT id, name, field, rule_type, severity, params_json
        FROM rules
        WHERE dataset_id=? AND enabled=1
        ORDER BY id
        """,
        (dataset_id,),
    ).fetchall()
    if not enabled_rules:
        raise ValueError("当前没有启用规则，无法发布空规则包")

    version = next_version(conn, dataset_id)
    cur = conn.execute(
        "INSERT INTO rule_packs(dataset_id, version, note, rule_count, created_at) VALUES (?,?,?,?,?)",
        (dataset_id, version, note, len(enabled_rules), now),
    )
    pack_id = int(cur.lastrowid)
    conn.executemany(
        """
        INSERT INTO rule_pack_snapshots(
          pack_id, source_rule_id, name, field, rule_type, severity, params_json
        ) VALUES (?,?,?,?,?,?,?)
        """,
        [
            (
                pack_id,
                r["id"],
                r["name"],
                r["field"],
                r["rule_type"],
                r["severity"],
                r["params_json"],
            )
            for r in enabled_rules
        ],
    )
    pack = get_pack(conn, pack_id)
    assert pack is not None
    return pack


def list_packs(conn: sqlite3.Connection, dataset_id: int | None = None) -> list[dict[str, Any]]:
    if dataset_id is None:
        rows = conn.execute(
            """
            SELECT p.id, p.dataset_id, p.version, p.note, p.rule_count, p.created_at,
                   d.name AS dataset_name
            FROM rule_packs p
            JOIN datasets d ON d.id = p.dataset_id
            ORDER BY p.dataset_id, p.version
            """
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT p.id, p.dataset_id, p.version, p.note, p.rule_count, p.created_at,
                   d.name AS dataset_name
            FROM rule_packs p
            JOIN datasets d ON d.id = p.dataset_id
            WHERE p.dataset_id=?
            ORDER BY p.version
            """,
            (dataset_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_pack(conn: sqlite3.Connection, pack_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT p.id, p.dataset_id, p.version, p.note, p.rule_count, p.created_at,
               d.name AS dataset_name
        FROM rule_packs p
        JOIN datasets d ON d.id = p.dataset_id
        WHERE p.id=?
        """,
        (pack_id,),
    ).fetchone()
    return dict(row) if row else None


def list_snapshot_rules(conn: sqlite3.Connection, pack_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, pack_id, source_rule_id, name, field, rule_type, severity, params_json
        FROM rule_pack_snapshots
        WHERE pack_id=?
        ORDER BY id
        """,
        (pack_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_pack_for_inspect(
    conn: sqlite3.Connection, pack_id: int, dataset_id: int
) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    """取规则包并校验归属数据集；返回 (包元信息, 可执行快照规则列表)。"""
    pack = get_pack(conn, pack_id)
    if not pack or pack["dataset_id"] != dataset_id:
        return None
    rules = [_snapshot_rule(r) for r in list_snapshot_rules(conn, pack_id)]
    return pack, rules
