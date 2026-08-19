<template>
  <div class="dir-view">
    <!-- 面包屑 + 工具栏 -->
    <div class="dir-head">
      <nav class="crumbs" :aria-label="'资产目录路径'">
        <span class="crumb root" :class="{ active: !cwd }" @click="emit('enter-dir', '')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"
              stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" />
          </svg>
          {{ root === 'docs' ? '原始产品文档' : '全部资产' }}
        </span>
        <template v-for="(seg, i) in segments" :key="i">
          <span class="sep">/</span>
          <span
            class="crumb mono"
            :class="{ active: i === segments.length - 1 }"
            :title="seg"
            @click="emit('enter-dir', prefix(i))"
          >{{ seg }}</span>
        </template>
      </nav>
      <div v-if="canManage" class="dir-tools">
        <button class="ghost-btn" @click="emit('action', { type: 'new-dir', target: cwd, isDir: true })">+ 新建</button>
        <button class="ghost-btn" @click="emit('action', { type: 'upload', target: cwd, isDir: true })">↑ 上传到此层</button>
        <button class="ghost-btn" @click="emit('open-trash')">🗑 回收站</button>
      </div>
    </div>

    <!-- 批量操作条 -->
    <div v-if="!readonly && selectedCount > 0" class="batch-bar">
      <span class="batch-count">已选 <b>{{ selectedCount }}</b> 项</span>
      <div class="batch-actions">
        <button class="ghost-btn" @click="emit('batch', { type: 'move', paths: selectedPaths })">批量移动</button>
        <button class="danger-btn" @click="emit('batch', { type: 'delete', paths: selectedPaths })">批量删除</button>
        <button class="link-btn" @click="clearSelection">取消选择</button>
      </div>
    </div>

    <!-- 列表 -->
    <div ref="bodyRef" class="dir-body" @scroll="onScroll" @contextmenu.prevent="onBlankMenu">
      <div v-if="loading" class="hint">加载中…</div>
      <div v-else-if="!sorted.length" class="hint empty">
        <span>空目录{{ canManage ? '（右键空白处可新建 / 上传）' : '' }}</span>
      </div>
      <div v-else class="ftable" role="table">
        <div class="fthead" role="row">
          <div v-if="!readonly" class="th th-check">
            <input
              v-if="sorted.length"
              type="checkbox"
              class="fcheck"
              :checked="allSelected"
              :indeterminate.prop="someSelected"
              title="全选"
              @click.stop
              @change="toggleAll($event)"
            />
          </div>
          <div class="th th-name">名称</div>
          <div class="th th-type">类型</div>
          <div class="th th-size">大小</div>
        </div>

        <div
          v-for="e in visible"
          :key="e.path"
          class="frow"
          :class="{ checked: selected.has(e.path) }"
          role="row"
          :title="e.path"
          @click="onRowClick(e)"
          @contextmenu.prevent.stop="onRowMenu($event, e)"
        >
          <div v-if="!readonly" class="td td-check" @click.stop>
            <input
              type="checkbox"
              class="fcheck"
              :checked="selected.has(e.path)"
              @change="toggleOne(e.path, $event)"
            />
          </div>
          <div class="td td-name">
            <span class="ficon">
              <svg v-if="e.is_dir" width="15" height="15" viewBox="0 0 24 24" fill="none">
                <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"
                  stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" />
              </svg>
              <svg v-else width="15" height="15" viewBox="0 0 24 24" fill="none">
                <path d="M6 3h8l4 4v14H6z M14 3v4h4"
                  stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
              </svg>
            </span>
            <span class="fname mono" :title="e.name">{{ e.name }}</span>
          </div>
          <div class="td td-type">{{ e.is_dir ? '文件夹' : inferType(e.name) }}</div>
          <div class="td td-size">{{ e.is_dir ? '—' : fmtSize(e.size) }}</div>
        </div>
      </div>

      <div v-if="visible.length < sorted.length" class="load-more">
        正在加载更多…（剩 {{ sorted.length - visible.length }} 项）
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 资产目录视图（云端文件管理器风格）：面包屑 + 表格 + 多选 + 渐进渲染。
 * 交互：单击文件夹=进入、单击文件=打开详情；文件复选框=选择；右键=菜单。
 * 大目录用渐进渲染（先 PAGE 条，滚到底追加），全选/批量对当前目录「全部文件」生效。
 * 动作 emit 给编排器：enter-dir/open-file（导航）、menu（右键）、action（工具栏）、batch（批量）。
 */
import { computed, ref, watch } from 'vue'
import { listFsChildren, listDocsChildren, type FsEntry } from '../../api'

const PAGE = 200

const props = defineProps<{
  cwd: string
  canManage: boolean
  refreshTick: number
  /** 数据源：assets = 图谱资产库（可管理）；docs = 原始产品文档 output/（只读） */
  root?: 'assets' | 'docs'
}>()
const emit = defineEmits<{
  (e: 'enter-dir', path: string): void
  (e: 'open-file', path: string): void
  (e: 'menu', m: { x: number; y: number; target: FsEntry | null }): void
  (e: 'action', a: { type: string; target: string; isDir: boolean }): void
  (e: 'batch', b: { type: 'delete' | 'move'; paths: string[] }): void
  (e: 'open-trash'): void
}>()

const entries = ref<FsEntry[]>([])
const loading = ref(false)
const selected = ref<Set<string>>(new Set())
const renderCount = ref(PAGE)
const bodyRef = ref<HTMLElement | null>(null)

/** docs（原始产品文档）只读：无批量/复选/写操作 */
const readonly = computed(() => props.root === 'docs')

async function load(): Promise<void> {
  loading.value = true
  try {
    entries.value = readonly.value
      ? await listDocsChildren(props.cwd)
      : await listFsChildren(props.cwd)
  } catch {
    entries.value = []
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.cwd, props.refreshTick, props.root],
  () => {
    selected.value = new Set()
    renderCount.value = PAGE
    if (bodyRef.value) bodyRef.value.scrollTop = 0
    void load()
  },
  { immediate: true },
)

const segments = computed(() => (props.cwd ? props.cwd.split('/').filter(Boolean) : []))
function prefix(i: number): string {
  return segments.value.slice(0, i + 1).join('/')
}

const sorted = computed(() => {
  // list_children 后端已按 目录在前+字母序 返回；这里再保底排序一次
  const byName = (a: FsEntry, b: FsEntry) => a.name.localeCompare(b.name, 'zh')
  const dirs = entries.value.filter((e) => e.is_dir).sort(byName)
  const files = entries.value.filter((e) => !e.is_dir).sort(byName)
  return [...dirs, ...files]
})

const visible = computed(() => sorted.value.slice(0, renderCount.value))

const selectedCount = computed(() => selected.value.size)
const selectedPaths = computed(() => [...selected.value])
const allSelected = computed(
  () => sorted.value.length > 0 && sorted.value.every((e) => selected.value.has(e.path)),
)
const someSelected = computed(() => {
  const n = sorted.value.filter((e) => selected.value.has(e.path)).length
  return n > 0 && n < sorted.value.length
})

function toggleOne(path: string, ev: Event): void {
  const next = new Set(selected.value)
  if ((ev.target as HTMLInputElement).checked) next.add(path)
  else next.delete(path)
  selected.value = next
}
function toggleAll(ev: Event): void {
  const checked = (ev.target as HTMLInputElement).checked
  selected.value = checked ? new Set(sorted.value.map((e) => e.path)) : new Set()
}
function clearSelection(): void {
  selected.value = new Set()
}

function onRowClick(e: FsEntry): void {
  if (e.is_dir) emit('enter-dir', e.path)
  else emit('open-file', e.path)
}
function onRowMenu(ev: MouseEvent, e: FsEntry): void {
  emit('menu', { x: ev.clientX, y: ev.clientY, target: e })
}
function onBlankMenu(ev: MouseEvent): void {
  emit('menu', { x: ev.clientX, y: ev.clientY, target: null })
}

function onScroll(): void {
  const el = bodyRef.value
  if (!el) return
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 80) {
    if (renderCount.value < sorted.value.length) {
      renderCount.value = Math.min(renderCount.value + PAGE, sorted.value.length)
    }
  }
}

/** 由文件名推断对象类型：strip .md → split '@' → ≥3 段取 [1]、2 段取 [0]。 */
function inferType(name: string): string {
  const stem = name.replace(/\.md$/i, '')
  const parts = stem.split('@')
  if (parts.length >= 3) return parts[1] || ''
  if (parts.length === 2) return parts[0] || ''
  return ''
}
function fmtSize(n?: number): string {
  if (!n) return '—'
  if (n < 1024) return n + ' B'
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB'
  return (n / 1024 / 1024).toFixed(1) + ' MB'
}
</script>

<style scoped>
.dir-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

/* 面包屑 + 工具栏 */
.dir-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-4);
  border-bottom: 1px solid var(--border-faint);
  flex-shrink: 0;
  background: var(--bg-elev);
}
.crumbs {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  overflow: hidden;
  flex-wrap: wrap;
}
.crumb {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  font-size: 12.5px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease);
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.crumb:hover {
  background: var(--bg-hover);
  color: var(--text);
}
.crumb.active {
  color: var(--accent);
  font-weight: 600;
}
.crumb.root {
  font-family: var(--display);
  font-weight: 600;
}
.sep {
  color: var(--text-faint);
  font-size: 12px;
  user-select: none;
}
.dir-tools {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

/* 批量操作条 */
.batch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-4);
  background: var(--accent-soft);
  border-bottom: 1px solid var(--accent-ring);
  flex-shrink: 0;
}
.batch-count {
  font-size: 12.5px;
  color: var(--text-muted);
}
.batch-count b {
  color: var(--accent);
}
.batch-actions {
  display: flex;
  gap: 6px;
  align-items: center;
}

/* 列表区 */
.dir-body {
  flex: 1;
  overflow: auto;
  min-height: 0;
}
.hint {
  padding: var(--space-8);
  text-align: center;
  color: var(--text-faint);
  font-size: 13px;
}

.ftable {
  width: 100%;
}
.fthead {
  position: sticky;
  top: 0;
  z-index: 1;
  display: grid;
  grid-template-columns: 40px 1fr 130px 90px;
  align-items: center;
  height: 32px;
  padding: 0 var(--space-3);
  background: var(--bg-sunken);
  border-bottom: 1px solid var(--border);
}
.th {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-faint);
}
.th-size,
.td-size {
  text-align: right;
}
.th-check,
.td-check {
  display: flex;
  align-items: center;
  justify-content: center;
}

.frow {
  display: grid;
  grid-template-columns: 40px 1fr 90px 70px;
  align-items: center;
  min-height: 32px;
  padding: 3px var(--space-3);
  border-bottom: 1px solid var(--border-faint);
  cursor: pointer;
  color: var(--text);
  transition: background var(--dur-fast) var(--ease);
}
.frow:hover {
  background: var(--bg-hover);
}
.frow.checked {
  background: var(--accent-soft);
}
.frow.checked:hover {
  background: var(--accent-soft);
}

.td-name {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}
.ficon {
  display: inline-flex;
  color: var(--text-muted);
  flex-shrink: 0;
}
.frow:hover .ficon,
.frow.checked .ficon {
  color: var(--accent);
}
.fname {
  font-size: 12.5px;
  /* 长文件名（产品文档中文长名）两行换行展示，不再单行截断成"看不见" */
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-height: 1.35;
  word-break: break-all;
  padding: 2px 0;
}
.td-type,
.td-size {
  font-size: 11.5px;
  color: var(--text-faint);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fcheck {
  accent-color: var(--accent);
  cursor: pointer;
  width: 14px;
  height: 14px;
}

.load-more {
  padding: var(--space-3);
  text-align: center;
  color: var(--text-faint);
  font-size: 11.5px;
}

.ghost-btn,
.danger-btn,
.link-btn {
  font-family: var(--sans);
  font-size: 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease);
  border: 1px solid var(--border-strong);
  background: var(--bg-elev);
  color: var(--text-muted);
  padding: 4px 10px;
}
.ghost-btn:hover {
  color: var(--accent);
  border-color: var(--accent);
}
.danger-btn {
  color: var(--danger);
}
.danger-btn:hover {
  color: #fff;
  background: var(--danger);
  border-color: var(--danger);
}
.link-btn {
  border: none;
  background: none;
  color: var(--accent);
  padding: 4px 6px;
}
</style>
