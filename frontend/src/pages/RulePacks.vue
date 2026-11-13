<script setup>
import { onMounted, ref } from 'vue'
import { getJSON, postJSON } from '../api'
const datasets = ref([])
const packs = ref([])
const datasetId = ref(1)
const note = ref('')
const busy = ref(false)
const err = ref('')
const detail = ref(null)

async function loadDatasets() {
  datasets.value = await getJSON('/api/datasets')
  if (datasets.value.length) datasetId.value = datasets.value[0].id
}
async function loadPacks() {
  packs.value = await getJSON(`/api/rule-packs?dataset_id=${datasetId.value}`)
  detail.value = null
}
async function publish() {
  busy.value = true
  err.value = ''
  try {
    const created = await postJSON('/api/rule-packs', {
      dataset_id: Number(datasetId.value),
      note: note.value || null,
    })
    note.value = ''
    await loadPacks()
    await show(created.id)
  } catch (e) {
    err.value = String(e.message || e)
  } finally {
    busy.value = false
  }
}
async function show(id) {
  detail.value = await getJSON(`/api/rule-packs/${id}`)
}
onMounted(async () => {
  try {
    await loadDatasets()
    await loadPacks()
  } catch (e) {
    err.value = String(e.message || e)
  }
})
</script>
<template>
  <div class="page">
    <header>
      <h1>规则包版本</h1>
      <p class="muted">把当前启用规则发布成不可变快照；发布后启停/改字段不会回写旧版本，要改规则只能发新版本</p>
    </header>
    <p v-if="err" class="tag danger">{{ err }}</p>
    <div class="panel row">
      <label>数据集
        <select v-model="datasetId" @change="loadPacks">
          <option v-for="d in datasets" :key="d.id" :value="d.id">{{ d.id }} · {{ d.name }}</option>
        </select>
      </label>
      <label>版本备注
        <input v-model="note" placeholder="例如：停用 price 校验" style="padding:6px 8px;border-radius:6px;border:1px solid var(--line)" />
      </label>
      <button :disabled="busy" @click="publish">{{ busy ? '发布中…' : '发布新版本（快照）' }}</button>
    </div>
    <div class="panel">
      <table>
        <thead><tr><th>版本</th><th>数据集</th><th>规则数</th><th>备注</th><th>发布时间</th><th></th></tr></thead>
        <tbody>
          <tr v-for="p in packs" :key="p.id" style="cursor:pointer" @click="show(p.id)">
            <td>v{{ p.version }}（包 #{{ p.id }}）</td>
            <td>{{ p.dataset_name }}</td>
            <td>{{ p.rule_count }}</td>
            <td class="muted">{{ p.note || '—' }}</td>
            <td class="muted">{{ p.created_at }}</td>
            <td><button @click.stop="show(p.id)">回看快照</button></td>
          </tr>
          <tr v-if="!packs.length"><td colspan="6" class="muted">该数据集暂无已发布版本</td></tr>
        </tbody>
      </table>
    </div>
    <div class="panel" v-if="detail">
      <h3>包 #{{ detail.id }} · v{{ detail.version }} 规则快照 <span class="tag ok">不可变</span></h3>
      <p class="muted">{{ detail.dataset_name }} · 发布于 {{ detail.created_at }} · {{ detail.note || '无备注' }}</p>
      <table>
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
    </div>
  </div>
</template>
