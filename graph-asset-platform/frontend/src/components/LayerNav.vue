<template>
  <div class="layer-nav">
    <!-- 顶部 4 个 UI 层 Tab -->
    <div class="layer-tabs">
      <button
        v-for="l in UI_LAYERS"
        :key="l"
        class="layer-tab"
        :class="{ 'layer-tab--active': state.activeLayer === l }"
        @click="onSelectLayer(l)"
      >
        {{ l }}
        <span class="layer-tab-count mono">{{ layerCount(l) }}</span>
      </button>
    </div>

    <!-- 当前层选择器 -->
    <div class="selectors">
      <template v-if="state.activeLayer === '业务层'">
        <el-select
          v-model="sel.domain"
          placeholder="域"
          size="small"
          filterable
          clearable
          class="sel"
          @change="onSelectorChange"
        >
          <el-option v-for="d in domainOptions" :key="d" :label="d" :value="d" />
        </el-select>
        <el-select
          v-model="sel.scenario"
          placeholder="场景"
          size="small"
          filterable
          clearable
          class="sel"
          @change="onSelectorChange"
        >
          <el-option v-for="s in scenarioOptions" :key="s" :label="s" :value="s" />
        </el-select>
        <el-select
          v-if="typeOptions.length > 1"
          v-model="sel.type"
          placeholder="类型"
          size="small"
          clearable
          class="sel"
          @change="onSelectorChange"
        >
          <el-option v-for="t in typeOptions" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
      </template>
      <template v-else>
        <el-select
          v-model="sel.nf"
          placeholder="网元"
          size="small"
          filterable
          clearable
          class="sel"
          @change="onNfChange"
        >
          <el-option v-for="n in nfOptions" :key="n" :label="n" :value="n" />
        </el-select>
        <el-select
          v-model="sel.version"
          placeholder="版本"
          size="small"
          filterable
          clearable
          class="sel sel-ver"
          :disabled="!sel.nf"
          @change="onSelectorChange"
        >
          <el-option v-for="v in versionOptions" :key="v" :label="v" :value="v" />
        </el-select>
        <el-select
          v-if="typeOptions.length > 1"
          v-model="sel.type"
          placeholder="类型"
          size="small"
          clearable
          class="sel sel-type"
          @change="onSelectorChange"
        >
          <el-option v-for="t in typeOptions" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
      </template>
      <el-input
        v-model="sel.q"
        placeholder="搜索 id / 名称 / 中文名"
        size="small"
        clearable
        class="sel-search"
        :prefix-icon="SearchIcon"
        @input="onSearchInput"
        @change="onSearchCommit"
        @clear="onSelectorChange"
      />
    </div>

    <!-- 列表（虚拟滚动） -->
    <div class="list-wrap">
      <div v-if="loading && accumulatedRows.length === 0" class="list-loading">加载中…</div>
      <div v-else-if="loadError" class="list-error">加载失败：{{ loadError }}</div>
      <div v-else-if="accumulatedRows.length === 0" class="list-empty">
        <span>{{ sel.version ? '该版本下无对象' : '当前条件下无对象' }}</span>
      </div>

      <el-table-v2
        v-else
        ref="tableRef"
        :columns="columns"
        :data="accumulatedRows"
        :row-height="36"
        :header-height="32"
        :width="tableWidth"
        :height="tableHeight"
        :row-class="rowClass"
        :estimated-row-height="36"
        class="nav-table"
        @row-click="onRowClick"
      />

      <!-- 加载更多 -->
      <div class="list-footer">
        <span v-if="loading" class="footer-text">加载中…</span>
        <button
          v-else-if="hasMore"
          class="load-more"
          @click="loadMore"
        >
          加载更多（第 {{ currentPage + 1 }} 页）
        </button>
        <span v-else-if="accumulatedRows.length > 0" class="footer-text">
          共 {{ totalCount }} 项<template v-if="totalCount > accumulatedRows.length">
            （已加载 {{ accumulatedRows.length }}）</template>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, h, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElSelect, ElOption, ElInput, ElTag } from 'element-plus'
import type { Column, TableV2Instance } from 'element-plus'
import { useNav, UI_LAYERS, UI_LAYER_TYPES, type UiLayer } from '../composables/useNav'
import { stats, type ObjectRow, type Stats } from '../api'

const { state, selectedId, viewVersion, loading, loadError, selectLayer, loadList } = useNav()

const PAGE_SIZE = 100

// 全局 stats（网元/版本/域 选项来源）
const globalStats = ref<Stats | null>(null)

async function loadStats(): Promise<void> {
  try {
    globalStats.value = await stats()
  } catch {
    /* 容错：选项为空时用户仍可手输 */
  }
}

onMounted(loadStats)

const sel = computed(() => state.selectors[state.activeLayer])

// 选项来源
const nfOptions = computed(() => {
  const layer = state.activeLayer
  const perNf = globalStats.value?.per_layer_per_nf?.[layer] ?? {}
  // 优先用 stats 里该层有计数的网元；否则回退到 nfs 全量
  const fromStats = Object.keys(perNf)
  if (fromStats.length > 0) return fromStats.sort()
  return globalStats.value?.nfs ?? []
})

const versionOptions = computed(() => {
  if (!sel.value.nf) return []
  return globalStats.value?.versions_per_nf?.[sel.value.nf] ?? []
})

const typeOptions = computed(() => {
  const types = UI_LAYER_TYPES[state.activeLayer] ?? []
  const labelMap: Record<string, string> = {
    MMLCommand: '命令',
    ConfigObject: '配置对象',
    Feature: '特性',
    License: 'License',
    AtomTask: '原子Task',
    CompoundTask: '步骤Task',
    FeatureTask: '特性Task',
    Task: '任务',
    BusinessDomain: '业务域',
    NetworkScenario: '网络场景',
    ConfigurationSolution: '配置方案',
  }
  return types.map((t) => ({ value: t, label: labelMap[t] ?? t }))
})

// 域/场景：stats 里 per_domain 给域；场景暂无聚合，从首次列表推导
const domainOptions = computed(() => {
  const fromStats = globalStats.value ? Object.keys(globalStats.value.per_domain ?? {}) : []
  if (fromStats.length > 0) return fromStats.sort()
  // 回退：从已加载行里推导
  return unique(accumulatedRows.value.map((r) => r.domain).filter((d): d is string => !!d))
})

const scenarioOptions = computed(() => {
  // 从 stats per_domain_scenario 取：选了域 → 该域下场景；未选域 → 所有场景并集
  const ds = globalStats.value?.per_domain_scenario ?? {}
  if (sel.value.domain) return Object.keys(ds[sel.value.domain] ?? {}).sort()
  const all = new Set<string>()
  for (const sc of Object.values(ds)) {
    for (const s of Object.keys(sc)) all.add(s)
  }
  return Array.from(all).sort()
})

function unique<T>(arr: T[]): T[] {
  return Array.from(new Set(arr))
}

// ---------- 累积多页行（响应式 computed：从 listCache 派生） ----------
/**
 * accumulatedRows 是 computed，自动跟随 useNav 状态变化（activeLayer / selectors /
 * pages / listCache）。这样跨栏跳转（syncTo 改选择器+loadList 写缓存）后，左栏列表
 * 即时重建并包含跳转目标，高亮+滚动才能定位。不再需要手动 rebuildAccumulated。
 */
const currentPage = computed(() => state.pages[state.activeLayer])
const accumulatedRows = computed<ObjectRow[]>(() => {
  const layer = state.activeLayer
  const s = state.selectors[layer]
  const rows: ObjectRow[] = []
  const seen = new Set<string>()
  for (let p = 1; p <= state.pages[layer]; p++) {
    const key = cacheKeyOf(layer, s, p)
    const cached = state.listCache.get(key)
    if (!cached) break
    for (const r of cached.rows) {
      if (!seen.has(r.id)) {
        seen.add(r.id)
        rows.push(r)
      }
    }
  }
  return rows
})

// 镜像 useNav.cacheKey（保持 key 一致）
function cacheKeyOf(layer: UiLayer, s: typeof sel.value, page: number): string {
  return [layer, s.nf, s.version, s.type, s.domain, s.scenario, s.q, String(page)].join('|')
}

/** 是否还有更多页：上一页满 PAGE_SIZE 则可能还有下一页（后端无 total）。 */
const hasMore = computed(() => {
  const layer = state.activeLayer
  const s = state.selectors[layer]
  const lastPage = state.pages[layer]
  const lastKey = cacheKeyOf(layer, s, lastPage)
  const last = state.listCache.get(lastKey)
  return last !== undefined && last.rows.length >= PAGE_SIZE
})

/** 当前条件下对象总数（X-Total-Count，取最近一页缓存条目）。 */
const totalCount = computed(() => {
  const layer = state.activeLayer
  const s = state.selectors[layer]
  const entry = state.listCache.get(cacheKeyOf(layer, s, state.pages[layer]))
  return entry?.total ?? accumulatedRows.value.length
})

// ---------- 交互 ----------
function onSelectLayer(l: UiLayer): void {
  if (state.activeLayer === l) return
  selectLayer(l)
  // 切层后：若该层选择器下尚未加载过，触发首屏加载
  void ensureLoaded()
}

function onNfChange(): void {
  // 网元变化 → 版本失效，清空
  sel.value.version = ''
  onSelectorChange()
}

function onSelectorChange(): void {
  // 选择器变化 → 回到第 1 页重新加载（accumulatedRows 是 computed，自动跟随）；
  // 版本上下文跟随左栏选择器（中栏详情/右栏邻居用同一版本取数）
  viewVersion.value = sel.value.version
  state.pages[state.activeLayer] = 1
  void ensureLoaded()
}

// ---------- 搜索：输入防抖 300ms，回车/清空立即 ----------
let searchTimer: ReturnType<typeof setTimeout> | null = null

function onSearchInput(): void {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    searchTimer = null
    onSelectorChange()
  }, 300)
}

function onSearchCommit(): void {
  if (searchTimer) {
    clearTimeout(searchTimer)
    searchTimer = null
  }
  onSelectorChange()
}

async function ensureLoaded(): Promise<void> {
  const layer = state.activeLayer
  const s = state.selectors[layer]
  const key = cacheKeyOf(layer, s, state.pages[layer])
  if (!state.listCache.has(key)) {
    await loadList()
  }
}

async function loadMore(): Promise<void> {
  state.pages[state.activeLayer] += 1
  await loadList()
}

function onRowClick(params: { row?: ObjectRow } | ObjectRow): void {
  // el-table-v2 的 row-click 回调参数是 { row, rowIndex, event }（兼容个别版本直接传 row）
  const row = (params as { row?: ObjectRow }).row ?? (params as ObjectRow)
  if (row && row.id) selectedId.value = row.id
}

// ---------- 高亮 + 滚动到选中行 ----------
function rowClass(params: { rowIndex: number }): string {
  const row = accumulatedRows.value[params.rowIndex]
  return row && row.id === selectedId.value ? 'nav-row--active' : ''
}

// 选中变化 → 滚动到对应行（el-table-v2 用 scrollToRow API）
watch(
  selectedId,
  async (id) => {
    if (!id) return
    await nextTick()
    const idx = accumulatedRows.value.findIndex((r) => r.id === id)
    if (idx >= 0) {
      // 通过 el-table-v2 的 ref 调用 scrollToRow
      tableRef.value?.scrollToRow?.(idx)
    }
  },
)

// ---------- 表格列 ----------
const tableRef = ref<TableV2Instance | null>(null)

const columns: Column[] = [
  {
    key: 'id',
    title: 'ID',
    dataKey: 'id',
    width: 0, // 用 flex 占满（见下 flexGrow）
    flexGrow: 1,
    cellRenderer: ({ cellData, rowData }: { cellData: string; rowData: ObjectRow }) =>
      h(
        'span',
        {
          class: 'cell-id mono',
          title: cellData,
          // 直接在单元格 DOM 上挂点击，不依赖 el-table-v2 的 row-click 事件（更可靠）
          onClick: () => {
            if (rowData?.id) selectedId.value = rowData.id
          },
        },
        cellData,
      ),
  },
  {
    key: 'type',
    title: '类型',
    dataKey: 'type',
    width: 96,
    align: 'center',
    cellRenderer: ({ cellData, rowData }: { cellData: string; rowData: ObjectRow }) =>
      h(
        ElTag,
        {
          size: 'small',
          effect: 'plain',
          class: 'cell-type',
          onClick: () => {
            if (rowData?.id) selectedId.value = rowData.id
          },
        },
        () => cellData,
      ),
  },
]

// ---------- 表格尺寸（虚拟表需显式宽高） ----------
const tableWidth = ref(360)
const tableHeight = ref(400)

function measure(): void {
  const el = document.querySelector('.list-wrap') as HTMLElement | null
  if (!el) return
  const rect = el.getBoundingClientRect()
  // 减去底部"加载更多"高度
  tableWidth.value = Math.max(240, Math.floor(rect.width))
  tableHeight.value = Math.max(160, Math.floor(rect.height) - 40)
}

let resizeObserver: ResizeObserver | null = null

/** 切回页签时刷新 stats（上传新版本后，网元/版本下拉即时可见新选项）。 */
function onWinFocus(): void {
  void loadStats()
}

onMounted(() => {
  measure()
  resizeObserver = new ResizeObserver(() => measure())
  const el = document.querySelector('.list-wrap') as HTMLElement | null
  if (el) resizeObserver.observe(el)
  // 首屏加载当前层
  void ensureLoaded()
  window.addEventListener('focus', onWinFocus)
})
onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  window.removeEventListener('focus', onWinFocus)
  if (searchTimer) clearTimeout(searchTimer)
})

// 切层 → 该层可能已缓存（syncTo 写入）或需加载，统一走 ensureLoaded（含 loadList + 重建）
watch(
  () => state.activeLayer,
  () => {
    void ensureLoaded()
  },
)

// selectedId 变化且来自 syncTo（跨栏跳转切层后）→ ensureLoaded 已由 activeLayer watch 触发；
// 但若同层内点选，selectedId 变化无需重建列表。此处不再额外 watch listCache（Map 写入不触发响应式）。
// loadList 的结果由 ensureLoaded/loadMore 内部 await 后直接 rebuildAccumulated 处理。

// ---------- 层计数 chip ----------
function layerCount(l: UiLayer): number {
  return globalStats.value?.per_layer?.[l] ?? 0
}

const SearchIcon = () =>
  h(
    'svg',
    { width: '14', height: '14', viewBox: '0 0 24 24', fill: 'none' },
    [
      h('circle', { cx: '11', cy: '11', r: '7', stroke: 'currentColor', 'stroke-width': '1.8' }),
      h('path', {
        d: 'm20 20-3-3',
        stroke: 'currentColor',
        'stroke-width': '1.8',
        'stroke-linecap': 'round',
      }),
    ],
  )
</script>

<style scoped>
.layer-nav {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-sunken);
  border-right: 1px solid var(--border);
  min-width: 0;
}

/* ---- 层 Tab ---- */
.layer-tabs {
  display: flex;
  border-bottom: 1px solid var(--border);
  background: var(--bg-elev);
  flex-shrink: 0;
}

.layer-tab {
  flex: 1;
  background: none;
  border: none;
  padding: 10px 8px;
  font-family: var(--display);
  font-size: 12.5px;
  font-weight: 500;
  color: var(--text-muted);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease),
    background var(--dur-fast) var(--ease);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.layer-tab:hover {
  color: var(--text);
  background: var(--bg-hover);
}

.layer-tab--active {
  color: var(--accent);
  border-bottom-color: var(--accent);
  background: var(--bg-elev);
}

.layer-tab-count {
  font-size: 10px;
  color: var(--text-faint);
  background: var(--bg-sunken);
  padding: 1px 6px;
  border-radius: 999px;
}

.layer-tab--active .layer-tab-count {
  color: var(--accent);
  background: var(--accent-soft);
}

/* ---- 选择器 ---- */
.selectors {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-faint);
  background: var(--bg-elev);
  flex-shrink: 0;
}

.sel {
  width: 100%;
  min-width: 0;
}

.sel-ver,
.sel-type {
  width: calc(50% - 3px);
}

.sel-search {
  width: 100%;
}

/* ---- 列表区 ---- */
.list-wrap {
  flex: 1;
  min-height: 0;
  position: relative;
  display: flex;
  flex-direction: column;
  background: var(--bg-elev);
}

.nav-table {
  flex: 1;
}

.list-loading,
.list-error,
.list-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-faint);
  font-size: 13px;
  padding: var(--space-6);
}

.list-error {
  color: var(--danger);
}

.list-footer {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-2);
  border-top: 1px solid var(--border-faint);
  min-height: 36px;
  background: var(--bg-sunken);
}

.load-more {
  background: var(--bg-elev);
  border: 1px solid var(--border-strong);
  color: var(--text-muted);
  font-size: 12px;
  padding: 4px 14px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease);
  font-family: var(--sans);
}

.load-more:hover {
  color: var(--accent);
  border-color: var(--accent);
  background: var(--accent-soft);
}

.footer-text {
  font-size: 11.5px;
  color: var(--text-faint);
}

/* ---- el-table-v2 行样式覆盖 ---- */
:deep(.el-table-v2) {
  --el-table-border: var(--border-faint);
  --el-fill-color-light: var(--bg-hover);
}

:deep(.el-table-v2__header-cell) {
  background: var(--bg-sunken);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-faint);
}

:deep(.el-table-v2__row) {
  cursor: pointer;
  transition: background var(--dur-fast) var(--ease);
}

:deep(.el-table-v2__row:hover) {
  background: var(--bg-hover);
}

:deep(.nav-row--active) {
  background: var(--accent-soft) !important;
}

:deep(.nav-row--active:hover) {
  background: var(--accent-soft) !important;
}

:deep(.cell-id) {
  font-size: 12px;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
}

:deep(.nav-row--active .cell-id) {
  color: var(--accent);
  font-weight: 500;
}

:deep(.cell-type) {
  font-size: 10.5px;
  font-family: var(--mono);
}
</style>
