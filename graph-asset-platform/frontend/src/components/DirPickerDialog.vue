<template>
  <el-dialog
    :model-value="visible"
    :title="title"
    width="640px"
    @update:model-value="emit('update:visible', $event)"
  >
    <div class="dp-breadcrumb">
      <span class="dp-crumb root" @click="go(-1)">📦 {{ bundleLabel }}</span>
      <template v-for="(seg, i) in segments" :key="i">
        <span class="dp-sep">/</span>
        <span class="dp-crumb" :title="seg" @click="go(i)">{{ seg }}</span>
      </template>
    </div>

    <div class="dp-body" v-loading="loading">
      <div v-if="!loading && !dirEntries.length" class="dp-empty">此层没有子目录</div>
      <ul v-else class="dp-list">
        <li
          v-for="e in dirEntries"
          :key="e.path"
          class="dp-row"
          @click="enter(e)"
        >
          <span class="dp-icon">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
              <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"
                stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" />
            </svg>
          </span>
          <span class="dp-name mono" :title="e.name">{{ e.name }}</span>
          <span class="dp-arrow">进入 ›</span>
        </li>
      </ul>
    </div>

    <template #footer>
      <span class="dp-cur mono" :title="current || '（包根目录）'">当前：{{ current || '（包根目录）' }}</span>
      <button class="dp-ghost" @click="emit('update:visible', false)">取消</button>
      <button class="dp-primary" :disabled="!current" @click="confirmPick">选定此目录</button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/**
 * 包内目录逐层浏览选择器（用户反馈 2026-08-19：候选下拉不够直观，需逐层进入选择）。
 * 数据源 = /docs/children（output 根相对路径）；只展示目录；emit('pick') 返回
 * 相对 bundle 根的正斜杠路径（'' 不允许——至少进一层）。
 */
import { computed, ref, watch } from 'vue'
import { ElDialog } from 'element-plus'
import { listDocsChildren, type FsEntry } from '../api'

const props = defineProps<{
  visible: boolean
  bundleDir: string      // 如 "UDG_20.15.2"（output 根下的一级目录名）
  title: string
}>()
const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'pick', relToBundle: string): void
}>()

const current = ref('')            // 相对 bundle 根
const dirEntries = ref<FsEntry[]>([])
const loading = ref(false)

const bundleLabel = computed(() => props.bundleDir)
const segments = computed(() => (current.value ? current.value.split('/') : []))

async function load(): Promise<void> {
  loading.value = true
  try {
    const path = props.bundleDir + (current.value ? `/${current.value}` : '')
    const entries = await listDocsChildren(path)
    dirEntries.value = entries.filter((e) => e.is_dir)   // 只列目录（md/assets 文件不可作源目录）
  } catch {
    dirEntries.value = []
  } finally {
    loading.value = false
  }
}

watch(
  () => props.visible,
  (v) => {
    if (v) void load()
  },
)

function enter(e: FsEntry) {
  current.value = e.path.slice(props.bundleDir.length + 1)
  void load()
}

function go(i: number) {
  // -1 = 包根；i = 保留 segments[0..i]
  current.value = i < 0 ? '' : segments.value.slice(0, i + 1).join('/')
  void load()
}

function confirmPick() {
  if (!current.value) return
  emit('pick', current.value)
  emit('update:visible', false)
}
</script>

<style scoped>
.dp-breadcrumb { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; padding-bottom: var(--space-3); border-bottom: 1px solid var(--border-faint); }
.dp-crumb { font-size: 12.5px; color: var(--text-muted); cursor: pointer; padding: 2px 6px; border-radius: var(--radius-sm); max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dp-crumb:hover { background: var(--bg-hover); color: var(--accent); }
.dp-crumb.root { font-weight: 600; color: var(--text); }
.dp-sep { color: var(--text-faint); font-size: 12px; }
.dp-body { min-height: 200px; max-height: 380px; overflow: auto; }
.dp-empty { padding: var(--space-8); text-align: center; color: var(--text-faint); font-size: 12.5px; }
.dp-list { list-style: none; margin: 0; padding: 0; }
.dp-row { display: flex; align-items: center; gap: var(--space-2); padding: 7px 8px; border-bottom: 1px solid var(--border-faint); cursor: pointer; font-size: 12.5px; }
.dp-row:hover { background: var(--bg-hover); }
.dp-row:hover .dp-arrow { color: var(--accent); }
.dp-icon { display: inline-flex; color: var(--text-muted); flex-shrink: 0; }
.dp-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text); }
.dp-arrow { font-size: 11px; color: var(--text-faint); flex-shrink: 0; }
.dp-cur { flex: 1; min-width: 0; font-size: 11px; color: var(--text-faint); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-right: var(--space-3); }
.dp-ghost, .dp-primary { font-size: 12.5px; border-radius: var(--radius-sm); cursor: pointer; padding: 5px 14px; border: 1px solid var(--border-strong); background: var(--bg-elev); color: var(--text-muted); }
.dp-ghost:hover { color: var(--accent); border-color: var(--accent); }
.dp-primary { background: var(--accent); border-color: var(--accent); color: #fff; }
.dp-primary:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
