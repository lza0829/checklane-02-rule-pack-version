# rule_pack_version：规则包版本
#
# 实现位置：
# - 表结构 / 迁移 / 种子首发：app/seed.py（rule_packs、rule_pack_snapshots，
#   inspect_batches.rule_pack_id）
# - 发布与快照读取：app/repositories/rule_packs.py
# - API：app/routers/rule_packs.py（GET/POST /api/rule-packs、GET /api/rule-packs/{id}）
# - 入检绑定与计数口径：app/services/inspect_service.py
#   （run_inspect(dataset_id, rule_pack_id)，未绑定已发布版本直接 400）
# - 批次详情回看：app/routers/batches.py（rule_pack + snapshot_rules）
# - 前端：frontend/src/pages/RulePacks.vue、Inspect.vue、Batches.vue
#
# 保证：
# 1. 发布 = 把当时启用规则复制进 rule_pack_snapshots 的不可变快照；
#    rules 表后续启停/改字段不影响任何已发布版本，要改只能发新版本。
# 2. 入检必须显式携带 rule_pack_id，且该包须属于当前数据集，否则拒绝入检。
# 3. 批次的扫描/隔离/签发计数只对绑定快照负责，report_json 内嵌该版规则清单，
#    进程重启/刷新后版本、快照、批次均持久保留在本机 SQLite。
