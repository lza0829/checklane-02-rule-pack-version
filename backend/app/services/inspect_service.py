from __future__ import annotations

import json
from typing import Any

from app.config import FIXTURES_DIR
from app.db import connect
from app.engines.parse_fixture import parse_jsonl
from app.engines.rule_engine import decide_disposition, evaluate_row
from app.repositories import batches as batch_repo
from app.repositories import curated as curated_repo
from app.repositories import datasets as dataset_repo
from app.repositories import quarantine as quarantine_repo
from app.repositories import rule_packs as rule_pack_repo
from app.seed import _now


def run_inspect(dataset_id: int, rule_pack_id: int) -> dict[str, Any]:
    conn = connect()
    try:
        ds = dataset_repo.get_dataset(conn, dataset_id)
        if not ds:
            raise ValueError(f"dataset {dataset_id} not found")
        if not ds["enabled"]:
            raise ValueError(f"dataset {dataset_id} disabled")

        # 入检必须显式绑定一个已发布、且属于该数据集的规则包版本
        bound = rule_pack_repo.get_pack_for_inspect(conn, rule_pack_id, dataset_id)
        if bound is None:
            raise ValueError(
                f"rule_pack {rule_pack_id} 不存在或不属于数据集 {dataset_id}，未绑定已发布版本不得入检"
            )
        pack, rules = bound

        path = FIXTURES_DIR / ds["fixture_path"]
        rows = parse_jsonl(path)

        scanned = len(rows)
        passed = failed = quarantined = released = 0
        row_results: list[dict[str, Any]] = []
        now = _now()

        # 评估只用规则包快照，与 rules 表当前草稿状态无关
        for idx, payload in enumerate(rows, start=1):
            hits = evaluate_row(payload, rules)
            disposition = decide_disposition(hits)
            entity_key = str(payload.get("entity_key") or "") or None
            if disposition == "quarantine":
                quarantined += 1
                failed += 1
            else:
                passed += 1
            row_results.append(
                {
                    "row_no": idx,
                    "entity_key": entity_key,
                    "payload": payload,
                    "disposition": disposition,
                    "rule_hits": hits,
                }
            )

        checks = [
            {
                "name": "scan_breakdown",
                "ok": scanned == passed + quarantined,
                "detail": f"scanned({scanned}) = passed({passed}) + quarantined({quarantined})",
            }
        ]

        # 批次报告内嵌绑定版本与快照清单，批次详情可回看当时规则
        snapshot_rules = rule_pack_repo.list_snapshot_rules(conn, pack["id"])
        report = {
            "dataset_id": dataset_id,
            "dataset_name": ds["name"],
            "fixture_path": ds["fixture_path"],
            "rule_pack": {
                "id": pack["id"],
                "version": pack["version"],
                "note": pack["note"],
                "rule_count": pack["rule_count"],
                "created_at": pack["created_at"],
            },
            "rule_count": len(rules),
            "snapshot_rules": snapshot_rules,
            "counts": {
                "scanned": scanned,
                "passed": passed,
                "failed": failed,
                "quarantined": quarantined,
                "released": 0,
            },
            "checks": checks,
        }
        batch_id = batch_repo.insert_batch(
            conn,
            dataset_id=dataset_id,
            rule_pack_id=pack["id"],
            status="inspected",
            scanned=scanned,
            passed=passed,
            failed=failed,
            quarantined=quarantined,
            released=0,
            report=report,
            created_at=now,
        )

        for item in row_results:
            batch_repo.insert_row(
                conn,
                batch_id=batch_id,
                row_no=item["row_no"],
                entity_key=item["entity_key"],
                payload=item["payload"],
                disposition=item["disposition"],
                rule_hits=item["rule_hits"],
            )
            if item["disposition"] == "quarantine":
                reasons = "; ".join(
                    f"{h['name']}:{h['detail']}" for h in item["rule_hits"] if h.get("severity") == "error"
                )
                quarantine_repo.insert(
                    conn,
                    batch_id=batch_id,
                    dataset_id=dataset_id,
                    row_no=item["row_no"],
                    entity_key=item["entity_key"],
                    reason=reasons or "rule hit",
                    payload=item["payload"],
                    created_at=now,
                )
            else:
                # pass rows auto-release to curated (base chain)
                key = item["entity_key"] or f"row-{item['row_no']}"
                curated_repo.upsert(
                    conn,
                    dataset_id=dataset_id,
                    batch_id=batch_id,
                    entity_key=key,
                    payload=item["payload"],
                    released_at=now,
                )
                released += 1

        report["counts"]["released"] = released
        report["checks"].append(
            {
                "name": "release_matches_passed",
                "ok": released == passed,
                "detail": f"released({released}) = passed({passed})",
            }
        )
        report["checks"].append(
            {
                "name": "quarantine_table_matches",
                "ok": quarantine_repo.count_all(conn) >= quarantined,
                "detail": "quarantine rows persisted for this and prior batches",
            }
        )
        conn.execute(
            """
            UPDATE inspect_batches
            SET released_count=?, report_json=?, status=?
            WHERE id=?
            """,
            (released, json.dumps(report, ensure_ascii=False), "released" if released else "inspected", batch_id),
        )
        conn.commit()

        detail = batch_repo.get_batch(conn, batch_id)
        assert detail is not None
        detail["rows"] = batch_repo.list_batch_rows(conn, batch_id)
        detail["rule_pack"] = rule_pack_repo.get_pack(conn, pack["id"])
        detail["snapshot_rules"] = snapshot_rules
        detail["curated_total"] = curated_repo.count_all(conn, dataset_id)
        detail["quarantine_total"] = quarantine_repo.count_all(conn)
        return detail
    finally:
        conn.close()


def dashboard_stats() -> dict[str, Any]:
    conn = connect()
    try:
        datasets = conn.execute("SELECT COUNT(*) AS c FROM datasets").fetchone()["c"]
        rules = conn.execute("SELECT COUNT(*) AS c FROM rules WHERE enabled=1").fetchone()["c"]
        batches = conn.execute("SELECT COUNT(*) AS c FROM inspect_batches").fetchone()["c"]
        return {
            "dataset_count": datasets,
            "enabled_rule_count": rules,
            "batch_count": batches,
            "curated_count": curated_repo.count_all(conn),
            "quarantine_count": quarantine_repo.count_all(conn),
        }
    finally:
        conn.close()
