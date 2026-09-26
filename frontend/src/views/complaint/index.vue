<template>
  <section class="page" data-module="complaint">
    <header class="page-head">
      <div>
        <h2>市民热线受理</h2>
        <p class="page-desc">受理市民来电，围绕记录编号、来电人、来电内容做登记，并完成转办部门、处理反馈与办结归档。</p>
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

    <div class="status-tabs" role="tablist">
      <button
        v-for="tab in statusTabs"
        :key="tab.value"
        type="button"
        class="status-tab"
        :class="{ active: activeStatus === tab.value }"
        @click="switchStatus(tab.value)"
      >
        {{ tab.label }}
      </button>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field.key" class="filter-item">
        <span>{{ field.label }}</span>
        <input v-model="filters[field.key]" :placeholder="`按${field.label}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <div v-if="banner" class="banner" :class="banner.type">
      <span>{{ banner.text }}</span>
      <button v-if="banner.retry" class="btn small" type="button" @click="banner.onRetry">重试</button>
      <button class="btn small ghost" type="button" @click="banner = null">关闭</button>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column.key">{{ column.label }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column.key">
            <button
              v-if="column.key === '记录编号'"
              type="button"
              class="link"
              @click="openDetail(row)"
            >
              {{ row[column.key] ?? '—' }}
            </button>
            <template v-else>{{ formatCell(row, column.key) }}</template>
          </td>
          <td class="row-actions">
            <button
              v-for="action in availableActions(row)"
              :key="action.key"
              class="link"
              type="button"
              @click="openAction(action.key, row)"
            >
              {{ action.label }}
            </button>
            <span v-if="!availableActions(row).length" class="muted-text">无可用操作</span>
          </td>
        </tr>
        <tr v-if="!loading && !loadError && !rows.length">
          <td :colspan="columns.length + 1" class="empty-state">
            <div class="empty-title">{{ emptyTitle }}</div>
            <div class="empty-desc">{{ emptyDesc }}</div>
            <button
              v-if="hasActiveFilters"
              class="btn small"
              type="button"
              @click="clearFiltersReload"
            >
              清空当前过滤条件
            </button>
          </td>
        </tr>
        <tr v-if="loading">
          <td :colspan="columns.length + 1" class="empty-state">正在加载热线记录…</td>
        </tr>
        <tr v-if="loadError">
          <td :colspan="columns.length + 1" class="empty-state error-text">
            <div class="empty-title">热线记录加载失败</div>
            <div class="empty-desc">{{ loadError }}</div>
            <button class="btn small primary" type="button" @click="reload">重新加载</button>
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条市民热线记录{{ activeStatus ? `（当前筛选：${activeStatus}）` : '' }}</span>
    </footer>

    <!-- 登记 / 转办 / 处理反馈 / 办结 共用弹窗 -->
    <div v-if="dialog" class="modal-mask" @click.self="closeDialog">
      <div class="modal">
        <div class="modal-head">
          <h3>{{ dialogTitle }}</h3>
          <button class="btn small ghost" type="button" @click="closeDialog">关闭</button>
        </div>

        <div v-if="dialog.readonly" class="modal-body">
          <dl class="detail-list">
            <template v-for="item in detailItems" :key="item.label">
              <dt>{{ item.label }}</dt>
              <dd :class="{ 'muted-text': item.empty }">{{ item.value }}</dd>
            </template>
          </dl>
        </div>

        <form v-else class="modal-body" @submit.prevent="submitDialog">
          <div v-if="dialog.row" class="dialog-context">
            <div><span class="muted-text">记录编号：</span>{{ dialog.row['记录编号'] }}</div>
            <div><span class="muted-text">来电内容：</span>{{ dialog.row['来电内容'] }}</div>
            <div>
              <span class="muted-text">当前处理结论：</span>
              <span :class="{ 'muted-text': !conclusion(dialog.row) }">
                {{ conclusion(dialog.row) || '暂无处理结论' }}
              </span>
            </div>
          </div>

          <template v-for="field in dialogFields" :key="field.key">
            <label v-if="field.type !== 'textarea'" class="form-item">
              <span>{{ field.label }}{{ field.required ? ' *' : '' }}</span>
              <input v-model="dialogForm[field.key]" :placeholder="field.placeholder ?? ''" />
            </label>
            <label v-else class="form-item">
              <span>{{ field.label }}{{ field.required ? ' *' : '' }}</span>
              <textarea v-model="dialogForm[field.key]" rows="4" :placeholder="field.placeholder ?? ''"></textarea>
            </label>
          </template>

          <div v-if="dialog.kind === 'archive'" class="form-tip">
            办结后当前处理结论将随记录归档，且不可再次处理反馈。
          </div>

          <div v-if="dialogError" class="banner inline error">
            <span>{{ dialogError }}</span>
            <button class="btn small" type="button" @click="submitDialog">重试提交</button>
          </div>

          <div class="modal-foot">
            <button class="btn" type="button" @click="closeDialog">取消</button>
            <button class="btn primary" type="submit" :disabled="submitting">
              {{ submitting ? '提交中…' : dialogSubmitText }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type BannerType = 'error' | 'success'
type DialogKind = 'create' | 'transfer' | 'feedback' | 'archive' | 'detail'

interface Column {
  key: string
  label: string
}
interface ActionMeta {
  key: string
  label: string
}
interface DialogState {
  kind: DialogKind
  row: Row | null
  readonly: boolean
}
interface FormField {
  key: string
  label: string
  type?: 'textarea'
  required?: boolean
  placeholder?: string
}
interface BannerState {
  type: BannerType
  text: string
  retry: boolean
  onRetry: () => void
}

const ENDPOINT = '/api/complaint'
const STATUS_ORDER = ['待转办', '已转办', '处理中', '已办结']

const columns: Column[] = [
  { key: '记录编号', label: '记录编号' },
  { key: '来电人', label: '来电人' },
  { key: '来电内容', label: '来电内容' },
  { key: '问题位置', label: '问题位置' },
  { key: '问题类型', label: '问题类型' },
  { key: '转办部门', label: '转办部门' },
  { key: '处理结果', label: '处理结论' },
  { key: '记录状态', label: '记录状态' },
]
const actionMetas: Record<string, ActionMeta> = {
  transfer: { key: 'transfer', label: '转办部门' },
  feedback: { key: 'feedback', label: '处理反馈' },
  archive: { key: 'archive', label: '办结归档' },
}
const statusTabs = [
  { value: '', label: '全部' },
  { value: '待转办', label: '待转办' },
  { value: '已转办', label: '已转办' },
  { value: '处理中', label: '处理中' },
  { value: '已办结', label: '已办结' },
]
const filterFields: { key: string; label: string }[] = [
  { key: 'keyword', label: '记录编号' },
  { key: 'caller', label: '来电人' },
  { key: 'content', label: '来电内容' },
]

const rows = ref<Row[]>([])
const total = ref(0)
const stats = ref<{ label: string; value: number }[]>([
  { label: '待转办记录', value: 0 },
  { label: '处理中记录', value: 0 },
  { label: '已办结记录', value: 0 },
])
const activeStatus = ref('待转办')
const filters = reactive<Record<string, string>>({ keyword: '', caller: '', content: '' })
const loading = ref(false)
const loadError = ref('')
const banner = ref<BannerState | null>(null)

const dialog = ref<DialogState | null>(null)
const dialogForm = reactive<Record<string, string>>({})
const dialogError = ref('')
const submitting = ref(false)

function conclusion(row: Row): string {
  // 受理列表、详情、转办弹窗三处的处理结论都走同一口径
  return String(row['处理结果'] ?? '').trim()
}

function formatCell(row: Row, key: string): string {
  if (key === '处理结果') {
    return conclusion(row) || '暂无处理结论'
  }
  if (key === '转办部门') {
    return String(row[key] ?? '').trim() || '—'
  }
  const value = row[key]
  return value === null || value === undefined || String(value) === '' ? '—' : String(value)
}

function availableActions(row: Row): ActionMeta[] {
  const status = String(row['记录状态'] ?? row.status ?? '待转办')
  const index = STATUS_ORDER.indexOf(status)
  const list: ActionMeta[] = []
  if (index <= STATUS_ORDER.indexOf('已转办')) list.push(actionMetas.transfer)
  if (index === STATUS_ORDER.indexOf('已转办')) list.push(actionMetas.feedback)
  if (index === STATUS_ORDER.indexOf('处理中')) list.push(actionMetas.archive)
  return list
}

const hasTextFilters = computed(() =>
  filterFields.some((field) => (filters[field.key] ?? '').trim() !== '')
)
const hasActiveFilters = computed(() => !!activeStatus.value || hasTextFilters.value)

const emptyTitle = computed(() => {
  if (hasTextFilters.value || (activeStatus.value && activeStatus.value !== '待转办')) {
    return '没有符合条件的热线记录'
  }
  if (activeStatus.value === '待转办') {
    return '暂无待转办记录'
  }
  return '暂无市民热线记录'
})
const emptyDesc = computed(() => {
  if (hasActiveFilters.value) {
    const parts: string[] = []
    if (activeStatus.value) parts.push(`状态「${activeStatus.value}」`)
    filterFields.forEach((field) => {
      const value = filters[field.key]?.trim()
      if (value) parts.push(`${field.label}含「${value}」`)
    })
    return `当前过滤条件（${parts.join('，')}）下没有记录，条件仍然保留，可调整后重新查询。`
  }
  return '当前没有待转办的市民来电，新登记的热线记录会出现在这里。'
})

function switchStatus(status: string) {
  activeStatus.value = status
  void reload()
}

function resetFilters() {
  filters.keyword = ''
  filters.caller = ''
  filters.content = ''
  void reload()
}

function clearFiltersReload() {
  filters.keyword = ''
  filters.caller = ''
  filters.content = ''
  activeStatus.value = ''
  void reload()
}

function exportRows() {
  const query = new URLSearchParams()
  if (activeStatus.value) query.set('status', activeStatus.value)
  if (filters.keyword.trim()) query.set('keyword', filters.keyword.trim())
  window.open(`${ENDPOINT}/export?${query.toString()}`, '_blank')
}

async function reload() {
  loading.value = true
  loadError.value = ''
  const query = new URLSearchParams()
  if (activeStatus.value) query.set('status', activeStatus.value)
  filterFields.forEach((field) => {
    const value = filters[field.key]?.trim()
    if (value) query.set(field.key, value)
  })
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error(await readError(response, '热线记录列表读取失败'))
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    // 失败时保留已有行与过滤条件，并明确区分于“暂无数据”
    loadError.value = error instanceof Error ? error.message : '市民热线列表读取失败'
  } finally {
    loading.value = false
  }
  void loadStats()
}

async function loadStats() {
  try {
    const response = await request(`${ENDPOINT}/stats`)
    if (!response.ok) return
    const payload = await response.json()
    if (Array.isArray(payload.items)) stats.value = payload.items
  } catch {
    // 统计卡片失败不打断受理主流程
  }
}

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json()
    if (payload?.message) return String(payload.message)
    if (payload?.detail) return String(payload.detail)
  } catch {
    // 非 JSON 错误响应时使用兜底文案
  }
  return `${fallback}（接口返回 ${response.status}）`
}

function openCreate() {
  dialog.value = { kind: 'create', row: null, readonly: false }
  Object.assign(dialogForm, {
    记录编号: '',
    来电人: '',
    来电内容: '',
    问题位置: '',
    问题类型: '',
  })
  dialogError.value = ''
}

function openDetail(row: Row) {
  dialog.value = { kind: 'detail', row, readonly: true }
  dialogError.value = ''
}

function openAction(key: string, row: Row) {
  const kind = key as DialogKind
  dialog.value = { kind, row, readonly: false }
  Object.keys(dialogForm).forEach((fieldKey) => delete dialogForm[fieldKey])
  if (kind === 'transfer') {
    Object.assign(dialogForm, { 转办部门: String(row['转办部门'] ?? '').trim() })
  } else if (kind === 'feedback') {
    Object.assign(dialogForm, { 处理结果: conclusion(row) })
  }
  dialogError.value = ''
}

function closeDialog() {
  if (submitting.value) return
  dialog.value = null
  dialogError.value = ''
}

const dialogTitle = computed(() => {
  switch (dialog.value?.kind) {
    case 'create':
      return '登记热线记录'
    case 'transfer':
      return `转办部门 · ${dialog.value.row?.['记录编号'] ?? ''}`
    case 'feedback':
      return `处理反馈 · ${dialog.value.row?.['记录编号'] ?? ''}`
    case 'archive':
      return `办结归档 · ${dialog.value.row?.['记录编号'] ?? ''}`
    case 'detail':
      return `热线记录详情 · ${dialog.value.row?.['记录编号'] ?? ''}`
    default:
      return ''
  }
})

const dialogSubmitText = computed(() => {
  switch (dialog.value?.kind) {
    case 'create':
      return '提交登记'
    case 'transfer':
      return '确认转办'
    case 'feedback':
      return '提交处理结论'
    case 'archive':
      return '确认办结归档'
    default:
      return '提交'
  }
})

const createFields: FormField[] = [
  { key: '记录编号', label: '记录编号', required: true, placeholder: '例如 COMP-2026-0004' },
  { key: '来电人', label: '来电人', required: true, placeholder: '来电人姓名或联系方式' },
  { key: '来电内容', label: '来电内容', type: 'textarea', required: true, placeholder: '请记录市民反映的具体问题' },
  { key: '问题位置', label: '问题位置', placeholder: '选填' },
  { key: '问题类型', label: '问题类型', placeholder: '选填，如井盖设施、路灯照明' },
]
const transferFields: FormField[] = [
  { key: '转办部门', label: '转办部门', required: true, placeholder: '请填写承办部门名称' },
]
const feedbackFields: FormField[] = [
  { key: '处理结果', label: '处理结论', type: 'textarea', required: true, placeholder: '请填写处置过程与处理结论' },
]

const dialogFields = computed<FormField[]>(() => {
  switch (dialog.value?.kind) {
    case 'create':
      return createFields
    case 'transfer':
      return transferFields
    case 'feedback':
      return feedbackFields
    default:
      return []
  }
})

const detailItems = computed(() => {
  const row = dialog.value?.row
  if (!row) return []
  const result = conclusion(row)
  return [
    { label: '记录编号', value: String(row['记录编号'] ?? '—'), empty: false },
    { label: '来电人', value: formatCell(row, '来电人'), empty: false },
    { label: '来电内容', value: formatCell(row, '来电内容'), empty: false },
    { label: '问题位置', value: formatCell(row, '问题位置'), empty: formatCell(row, '问题位置') === '—' },
    { label: '问题类型', value: formatCell(row, '问题类型'), empty: formatCell(row, '问题类型') === '—' },
    { label: '转办部门', value: String(row['转办部门'] ?? '').trim() || '暂未转办', empty: !String(row['转办部门'] ?? '').trim() },
    { label: '处理结论', value: result || '暂无处理结论', empty: !result },
    { label: '记录状态', value: String(row['记录状态'] ?? row.status ?? '—'), empty: false },
  ]
})

function buildPayload(): Record<string, unknown> {
  const kind = dialog.value?.kind
  if (kind === 'create') {
    return { values: { ...dialogForm } }
  }
  const actionMap: Record<'transfer' | 'feedback' | 'archive', string> = {
    transfer: '转办部门',
    feedback: '处理反馈',
    archive: '办结归档',
  }
  if (kind !== 'transfer' && kind !== 'feedback' && kind !== 'archive') {
    return { values: { ...dialogForm } }
  }
  return { values: { action: actionMap[kind], ...dialogForm } }
}

async function submitDialog() {
  if (!dialog.value || submitting.value) return
  submitting.value = true
  dialogError.value = ''
  const kind = dialog.value.kind
  const rowId = dialog.value.row?.id
  try {
    const url = kind === 'create' ? ENDPOINT : `${ENDPOINT}/${rowId}/actions`
    const response = await request(url, {
      method: 'POST',
      body: JSON.stringify(buildPayload()),
    })
    const payload = response.headers.get('content-type')?.includes('application/json')
      ? await response.json().catch(() => null)
      : null
    if (!response.ok || payload?.ok === false) {
      throw new Error(payload?.message || payload?.detail || '提交失败，请稍后重试')
    }
    // 成功后统一重新拉取列表，绝不把返回记录直接追加到本地，避免重复显示同一编号
    banner.value = { type: 'success', text: payload?.message ?? '操作已生效', retry: false, onRetry: () => {} }
    dialog.value = null
    await reload()
    window.setTimeout(() => {
      if (banner.value?.type === 'success') banner.value = null
    }, 4000)
  } catch (error) {
    // 提交失败：弹窗保留、表单内容保留、按钮恢复可点，可直接重试
    dialogError.value = error instanceof Error ? error.message : '提交失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

onMounted(reload)
</script>

<style scoped>
.status-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.status-tab {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 16px;
  padding: 4px 14px;
  font-size: 13px;
  cursor: pointer;
}
.status-tab.active {
  background: var(--brand);
  border-color: var(--brand);
  color: #fff;
}
.banner {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: space-between;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 12px;
  margin-bottom: 10px;
  font-size: 13px;
}
.banner.error {
  background: #fef3f2;
  border-color: #fecdca;
  color: #b42318;
}
.banner.success {
  background: #ecfdf3;
  border-color: #abefc6;
  color: #067647;
}
.banner.inline {
  margin: 8px 0 0;
}
.btn.small {
  padding: 3px 10px;
  font-size: 12px;
}
.empty-title {
  font-size: 14px;
  color: #1f2937;
  margin-bottom: 4px;
}
.empty-desc {
  font-size: 12px;
  margin-bottom: 8px;
}
.muted-text {
  color: var(--muted);
}
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(16, 24, 40, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.modal {
  width: 520px;
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 64px);
  overflow-y: auto;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 12px 32px rgba(16, 24, 40, 0.2);
}
.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}
.modal-head h3 {
  margin: 0;
  font-size: 15px;
}
.modal-body {
  padding: 14px 16px;
}
.dialog-context {
  background: #f8fafc;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 12px;
  font-size: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.form-item {
  display: block;
  margin-bottom: 12px;
}
.form-item span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
}
.form-item input,
.form-item textarea {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 13px;
  font-family: inherit;
  resize: vertical;
}
.form-tip {
  font-size: 12px;
  color: var(--muted);
  background: #f8fafc;
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 10px;
}
.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
}
.detail-list {
  display: grid;
  grid-template-columns: 88px 1fr;
  gap: 8px 12px;
  margin: 0;
  font-size: 13px;
}
.detail-list dt {
  color: var(--muted);
}
.detail-list dd {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
