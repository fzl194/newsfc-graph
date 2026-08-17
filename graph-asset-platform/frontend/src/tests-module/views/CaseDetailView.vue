<template>
  <div class="compare-page">
    <div class="topbar">
      <span class="back" @click="back">← 返回</span>
      <div class="title-block" v-if="c">
        <span class="case-title">{{ c.name || c.id }}</span>
        <span class="tag">{{ c.domain || '未分类' }}</span>
        <span v-if="c.scenario" class="tag tag-scene">{{ c.scenario }}</span>
      </div>
      <div class="top-actions" v-if="c">
        <button class="tb-btn" @click="showUploadPanel = !showUploadPanel">↑ 上传运行</button>
        <button class="tb-btn" @click="downloadCase">打包下载</button>
        <button class="tb-btn" @click="toggleCollapse">{{ runCollapsed ? '展开运行' : '缩起运行' }}</button>
      </div>
    </div>

    <!-- 上传运行面板 -->
    <div v-if="showUploadPanel && c" class="upload-panel">
      <div class="up-row">
        <el-input v-model="uploadName" placeholder="运行名称（可读，如 第一次跑-缺URRGROUP）" class="up-input" />
        <el-input v-model="uploadRunner" placeholder="runner（如 agent:cg@2.0 或 SA-zhang）" class="up-input" />
      </div>
      <div class="up-row">
        <input ref="runFileEl" type="file" accept=".zip" class="file-input" @change="onUploadRun" />
        <span class="up-hint">zip 内直接放运行产出文件（可含子目录）</span>
      </div>
    </div>

    <div v-if="err" class="err">{{ err }}</div>

    <div v-loading="loading" class="compare-body">
      <div v-if="c" class="compare-flex" :class="{ collapsed: runCollapsed }">
        <!-- 左：用例 -->
        <section class="pane pane-case">
          <div class="card">
            <h2 class="sec-title">输入（业务诉求）</h2>
            <div class="md-body" v-html="renderMd(c.body_md)" />
          </div>
          <div v-for="g in fileGroups" :key="g.label" class="card">
            <h2 class="sec-title">{{ g.label }} <span class="count">{{ g.items.length }}</span></h2>
            <FilePreview v-for="f in g.items" :key="f" :case-id="c.id" :name="f" />
          </div>
        </section>

        <!-- 右：运行（可缩起） -->
        <section v-if="!runCollapsed" class="pane pane-run">
          <div class="run-toolbar">
            <el-select v-model="selectedRunId" placeholder="选择运行" class="run-select" @change="loadRun">
              <el-option
                v-for="r in c.runs"
                :key="r.id"
                :value="r.id"
                :label="(r.run_at || '时间未知') + ' · ' + (r.runner || '未知') + ' · ' + (r.verdict || '未审查')"
              />
            </el-select>
            <button v-if="selectedRun" class="tb-btn" @click="toggleRunInfo">{{ showRunInfo ? '收起信息' : '编辑信息' }}</button>
            <button v-if="selectedRun" class="tb-btn" @click="downloadRun">下载运行</button>
            <button v-if="selectedRun" class="tb-btn danger" @click="delRun">删除运行</button>
          </div>

          <div v-if="c.runs.length === 0" class="empty-run">
            暂无运行。点上方"↑ 上传运行"传一个 zip（内放运行的产出文件）。
          </div>

          <div v-else-if="selectedRun" v-loading="runLoading">
            <!-- 运行信息卡（可编辑） -->
            <div v-if="showRunInfo" class="card">
              <h2 class="sec-title">运行信息</h2>
              <div class="ri-field"><label>名称</label><el-input v-model="runInfo.name" /></div>
              <div class="ri-field"><label>runner</label><el-input v-model="runInfo.runner" /></div>
              <div class="ri-field"><label>时间</label><el-input v-model="runInfo.run_at" placeholder="如 2026-07-22T10:30" /></div>
              <div class="ri-field"><label>状态</label><el-input v-model="runInfo.status" /></div>
              <div class="ri-field"><label>备注</label><el-input v-model="runInfo.notes" type="textarea" :rows="2" /></div>
              <div class="ri-actions">
                <el-button size="small" @click="showRunInfo = false">取消</el-button>
                <el-button size="small" type="primary" :loading="savingRunInfo" @click="saveRunInfo">保存信息</el-button>
              </div>
            </div>

            <!-- 产出（按目录分组） -->
            <div class="card">
              <h2 class="sec-title">产出 <span class="count">{{ selectedRun.artifacts.length }}</span></h2>
              <div v-if="selectedRun.artifacts.length === 0" class="muted">该运行无产出文件。</div>
              <div v-else>
                <div v-for="grp in artifactGroups" :key="grp.dir" class="art-group">
                  <div class="art-dir">{{ grp.dir }}</div>
                  <div class="atabs">
                    <button
                      v-for="a in grp.files"
                      :key="a"
                      :class="['atab', { active: a === activeArtifact }]"
                      @click="selectArtifact(a)"
                    >{{ shortName(a) }}</button>
                  </div>
                </div>
                <div v-if="activeArtifact" v-loading="artLoading" class="art-body">
                  <pre v-if="!isMd(activeArtifact)" class="code-block">{{ artifactText }}</pre>
                  <div v-else class="md-body" v-html="renderMd(artifactText)" />
                </div>
              </div>
            </div>

            <!-- 审查 -->
            <div class="card">
              <div class="reviews-head">
                <h2 class="sec-title">审查 <span class="count">{{ selectedRun.reviews.length }}</span></h2>
                <button class="tb-btn primary" @click="openAddReview">{{ showReviewForm ? '收起' : '+ 添加审查' }}</button>
              </div>
              <ReviewForm
                v-if="showReviewForm"
                :run-id="selectedRun.id"
                :review="editingReview"
                @submitted="onReviewSubmitted"
                @cancel="cancelReview"
              />
              <div v-if="selectedRun.reviews.length === 0 && !showReviewForm" class="muted">暂无审查。</div>
              <div v-for="rv in selectedRun.reviews" :key="rv.id" class="review-card">
                <div class="rv-head">
                  <span :class="['verdict', verdictClass(rv.verdict)]">{{ rv.verdict || '未判定' }}</span>
                  <span class="rv-reviewer">{{ rv.reviewer || '匿名' }}</span>
                  <span class="rv-time">{{ rv.reviewed_at }}</span>
                  <span class="rv-actions">
                    <button class="link-btn" @click="editReview(rv)">修改</button>
                    <button class="link-btn danger" @click="delReview(rv)">删除</button>
                  </span>
                </div>
                <div v-if="rv.problems.length" class="rv-problems">
                  <div v-for="(p, i) in rv.problems" :key="i" class="rv-prob">
                    <div class="rp-desc">{{ p.description }}</div>
                    <div class="rp-tags">
                      <span v-for="a in p.attribution" :key="a" :class="['attr', attrClass(a)]">{{ a }}</span>
                      <span v-if="!p.attribution.length" class="attr a-other">未归因</span>
                      <span v-for="o in p.objects" :key="o" class="rp-obj">{{ o }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElSelect, ElOption, ElInput, ElButton, ElMessage, ElMessageBox } from 'element-plus'
import {
  getCase, getRun, getArtifact, uploadRun, updateRun, deleteRun,
  downloadCaseURL, downloadRunURL, deleteReview,
  type CaseDetail, type RunDetail, type ReviewDetail, type RunInfo,
} from '../api'
import { renderMd } from '../md'
import FilePreview from '../components/FilePreview.vue'
import ReviewForm from '../components/ReviewForm.vue'

const route = useRoute()
const router = useRouter()
const c = ref<CaseDetail | null>(null)
const loading = ref(false)
const err = ref('')

const selectedRunId = ref('')
const selectedRun = ref<RunDetail | null>(null)
const runLoading = ref(false)
const runCollapsed = ref(false)

const activeArtifact = ref('')
const artifactText = ref('')
const artifactCache = ref<Record<string, string>>({})
const artLoading = ref(false)

const showReviewForm = ref(false)
const editingReview = ref<ReviewDetail | null>(null)

const showUploadPanel = ref(false)
const uploadName = ref('')
const uploadRunner = ref('')
const runFileEl = ref<HTMLInputElement | null>(null)

const showRunInfo = ref(false)
const savingRunInfo = ref(false)
const runInfo = ref<RunInfo>({})

const fileGroups = computed(() => {
  const groups = [
    { label: '输入配置', items: [] as string[] },
    { label: '参考输出', items: [] as string[] },
    { label: '其他文件', items: [] as string[] },
  ]
  for (const f of c.value?.files || []) {
    if (f.startsWith('inputs/')) groups[0].items.push(f)
    else if (f.startsWith('references/')) groups[1].items.push(f)
    else groups[2].items.push(f)
  }
  return groups.filter((g) => g.items.length)
})

// 产出按目录分组（无 "/" 的归"根目录"）
const artifactGroups = computed(() => {
  const map: Record<string, string[]> = {}
  for (const a of selectedRun.value?.artifacts || []) {
    const idx = a.lastIndexOf('/')
    const dir = idx >= 0 ? a.slice(0, idx) : '根目录'
    ;(map[dir] = map[dir] || []).push(a)
  }
  return Object.keys(map).sort().map((dir) => ({ dir, files: map[dir].sort() }))
})

function shortName(a: string): string {
  const idx = a.lastIndexOf('/')
  return idx >= 0 ? a.slice(idx + 1) : a
}

async function loadCase(): Promise<void> {
  const id = String(route.params.id)
  loading.value = true
  err.value = ''
  try {
    c.value = await getCase(id)
    if (c.value.runs.length) {
      selectedRunId.value = c.value.runs[0].id
      await loadRun()
    } else {
      selectedRun.value = null
    }
  } catch (e) {
    err.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

async function loadRun(): Promise<void> {
  if (!selectedRunId.value) {
    selectedRun.value = null
    return
  }
  runLoading.value = true
  artifactCache.value = {}
  activeArtifact.value = ''
  artifactText.value = ''
  showRunInfo.value = false
  try {
    selectedRun.value = await getRun(selectedRunId.value)
    runInfo.value = {
      name: selectedRun.value.name,
      runner: selectedRun.value.runner,
      run_at: selectedRun.value.run_at,
      status: selectedRun.value.status,
      notes: (selectedRun.value.frontmatter.notes as string) || '',
    }
    const def = selectedRun.value.artifacts.find((a) => a.endsWith('.txt')) || selectedRun.value.artifacts[0]
    if (def) await selectArtifact(def)
  } catch {
    selectedRun.value = null
  } finally {
    runLoading.value = false
  }
}

async function selectArtifact(name: string): Promise<void> {
  if (!selectedRun.value) return
  activeArtifact.value = name
  if (name in artifactCache.value) {
    artifactText.value = artifactCache.value[name]
    return
  }
  artLoading.value = true
  try {
    const text = await getArtifact(selectedRun.value.id, name)
    artifactCache.value[name] = text
    artifactText.value = text
  } catch {
    artifactText.value = '（加载失败）'
  } finally {
    artLoading.value = false
  }
}

function isMd(name: string): boolean {
  return name.toLowerCase().endsWith('.md')
}

async function onUploadRun(e: Event): Promise<void> {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !c.value) return
  try {
    const r = await uploadRun(c.value.id, file, { name: uploadName.value || undefined, runner: uploadRunner.value || undefined })
    showUploadPanel.value = false
    uploadName.value = ''
    uploadRunner.value = ''
    await loadCase()
    selectedRunId.value = r.id
    await loadRun()
    ElMessage.success('运行已上传')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  } finally {
    input.value = ''
  }
}

async function saveRunInfo(): Promise<void> {
  if (!selectedRun.value) return
  savingRunInfo.value = true
  try {
    await updateRun(selectedRun.value.id, runInfo.value)
    await loadRun()
    await loadCase()
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  } finally {
    savingRunInfo.value = false
  }
}

function toggleRunInfo(): void {
  showRunInfo.value = !showRunInfo.value
}

async function delRun(): Promise<void> {
  if (!selectedRun.value) return
  try {
    await ElMessageBox.confirm(`确定删除运行「${selectedRun.value.id}」？`, '确认删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteRun(selectedRun.value.id)
    ElMessage.success('已删除')
    await loadCase()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  }
}

function downloadCase(): void {
  if (c.value) window.open(downloadCaseURL(c.value.id), '_blank')
}
function downloadRun(): void {
  if (selectedRun.value) window.open(downloadRunURL(selectedRun.value.id), '_blank')
}
function toggleCollapse(): void {
  runCollapsed.value = !runCollapsed.value
}

function openAddReview(): void {
  if (showReviewForm.value) {
    showReviewForm.value = false
    editingReview.value = null
  } else {
    editingReview.value = null
    showReviewForm.value = true
  }
}
function editReview(rv: ReviewDetail): void {
  editingReview.value = rv
  showReviewForm.value = true
}
function cancelReview(): void {
  showReviewForm.value = false
  editingReview.value = null
}
async function onReviewSubmitted(): Promise<void> {
  showReviewForm.value = false
  editingReview.value = null
  await loadRun()
}
async function delReview(rv: ReviewDetail): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定删除审查 ${rv.id}？`, '确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteReview(rv.id)
    await loadRun()
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  }
}

function back(): void {
  router.push({ name: 'tests' })
}
function verdictClass(v: string): string {
  if (v === '通过') return 'v-pass'
  if (v === '不通过') return 'v-fail'
  if (v === '部分通过') return 'v-partial'
  return 'v-none'
}
function attrClass(a: string): string {
  if (a === '图谱知识') return 'a-graph'
  if (a === '配置流程') return 'a-flow'
  return 'a-other'
}

onMounted(loadCase)
watch(() => route.params.id, loadCase)
</script>

<style scoped>
.compare-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.topbar {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-5);
  border-bottom: 1px solid var(--border);
  background: var(--bg-elev);
  flex-shrink: 0;
}
.back {
  font-size: 13px;
  color: var(--accent);
  cursor: pointer;
}
.title-block {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}
.case-title {
  font-family: var(--display);
  font-size: 16px;
  font-weight: 700;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.tag {
  padding: 1px 7px;
  background: var(--bg-sunken);
  border-radius: 4px;
  font-size: 11px;
  color: var(--text-muted);
  flex-shrink: 0;
}
.tag-scene {
  color: var(--accent);
}
.top-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
.tb-btn {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-sunken);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 4px 10px;
  cursor: pointer;
  white-space: nowrap;
}
.tb-btn:hover:not(:disabled) {
  color: var(--accent);
  border-color: var(--accent);
}
.tb-btn.primary {
  color: #fff;
  background: var(--accent);
  border-color: var(--accent);
}
.tb-btn.danger:hover {
  color: #dc2626;
  border-color: #dc2626;
}
.upload-panel {
  background: var(--bg-sunken);
  border-bottom: 1px solid var(--border);
  padding: var(--space-3) var(--space-5);
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex-shrink: 0;
}
.up-row {
  display: flex;
  gap: var(--space-3);
  align-items: center;
}
.up-input {
  flex: 1;
}
.up-hint {
  font-size: 11.5px;
  color: var(--text-faint);
}
.file-input {
  font-size: 12.5px;
}
.hidden-input {
  display: none;
}
.err {
  color: #dc2626;
  font-size: 13px;
  padding: var(--space-3) var(--space-5);
}
.compare-body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.compare-flex {
  display: flex;
  height: 100%;
  gap: 1px;
  background: var(--border);
}
.compare-flex > .pane {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  background: var(--bg);
  padding: var(--space-4);
}
.compare-flex.collapsed > .pane-case {
  flex: 1;
}
.pane {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.card {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: var(--space-4);
}
.sec-title {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text);
  margin: 0 0 var(--space-3);
}
.count {
  color: var(--text-faint);
  font-weight: 400;
  font-size: 12px;
}
.muted {
  font-size: 12.5px;
  color: var(--text-muted);
}
.md-body {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text);
}
.md-body :deep(h1),
.md-body :deep(h2) {
  font-size: 14px;
  margin: var(--space-3) 0 var(--space-2);
}
.run-toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
}
.run-select {
  flex: 1;
  min-width: 200px;
}
.empty-run {
  padding: var(--space-6);
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  background: var(--bg-sunken);
  border-radius: var(--radius);
  border: 1px dashed var(--border);
  line-height: 1.8;
}
.ri-field {
  margin-bottom: 10px;
}
.ri-field label {
  display: block;
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text-faint);
  margin-bottom: 4px;
}
.ri-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: var(--space-2);
}
.art-group {
  margin-bottom: var(--space-3);
}
.art-dir {
  font-size: 11.5px;
  font-family: var(--mono);
  color: var(--text-faint);
  margin-bottom: 4px;
}
.atabs {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
}
.atab {
  padding: 3px 10px;
  font-size: 12px;
  background: var(--bg-sunken);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--text-muted);
  font-family: var(--mono);
}
.atab.active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}
.art-body {
  margin-top: var(--space-2);
}
.code-block {
  background: var(--bg-sunken);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: var(--space-3);
  font-family: var(--mono);
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  color: var(--text);
  overflow-x: auto;
  margin: 0;
  max-height: 480px;
}
.reviews-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3);
}
.review-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: var(--space-3);
  margin-top: 8px;
}
.rv-head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: 4px;
  flex-wrap: wrap;
}
.rv-reviewer {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}
.rv-time {
  font-size: 12px;
  color: var(--text-faint);
}
.rv-actions {
  margin-left: auto;
  display: flex;
  gap: 10px;
}
.link-btn {
  font-size: 12px;
  color: var(--accent);
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
}
.link-btn.danger {
  color: #dc2626;
}
.rv-problems {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 6px;
}
.rv-prob {
  background: var(--bg-sunken);
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-3);
}
.rp-desc {
  font-size: 12.5px;
  color: var(--text);
  line-height: 1.6;
}
.rp-tags {
  display: flex;
  gap: 6px;
  margin-top: 4px;
  align-items: center;
  flex-wrap: wrap;
}
.attr {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 7px;
  border-radius: 4px;
}
.a-graph {
  background: rgba(79, 70, 229, 0.12);
  color: #4338ca;
}
.a-flow {
  background: rgba(245, 158, 11, 0.14);
  color: #d97706;
}
.a-other {
  background: var(--bg-elev);
  color: var(--text-muted);
}
.rp-obj {
  font-size: 11px;
  font-family: var(--mono);
  color: var(--text-faint);
}
.verdict {
  font-size: 12px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 999px;
}
.v-pass {
  background: rgba(16, 185, 129, 0.12);
  color: #059669;
}
.v-fail {
  background: rgba(239, 68, 68, 0.12);
  color: #dc2626;
}
.v-partial {
  background: rgba(245, 158, 11, 0.14);
  color: #d97706;
}
.v-none {
  background: var(--bg-sunken);
  color: var(--text-faint);
}
</style>
