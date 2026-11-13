import importlib

import pytest


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import app.config
    import app.db
    import app.repositories.rule_packs as rule_pack_repo
    import app.seed
    import app.services.inspect_service as svc

    importlib.reload(app.config)
    importlib.reload(app.db)
    importlib.reload(app.seed)
    importlib.reload(rule_pack_repo)
    importlib.reload(svc)
    app.seed.init_db()
    return svc, rule_pack_repo


def _pack_id(rule_pack_repo, conn, dataset_id, version):
    packs = rule_pack_repo.list_packs(conn, dataset_id)
    return next(p["id"] for p in packs if p["version"] == version)


def test_inspect_requires_published_pack_binding(env):
    svc, rule_pack_repo = env
    # 未绑定规则包（不存在的 id）不得入检成功
    with pytest.raises(ValueError):
        svc.run_inspect(1, 999)
    # 别的数据集的包也不能绑定
    with pytest.raises(ValueError):
        svc.run_inspect(1, _pack_id(rule_pack_repo, svc.connect(), 2, 1))


def test_two_versions_on_same_fixture_give_distinguishable_results(env):
    svc, rule_pack_repo = env
    conn = svc.connect()
    v1_id = _pack_id(rule_pack_repo, conn, 1, 1)
    v1_snapshot = rule_pack_repo.list_snapshot_rules(conn, v1_id)
    # v1 含三条规则（两条 error + 一条 warn）
    assert len(v1_snapshot) == 3

    # 草稿改动：停用 price error 规则后发布 v2
    conn.execute("UPDATE rules SET enabled=0 WHERE dataset_id=1 AND field='price'")
    conn.commit()
    pack_v2 = rule_pack_repo.create_pack(conn, dataset_id=1, note="停用 price", now=svc._now())
    assert pack_v2["version"] == 2
    v2_id = pack_v2["id"]
    conn.commit()
    conn.close()

    # 同一夹具分别用两个版本入检
    batch_v1 = svc.run_inspect(1, v1_id)
    batch_v2 = svc.run_inspect(1, v2_id)

    # v1：ORD-3 缺 sku + ORD-4 price 非数字 → 2 隔离
    assert batch_v1["quarantined_count"] == 2
    assert batch_v1["passed_count"] == 4
    # v2：price 规则已不在快照，ORD-4 仅剩 warn 级 qty 问题 → 放行；只隔离 ORD-3
    assert batch_v2["quarantined_count"] == 1
    assert batch_v2["passed_count"] == 5

    # 批次各自记录绑定版本，结果可区分
    assert batch_v1["rule_pack_id"] == v1_id
    assert batch_v2["rule_pack_id"] == v2_id
    assert batch_v1["report"]["rule_pack"]["version"] == 1
    assert batch_v2["report"]["rule_pack"]["version"] == 2


def test_published_snapshot_immune_to_later_draft_changes(env):
    svc, rule_pack_repo = env
    conn = svc.connect()
    v1_id = _pack_id(rule_pack_repo, conn, 1, 1)
    before = rule_pack_repo.list_snapshot_rules(conn, v1_id)

    # 发布后再启停/改字段，v1 快照保持不变
    conn.execute("UPDATE rules SET enabled=0, severity='warn', field='renamed' WHERE dataset_id=1")
    conn.commit()
    after = rule_pack_repo.list_snapshot_rules(conn, v1_id)
    assert before == after

    # 已绑定 v1 的批次计数仍按 v1 快照：依旧 2 隔离，与当前草稿无关
    detail = svc.run_inspect(1, v1_id)
    assert detail["quarantined_count"] == 2
    assert len(detail["snapshot_rules"]) == 3
    conn.close()


def test_batch_detail_can_review_snapshot_rules(env):
    svc, rule_pack_repo = env
    detail = svc.run_inspect(1, 1)
    assert detail["rule_pack"]["version"] == 1
    names = {r["name"] for r in detail["snapshot_rules"]}
    assert {"sku 必填", "price 须为数字", "qty 须为整数"} <= names
    # 报告内嵌的快照与独立查询一致
    assert detail["report"]["snapshot_rules"] == detail["snapshot_rules"]


def test_pack_and_batches_survive_reopen(env, tmp_path, monkeypatch):
    svc, rule_pack_repo = env
    detail = svc.run_inspect(1, 1)
    pack_before = rule_pack_repo.list_packs(svc.connect(), 1)

    # 模拟进程重启：重新加载配置/数据库连接并再次 init_db（迁移幂等）
    import app.config
    import app.db
    import app.seed

    importlib.reload(app.config)
    importlib.reload(app.db)
    importlib.reload(app.seed)
    app.seed.init_db()
    conn = app.db.connect()
    assert rule_pack_repo.list_packs(conn, 1) == pack_before
    import app.repositories.batches as batch_repo

    batch = batch_repo.get_batch(conn, detail["id"])
    assert batch is not None
    assert batch["rule_pack_id"] == 1
    assert batch["quarantined_count"] == detail["quarantined_count"]
    conn.close()


def test_cannot_publish_empty_pack(env):
    svc, rule_pack_repo = env
    conn = svc.connect()
    conn.execute("UPDATE rules SET enabled=0 WHERE dataset_id=2")
    conn.commit()
    with pytest.raises(ValueError):
        rule_pack_repo.create_pack(conn, dataset_id=2, note="空包", now=svc._now())
    conn.close()
