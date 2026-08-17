<template>
  <div class="tests-page">
    <div class="back" @click="back">← 返回用例</div>
    <div v-if="err" class="err">{{ err }}</div>
    <div v-loading="loading">
      <div v-if="r">
        <div class="run-head">
          <h1 class="page-title">运行详情</h1>
          <div class="run-meta">
            <span><b>{{ r.runner || '未知 runner' }}</b></span>
            <span class="dot">·</span>
            <span>{{ r.run_at || '时间未知' }}</span>
            <span v-if="r.status" class="dot">·</span>
            <span v-if="r.status">{{ r.status }}</span>
          </div>
        </div>

        <!-- 产出物 -->
        <section class="card">
          <h2 class="sec-title">产出 <span class="count">{{ r.artifacts.length }} 个文件</span></h2>
          <div v-if="r.artifacts.length === 0" class="empty">该运行无产出文件。</div>
          <div v-else>
            <div class="artifact-tabs">
              <button
                v-for="a in r.artifacts"
                :key="a"
                :class="['atab', { active: a === activeArtifact }]"
                @click="selectArtifact(a)"
              >
                {{ a }}
              </button>
            </div>
            <div v-if="activeArtifact" v-loading="artLoading" class="artifact-body">
              <pre v-if="!isMd(activeArtifact)" class="code-block">{{ artifactText }}</pre>
              <div v-else class="md-body" v-html="renderMd(artifactText)" />
            </div>
          </div>
        </section>

        <!-- 审查 -->
        <section class="card">
          <div class="reviews-head">
            <h2 class="sec-title">审查记录 <span class="count">{{ r.reviews.length }}</span></h2>
            <el-button size="small" type="primary" @click="toggleForm">
              {{ showForm ? '收起' : '+ 添加审查' }}
            </el-button>
          </div>

          <ReviewForm
            v-if="showForm"
            :run-id="r.id"
            :review="editing"
            @submitted="onSubmitted"
            @cancel="cancelForm"
          />

          <div v-if="r.reviews.length === 0 && !showForm" class="empty">暂无审查。</div>
          <div v-for="rv in r.reviews" :key="rv.id" class="review-card">
            <div class="rv-head">
              <span :class="['verdict', verdictClass(rv.verdict)]">{{ rv.verdict || '未判定' }}</span>
              <span class="rv-reviewer">{{ rv.reviewer || '匿名' }}</span>
              <span class="rv-time">{{ rv.reviewed_at }}</span>
              <el-button size="small" link @click="editReview(rv)">修改</el-button>
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
            <details v-if="rv.body_md" class="rv-raw">
              <summary>正文</summary>
              <div class="md-body" v-html="renderMd(rv.body_md)" />
            </details>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElButton } from 'element-plus'
import { getRun, getArtifact, type RunDetail, type ReviewDetail } from '../api'
import { renderMd } from '../md'
import ReviewForm from '../components/ReviewForm.vue'

const route = useRoute()
const router = useRouter()
const r = ref<RunDetail | null>(null)
const loading = ref(false)
const err = ref('')

const activeArtifact = ref('')
const artifactText = ref('')
const artLoading = ref(false)
const artifactCache = ref<Record<string, string>>({})

const showForm = ref(false)
const editing = ref<ReviewDetail | null>(null)

async function load(): Promise<void> {
  const id = String(route.params.id)
  loading.value = true
  err.value = ''
  artifactCache.value = {}
  activeArtifact.value = ''
  artifactText.value = ''
  try {
    r.value = await getRun(id)
    // 默认选 config.txt，否则首个产出
    const def = r.value.artifacts.find((a) => a.endsWith('.txt')) || r.value.artifacts[0]
    if (def) await selectArtifact(def)
  } catch (e) {
    err.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

async function selectArtifact(name: string): Promise<void> {
  if (!r.value) return
  activeArtifact.value = name
  if (name in artifactCache.value) {
    artifactText.value = artifactCache.value[name]
    return
  }
  artLoading.value = true
  try {
    const text = await getArtifact(r.value.id, name)
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

function back(): void {
  router.back()
}

function toggleForm(): void {
  if (showForm.value) {
    showForm.value = false
    editing.value = null
  } else {
    editing.value = null
    showForm.value = true
  }
}
function editReview(rv: ReviewDetail): void {
  editing.value = rv
  showForm.value = true
}
function cancelForm(): void {
  showForm.value = false
  editing.value = null
}
async function onSubmitted(): Promise<void> {
  showForm.value = false
  editing.value = null
  await load()
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

onMounted(load)
watch(() => route.params.id, load)
</script>

<style scoped>
.tests-page {
  height: 100%;
  overflow-y: auto;
  padding: var(--space-6) var(--space-7);
  max-width: 920px;
  margin: 0 auto;
}
.back {
  font-size: 13px;
  color: var(--accent);
  cursor: pointer;
  margin-bottom: var(--space-4);
  width: fit-content;
}
.err {
  color: #dc2626;
  font-size: 13px;
  padding: var(--space-4);
  background: rgba(239, 68, 68, 0.06);
  border-radius: var(--radius);
}
.run-head {
  margin-bottom: var(--space-5);
}
.page-title {
  font-family: var(--display);
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
  margin: 0 0 6px;
}
.run-meta {
  font-size: 13px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 6px;
}
.dot {
  opacity: 0.4;
}
.card {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: var(--space-5);
  margin-bottom: var(--space-4);
}
.sec-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  margin: 0;
}
.count {
  color: var(--text-faint);
  font-weight: 400;
  font-size: 12px;
}
.empty {
  font-size: 13px;
  color: var(--text-muted);
}
.reviews-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3);
}
.artifact-tabs {
  display: flex;
  gap: 6px;
  margin: var(--space-3) 0;
  flex-wrap: wrap;
}
.atab {
  padding: 4px 12px;
  font-size: 12.5px;
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
.artifact-body {
  margin-top: var(--space-2);
}
.code-block {
  background: var(--bg-sunken);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: var(--space-4);
  font-family: var(--mono);
  font-size: 12.5px;
  line-height: 1.6;
  white-space: pre-wrap;
  color: var(--text);
  overflow-x: auto;
  margin: 0;
}
.md-body {
  font-size: 13.5px;
  line-height: 1.75;
  color: var(--text);
}
.md-body :deep(h1),
.md-body :deep(h2) {
  font-size: 15px;
  margin: var(--space-3) 0 var(--space-2);
}
.md-body :deep(table) {
  border-collapse: collapse;
}
.md-body :deep(th),
.md-body :deep(td) {
  border: 1px solid var(--border);
  padding: 4px 8px;
}
.review-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: var(--space-3) var(--space-4);
  margin-top: 10px;
}
.rv-head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: 6px;
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
.rv-problems {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.rv-prob {
  background: var(--bg-sunken);
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-3);
}
.rp-desc {
  font-size: 13px;
  color: var(--text);
  line-height: 1.6;
}
.rp-tags {
  display: flex;
  gap: 6px;
  margin-top: 4px;
  align-items: center;
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
.rv-raw {
  margin-top: 8px;
  font-size: 12px;
}
.rv-raw summary {
  cursor: pointer;
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
