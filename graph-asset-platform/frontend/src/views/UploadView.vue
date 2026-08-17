<template>
  <div class="upload-view">
    <div class="upload-container">
      <header class="page-head">
        <h1 class="page-title">指定层上传</h1>
        <p class="page-sub">
          选层 + 网元/版本（Task 层无版本；命令/特性层有版本；业务层为 域/场景）。网元/版本/域/场景
          均可自由输入新值。拖入 md 或 zip，系统自动建目录、以指定位置覆盖 frontmatter 后写入。
        </p>
      </header>

      <!-- 目标位置 -->
      <section class="card target-card">
        <div class="field">
          <label>层 layer <span class="req">*</span></label>
          <el-select v-model="layer" filterable placeholder="选择层" class="full" @change="onLayerChange">
            <el-option v-for="l in LAYERS" :key="l.name" :label="l.label" :value="l.name" />
          </el-select>
        </div>

        <template v-if="layerKind === 'task'">
          <div class="field">
            <label>网元 nf <span class="req">*</span></label>
            <el-input v-model="nf" placeholder="如 UDG（可输入新网元）" class="full" />
            <span v-if="nfHints.length" class="hint mono">现有：{{ nfHints.join(', ') }}</span>
          </div>
        </template>
        <template v-else-if="layerKind === 'nf'">
          <div class="field">
            <label>网元 nf <span class="req">*</span></label>
            <el-input v-model="nf" placeholder="如 UDG（可输入新网元）" class="full" />
            <span v-if="nfHints.length" class="hint mono">现有：{{ nfHints.join(', ') }}</span>
          </div>
          <div class="field">
            <label>版本 version <span class="req">*</span></label>
            <el-input v-model="version" placeholder="如 20.15.2（可输入新版本）" class="full" />
            <span v-if="versionHints.length" class="hint mono">{{ nf }} 现有版本：{{ versionHints.join(', ') }}</span>
          </div>
        </template>
        <template v-else-if="layerKind === 'cross'">
          <div class="field">
            <label>域 domain <span class="req">*</span></label>
            <el-input v-model="domain" placeholder="如 apn-domain（可输入新城）" class="full" />
            <span v-if="domainHints.length" class="hint mono">现有：{{ domainHints.join(', ') }}</span>
          </div>
          <div class="field">
            <label>场景 scenario（可选）</label>
            <el-input v-model="scenario" placeholder="如 apn-access（可输入新场景）" class="full" />
          </div>
        </template>
        <p v-if="targetPath" class="target-preview mono">→ {{ targetPath }}/<span class="dim">{id}.md</span></p>
      </section>

      <!-- 文件 -->
      <section class="card">
        <div
          class="dropzone"
          :class="{ 'is-drag': isDrag, 'is-target-ready': targetReady }"
          @dragenter.prevent="isDrag = true"
          @dragover.prevent="isDrag = true"
          @dragleave.prevent="isDrag = false"
          @drop.prevent="onDrop"
        >
          <input ref="fileInput" type="file" multiple accept=".md,.zip" class="file-input" @change="onFileChange" />
          <div class="dz-content">
            <div class="dz-title">拖拽 .md / .zip 到此处</div>
            <div class="dz-sub">支持多选；zip 内所有 md 会被展开</div>
            <el-button :disabled="!targetReady" type="primary" @click="pickFile">选择文件</el-button>
            <div v-if="!targetReady" class="dz-hint">请先填好目标位置</div>
          </div>
        </div>

        <div v-if="files.length" class="file-list">
          <div class="fl-head">
            <span>待传 {{ files.length }} 个</span>
            <button class="link-btn" @click="clearFiles">清空</button>
          </div>
          <ul>
            <li v-for="(f, i) in filePreview" :key="i" class="fl-item">
              <span class="fl-name mono" :title="f.name">{{ f.name }}</span>
              <span class="fl-meta mono">{{ f.size }}</span>
            </li>
          </ul>
        </div>
      </section>

      <div v-if="errorMsg" class="error-banner mono">{{ errorMsg }}</div>

      <transition name="slide-up">
        <section v-if="result" class="card result-card">
          <div class="result-head">
            <span class="result-title">上传结果</span>
            <span class="result-target mono">{{ targetPath }}</span>
          </div>
          <div class="stat-grid">
            <div class="stat stat-added"><div class="stat-val">{{ result.added }}</div><div class="stat-label">新增</div></div>
            <div class="stat stat-updated"><div class="stat-val">{{ result.updated }}</div><div class="stat-label">更新</div></div>
            <div class="stat stat-skipped"><div class="stat-val">{{ result.skipped }}</div><div class="stat-label">跳过</div></div>
          </div>
          <div v-if="result.warnings.length" class="warnings">
            <div class="warn-head">警告 ({{ result.warnings.length }})</div>
            <ul class="warn-list">
              <li v-for="(w, i) in result.warnings" :key="i" class="warn-item mono">{{ w }}</li>
            </ul>
          </div>
        </section>
      </transition>

      <div class="actions">
        <button class="primary-btn big" :disabled="!canSubmit || uploading" @click="doUpload">
          {{ uploading ? '上传中…' : `上传到 ${targetPath || '...'}` }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElButton, ElInput, ElSelect, ElOption, ElMessage } from 'element-plus'
import { stats, uploadToDir, type FsUploadResult, type Stats } from '../api'

const route = useRoute()

// 顶层目录 = platform-data/assets 真实目录名；kind 决定字段：task(无版本)/nf(有版本)/cross(域场景)
const LAYERS = [
  { name: 'AtomTask', label: 'AtomTask（原子 Task，无版本）', kind: 'task' as const },
  { name: 'CompoundTask', label: 'CompoundTask（步骤 Task，无版本）', kind: 'task' as const },
  { name: 'FeatureTask', label: 'FeatureTask（特性 Task，无版本）', kind: 'task' as const },
  { name: 'Command', label: 'Command（MML 命令，有版本）', kind: 'nf' as const },
  { name: 'ConfigObject', label: 'ConfigObject（配置对象，有版本）', kind: 'nf' as const },
  { name: 'Feature', label: 'Feature（特性，有版本）', kind: 'nf' as const },
  { name: 'License', label: 'License（有版本）', kind: 'nf' as const },
  { name: 'Business', label: 'Business（业务，域/场景）', kind: 'cross' as const },
]

const layer = ref('')
const nf = ref('')
const version = ref('')
const domain = ref('')
const scenario = ref('')

const layerKind = computed(() => LAYERS.find((l) => l.name === layer.value)?.kind ?? '')

const globalStats = ref<Stats | null>(null)
async function loadStats() {
  try { globalStats.value = await stats() } catch { /* 容错 */ }
}
onMounted(async () => {
  await loadStats()
  // query 预填（从资产目录跳转）
  const q = route.query
  if (q.layer) layer.value = String(q.layer)
  if (q.nf) nf.value = String(q.nf)
  if (q.version) version.value = String(q.version)
  if (q.domain) domain.value = String(q.domain)
  if (q.scenario) scenario.value = String(q.scenario)
})

// 现有值提示（仅提示，不限输入——支持新网元/新版本）
const nfHints = computed(() => globalStats.value?.nfs ?? [])
const versionHints = computed(() => (globalStats.value?.versions_per_nf ?? {})[nf.value] ?? [])
const domainHints = computed(() => Object.keys(globalStats.value?.per_domain ?? {}))

function onLayerChange() {
  nf.value = ''; version.value = ''; domain.value = ''; scenario.value = ''
}

const targetReady = computed(() => {
  if (!layer.value) return false
  if (layerKind.value === 'cross') return !!domain.value
  if (layerKind.value === 'task') return !!nf.value
  return !!nf.value && !!version.value
})

const targetPath = computed(() => {
  if (!layer.value) return ''
  if (layerKind.value === 'cross') {
    return domain.value ? `Business/${domain.value}${scenario.value ? '/' + scenario.value : ''}` : ''
  }
  if (layerKind.value === 'task') {
    return nf.value ? `${layer.value}/${nf.value}` : ''
  }
  return nf.value && version.value ? `${layer.value}/${nf.value}/${version.value}` : ''
})

// ---- 文件 ----
const fileInput = ref<HTMLInputElement | null>(null)
const files = ref<File[]>([])
const isDrag = ref(false)

function pickFile() { fileInput.value?.click() }
function onFileChange(e: Event) {
  const list = (e.target as HTMLInputElement).files
  if (list) files.value = [...files.value, ...Array.from(list)]
}
function onDrop(e: DragEvent) {
  isDrag.value = false
  const list = e.dataTransfer?.files
  if (list) files.value = [...files.value, ...Array.from(list)]
}
function clearFiles() { files.value = []; if (fileInput.value) fileInput.value.value = '' }

const filePreview = computed(() =>
  files.value.map((f) => ({
    name: f.name,
    size: `${(f.size / 1024).toFixed(1)}kb`,
  })),
)

const canSubmit = computed(() => targetReady.value && files.value.length > 0)

// ---- 上传 ----
const uploading = ref(false)
const result = ref<FsUploadResult | null>(null)
const errorMsg = ref('')

async function doUpload() {
  if (!canSubmit.value) return
  uploading.value = true
  result.value = null
  errorMsg.value = ''
  try {
    // overrides 按 kind：task={nf}；nf={nf,version}；cross={domain,scenario}
    const overrides: Record<string, string> = {}
    if (layerKind.value === 'task') {
      overrides.nf = nf.value
    } else if (layerKind.value === 'nf') {
      overrides.nf = nf.value
      overrides.version = version.value
    } else {
      overrides.domain = domain.value
      if (scenario.value) overrides.scenario = scenario.value
    }
    const r = await uploadToDir(targetPath.value, files.value, overrides)
    result.value = r
    ElMessage.success(`新增 ${r.added} / 更新 ${r.updated} / 跳过 ${r.skipped}`)
    clearFiles()
    ;(window as unknown as { __refreshStats?: () => Promise<void> }).__refreshStats?.()
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : String(e)
  } finally {
    uploading.value = false
  }
}
</script>

<style scoped>
.upload-view { height: 100%; overflow: auto; padding: var(--space-8) var(--space-6); }
.upload-container { max-width: 720px; margin: 0 auto; display: flex; flex-direction: column; gap: var(--space-5); }
.page-head { display: flex; flex-direction: column; gap: var(--space-2); }
.page-title { font-family: var(--display); font-size: 24px; font-weight: 700; color: var(--text); margin: 0; letter-spacing: -0.02em; }
.page-sub { margin: 0; color: var(--text-muted); font-size: 12.5px; line-height: 1.55; max-width: 600px; }

.card { background: var(--bg-elev); border: 1px solid var(--border); border-radius: var(--radius); padding: var(--space-4) var(--space-5); box-shadow: var(--shadow-sm); }
.target-card { display: flex; flex-wrap: wrap; gap: var(--space-3) var(--space-4); }
.field { display: flex; flex-direction: column; gap: 4px; flex: 1; min-width: 160px; }
.field label { font-size: 11.5px; color: var(--text-muted); font-weight: 500; }
.req { color: var(--danger); }
.full { width: 100%; }
.hint { font-size: 10.5px; color: var(--text-faint); margin-top: 2px; }
.target-preview { width: 100%; font-size: 12px; color: var(--accent); background: var(--accent-soft); padding: var(--space-2) var(--space-3); border-radius: var(--radius-sm); margin-top: var(--space-1); }
.target-preview .dim { color: var(--text-faint); }

.dropzone { border: 1.5px dashed var(--border-strong); border-radius: var(--radius); background: var(--bg-sunken); padding: var(--space-8); display: flex; align-items: center; justify-content: center; transition: all var(--dur) var(--ease); }
.dropzone.is-drag { border-color: var(--accent); background: var(--accent-soft); }
.dropzone.is-target-ready { border-color: var(--accent); }
.file-input { display: none; }
.dz-content { display: flex; flex-direction: column; align-items: center; gap: var(--space-2); text-align: center; }
.dz-title { font-family: var(--display); font-size: 14px; font-weight: 600; color: var(--text); }
.dz-sub { font-size: 12px; color: var(--text-faint); }
.dz-hint { font-size: 11px; color: var(--warn); margin-top: 4px; }

.file-list { margin-top: var(--space-3); }
.fl-head { display: flex; align-items: center; justify-content: space-between; font-size: 12px; color: var(--text-muted); margin-bottom: var(--space-2); }
.fl-item { display: grid; grid-template-columns: 1fr auto; gap: var(--space-3); align-items: center; padding: 6px 10px; border-bottom: 1px solid var(--border-faint); font-size: 12px; }
.fl-name { color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.fl-meta { color: var(--text-faint); font-size: 11px; }

.error-banner { background: #fef2f2; border: 1px solid #fecaca; color: var(--danger); padding: var(--space-3) var(--space-4); border-radius: var(--radius-sm); font-size: 12.5px; }

.result-card { padding: 0; overflow: hidden; }
.result-head { display: flex; align-items: baseline; justify-content: space-between; padding: var(--space-3) var(--space-5); border-bottom: 1px solid var(--border-faint); }
.result-title { font-family: var(--display); font-weight: 600; font-size: 14px; }
.result-target { font-size: 11.5px; color: var(--text-muted); }
.stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); padding: var(--space-4) var(--space-5); gap: var(--space-4); }
.stat { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.stat-val { font-family: var(--display); font-size: 28px; font-weight: 700; line-height: 1; }
.stat-added .stat-val { color: var(--success); }
.stat-updated .stat-val { color: var(--accent); }
.stat-skipped .stat-val { color: var(--text-faint); }
.stat-label { font-size: 11.5px; color: var(--text-muted); }
.warnings { border-top: 1px solid var(--border-faint); padding: var(--space-3) var(--space-5); }
.warn-head { font-size: 12px; font-weight: 600; color: var(--warn); margin-bottom: var(--space-2); }
.warn-list { list-style: none; margin: 0; padding: 0; max-height: 160px; overflow: auto; display: flex; flex-direction: column; gap: 4px; }
.warn-item { font-size: 11px; color: var(--text-muted); background: var(--bg-sunken); padding: var(--space-2) var(--space-3); border-radius: var(--radius-sm); }

.actions { display: flex; justify-content: flex-end; }
.primary-btn { font-family: var(--sans); font-size: 13px; border-radius: var(--radius-sm); cursor: pointer; background: var(--accent); border: 1px solid var(--accent); color: #fff; padding: 6px 16px; transition: all var(--dur-fast) var(--ease); }
.primary-btn:hover:not(:disabled) { background: var(--accent-hover); }
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.primary-btn.big { padding: 9px 24px; font-size: 14px; }
.link-btn { background: none; border: none; color: var(--accent); font-size: 11.5px; cursor: pointer; padding: 0; }

.slide-up-enter-active { transition: all var(--dur) var(--ease); }
.slide-up-enter-from { opacity: 0; transform: translateY(8px); }
</style>
