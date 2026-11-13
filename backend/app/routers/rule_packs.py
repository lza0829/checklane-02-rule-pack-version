from fastapi import APIRouter, HTTPException

from app.db import connect
from app.repositories import rule_packs as rule_pack_repo
from app.schemas.entities import RulePackCreate
from app.seed import _now

router = APIRouter(tags=["rule-packs"])


@router.get("/rule-packs")
def list_rule_packs(dataset_id: int | None = None):
    conn = connect()
    try:
        return rule_pack_repo.list_packs(conn, dataset_id)
    finally:
        conn.close()


@router.get("/rule-packs/{pack_id}")
def get_rule_pack(pack_id: int):
    conn = connect()
    try:
        pack = rule_pack_repo.get_pack(conn, pack_id)
        if not pack:
            raise HTTPException(404, "rule pack not found")
        pack["snapshot_rules"] = rule_pack_repo.list_snapshot_rules(conn, pack_id)
        return pack
    finally:
        conn.close()


@router.post("/rule-packs")
def create_rule_pack(body: RulePackCreate):
    conn = connect()
    try:
        pack = rule_pack_repo.create_pack(
            conn,
            dataset_id=body.dataset_id,
            note=body.note,
            now=_now(),
        )
        pack["snapshot_rules"] = rule_pack_repo.list_snapshot_rules(conn, pack["id"])
        conn.commit()
        return pack
    except ValueError as exc:
        conn.rollback()
        raise HTTPException(400, str(exc)) from exc
    finally:
        conn.close()
