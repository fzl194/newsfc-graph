<template>
  <div class="fs-view">
    <FsDirView
      v-if="mode === 'dir'"
      :cwd="cwd"
      :can-manage="canAssets"
      :refresh-tick="refreshTick"
      @enter-dir="cwd = $event"
      @open-file="openFile"
      @menu="onMenu"
      @action="(a) => runAction(a.type, a.target, a.isDir)"
      @batch="onBatch"
      @open-trash="openTrash"
    />
    <FsFileDetail
      v-else
      :path="activeFile"
      :can-manage="canAssets"
      @back="mode = 'dir'"
      @action="onDetailAction"
    />

    <!-- 右键浮层（无可用项时不渲染，如无 upload 权限右键空白区） -->
    <FsContextMenu
      v-if="menu && menuItems.length"
      :x="menu.x"
      :y="menu.y"
      :items="menuItems"
      @select="onMenuSelect"
      @close="menu = null"
    />

    <!-- 新建 -->
    <el-dialog v-model="newVisible" title="新建" width="440px">
      <div class="dialog-body">
        <label>类型</label>
        <el-select v-model="newForm.kind" class="full">
          <el-option label="空文件夹" value="dir" />
          <el-option label="空 md 文件" value="md" />
        </el-select>
        <label>路径（相对 assets 根，已预填目标目录）</label>
        <el-input v-model="newForm.path" placeholder="Layer/nf/version/..." />
      </div>
      <template #footer>
        <button class="ghost-btn" @click="newVisible = false">取消</button>
        <button class="primary-btn" @click="doNew">创建</button>
      </template>
    </el-dialog>

    <!-- 移动 -->
    <el-dialog v-model="moveVisible" title="移动文件" width="480px">
      <div class="dialog-body">
        <p class="dialog-hint mono">{{ moveTarget }}</p>
        <label>目标目录（相对 assets 根，如 AtomTask/UDG/20.16.0）</label>
        <el-input v-model="moveForm.target_dir" placeholder="顶层目录/nf/version" />
        <label>覆盖 frontmatter（可选，留空不改）</label>
        <div class="move-row">
          <el-input v-model="moveForm.nf" placeholder="nf" />
          <el-input v-model="moveForm.version" placeholder="version" />
          <el-input v-model="moveForm.domain" placeholder="domain" />
          <el-input v-model="moveForm.scenario" placeholder="scenario" />
        </div>
      </div>
      <template #footer>
        <button class="ghost-btn" @click="moveVisible = false">取消</button>
        <button class="primary-btn" :disabled="moving" @click="doMove">{{ moving ? '移动中…' : '移动' }}</button>
      </template>
    </el-dialog>

    <!-- 重命名 -->
    <el-dialog v-model="renameVisible" title="重命名（改 id）" width="520px">
      <div class="dialog-body">
        <label>新 id</label>
        <el-input v-model="renameForm.new_id" placeholder="如：UDG@AtomTask@NEW NAME" />
        <div v-if="renamePreview" class="rename-impact">
          <span>将影响 <b>{{ renamePreview.affected }}</b> 个文件的 [[wikilink]]</span>
          <span class="mono new-path">→ {{ renamePreview.new_path }}</span>
        </div>
      </div>
      <template #footer>
        <button class="ghost-btn" @click="renameVisible = false">取消</button>
        <button class="ghost-btn" :disabled="renaming" @click="previewRename">预览影响</button>
        <button class="primary-btn" :disabled="renaming || !renameForm.new_id" @click="doRename">
          {{ renaming ? '执行中…' : '确认重命名' }}
        </button>
      </template>
    </el-dialog>

    <!-- 批量移动 -->
    <el-dialog v-model="batchMoveVisible" :title="`批量移动 ${batchTargets.length} 个文件`" width="480px">
      <div class="dialog-body">
        <p class="dialog-hint">
          将把这 {{ batchTargets.length }} 个文件移动到目标目录（文件名 = id 不变）。
          <span v-if="batchSkipped > 0">已跳过 {{ batchSkipped }} 个文件夹（移动仅支持文件）。</span>
        </p>
        <label>目标目录（相对 assets 根，如 AtomTask/UDG/20.16.0）</label>
        <el-input v-model="batchMoveForm.target_dir" placeholder="顶层目录/nf/version" />
        <label>覆盖 frontmatter（可选，留空不改）</label>
        <div class="move-row">
          <el-input v-model="batchMoveForm.nf" placeholder="nf" />
          <el-input v-model="batchMoveForm.version" placeholder="version" />
          <el-input v-model="batchMoveForm.domain" placeholder="domain" />
          <el-input v-model="batchMoveForm.scenario" placeholder="scenario" />
        </div>
      </div>
      <template #footer>
        <button class="ghost-btn" @click="batchMoveVisible = false">取消</button>
        <button class="primary-btn" :disabled="batchMoving || !batchMoveForm.target_dir.trim()" @click="doBatchMove">
          {{ batchMoving ? '移动中…' : '移动' }}
        </button>
      </template>
    </el-dialog>

    <!-- 回收站 -->
    <el-dialog v-model="trashVisible" title="回收站（软删除，可还原）" width="720px">
      <div v-if="trashLoading" class="trash-hint">加载中…</div>
      <div v-else-if="!trashItems.length" class="trash-hint">回收站为空</div>
      <ul v-else class="trash-list">
        <li v-for="t in trashItems" :key="t.id" class="trash-row">
          <span class="trash-icon">
            <svg v-if="t.is_dir" width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"
                stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" />
            </svg>
            <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M6 3h8l4 4v14H6z M14 3v4h4" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
            </svg>
          </span>
          <div class="trash-main">
            <span class="trash-path mono" :title="t.original_path">{{ t.original_path }}</span>
            <span class="trash-meta">
              {{ t.is_dir ? `文件夹 · 含 ${t.md_count} 个 md` : '文件' }}
              · {{ fmtTs(t.deleted_at) }} · {{ t.deleted_by || '-' }}
            </span>
          </div>
          <div class="trash-actions">
            <button class="ghost-btn" @click="doRestore(t.id)">还原</button>
            <button v-if="isAdmin" class="danger-btn" @click="doPurge(t.id)">彻底删除</button>
          </div>
        </li>
      </ul>
      <template #footer>
        <button class="ghost-btn" @click="trashVisible = false">关闭</button>
        <button v-if="isAdmin && trashItems.length" class="danger-btn" @click="doEmptyTrash">清空回收站</button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * 资产目录编排器（云端文件管理器风格）。
 * 持有 cwd/mode/activeFile/refreshTick/menu 状态；统一分发 runAction；
 * 新建/移动/重命名弹窗 + 删除确认在此（target 显式参数化，不再绑定单一选中文件）。
 * 子组件：FsDirView（目录视图）/ FsFileDetail（文件详情整页）/ FsContextMenu（右键浮层）。
 * 写操作均经 canAssets 门控；后端仅支持文件级写，故文件夹菜单无 rename/move/delete。
 */
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElDialog, ElInput, ElSelect, ElOption, ElMessage, ElMessageBox } from 'element-plus'
import FsDirView from './fs/FsDirView.vue'
import FsFileDetail from './fs/FsFileDetail.vue'
import FsContextMenu, { type CtxItem } from '../components/fs/FsContextMenu.vue'
import {
  writeFsFile,
  deleteFsFile,
  mkdirFs,
  moveFsFile,
  renameFsFile,
  listTrash,
  restoreTrash,
  purgeTrash,
  emptyTrash,
  type FsEntry,
  type TrashItem,
} from '../api'
import { getSession } from '../auth'

const router = useRouter()
const canAssets = !!getSession()?.can_assets
const isAdmin = !!getSession()?.is_admin

// ---- 导航状态 ----
const cwd = ref('')
const mode = ref<'dir' | 'file'>('dir')
const activeFile = ref('')
const refreshTick = ref(0)

function openFile(p: string): void {
  activeFile.value = p
  mode.value = 'file'
}

// ---- 右键菜单 ----
interface MenuState {
  x: number
  y: number
  target: FsEntry | null
}
const menu = ref<MenuState | null>(null)

const ICON = {
  open: '<svg viewBox="0 0 24 24" fill="none"><path d="M8 12h8M13 9l3 3-3 3" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  folder: '<svg viewBox="0 0 24 24" fill="none"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>',
  file: '<svg viewBox="0 0 24 24" fill="none"><path d="M6 3h8l4 4v14H6z M14 3v4h4" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>',
  upload: '<svg viewBox="0 0 24 24" fill="none"><path d="M12 16V4M7 9l5-5 5 5M5 20h14" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  rename: '<svg viewBox="0 0 24 24" fill="none"><path d="M4 20h4L18 10l-4-4L4 16v4z M14 6l4 4" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>',
  move: '<svg viewBox="0 0 24 24" fill="none"><path d="M4 10h12M4 10l3-3M4 10l3 3M20 14H8M20 14l-3-3M20 14l-3 3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  delete: '<svg viewBox="0 0 24 24" fill="none"><path d="M5 7h14M10 7V4h4v3M6 7l1 13h10l1-13" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
}

const menuItems = computed<CtxItem[]>(() => {
  const t = menu.value?.target ?? null
  if (!t) {
    // 空白区
    return canAssets
      ? [
          { key: 'new-dir', label: '新建文件夹', icon: ICON.folder },
          { key: 'new-md', label: '新建 md 文件', icon: ICON.file },
          { key: 'upload', label: '上传到此层', icon: ICON.upload },
        ]
      : []
  }
  if (t.is_dir) {
    const items: CtxItem[] = [{ key: 'open', label: '打开', icon: ICON.open }]
    if (canAssets) {
      items.push(
        { key: 'new-dir', label: '在此新建文件夹', icon: ICON.folder },
        { key: 'new-md', label: '在此新建 md', icon: ICON.file },
        { key: 'upload', label: '上传到此层', icon: ICON.upload },
        { key: 'delete', label: '删除（递归）', icon: ICON.delete, danger: true },
      )
    }
    return items
  }
  // 文件
  const items: CtxItem[] = [{ key: 'open', label: '打开', icon: ICON.open }]
  if (canAssets) {
    items.push(
      { key: 'rename', label: '重命名（改 id）', icon: ICON.rename },
      { key: 'move', label: '移动', icon: ICON.move },
      { key: 'delete', label: '删除', icon: ICON.delete, danger: true },
    )
  }
  return items
})

function onMenu(m: MenuState): void {
  menu.value = m
}
function onMenuSelect(key: string): void {
  const t = menu.value?.target ?? null
  const target = t ? t.path : cwd.value
  const isDir = t ? t.is_dir : true
  menu.value = null
  runAction(key, target, isDir)
}

// ---- 统一动作分发 ----
function runAction(type: string, target: string, isDir: boolean): void {
  switch (type) {
    case 'open':
      if (isDir) {
        cwd.value = target
        mode.value = 'dir'
      } else {
        openFile(target)
      }
      break
    case 'new-dir':
      openNew(target, 'dir')
      break
    case 'new-md':
      openNew(target, 'md')
      break
    case 'upload':
      uploadHere(target)
      break
    case 'rename':
      openRename(target)
      break
    case 'move':
      openMove(target)
      break
    case 'delete':
      void onDelete(target, isDir)
      break
    case 'refresh':
      refreshTick.value++
      break
    default:
      break
  }
}

// FsFileDetail 的 action：refresh / moved 自带语义；rename/move/delete 针对当前 activeFile
function onDetailAction(a: { type: string; path?: string }): void {
  if (a.type === 'refresh') {
    refreshTick.value++
    return
  }
  if (a.type === 'moved' && a.path) {
    activeFile.value = a.path
    refreshTick.value++
    return
  }
  runAction(a.type, activeFile.value, false)
}

// ---- 新建 ----
const newVisible = ref(false)
const newForm = ref<{ kind: 'dir' | 'md'; path: string }>({ kind: 'dir', path: '' })

function openNew(parentDir: string, kind: 'dir' | 'md'): void {
  newForm.value = { kind, path: parentDir ? parentDir + '/' : '' }
  newVisible.value = true
}
async function doNew(): Promise<void> {
  const p = newForm.value.path.trim().replace(/\/+$/, '')
  if (!p) return
  try {
    if (newForm.value.kind === 'dir') {
      await mkdirFs(p)
      ElMessage.success(`已创建目录 ${p}`)
    } else {
      const fname = p.split('/').pop() ?? 'new.md'
      const id = fname.replace(/\.md$/i, '')
      const placeholder = `---\nid: ${id}\ntype: \n---\n# ${id}\n`
      await writeFsFile(p, placeholder)
      ElMessage.success(`已创建文件 ${p}`)
    }
    newVisible.value = false
    refreshTick.value++
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  }
}

// ---- 移动 ----
const moveVisible = ref(false)
const moving = ref(false)
const moveTarget = ref('')
const moveForm = ref({ target_dir: '', nf: '', version: '', domain: '', scenario: '' })

function openMove(filePath: string): void {
  moveTarget.value = filePath
  const parent = filePath.split('/').slice(0, -1).join('/')
  moveForm.value = { target_dir: parent, nf: '', version: '', domain: '', scenario: '' }
  moveVisible.value = true
}
async function doMove(): Promise<void> {
  if (!moveTarget.value || !moveForm.value.target_dir.trim()) return
  moving.value = true
  try {
    const r = await moveFsFile({
      src: moveTarget.value,
      target_dir: moveForm.value.target_dir,
      nf: moveForm.value.nf || undefined,
      version: moveForm.value.version || undefined,
      domain: moveForm.value.domain || undefined,
      scenario: moveForm.value.scenario || undefined,
    })
    moveVisible.value = false
    ElMessage.success(`已移动到 ${r.new_path}`)
    if (moveTarget.value === activeFile.value && mode.value === 'file') activeFile.value = r.new_path
    refreshTick.value++
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  } finally {
    moving.value = false
  }
}

// ---- 重命名（改 id）----
const renameVisible = ref(false)
const renaming = ref(false)
const renameTarget = ref('')
const renameForm = ref({ new_id: '' })
const renamePreview = ref<{ affected: number; new_path: string } | null>(null)

function openRename(filePath: string): void {
  renameTarget.value = filePath
  const stem = filePath.split('/').pop()?.replace(/\.md$/i, '') ?? ''
  renameForm.value.new_id = stem
  renamePreview.value = null
  renameVisible.value = true
}
async function previewRename(): Promise<void> {
  if (!renameTarget.value || !renameForm.value.new_id) return
  renaming.value = true
  try {
    const r = await renameFsFile({ path: renameTarget.value, new_id: renameForm.value.new_id, dry_run: true })
    renamePreview.value = { affected: r.affected ?? 0, new_path: r.new_path ?? '' }
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  } finally {
    renaming.value = false
  }
}
async function doRename(): Promise<void> {
  if (!renameTarget.value || !renameForm.value.new_id) return
  renaming.value = true
  try {
    const r = await renameFsFile({ path: renameTarget.value, new_id: renameForm.value.new_id, dry_run: false })
    renameVisible.value = false
    ElMessage.success(`已重命名（影响 ${r.affected ?? 0} 个文件的引用）→ ${r.new_path}`)
    if (renameTarget.value === activeFile.value && mode.value === 'file' && r.new_path) activeFile.value = r.new_path
    refreshTick.value++
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  } finally {
    renaming.value = false
  }
}

// ---- 删除 ----
async function onDelete(targetPath: string, isDir = false): Promise<void> {
  if (!targetPath) return
  const msg = isDir
    ? `确定删除文件夹「${targetPath}」及其全部子内容？删除后移入回收站，可还原。`
    : `确定删除「${targetPath}」？删除后移入回收站，可还原。`
  try {
    await ElMessageBox.confirm(msg, '确认删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteFsFile(targetPath)
    ElMessage.success('已移入回收站，可在回收站还原')
    if (targetPath === activeFile.value && mode.value === 'file') {
      mode.value = 'dir'
      activeFile.value = ''
    }
    refreshTick.value++
    ;(window as unknown as { __refreshStats?: () => Promise<void> }).__refreshStats?.()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  }
}

// ---- 批量操作 ----
function onBatch(b: { type: 'delete' | 'move'; paths: string[] }): void {
  if (!b.paths.length) return
  if (b.type === 'delete') void batchDelete(b.paths)
  else openBatchMove(b.paths)
}

async function batchDelete(paths: string[]): Promise<void> {
  const dirCount = paths.filter((p) => !p.toLowerCase().endsWith('.md')).length
  const msg = dirCount > 0
    ? `确定删除选中的 ${paths.length} 项（含 ${dirCount} 个文件夹，将递归删除其全部内容）？删除后移入回收站，可还原。`
    : `确定删除选中的 ${paths.length} 个文件？删除后移入回收站，可还原。`
  try {
    await ElMessageBox.confirm(msg, '批量删除', { type: 'warning' })
  } catch {
    return
  }
  let ok = 0
  let fail = 0
  for (const p of paths) {
    try {
      await deleteFsFile(p)
      ok++
    } catch {
      fail++
    }
  }
  ElMessage.success(`已移入回收站 ${ok} 项${fail ? `，失败 ${fail} 个` : ''}`)
  refreshTick.value++
  ;(window as unknown as { __refreshStats?: () => Promise<void> }).__refreshStats?.()
}

const batchMoveVisible = ref(false)
const batchMoving = ref(false)
const batchTargets = ref<string[]>([])
const batchSkipped = ref(0)
const batchMoveForm = ref({ target_dir: '', nf: '', version: '', domain: '', scenario: '' })

function openBatchMove(paths: string[]): void {
  const mdPaths = paths.filter((p) => p.toLowerCase().endsWith('.md'))
  if (!mdPaths.length) {
    ElMessage.warning('选中的都是文件夹，批量移动仅支持文件')
    return
  }
  batchTargets.value = mdPaths
  batchSkipped.value = paths.length - mdPaths.length
  batchMoveForm.value = { target_dir: cwd.value, nf: '', version: '', domain: '', scenario: '' }
  batchMoveVisible.value = true
}

async function doBatchMove(): Promise<void> {
  const td = batchMoveForm.value.target_dir.trim()
  if (!td || !batchTargets.value.length) return
  batchMoving.value = true
  let ok = 0
  let fail = 0
  try {
    for (const src of batchTargets.value) {
      try {
        await moveFsFile({
          src,
          target_dir: td,
          nf: batchMoveForm.value.nf || undefined,
          version: batchMoveForm.value.version || undefined,
          domain: batchMoveForm.value.domain || undefined,
          scenario: batchMoveForm.value.scenario || undefined,
        })
        ok++
      } catch {
        fail++
      }
    }
    batchMoveVisible.value = false
    ElMessage.success(`已移动 ${ok} 个${fail ? `，失败 ${fail} 个` : ''}`)
    refreshTick.value++
  } finally {
    batchMoving.value = false
  }
}

// ---- 上传到此层（跳 /upload 带 query）----
function uploadHere(targetDir: string): void {
  const parts = targetDir.split('/').filter(Boolean)
  const q: Record<string, string> = {}
  if (parts[0]) q.layer = parts[0]
  if (parts[0] === 'Business') {
    if (parts[1]) q.domain = parts[1]
    if (parts[2]) q.scenario = parts[2]
  } else {
    if (parts[1]) q.nf = parts[1]
    if (parts[2]) q.version = parts[2]
  }
  router.push({ path: '/upload', query: q })
}

// ---- 回收站（软删除；永久清理仅 admin）----
const trashVisible = ref(false)
const trashItems = ref<TrashItem[]>([])
const trashLoading = ref(false)

async function loadTrash(): Promise<void> {
  trashLoading.value = true
  try {
    trashItems.value = await listTrash()
  } catch {
    trashItems.value = []
  } finally {
    trashLoading.value = false
  }
}
async function openTrash(): Promise<void> {
  trashVisible.value = true
  await loadTrash()
}
async function doRestore(id: string): Promise<void> {
  try {
    const r = await restoreTrash(id)
    ElMessage.success(`已还原到 ${r.path}`)
    await loadTrash()
    refreshTick.value++
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  }
}
async function doPurge(id: string): Promise<void> {
  try {
    await ElMessageBox.confirm('永久删除该条目？此操作不可恢复（不再是回收站）。', '彻底删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    await purgeTrash(id)
    ElMessage.success('已永久删除')
    await loadTrash()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  }
}
async function doEmptyTrash(): Promise<void> {
  try {
    await ElMessageBox.confirm('清空回收站将永久删除全部条目，不可恢复。', '清空回收站', { type: 'warning' })
  } catch {
    return
  }
  try {
    const r = await emptyTrash()
    ElMessage.success(`已清空 ${r.purged} 项`)
    await loadTrash()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  }
}
function fmtTs(iso: string): string {
  return iso ? iso.replace('T', ' ').slice(0, 19) : ''
}
</script>

<style scoped>
.fs-view {
  height: 100%;
  min-height: 0;
}

.dialog-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.dialog-body label {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: var(--space-2);
}
.dialog-body .full {
  width: 100%;
}
.dialog-hint {
  font-size: 11.5px;
  color: var(--text-faint);
  background: var(--bg-sunken);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  word-break: break-all;
  margin: 0;
}
.rename-impact {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--accent-soft);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--text-muted);
}
.rename-impact .new-path {
  font-size: 11px;
  color: var(--text-faint);
  word-break: break-all;
}
.rename-impact b {
  color: var(--warn);
}
.move-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-2);
}

/* 回收站 */
.trash-hint {
  padding: var(--space-6);
  text-align: center;
  color: var(--text-faint);
  font-size: 13px;
}
.trash-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 420px;
  overflow: auto;
}
.trash-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-2);
  border-bottom: 1px solid var(--border-faint);
}
.trash-row:last-child {
  border-bottom: none;
}
.trash-icon {
  display: inline-flex;
  color: var(--text-muted);
  flex-shrink: 0;
}
.trash-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.trash-path {
  font-size: 12px;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.trash-meta {
  font-size: 11px;
  color: var(--text-faint);
}
.trash-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
.danger-btn {
  font-family: var(--sans);
  font-size: 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease);
  border: 1px solid var(--border-strong);
  background: var(--bg-elev);
  color: var(--danger);
  padding: 4px 10px;
}
.danger-btn:hover {
  color: #fff;
  background: var(--danger);
  border-color: var(--danger);
}

.ghost-btn,
.primary-btn {
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
.primary-btn {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
.primary-btn:hover {
  background: var(--accent-hover);
}
.primary-btn:disabled,
.ghost-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
