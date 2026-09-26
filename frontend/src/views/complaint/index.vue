<template>
  <section class="page" data-module="complaint">
    <header class="page-head">
      <div>
        <h2>市民热线受理</h2>
        <p class="page-desc">受理市民来电，围绕记录编号、来电人、来电内容做登记、转办、反馈与办结归档。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记热线记录</button>
        <button class="btn" type="button" @click="exportRows">导出市民热线清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>记录编号</span>
        <input v-model="filters.记录编号" placeholder="按记录编号检索" />
      </label>
      <label class="filter-item">
        <span>来电人</span>
        <input v-model="filters.来电人" placeholder="按来电人检索" />
      </label>
      <label class="filter-item">
        <span>来电内容</span>
        <input v-model="filters.来电内容" placeholder="按来电内容检索" />
      </label>
      <label class="filter-item">
        <span>记录状态</span>
        <select v-model="filters.记录状态" class="filter-select">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <div v-if="loadError" class="error-banner">
      <span>热线记录列表加载失败：{{ loadError }}</span>
      <button class="btn" type="button" @click="reload">重试</button>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading">
          <td :colspan="columns.length + 1" class="empty-state">正在加载热线记录…</td>
        </tr>
        <template v-else>
          <tr v-for="row in rows" :key="String(row.id)">
            <td v-for="column in columns" :key="column">{{ cellText(row, column) }}</td>
            <td class="row-actions">
              <button class="link" type="button" @click="openDetail(row)">详情</button>
              <button
                v-for="action in actionsFor(row)"
                :key="action"
                class="link"
                type="button"
                @click="openAction(action, row)"
              >
                {{ action }}
              </button>
            </td>
          </tr>
          <tr v-if="!rows.length && !loadError">
            <td :colspan="columns.length + 1" class="empty-state">
              <p>{{ emptyText }}</p>
              <p v-if="activeFilterText" class="empty-filter">当前筛选条件：{{ activeFilterText }}</p>
              <button v-if="hasFilters" class="link" type="button" @click="resetFilters">清除筛选条件</button>
            </td>
          </tr>
        </template>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条市民热线记录</span>
      <span v-if="notice" class="notice-text">{{ notice }}</span>
    </footer>

    <div v-if="detail.visible" class="modal-mask" @click.self="detail.visible = false">
      <div class="modal">
        <header class="modal-head">
          <h3>热线记录详情</h3>
          <button class="link" type="button" @click="detail.visible = false">关闭</button>
        </header>
        <div v-if="detail.loading" class="modal-body">正在读取详情…</div>
        <div v-else-if="detail.error" class="modal-body">
          <p class="error-text">详情读取失败：{{ detail.error }}</p>
          <button class="btn" type="button" @click="openDetail(detail.row)">重试</button>
        </div>
        <dl v-else-if="detail.entry" class="modal-body detail-grid">
          <template v-for="field in columns" :key="field">
            <dt>{{ field }}</dt>
            <dd>{{ cellText(detail.entry, field) }}</dd>
          </template>
        </dl>
      </div>
    </div>

    <div v-if="actionDialog.visible" class="modal-mask" @click.self="closeAction">
      <form class="modal" @submit.prevent="submitAction">
        <header class="modal-head">
          <h3>{{ actionDialog.action }} · {{ cellText(actionDialog.row, '记录编号') }}</h3>
          <button class="link" type="button" @click="closeAction">关闭</button>
        </header>
        <div class="modal-body">
          <p class="conclusion-line">当前处理结论：{{ cellText(actionDialog.row, '处理结果') }}</p>
          <label v-if="actionDialog.field" class="form-item">
            <span>{{ actionDialog.field }}<em class="required">*</em></span>
            <textarea
              v-if="actionDialog.field === '处理结果'"
              v-model="actionDialog.value"
              rows="3"
              :placeholder="`请填写${actionDialog.field}`"
            ></textarea>
            <input
              v-else
              v-model="actionDialog.value"
              :placeholder="`请填写${actionDialog.field}`"
            />
          </label>
          <p v-else>确认将该记录办结归档？归档后不可再转办或反馈。</p>
          <p v-if="actionDialog.error" class="error-text">{{ actionDialog.error }}</p>
        </div>
        <footer class="modal-foot">
          <button class="btn primary" type="submit" :disabled="actionDialog.submitting">
            {{ actionDialog.submitting ? '提交中…' : actionDialog.error ? '重试提交' : '提交' }}
          </button>
        </footer>
      </form>
    </div>

    <div v-if="createDialog.visible" class="modal-mask" @click.self="createDialog.visible = false">
      <form class="modal" @submit.prevent="submitCreate">
        <header class="modal-head">
          <h3>登记热线记录</h3>
          <button class="link" type="button" @click="createDialog.visible = false">关闭</button>
        </header>
        <div class="modal-body">
          <label v-for="field in createFields" :key="field.name" class="form-item">
            <span>
              {{ field.name }}
              <em v-if="field.required" class="required">*</em>
            </span>
            <textarea
              v-if="field.name === '来电内容'"
              v-model="createDialog.form[field.name]"
              rows="3"
              :placeholder="field.placeholder"
            ></textarea>
            <input v-else v-model="createDialog.form[field.name]" :placeholder="field.placeholder" />
            <span v-if="createDialog.fieldErrors[field.name]" class="field-error">
              {{ createDialog.fieldErrors[field.name] }}
            </span>
          </label>
          <p v-if="createDialog.error" class="error-text">{{ createDialog.error }}</p>
        </div>
        <footer class="modal-foot">
          <button class="btn primary" type="submit" :disabled="createDialog.submitting">
            {{ createDialog.submitting ? '提交中…' : createDialog.error ? '重试提交' : '提交' }}
          </button>
        </footer>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/complaint'
const columns = ["记录编号", "来电人", "来电内容", "问题位置", "问题类型", "转办部门", "处理结果", "记录状态"]
const statuses = ["待转办", "已转办", "处理中", "已办结"]
// 每个状态下允许执行的动作，与后端 ACTION_RULES 保持一致
const STATUS_ACTIONS: Record<string, string[]> = {
  待转办: ["转办部门"],
  已转办: ["处理反馈"],
  处理中: ["处理反馈", "办结归档"],
  已办结: [],
}
// 动作需要填写的字段；办结归档不需要填写，弹窗里只做确认
const ACTION_FIELDS: Record<string, string | null> = {
  转办部门: "转办部门",
  处理反馈: "处理结果",
  办结归档: null,
}
const createFields = [
  { name: '记录编号', required: true, placeholder: '请填写受理编号，如 COMP-0004' },
  { name: '来电人', required: true, placeholder: '请填写来电人称呼' },
  { name: '来电内容', required: true, placeholder: '请记录市民反映的问题' },
  { name: '问题位置', required: false, placeholder: '选填' },
  { name: '问题类型', required: false, placeholder: '选填' },
]

const rows = ref<Row[]>([])
const total = ref(0)
const loading = ref(false)
const loadError = ref('')
const notice = ref('')
const stats = ref([
  { label: '待转办记录', value: 0 },
  { label: '处理中记录', value: 0 },
  { label: '已办结记录', value: 0 },
])
const filters = reactive({ 记录编号: '', 来电人: '', 来电内容: '', 记录状态: '' })

const detail = reactive({
  visible: false,
  loading: false,
  error: '',
  row: null as Row | null,
  entry: null as Row | null,
})

const actionDialog = reactive({
  visible: false,
  action: '',
  row: null as Row | null,
  field: null as string | null,
  value: '',
  error: '',
  submitting: false,
})

const createDialog = reactive({
  visible: false,
  form: {} as Record<string, string>,
  fieldErrors: {} as Record<string, string>,
  error: '',
  submitting: false,
})

const hasFilters = computed(() =>
  Boolean(filters.记录编号 || filters.来电人 || filters.来电内容 || filters.记录状态),
)

const activeFilterText = computed(() => {
  const parts: string[] = []
  if (filters.记录编号) parts.push(`记录编号「${filters.记录编号}」`)
  if (filters.来电人) parts.push(`来电人「${filters.来电人}」`)
  if (filters.来电内容) parts.push(`来电内容「${filters.来电内容}」`)
  if (filters.记录状态) parts.push(`记录状态「${filters.记录状态}」`)
  return parts.join('、')
})

const emptyText = computed(() => {
  if (filters.记录状态) return `暂无${filters.记录状态}记录`
  if (hasFilters.value) return '没有符合当前筛选条件的热线记录'
  return '暂无市民热线记录，可点击右上角「登记热线记录」受理新来电'
})

// 列表、详情、转办弹窗共用同一个取值口径，保证三处处理结论一致
function cellText(row: Row | null, column: string): string {
  if (!row) return '—'
  const value = column === '记录状态' ? row['记录状态'] ?? row['status'] : row[column]
  return value === null || value === undefined || value === '' ? '—' : String(value)
}

function actionsFor(row: Row): string[] {
  return STATUS_ACTIONS[String(row.status ?? row['记录状态'] ?? '')] ?? []
}

function resetFilters() {
  filters.记录编号 = ''
  filters.来电人 = ''
  filters.来电内容 = ''
  filters.记录状态 = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function reload() {
  loading.value = true
  loadError.value = ''
  notice.value = ''
  const query = new URLSearchParams()
  if (filters.记录编号) query.set('keyword', filters.记录编号)
  if (filters.来电人) query.set('caller', filters.来电人)
  if (filters.来电内容) query.set('content', filters.来电内容)
  if (filters.记录状态) query.set('status', filters.记录状态)
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error(`接口返回 ${response.status}`)
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '市民热线列表读取失败'
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    const response = await request(`${ENDPOINT}/summary`)
    if (!response.ok) return
    const payload = await response.json()
    stats.value = [
      { label: '待转办记录', value: payload['待转办'] ?? 0 },
      { label: '处理中记录', value: payload['处理中'] ?? 0 },
      { label: '已办结记录', value: payload['已办结'] ?? 0 },
    ]
  } catch {
    // 统计卡片读取失败不阻塞列表
  }
}

async function openDetail(row: Row | null) {
  if (!row) return
  detail.visible = true
  detail.loading = true
  detail.error = ''
  detail.row = row
  detail.entry = null
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error(`接口返回 ${response.status}`)
    }
    detail.entry = await response.json()
  } catch (error) {
    detail.error = error instanceof Error ? error.message : '热线记录详情读取失败'
  } finally {
    detail.loading = false
  }
}

function openAction(action: string, row: Row) {
  notice.value = ''
  const field = ACTION_FIELDS[action] ?? null
  actionDialog.visible = true
  actionDialog.action = action
  actionDialog.row = row
  actionDialog.field = field
  actionDialog.value = field ? String(row[field] ?? '') : ''
  actionDialog.error = ''
  actionDialog.submitting = false
}

function closeAction() {
  if (actionDialog.submitting) return
  actionDialog.visible = false
}

async function submitAction() {
  if (!actionDialog.row || actionDialog.submitting) return
  if (actionDialog.field && !actionDialog.value.trim()) {
    actionDialog.error = `${actionDialog.field}不能为空：请填写${actionDialog.field}后再提交`
    return
  }
  actionDialog.submitting = true
  actionDialog.error = ''
  const values: Record<string, string> = { action: actionDialog.action }
  if (actionDialog.field) values[actionDialog.field] = actionDialog.value.trim()
  try {
    const response = await request(`${ENDPOINT}/${actionDialog.row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok) {
      throw new Error(payload?.detail ?? `接口返回 ${response.status}`)
    }
    if (!payload?.ok) {
      throw new Error(payload?.message ?? '市民热线动作未生效')
    }
    actionDialog.visible = false
    await Promise.all([reload(), loadStats()])
    notice.value = payload.message
  } catch (error) {
    // 失败原因留在弹窗里，按钮恢复可点，直接重试即可
    actionDialog.error = error instanceof Error ? error.message : '市民热线操作失败，请重试'
  } finally {
    actionDialog.submitting = false
  }
}

function openCreate() {
  notice.value = ''
  createDialog.visible = true
  createDialog.form = { 记录编号: '', 来电人: '', 来电内容: '', 问题位置: '', 问题类型: '' }
  createDialog.fieldErrors = {}
  createDialog.error = ''
  createDialog.submitting = false
}

async function submitCreate() {
  if (createDialog.submitting) return
  const errors: Record<string, string> = {}
  if (!createDialog.form.记录编号?.trim()) errors.记录编号 = '请填写记录编号'
  if (!createDialog.form.来电人?.trim()) errors.来电人 = '请填写来电人'
  if (!createDialog.form.来电内容?.trim()) {
    errors.来电内容 = '来电内容不能为空：请补充市民反映的问题后再提交'
  }
  createDialog.fieldErrors = errors
  if (Object.keys(errors).length) return
  createDialog.submitting = true
  createDialog.error = ''
  const values: Record<string, string> = {}
  for (const field of createFields) {
    values[field.name] = (createDialog.form[field.name] ?? '').trim()
  }
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok) {
      throw new Error(payload?.detail ?? `接口返回 ${response.status}`)
    }
    if (!payload?.ok) {
      throw new Error(payload?.message ?? '热线记录登记失败')
    }
    // 重复提交同一记录编号时后端只生效一次，这里刷新列表即可，不会重复显示
    createDialog.visible = false
    await Promise.all([reload(), loadStats()])
    notice.value = payload.message
  } catch (error) {
    createDialog.error = error instanceof Error ? error.message : '热线记录登记失败，请重试'
  } finally {
    createDialog.submitting = false
  }
}

onMounted(() => {
  void reload()
  void loadStats()
})
</script>
