<script setup>
import { onMounted, ref, watch } from 'vue'
import { getJSON, postJSON } from '../api'
const datasets = ref([])
const datasetId = ref(1)
const packs = ref([])
const packId = ref(null)
const busy = ref(false)
const err = ref('')
const last = ref(null)

async function loadPacks() {
  packs.value = await getJSON(`/api/rule-packs?dataset_id=${datasetId.value}`)
  packId.value = packs.value.length ? packs.value[packs.value.length - 1].id : null
}
onMounted(async () => {
  datasets.value = await getJSON('/api/datasets')
  if (datasets.value.length) datasetId.value = datasets.value[0].id
  await loadPacks()
})
watch(datasetId, loadPacks)

async function run() {
  busy.value = true
  err.value = ''
  try {
    last.value = await postJSON('/api/inspect', {
      dataset_id: Number(datasetId.value),
      rule_pack_id: Number(packId.value),
    })
  } catch (e) {
    err.value = String(e.message || e)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <div class="page">
    <header>
      <h1>入检台</h1>
      <p class="muted">装载夹具 → 按绑定版本的规则快照裁决 → 隔离失败行 → 放行通过行到精选区</p>
    </header>
    <div class="panel row">
      <label>数据集
        <select v-model="datasetId">
          <option v-for="d in datasets" :key="d.id" :value="d.id">{{ d.id }} · {{ d.name }}</option>
        </select>
      </label>
      <label>规则包版本（必选）
        <select v-model="packId">
          <option v-for="p in packs" :key="p.id" :value="p.id">
            v{{ p.version }} · {{ p.rule_count }} 条规则 · {{ p.note || '无备注' }}
          </option>
        </select>
      </label>
      <button :disabled="busy || !packId" @click="run">{{ busy ? '入检中…' : '开始入检' }}</button>
    </div>
    <p v-if="!packs.length" class="tag danger">该数据集尚无已发布规则包，请先到「规则包版本」发布后再入检</p>
    <p v-if="err" class="tag danger">{{ err }}</p>
    <div class="panel" v-if="last">
      <h3>
        批次 #{{ last.id }}
        <span class="tag" :class="last.status === 'released' ? 'ok' : ''">{{ last.status }}</span>
        <span class="tag">绑定 v{{ last.report.rule_pack.version }}（包 #{{ last.rule_pack_id }}）</span>
      </h3>
      <div class="tiles">
        <div class="tile"><div class="hero-num">{{ last.scanned_count }}</div><div class="muted">扫描</div></div>
        <div class="tile"><div class="hero-num">{{ last.passed_count }}</div><div class="muted">通过</div></div>
        <div class="tile"><div class="hero-num">{{ last.quarantined_count }}</div><div class="muted">隔离</div></div>
        <div class="tile"><div class="hero-num">{{ last.released_count }}</div><div class="muted">签发</div></div>
      </div>
      <h4>本版规则快照（{{ last.snapshot_rules.length }} 条）</h4>
      <table>
        <thead><tr><th>源规则</th><th>名称</th><th>字段</th><th>类型</th><th>严重度</th></tr></thead>
        <tbody>
          <tr v-for="r in last.snapshot_rules" :key="r.id">
            <td>#{{ r.source_rule_id }}</td>
            <td>{{ r.name }}</td>
            <td><code>{{ r.field }}</code></td>
            <td>{{ r.rule_type }}</td>
            <td><span class="tag" :class="r.severity === 'error' ? 'danger' : ''">{{ r.severity }}</span></td>
          </tr>
        </tbody>
      </table>
      <h4>对账</h4>
      <table>
        <thead><tr><th>校验</th><th>结果</th><th>说明</th></tr></thead>
        <tbody>
          <tr v-for="c in last.report.checks" :key="c.name">
            <td>{{ c.name }}</td>
            <td><span class="tag" :class="c.ok ? 'ok' : 'danger'">{{ c.ok ? '通过' : '失败' }}</span></td>
            <td class="muted">{{ c.detail }}</td>
          </tr>
        </tbody>
      </table>
      <h4>行清单</h4>
      <table>
        <thead><tr><th>#</th><th>键</th><th>处置</th><th>命中</th></tr></thead>
        <tbody>
          <tr v-for="r in last.rows" :key="r.id">
            <td>{{ r.row_no }}</td>
            <td>{{ r.entity_key }}</td>
            <td><span class="tag" :class="r.disposition === 'pass' ? 'ok' : 'danger'">{{ r.disposition }}</span></td>
            <td class="muted">{{ r.rule_hits.map(h => h.name).join('；') || '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
