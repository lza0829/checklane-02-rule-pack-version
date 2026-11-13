# 04-checklane（检道）

Checklane — 数据质检通道：入检批次装载 → 规则命中与严重度裁决 → 隔离/放行签发 → 签发清单与源批对账。

**不是** Feed 多源归并（Feedstitch），**不是** 作业依赖编排（Batchgate），**不是** CDC 变更流按序落库（Changeflow）。
**也不是** 报表看板 / CRUD 后台 / 电商订单 / OA 工单。

## 启动

`ash
docker compose up --build
`

| 入口 | 地址 |
| --- | --- |
| 前端 | http://localhost:5400 |
| API | http://localhost:10400 |

本地开发（可选）：

`ash
# backend
cd backend && pip install -r requirements.txt
set DATA_DIR=..\\data
uvicorn app.main:app --reload --port 10400

# frontend
cd frontend && npm install && npm run dev
`

## 主链

登记数据集与规则 → 发布规则包版本（启用规则的不可变快照）→ 入检时显式绑定版本 → 按快照裁决放行/隔离 → 签发到精选区 → 批次报告回看该版规则清单，计数与各列表数字同源

## 规则包版本（rule_pack_version）

- **发布**：「规则包版本」页选数据集后发布，系统把当时**启用规则**复制成不可变快照（`rule_packs` + `rule_pack_snapshots`），版本号按数据集自增。空规则集禁止发布。
- **入检绑定**：入检台必须选择一个已发布版本；未带 `rule_pack_id`、版本不存在或不属于该数据集，一律 400 拒绝入检。
- **不可变**：发布后在「规则」页启停/改字段只影响草稿，不回写任何已发布版本；要改规则只能发新版本。同一夹具用两个版本入检，隔离/签发结果按各自快照独立计算。
- **批次口径**：批次记录 `rule_pack_id`，报告内嵌该版规则清单；扫描/隔离/签发计数只对绑定快照负责，与当前草稿无关。批次详情可回看快照，进程重启后版本、快照与批次均持久保留在 SQLite。

## 种子说明

- **Orders Snapshot**：JSONL 商品快照，含必填缺失与类型错误行，用于演示入检与隔离。
- **Inventory Snapshot**：库存快照，独立数据集，用于第二路规则演示。

打开「入检台」选数据集跑一次，再看隔离区 / 精选区 / 批次报告计数是否与本次报告一致。

## 技术栈

Python 3.12 + FastAPI + SQLite；Vue 3 + Vite + Nginx。

## 0-1 切口（未实现，见题单）

当前仓库已实现「单批入检 + 基础规则 + 放行签发 + 规则包版本」主链。严重度整批阻断、抽样入检、跨字段规则、批次重开、金标对照、批内重复键、放行冻结窗、规则临时豁免、跨数据集参照检查等均在 ackend/app/modules/* 留空包，按题单逐题换主链路实现。
