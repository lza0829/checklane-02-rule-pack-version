<script setup>
import { onMounted, ref } from 'vue'
import { getJSON } from '../api'
const rows = ref([])
const detail = ref(null)
const err = ref('')
async function load() {
  rows.value = await getJSON('/api/batches')
}
async function show(id) {
  detail.value = await getJSON(`/api/batches/${id}`)
}
onMounted(async () => {
  try { await load() }
  catch (e) { err.value = String(e.message || e) }
})
</script>
<template>
  <div class="page">
    <header>
      <h1>批次</h1>
      <p class="muted">历史入检批次与报告；计数只对绑定版本的规则快照负责</p>
    </header>
    <p v-if="err" class="tag danger">{{ err }}</p>
    <div class="panel">
      <table>
        <thead><tr><th>ID</th><th>数据集</th><th>规则包</th><th>状态</th><th>扫描</th><th>通过</th><th>隔离</th><th>签发</th><th>时间</th></tr></thead>
        <tbody>
          <tr v-for="r in rows" :key="r.id" style="cursor:pointer" @click="show(r.id)">
            <td>{{ r.id }}</td>
            <td>{{ r.dataset_id }}</td>
            <td>
              <span v-if="r.report.rule_pack" class="tag">v{{ r.report.rule_pack.version }}（#{{ r.rule_pack_id }}）</span>
              <span v-else class="muted">未绑定</span>
            </td>
            <td>{{ r.status }}</td>
            <td>{{ r.scanned_count }}</td>
            <td>{{ r.passed_count }}</td>
            <td>{{ r.quarantined_count }}</td>
            <td>{{ r.released_count }}</td>
            <td>{{ r.created_at }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="panel" v-if="detail">
      <h3>
        批次 #{{ detail.id }} 明细
        <span v-if="detail.rule_pack" class="tag">绑定 v{{ detail.rule_pack.version }}（包 #{{ detail.rule_pack_id }}）· {{ detail.rule_pack.note || '无备注' }}</span>
      </h3>
      <h4 v-if="detail.snapshot_rules && detail.snapshot_rules.length">该版规则清单（不可变快照）</h4>
      <table v-if="detail.snapshot_rules && detail.snapshot_rules.length">
        <thead><tr><th>源规则</th><th>名称</th><th>字段</th><th>类型</th><th>严重度</th><th>参数</th></tr></thead>
        <tbody>
          <tr v-for="r in detail.snapshot_rules" :key="r.id">
            <td>#{{ r.source_rule_id }}</td>
            <td>{{ r.name }}</td>
            <td><code>{{ r.field }}</code></td>
            <td>{{ r.rule_type }}</td>
            <td><span class="tag" :class="r.severity === 'error' ? 'danger' : ''">{{ r.severity }}</span></td>
            <td class="muted"><code>{{ r.params_json }}</code></td>
          </tr>
        </tbody>
      </table>
      <h4>报告</h4>
      <pre class="muted" style="white-space:pre-wrap">{{ JSON.stringify(detail.report, null, 2) }}</pre>
    </div>
  </div>
</template>
