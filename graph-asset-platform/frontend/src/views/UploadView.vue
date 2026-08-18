<template>
  <div class="upload-view">
    <div class="upload-container">
      <header class="page-head">
        <div class="mode-switch">
          <button class="mode-btn" :class="{ active: mode === 'layer' }" @click="mode = 'layer'">指定层上传</button>
          <button class="mode-btn" :class="{ active: mode === 'pdoc' }" @click="mode = 'pdoc'">产品文档导入</button>
        </div>
        <template v-if="mode === 'layer'">
          <h1 class="page-title">指定层上传</h1>
          <p class="page-sub">
            选层 + 网元/版本（Task 层无版本；命令/特性层有版本；业务层为 域/场景）。网元/版本/域/场景
            均可自由输入新值。拖入 md 或 zip，系统自动建目录、以指定位置覆盖 frontmatter 后写入。
          </p>
        </template>
        <template v-else>
          <h1 class="page-title">产品文档导入</h1>
          <p class="page-sub">
            上传产品文档归档（.hwics/.hdx），后台自动解压导出并构建 命令 / 配置对象 / License / 特性
            四类图谱资产；导出的原始 md 留存于「原始产品文档」可浏览，html 中间态自动清理。
            全程异步，提交后看分步进度。
          </p>
        </template>
      </header>

      <!-- ============ 模式一：指定层上传（md/zip） ============ -->
      <template v-if="mode === 'layer'">

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
      </template>

      <!-- ============ 模式二：产品文档导入（.hwics 异步构建） ============ -->
      <section v-else class="card pdoc-card">
        <div class="pdoc-grid">
          <div class="field">
            <label>网元 nf <span class="req">*</span></label>
            <el-input v-model="pdNf" placeholder="如 UDG / UNC" class="full" :disabled="pdBusy" />
            <span v-if="nfHints.length" class="hint mono">现有：{{ nfHints.join(', ') }}</span>
          </div>
          <div class="field">
            <label>版本 version <span class="req">*</span></label>
            <el-input v-model="pdVersion" placeholder="如 20.15.2" class="full" :disabled="pdBusy" />
          </div>
        </div>

        <div
          class="dropzone pdoc-drop"
          :class="{ 'is-drag': pdIsDrag }"
          @dragenter.prevent="pdIsDrag = true"
          @dragover.prevent="pdIsDrag = true"
          @dragleave.prevent="pdIsDrag = false"
          @drop.prevent="onPdDrop"
        >
          <input ref="pdFileInput" type="file" accept=".hwics,.hdx,.zip" class="file-input" @change="onPdFileChange" />
          <div class="dz-content">
            <div class="dz-title">拖拽产品文档归档到此处</div>
            <div class="dz-sub">.hwics / .hdx / .zip，单个文件</div>
            <el-button type="primary" @click="pdFileInput?.click()">选择文件</el-button>
            <div v-if="pdFile" class="dz-file mono">{{ pdFile.name }} · {{ pdSize }}</div>
          </div>
        </div>

        <label class="pd-force">
          <input v-model="pdForce" type="checkbox" :disabled="pdBusy" />
          覆盖重建（同网元+版本已有资产时先清理再全量重建；默认拒绝重复导入）
        </label>

        <div class="actions">
          <button class="primary-btn big" :disabled="!pdCanSubmit || pdBusy || hasRunning" @click="doPdUpload">
            {{ pdBusy || hasRunning ? '构建中…' : '开始导入' }}
          </button>
          <span v-if="hasRunning" class="pd-mutex-hint">同时只允许一个构建任务（完成后自动解锁）</span>
        </div>

        <div v-if="pdErrorMsg" class="error-banner mono">{{ pdErrorMsg }}</div>

        <!-- 分步进度 + 结果 -->
        <div v-if="pdJob" class="pd-job">
          <div class="pd-job-head">
            <span class="pd-job-title">构建任务</span>
            <span class="mono pd-job-id">{{ pdJob.job_id }}</span>
            <span class="pd-status" :class="`pd-${pdJob.status}`">
              {{ pdJob.status === 'processing' ? '进行中' : pdJob.status === 'done' ? '完成' : '失败' }}
            </span>
          </div>
          <ol class="pd-steps">
            <li v-for="s in pdJob.steps" :key="s.name" class="pd-step" :class="`pd-${s.status}`">
              <span class="pd-step-dot">{{ s.status === 'done' ? '✓' : s.status === 'processing' ? '…' : '·' }}</span>
              <span class="pd-step-name">{{ s.name }}</span>
              <span v-if="s.detail" class="pd-step-detail">{{ s.detail }}</span>
            </li>
          </ol>
          <div v-if="pdJob.status === 'done' && resultRows.length" class="stat-grid pd-stats">
            <div v-for="r in resultRows" :key="r.k" class="stat">
              <div class="stat-val">{{ r.v }}</div>
              <div class="stat-label">{{ r.k }}</div>
            </div>
          </div>
          <div v-if="pdJob.status === 'done'" class="pd-done-hint">
            图谱资产已入库 →「图谱资产」浏览；原始 md →「图谱资产」tab 切换「原始产品文档」查看。
          </div>
          <div v-if="pdJob.warnings.length" class="warnings">
            <div class="warn-head">警告 ({{ pdJob.warnings.length }})</div>
            <ul class="warn-list">
              <li v-for="(w, i) in pdJob.warnings" :key="i" class="warn-item mono">{{ w }}</li>
            </ul>
          </div>
          <div v-if="pdJob.status === 'failed'" class="error-banner mono pd-err">{{ pdJob.error }}</div>
        </div>

        <!-- 历史任务（后端持久化，跨刷新/重启；进行中不可删，完成后可删） -->
        <div v-if="pdHistory.length" class="pd-history">
          <div class="pd-history-head">
            <span class="pd-job-title">历史任务</span>
            <span class="hint">点击查看详情；完成/失败可删除，进行中不可</span>
          </div>
          <ul class="pd-hlist">
            <li
              v-for="j in pdHistory"
              :key="j.job_id"
              class="pd-hrow"
              :class="{ cur: pdJob?.job_id === j.job_id }"
              @click="viewJob(j)"
            >
              <span class="pd-status" :class="`pd-${j.status}`">
                {{ j.status === 'processing' ? '进行中' : j.status === 'done' ? '完成' : '失败' }}
              </span>
              <span class="pd-hnf mono">{{ j.nf }} {{ j.version }}</span>
              <span class="pd-htime">{{ fmtJobTime(j.started_at) }}</span>
              <span class="pd-hsteps mono">
                {{ j.steps.filter((s) => s.status === 'done').length }}/{{ j.steps.length || '—' }} 步
              </span>
              <button
                v-if="j.status !== 'processing'"
                class="link-btn pd-del"
                @click.stop="removeJob(j)"
              >删除</button>
              <span v-else class="pd-running-tag mono">构建中…</span>
            </li>
          </ul>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElButton, ElInput, ElSelect, ElOption, ElMessage } from 'element-plus'
import {
  stats,
  uploadToDir,
  uploadProductDoc,
  getImportJob,
  listImportJobs,
  deleteImportJob,
  type FsUploadResult,
  type ImportJob,
  type Stats,
} from '../api'

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
  // 产品文档：拉历史任务；有进行中的 → 恢复进度面板并续接轮询（刷新不丢）
  await loadPdHistory()
  const running = pdHistory.value.find((j) => j.kind === 'product_doc' && j.status === 'processing')
  if (running) {
    pdJob.value = running
    pdBusy.value = true
    pollJob(running.job_id)
  }
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

// ============ 模式二：产品文档导入（.hwics 异步构建） ============

const mode = ref<'layer' | 'pdoc'>('layer')

const pdNf = ref('')
const pdVersion = ref('')
const pdForce = ref(false)
const pdFile = ref<File | null>(null)
const pdIsDrag = ref(false)
const pdFileInput = ref<HTMLInputElement | null>(null)
const pdBusy = ref(false)
const pdJob = ref<ImportJob | null>(null)
const pdErrorMsg = ref('')
let pdTimer: ReturnType<typeof setInterval> | null = null

const pdSize = computed(() =>
  pdFile.value ? `${(pdFile.value.size / 1024 / 1024).toFixed(1)} MB` : '',
)

const pdCanSubmit = computed(
  () => !!pdNf.value.trim() && !!pdVersion.value.trim() && !!pdFile.value,
)

// ---- 历史任务（后端持久化；刷新/重开页面自动恢复进行中的轮询） ----
const pdHistory = ref<ImportJob[]>([])

const hasRunning = computed(
  () =>
    pdJob.value?.status === 'processing' ||
    pdHistory.value.some((j) => j.kind === 'product_doc' && j.status === 'processing'),
)

async function loadPdHistory(): Promise<void> {
  try {
    pdHistory.value = (await listImportJobs()).filter((j) => j.kind === 'product_doc')
  } catch {
    pdHistory.value = []
  }
}

function viewJob(j: ImportJob): void {
  pdJob.value = j
  pdErrorMsg.value = ''
  if (j.status === 'processing') {
    pdBusy.value = true
    pollJob(j.job_id)
  }
}

async function removeJob(j: ImportJob): Promise<void> {
  try {
    await deleteImportJob(j.job_id)
    ElMessage.success(`已删除任务 ${j.job_id}`)
    await loadPdHistory()
    if (pdJob.value?.job_id === j.job_id) pdJob.value = null
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  }
}

function fmtJobTime(ts: number): string {
  return ts ? new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false }) : ''
}

const RESULT_LABELS: Array<[string, string]> = [
  ['commands', '命令'],
  ['config_objects', '配置对象'],
  ['licenses', 'License'],
  ['features', '特性'],
  ['feature_docs', '特性文档'],
  ['export_md', '原始 md'],
]

const resultRows = computed(() => {
  const r = pdJob.value?.result ?? {}
  return RESULT_LABELS.filter(([k]) => r[k] != null).map(([k, label]) => ({
    k: label,
    v: r[k] as number,
  }))
})

function onPdFileChange(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (f) pdFile.value = f
}
function onPdDrop(e: DragEvent) {
  pdIsDrag.value = false
  const f = e.dataTransfer?.files?.[0]
  if (f) pdFile.value = f
}

function stopPolling() {
  if (pdTimer) {
    clearInterval(pdTimer)
    pdTimer = null
  }
}
onBeforeUnmount(stopPolling)

async function pollJob(jobId: string) {
  stopPolling()
  pdTimer = setInterval(async () => {
    try {
      const j = await getImportJob(jobId)
      pdJob.value = j
      if (j.status !== 'processing') {
        stopPolling()
        pdBusy.value = false
        void loadPdHistory() // 终态 → 刷新历史列表
        if (j.status === 'done') {
          ElMessage.success('产品文档构建完成')
          ;(window as unknown as { __refreshStats?: () => Promise<void> }).__refreshStats?.()
        }
      }
    } catch {
      /* 轮询失败容忍一次网络抖动，下轮再试 */
    }
  }, 2000)
}

async function doPdUpload() {
  if (!pdCanSubmit.value || !pdFile.value) return
  pdBusy.value = true
  pdJob.value = null
  pdErrorMsg.value = ''
  try {
    const r = await uploadProductDoc(
      pdNf.value.trim(),
      pdVersion.value.trim(),
      pdForce.value,
      pdFile.value,
    )
    pdFile.value = null
    if (pdFileInput.value) pdFileInput.value.value = ''
    // 立即拉一次，然后轮询；历史列表同步刷新
    pdJob.value = await getImportJob(r.job_id)
    void loadPdHistory()
    pollJob(r.job_id)
  } catch (e: unknown) {
    pdBusy.value = false
    // 409：已有资产（后端 detail = {message, existing}）
    const detail = (e as { detail?: unknown }).detail
    if (detail && typeof detail === 'object' && 'message' in detail) {
      pdErrorMsg.value = String((detail as { message: unknown }).message)
    } else {
      pdErrorMsg.value = e instanceof Error ? e.message : String(e)
    }
  }
}
</script>

<style scoped>
.upload-view { height: 100%; overflow: auto; padding: var(--space-8) var(--space-6); }
.upload-container { max-width: 720px; margin: 0 auto; display: flex; flex-direction: column; gap: var(--space-5); }
.page-head { display: flex; flex-direction: column; gap: var(--space-2); }

.mode-switch { display: inline-flex; gap: 4px; background: var(--bg-sunken); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 3px; width: fit-content; }
.mode-btn { border: none; background: transparent; color: var(--text-muted); font-size: 12.5px; font-weight: 500; padding: 5px 14px; border-radius: var(--radius-sm); cursor: pointer; transition: all var(--dur-fast) var(--ease); }
.mode-btn.active { background: var(--bg-elev); color: var(--accent); box-shadow: var(--shadow-sm); }

.pdoc-card { display: flex; flex-direction: column; gap: var(--space-4); }
.pdoc-grid { display: flex; flex-wrap: wrap; gap: var(--space-3) var(--space-4); }
.pdoc-drop { padding: var(--space-6); }
.dz-file { font-size: 12px; color: var(--accent); margin-top: 4px; }
.pd-force { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--text-muted); cursor: pointer; }
.pd-force input { accent-color: var(--accent); }

.pd-job { border-top: 1px solid var(--border-faint); padding-top: var(--space-4); display: flex; flex-direction: column; gap: var(--space-3); }
.pd-job-head { display: flex; align-items: center; gap: var(--space-3); }
.pd-job-title { font-family: var(--display); font-weight: 600; font-size: 13.5px; }
.pd-job-id { font-size: 11px; color: var(--text-faint); }
.pd-status { font-size: 11px; font-weight: 600; padding: 2px 10px; border-radius: 999px; }
.pd-processing { background: var(--accent-soft); color: var(--accent); }
.pd-done { background: rgba(16, 185, 129, 0.12); color: var(--success); }
.pd-failed { background: #fef2f2; color: var(--danger); }
.pd-steps { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.pd-step { display: flex; align-items: baseline; gap: 8px; font-size: 12.5px; color: var(--text-muted); }
.pd-step.pd-done { color: var(--text); }
.pd-step.pd-processing { color: var(--accent); }
.pd-step-dot { width: 16px; text-align: center; flex-shrink: 0; color: var(--text-faint); }
.pd-step.pd-done .pd-step-dot { color: var(--success); }
.pd-step.pd-processing .pd-step-dot { color: var(--accent); }
.pd-step-detail { font-size: 11px; color: var(--text-faint); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pd-stats { padding: 0; }
.pd-done-hint { font-size: 12px; color: var(--text-muted); background: var(--bg-sunken); border-radius: var(--radius-sm); padding: var(--space-2) var(--space-3); }
.pd-err { white-space: pre-wrap; word-break: break-all; }

.pd-mutex-hint { font-size: 11.5px; color: var(--text-faint); align-self: center; }

.pd-history { border-top: 1px solid var(--border-faint); padding-top: var(--space-4); display: flex; flex-direction: column; gap: var(--space-2); }
.pd-history-head { display: flex; align-items: baseline; gap: var(--space-3); }
.pd-history-head .hint { font-size: 11px; color: var(--text-faint); }
.pd-hlist { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.pd-hrow { display: flex; align-items: center; gap: var(--space-3); padding: 7px 10px; border-bottom: 1px solid var(--border-faint); cursor: pointer; font-size: 12px; transition: background var(--dur-fast) var(--ease); }
.pd-hrow:hover { background: var(--bg-hover); }
.pd-hrow.cur { background: var(--accent-soft); }
.pd-hnf { color: var(--text); min-width: 110px; }
.pd-htime { color: var(--text-faint); font-size: 11px; flex: 1; }
.pd-hsteps { color: var(--text-faint); font-size: 11px; }
.pd-running-tag { color: var(--accent); font-size: 11px; }
.pd-del { flex-shrink: 0; }
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
