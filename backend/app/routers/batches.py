from fastapi import APIRouter, HTTPException

from app.db import connect
from app.repositories import batches as batch_repo
from app.repositories import rule_packs as rule_pack_repo

router = APIRouter(tags=["batches"])


@router.get("/batches")
def list_batches():
    conn = connect()
    try:
        return batch_repo.list_batches(conn)
    finally:
        conn.close()


@router.get("/batches/{batch_id}")
def get_batch(batch_id: int):
    conn = connect()
    try:
        detail = batch_repo.get_batch(conn, batch_id)
        if not detail:
            raise HTTPException(404, "batch not found")
        detail["rows"] = batch_repo.list_batch_rows(conn, batch_id)
        # 回看该批次绑定版本的规则清单（不可变快照，不随当前草稿变化）
        if detail["rule_pack_id"]:
            detail["rule_pack"] = rule_pack_repo.get_pack(conn, detail["rule_pack_id"])
            detail["snapshot_rules"] = rule_pack_repo.list_snapshot_rules(conn, detail["rule_pack_id"])
        else:
            detail["rule_pack"] = None
            detail["snapshot_rules"] = []
        return detail
    finally:
        conn.close()
