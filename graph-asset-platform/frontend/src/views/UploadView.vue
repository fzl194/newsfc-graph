<template>
  <div class="upload-view">
    <div class="upload-container">
      <header class="page-head">
        <div class="mode-switch">
          <button class="mode-btn" :class="{ active: mode === 'layer' }" @click="mode = 'layer'">指定层上传</button>
          <button class="mode-btn" :class="{ active: mode === 'extract' }" @click="mode = 'extract'">产品文档解压</button>
          <button class="mode-btn" :class="{ active: mode === 'mine' }" @click="mode = 'mine'">自动抽取</button>
        </div>
        <template v-if="mode === 'layer'">
          <h1 class="page-title">指定层上传</h1>
          <p class="page-sub">
            选层 + 网元/版本（Task 层无版本；命令/特性层有版本；业务层为 域/场景）。网元/版本/域/场景
            均可自由输入新值。拖入 md 或 zip，系统自动建目录、以指定位置覆盖 frontmatter 后写入。
          </p>
        </template>
        <template v-else-if="mode === 'extract'">
          <h1 class="page-title">产品文档解压</h1>
          <p class="page-sub">
            上传产品文档归档（.hwics/.hdx）→ 后台异步解压转换为 md 留存（只留最终 md + 元信息，
            html 中间态自动清理；同网元+版本重复上传自动覆盖旧包）。构建图谱走「自动抽取」。
          </p>
        </template>
        <template v-else>
          <h1 class="page-title">自动抽取</h1>
          <p class="page-sub">
            选择已解压的产品文档包 → 确认源目录（自动推荐，可改选）→ 勾选抽取范围（默认全选，
            依赖层资产缺失时自动补齐锁定）→ 选择解析模式 → 确认抽取。同一时间仅一个挖掘任务。
          </p>
        </template>
      </header>

      <!-- ============ 模式一：指定层上传（md/zip） ============ -->
      <template v-if="mode === 'layer'">
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

      <!-- ============ 模式二：产品文档解压（步骤①，只解压转换留存） ============ -->
      <section v-else-if="mode === 'extract'" class="card pdoc-card">
        <div class="pdoc-grid">
          <div class="field">
            <label>网元 nf <span class="req">*</span></label>
            <el-input v-model="exNf" placeholder="如 UDG / UNC" class="full" :disabled="exBusy" />
            <span v-if="nfHints.length" class="hint mono">现有：{{ nfHints.join(', ') }}</span>
          </div>
          <div class="field">
            <label>版本 version <span class="req">*</span></label>
            <el-input v-model="exVersion" placeholder="如 20.15.2（需与归档内版本一致）" class="full" :disabled="exBusy" />
          </div>
        </div>

        <div
          class="dropzone pdoc-drop"
          :class="{ 'is-drag': exIsDrag }"
          @dragenter.prevent="exIsDrag = true"
          @dragover.prevent="exIsDrag = true"
          @dragleave.prevent="exIsDrag = false"
          @drop.prevent="onExDrop"
        >
          <input ref="exFileInput" type="file" accept=".hwics,.hdx,.zip" class="file-input" @change="onExFileChange" />
          <div class="dz-content">
            <div class="dz-title">拖拽产品文档归档到此处</div>
            <div class="dz-sub">.hwics / .hdx / .zip，单个文件，≤2GB；重复上传同网元+版本自动覆盖</div>
            <el-button type="primary" @click="exFileInput?.click()">选择文件</el-button>
            <div v-if="exFile" class="dz-file mono">{{ exFile.name }} · {{ fmtSize(exFile.size) }}</div>
          </div>
        </div>

        <div class="actions">
          <button class="primary-btn big" :disabled="!exCanSubmit || exBusy || hasRunning('product_doc_extract')" @click="doExtract">
            {{ exBusy || hasRunning('product_doc_extract') ? '解压中…' : '开始解压' }}
          </button>
        </div>

        <div v-if="exErrorMsg" class="error-banner mono">{{ exErrorMsg }}</div>
        <JobPanel
          :job="exJob"
          :stats-labels="[{ k: 'md_count', label: 'md' }, { k: 'convert_failed', label: '转换失败' }]"
          done-hint="解压完成 → 切「自动抽取」构建图谱；原始 md 在「图谱资产」页签切换查看"
          @refresh-history="loadHistory"
        />
        <JobHistory
          :jobs="historyFor('product_doc_extract')"
          :active-id="exJob?.job_id"
          @view="(j) => viewJob(j, 'extract')"
          @remove="removeJob"
        />
      </section>

      <!-- ============ 模式三：自动抽取（步骤②，从已解压包挖掘） ============ -->
      <template v-else>
        <!-- ① 包列表 -->
        <section class="card mine-card">
          <div class="mine-head">
            <span class="mine-title">已解压的产品文档包</span>
            <button class="ghost-btn2" @click="loadBundles">刷新</button>
          </div>
          <div v-if="bundlesLoading" class="hint">加载中…</div>
          <div v-else-if="!bundleList.length" class="hint empty">
            暂无已解压包——先到「产品文档解压」上传归档
          </div>
          <ul v-else class="bundle-list">
            <li
              v-for="b in bundleList"
              :key="b.dir"
              class="bundle-row"
              :class="{ cur: sel?.dir === b.dir, dim: b.status !== 'done' }"
              @click="selectBundle(b)"
            >
              <span class="b-nf mono">{{ b.nf }} {{ b.version }}</span>
              <span class="b-meta">{{ b.legacy ? '旧格式' : (b.uploaded_at || '').slice(0, 19).replace('T', ' ') }}</span>
              <span class="b-meta mono">md {{ b.md_count ?? '?' }}</span>
              <span v-if="b.convert_failed" class="b-warn mono">转换失败 {{ b.convert_failed }}</span>
              <span class="b-assets mono">
                <template v-for="(v, layer) in b.assets" :key="layer">
                  <span :class="v ? 'has' : 'none'">{{ layer[0] }}</span>
                </template>
              </span>
              <span v-if="b.mode_id" class="b-meta mono">最近:{{ b.mode_id }}</span>
            </li>
          </ul>
        </section>

        <!-- ② 抽取配置 -->
        <section v-if="sel" class="card mine-card">
          <div class="mine-head">
            <span class="mine-title">抽取配置 · {{ sel.nf }} {{ sel.version }}</span>
            <button class="ghost-btn2" @click="refreshLocate">重新定位</button>
          </div>

          <div v-if="locating" class="hint">定位中…</div>
          <template v-else-if="locate">
            <div v-for="(role, key) in locate" :key="key" class="field loc-field">
              <label>
                {{ ROLE_LABEL[key as string] || key }} 源目录 <span class="req">*</span>
                <span v-if="role.note" class="loc-note">⚠ {{ role.note }}</span>
              </label>
              <el-select
                v-model="dirs[key as string]"
                filterable
                placeholder="选择目录"
                class="full"
              >
                <el-option
                  v-for="c in role.candidates"
                  :key="c"
                  :label="c + (c === role.recommended ? '（推荐）' : '')"
                  :value="c"
                />
              </el-select>
            </div>
          </template>

          <div class="pdoc-grid mine-grid">
            <div class="field">
              <label>解析模式 <span class="req">*</span></label>
              <el-select v-model="modeSel" class="full">
                <el-option v-for="m in modeOptions" :key="m.id" :label="m.name" :value="m.id" />
              </el-select>
              <span class="hint">模式与网元由你匹配；新脚本注册后此处自动出现</span>
            </div>
            <div class="field">
              <label>抽取范围（默认全选；⚠ 锁定=依赖层资产缺失，必须抽取）</label>
              <div class="scope-row">
                <label
                  v-for="l in SCOPE_LAYERS"
                  :key="l"
                  class="scope-item"
                  :class="{ locked: isLocked(l) }"
                  :title="isLocked(l) ? '被勾选层依赖且该层资产不存在，已自动补选锁定' : ''"
                >
                  <input
                    type="checkbox"
                    :checked="scope[l]"
                    :disabled="isLocked(l) || mineBusy"
                    @change="toggleScope(l, ($event.target as HTMLInputElement).checked)"
                  />
                  {{ l }}
                </label>
              </div>
            </div>
          </div>

          <label v-if="hasExistingAssets" class="pd-force">
            <input v-model="mineForce" type="checkbox" :disabled="mineBusy" />
            覆盖重建（清空勾选层的旧资产后全量重建；同网元+版本已检测到现有资产）
          </label>

          <div class="actions">
            <button
              class="primary-btn big"
              :disabled="!mineCanSubmit || mineBusy || hasRunning('product_doc_mine')"
              @click="doMine"
            >
              {{ mineBusy || hasRunning('product_doc_mine') ? '挖掘中…' : `确认抽取（${finalScope.length} 层）` }}
            </button>
          </div>
          <div v-if="mineErrorMsg" class="error-banner mono">{{ mineErrorMsg }}</div>
        </section>

        <JobPanel
          :job="mineJob"
          :stats-labels="MINE_STAT_LABELS"
          done-hint="图谱资产已入库 →「图谱浏览」查看；边/引用基线见《图谱边定义.md》"
          @refresh-history="loadHistory"
        />
        <JobHistory
          :jobs="historyFor('product_doc_mine')"
          :active-id="mineJob?.job_id"
          @view="(j) => viewJob(j, 'mine')"
          @remove="removeJob"
        />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElButton, ElInput, ElSelect, ElOption, ElMessage } from 'element-plus'
import {
  stats,
  uploadToDir,
  uploadProductDoc,
  listBundles,
  listModes,
  locateBundle,
  startMine,
  getImportJob,
  listImportJobs,
  deleteImportJob,
  type FsUploadResult,
  type ImportJob,
  type DocBundle,
  type ModeOption,
  type LocateResult,
  type Stats,
} from '../api'
import JobPanel from '../components/JobPanel.vue'
import JobHistory from '../components/JobHistory.vue'

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

const mode = ref<'layer' | 'extract' | 'mine'>('layer')

// ============ 模式一：指定层上传（原逻辑不变） ============
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
  const q = route.query
  if (q.layer) layer.value = String(q.layer)
  if (q.nf) nf.value = String(q.nf)
  if (q.version) version.value = String(q.version)
  if (q.domain) domain.value = String(q.domain)
  if (q.scenario) scenario.value = String(q.scenario)
  await loadHistory()
  // 有进行中的任务 → 恢复对应模式进度轮询（刷新不丢）
  const runningExtract = history.value.find((j) => j.kind === 'product_doc_extract' && j.status === 'processing')
  if (runningExtract) { exJob.value = runningExtract; exBusy.value = true; pollJob(runningExtract.job_id, 'extract') }
  const runningMine = history.value.find((j) => j.kind === 'product_doc_mine' && j.status === 'processing')
  if (runningMine) { mineJob.value = runningMine; mineBusy.value = true; pollJob(runningMine.job_id, 'mine') }
})

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
  files.value.map((f) => ({ name: f.name, size: `${(f.size / 1024).toFixed(1)}kb` })),
)

const canSubmit = computed(() => targetReady.value && files.value.length > 0)

const uploading = ref(false)
const result = ref<FsUploadResult | null>(null)
const errorMsg = ref('')

async function doUpload() {
  if (!canSubmit.value) return
  uploading.value = true
  result.value = null
  errorMsg.value = ''
  try {
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

// ============ 任务面板共用（解压/挖掘两模式） ============

const history = ref<ImportJob[]>([])
async function loadHistory(): Promise<void> {
  try { history.value = await listImportJobs() } catch { history.value = [] }
}
function historyFor(kind: 'product_doc_extract' | 'product_doc_mine'): ImportJob[] {
  return history.value.filter((j) => j.kind === kind)
}
function hasRunning(kind: 'product_doc_extract' | 'product_doc_mine'): boolean {
  return history.value.some((j) => j.kind === kind && j.status === 'processing')
}
async function removeJob(j: ImportJob): Promise<void> {
  try {
    await deleteImportJob(j.job_id)
    ElMessage.success(`已删除任务 ${j.job_id}`)
    await loadHistory()
    if (exJob.value?.job_id === j.job_id) exJob.value = null
    if (mineJob.value?.job_id === j.job_id) mineJob.value = null
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  }
}

function fmtSize(n: number): string {
  if (n > 1024 * 1024 * 1024) return `${(n / 1024 / 1024 / 1024).toFixed(1)} GB`
  if (n > 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`
  return `${(n / 1024).toFixed(0)} KB`
}

// 通用轮询（D13：连续 5 次失败或 404 即终态，不再无限重试）
type PollKind = 'extract' | 'mine'
const pollFailCount: Record<PollKind, number> = { extract: 0, mine: 0 }
let pollTimer: ReturnType<typeof setInterval> | null = null

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}
onBeforeUnmount(stopPolling)
watch(mode, () => stopPolling()) // 切模式即停当前轮询（历史可点回恢复）

function pollJob(jobId: string, kind: PollKind) {
  stopPolling()
  pollFailCount[kind] = 0
  pollTimer = setInterval(async () => {
    try {
      const j = await getImportJob(jobId)
      pollFailCount[kind] = 0
      if (kind === 'extract') exJob.value = j
      else mineJob.value = j
      if (j.status !== 'processing') {
        stopPolling()
        if (kind === 'extract') exBusy.value = false
        else mineBusy.value = false
        void loadHistory()
        if (j.status === 'done') {
          ElMessage.success(kind === 'extract' ? '解压完成' : '图谱抽取完成')
          ;(window as unknown as { __refreshStats?: () => Promise<void> }).__refreshStats?.()
          if (kind === 'mine') void loadBundles() // 刷新资产存在标志
        }
      }
    } catch (e) {
      const status = (e as { status?: number }).status
      pollFailCount[kind] += 1
      if (status === 404 || pollFailCount[kind] >= 5) {
        stopPolling()
        if (kind === 'extract') exBusy.value = false
        else mineBusy.value = false
        ElMessage.warning('任务状态查询失败（后端可能已重启），请刷新页面或查看历史')
      }
    }
  }, 2000)
}

function viewJob(j: ImportJob, kind: PollKind) {
  if (kind === 'extract') { exJob.value = j; exErrorMsg.value = '' }
  else { mineJob.value = j; mineErrorMsg.value = '' }
  if (j.status === 'processing') {
    if (kind === 'extract') exBusy.value = true
    else mineBusy.value = true
    pollJob(j.job_id, kind)
  }
}

// ============ 模式二：产品文档解压（步骤①） ============

const exNf = ref('')
const exVersion = ref('')
const exFile = ref<File | null>(null)
const exIsDrag = ref(false)
const exFileInput = ref<HTMLInputElement | null>(null)
const exBusy = ref(false)
const exJob = ref<ImportJob | null>(null)
const exErrorMsg = ref('')

const exCanSubmit = computed(
  () => !!exNf.value.trim() && !!exVersion.value.trim() && !!exFile.value,
)

function onExFileChange(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (f) exFile.value = f
}
function onExDrop(e: DragEvent) {
  exIsDrag.value = false
  const f = e.dataTransfer?.files?.[0]
  if (f) exFile.value = f
}

async function doExtract() {
  if (!exCanSubmit.value || !exFile.value) return
  exBusy.value = true
  exJob.value = null
  exErrorMsg.value = ''
  try {
    const r = await uploadProductDoc(exNf.value.trim(), exVersion.value.trim(), exFile.value)
    exFile.value = null
    if (exFileInput.value) exFileInput.value.value = ''
    exJob.value = await getImportJob(r.job_id)
    void loadHistory()
    pollJob(r.job_id, 'extract')
  } catch (e: unknown) {
    exBusy.value = false
    const detail = (e as { detail?: unknown }).detail
    if (detail && typeof detail === 'object' && 'message' in detail) {
      exErrorMsg.value = String((detail as { message: unknown }).message)
    } else {
      exErrorMsg.value = e instanceof Error ? e.message : String(e)
    }
  }
}

// ============ 模式三：自动抽取（步骤②） ============

const ROLE_LABEL: Record<string, string> = { mml: '命令', feature: '特性', license: 'License' }
const SCOPE_LAYERS = ['Command', 'ConfigObject', 'License', 'Feature'] as const
type ScopeLayer = (typeof SCOPE_LAYERS)[number]
// 依赖声明（与后端模式注册表一致；用于前端锁定 UI）
const NEEDS: Record<string, string[]> = {
  ConfigObject: ['Command'],
  Feature: ['Command', 'License'],
}

const bundleList = ref<DocBundle[]>([])
const bundlesLoading = ref(false)
const sel = ref<DocBundle | null>(null)
const locating = ref(false)
const locate = ref<LocateResult | null>(null)
const dirs = ref<Record<string, string>>({})
const modeOptions = ref<ModeOption[]>([])
const modeSel = ref('5gc')
const scope = reactive<Record<ScopeLayer, boolean>>({
  Command: true, ConfigObject: true, License: true, Feature: true,
})
const mineForce = ref(false)
const mineBusy = ref(false)
const mineJob = ref<ImportJob | null>(null)
const mineErrorMsg = ref('')

const MINE_STAT_LABELS = [
  { k: 'total', label: '总计' },
  { k: 'Command', label: '命令' },
  { k: 'ConfigObject', label: '配置对象' },
  { k: 'License', label: 'License' },
  { k: 'Feature', label: '特性' },
]

async function loadBundles(): Promise<void> {
  bundlesLoading.value = true
  try {
    bundleList.value = (await listBundles()).filter((b) => b.status === 'done')
    // 当前选中包若被覆盖更新 → 同步刷新
    if (sel.value) {
      const again = bundleList.value.find((b) => b.dir === sel.value!.dir)
      sel.value = again ?? null
    }
  } catch {
    bundleList.value = []
  } finally {
    bundlesLoading.value = false
  }
}

async function loadModeOptions(): Promise<void> {
  try { modeOptions.value = await listModes() } catch { modeOptions.value = [] }
}

async function selectBundle(b: DocBundle): Promise<void> {
  if (b.status !== 'done') return
  sel.value = b
  await refreshLocate()
}

async function refreshLocate(): Promise<void> {
  if (!sel.value) return
  locating.value = true
  locate.value = null
  try {
    locate.value = await locateBundle(sel.value.nf, sel.value.version, modeSel.value)
    const next: Record<string, string> = {}
    for (const [role, r] of Object.entries(locate.value)) {
      next[role] = r.recommended ?? r.candidates[0] ?? ''
    }
    dirs.value = next
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  } finally {
    locating.value = false
  }
}

// 依赖强制（与后端 expand_scope 同规则）：勾选层依赖的层若资产不存在 → 自动勾上并锁定
function enforceScope(): void {
  for (const l of SCOPE_LAYERS) {
    if (!scope[l]) continue
    for (const dep of NEEDS[l] ?? []) {
      if (!sel.value?.assets[dep]) {
        scope[dep as ScopeLayer] = true
      }
    }
  }
}
watch(scope, enforceScope, { deep: true })
watch(() => sel.value, enforceScope)

function isLocked(l: string): boolean {
  if (!sel.value) return false
  for (const layer of SCOPE_LAYERS) {
    if (layer === l || !scope[layer]) continue
    for (const dep of NEEDS[layer] ?? []) {
      if (dep === l && !sel.value.assets[l]) return true
    }
  }
  return false
}

function toggleScope(l: ScopeLayer, checked: boolean) {
  if (isLocked(l)) return
  scope[l] = checked
}

const finalScope = computed(() => SCOPE_LAYERS.filter((l) => scope[l]))
const hasExistingAssets = computed(() =>
  !!sel.value && finalScope.value.some((l) => sel.value!.assets[l]))

const mineCanSubmit = computed(() => {
  if (!sel.value || !finalScope.value.length) return false
  // 三个源目录角色至少 mml/feature 被 Build 使用时不强制——由后端校验缺失参数；
  // 前端宽松放行（后端 run 校验 dirs 完整性），仅要求定位已加载
  return !!locate.value
})

async function doMine(): Promise<void> {
  if (!mineCanSubmit.value || !sel.value) return
  mineBusy.value = true
  mineJob.value = null
  mineErrorMsg.value = ''
  try {
    const r = await startMine({
      nf: sel.value.nf,
      version: sel.value.version,
      mode: modeSel.value,
      dirs: { ...dirs.value },
      scope: [...finalScope.value],
      force: mineForce.value,
    })
    mineJob.value = await getImportJob(r.job_id)
    void loadHistory()
    pollJob(r.job_id, 'mine')
  } catch (e: unknown) {
    mineBusy.value = false
    const detail = (e as { detail?: unknown }).detail
    if (detail && typeof detail === 'object' && 'message' in detail) {
      mineErrorMsg.value = String((detail as { message: unknown }).message)
    } else {
      mineErrorMsg.value = e instanceof Error ? e.message : String(e)
    }
  }
}

watch(mode, async (m) => {
  if (m === 'mine') {
    await Promise.all([loadBundles(), loadModeOptions()])
  }
}, { immediate: false })
</script>

<style scoped>
.upload-view { height: 100%; overflow: auto; padding: var(--space-8) var(--space-6); }
.upload-container { max-width: 760px; margin: 0 auto; display: flex; flex-direction: column; gap: var(--space-5); }
.page-head { display: flex; flex-direction: column; gap: var(--space-2); }

.mode-switch { display: inline-flex; gap: 4px; background: var(--bg-sunken); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 3px; width: fit-content; }
.mode-btn { border: none; background: transparent; color: var(--text-muted); font-size: 12.5px; font-weight: 500; padding: 5px 14px; border-radius: var(--radius-sm); cursor: pointer; transition: all var(--dur-fast) var(--ease); }
.mode-btn.active { background: var(--bg-elev); color: var(--accent); box-shadow: var(--shadow-sm); }

.page-title { font-family: var(--display); font-size: 24px; font-weight: 700; color: var(--text); margin: 0; letter-spacing: -0.02em; }
.page-sub { margin: 0; color: var(--text-muted); font-size: 12.5px; line-height: 1.55; max-width: 640px; }

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
.dz-file { font-size: 12px; color: var(--accent); margin-top: 4px; }

.file-list { margin-top: var(--space-3); }
.fl-head { display: flex; align-items: center; justify-content: space-between; font-size: 12px; color: var(--text-muted); margin-bottom: var(--space-2); }
.fl-item { display: grid; grid-template-columns: 1fr auto; gap: var(--space-3); align-items: center; padding: 6px 10px; border-bottom: 1px solid var(--border-faint); font-size: 12px; }
.fl-name { color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.fl-meta { color: var(--text-faint); font-size: 11px; }

.error-banner { background: #fef2f2; border: 1px solid #fecaca; color: var(--danger); padding: var(--space-3) var(--space-4); border-radius: var(--radius-sm); font-size: 12.5px; white-space: pre-wrap; word-break: break-all; }

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

.actions { display: flex; gap: var(--space-3); align-items: center; }
.primary-btn { font-family: var(--sans); font-size: 13px; border-radius: var(--radius-sm); cursor: pointer; background: var(--accent); border: 1px solid var(--accent); color: #fff; padding: 6px 16px; transition: all var(--dur-fast) var(--ease); }
.primary-btn:hover:not(:disabled) { background: var(--accent-hover); }
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.primary-btn.big { padding: 9px 24px; font-size: 14px; }
.link-btn { background: none; border: none; color: var(--accent); font-size: 11.5px; cursor: pointer; padding: 0; }

.slide-up-enter-active { transition: all var(--dur) var(--ease); }
.slide-up-enter-from { opacity: 0; transform: translateY(8px); }

/* ---- 产品文档解压 / 自动抽取 ---- */
.pdoc-card, .mine-card { display: flex; flex-direction: column; gap: var(--space-4); }
.pdoc-grid { display: flex; flex-wrap: wrap; gap: var(--space-3) var(--space-4); }
.pdoc-drop { padding: var(--space-6); }
.pd-force { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--text-muted); cursor: pointer; }
.pd-force input { accent-color: var(--accent); }
.mine-head { display: flex; align-items: center; justify-content: space-between; }
.mine-title { font-family: var(--display); font-weight: 600; font-size: 13.5px; }
.ghost-btn2 { font-size: 12px; border: 1px solid var(--border-strong); background: var(--bg-elev); color: var(--text-muted); border-radius: var(--radius-sm); padding: 3px 10px; cursor: pointer; }
.ghost-btn2:hover { color: var(--accent); border-color: var(--accent); }
.mine-card .hint { padding: var(--space-4); text-align: center; font-size: 12.5px; }
.bundle-list { list-style: none; margin: 0; padding: 0; }
.bundle-row { display: flex; align-items: center; gap: var(--space-3); padding: 8px 10px; border-bottom: 1px solid var(--border-faint); cursor: pointer; font-size: 12.5px; transition: background var(--dur-fast) var(--ease); }
.bundle-row:hover { background: var(--bg-hover); }
.bundle-row.cur { background: var(--accent-soft); }
.bundle-row.dim { opacity: 0.55; }
.b-nf { color: var(--text); min-width: 120px; font-weight: 600; }
.b-meta { color: var(--text-faint); font-size: 11px; }
.b-warn { color: var(--warn); font-size: 11px; }
.b-assets { margin-left: auto; display: inline-flex; gap: 3px; font-size: 10.5px; }
.b-assets .has { color: var(--success); border: 1px solid var(--success); border-radius: 4px; padding: 0 4px; }
.b-assets .none { color: var(--text-faint); border: 1px solid var(--border); border-radius: 4px; padding: 0 4px; }
.loc-field { min-width: 100%; }
.loc-note { color: var(--warn); font-size: 10.5px; font-weight: 400; margin-left: 6px; }
.mine-grid { border-top: 1px solid var(--border-faint); padding-top: var(--space-4); }
.scope-row { display: flex; flex-wrap: wrap; gap: var(--space-2) var(--space-4); padding: 4px 0; }
.scope-item { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; color: var(--text); cursor: pointer; }
.scope-item input { accent-color: var(--accent); }
.scope-item.locked { color: var(--accent); cursor: not-allowed; }
.scope-item.locked input { cursor: not-allowed; }
</style>
