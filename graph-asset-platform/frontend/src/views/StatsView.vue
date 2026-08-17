<template>
  <div class="stats-view">
    <div class="stats-container">
      <header class="page-head stagger-in">
        <div>
          <h1 class="page-title">资产统计</h1>
          <p class="page-sub">按图谱层级聚合对象与关系边计数</p>
        </div>
        <el-button :icon="Refresh" :loading="loading" text @click="load">
          刷新
        </el-button>
      </header>

      <!-- 总览条：对象总数 + 边总数 + 各层分布 -->
      <section v-if="s" class="overview stagger-in">
        <div class="ov-item">
          <span class="ov-label">对象总数</span>
          <span class="ov-val mono">{{ formatNum(totalObjects) }}</span>
        </div>
        <div class="ov-sep" aria-hidden="true" />
        <div class="ov-item">
          <span class="ov-label">关系边</span>
          <span class="ov-val mono">{{ formatNum(s.edge_count) }}</span>
        </div>
        <div class="ov-sep" aria-hidden="true" />
        <div class="ov-distribution">
          <span class="ov-label">层级分布</span>
          <div class="ov-bar">
            <div
              v-for="seg in distribution"
              :key="seg.layer"
              class="ov-seg"
              :style="{
                flex: String(seg.count || 0.0001),
                background: seg.color,
              }"
              :title="`${seg.layer}: ${seg.count}`"
            />
          </div>
          <div class="ov-legend">
            <span v-for="seg in distribution" :key="seg.layer" class="legend-item">
              <span class="legend-dot" :style="{ background: seg.color }" />
              <span class="legend-label">{{ seg.layer }}</span>
              <span class="legend-val mono">{{ formatNum(seg.count) }}</span>
            </span>
          </div>
        </div>
      </section>

      <!-- 4 张层级卡片 -->
      <section v-if="s" class="card-grid">
        <StatCard
          v-for="card in cards"
          :key="card.title"
          :title="card.title"
          :total="card.total"
          :total-label="card.totalLabel"
          :details="card.details"
          :accent="card.accent"
          :hint="card.hint"
        />
      </section>

      <!-- 知识取用频次（取用打点聚合） -->
      <TelemetrySection v-if="s" />

      <!-- 空态 -->
      <div v-if="!loading && !s" class="empty-state">
        <div class="empty-title">暂无统计数据</div>
        <div class="empty-sub">导入资产包后将在此展示层级统计</div>
      </div>

      <!-- 错误态 -->
      <div v-if="errorMsg" class="error-banner">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.8" />
          <path
            d="M12 7v6m0 3v.5"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
          />
        </svg>
        <span class="mono">{{ errorMsg }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { stats, type Stats } from '../api'
import { UI_LAYER_TYPES } from '../composables/useNav'
import StatCard, { type StatDetail } from '../components/StatCard.vue'
import TelemetrySection from '../components/TelemetrySection.vue'

// 对象 type → 中文标签（统计卡"按对象类型"明细用）
const TYPE_LABELS: Record<string, string> = {
  MMLCommand: '命令',
  ConfigObject: '配置对象',
  Feature: '特性',
  License: 'License',
  AtomTask: '原子Task',
  CompoundTask: '步骤Task',
  FeatureTask: '特性Task',
  Task: '任务',
  BusinessDomain: '业务域',
  NetworkScenario: '场景',
  ConfigurationSolution: '方案',
}

// Element Plus Refresh 图标（内联 SVG，避免引 @element-plus/icons-vue 依赖膨胀）
const Refresh = () =>
  h(
    'svg',
    { width: '14', height: '14', viewBox: '0 0 24 24', fill: 'none' },
    [
      h('path', {
        d: 'M3 12a9 9 0 0 1 15.5-6.3M21 4v4h-4',
        stroke: 'currentColor',
        'stroke-width': '1.8',
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
      }),
      h('path', {
        d: 'M21 12a9 9 0 0 1-15.5 6.3M3 20v-4h4',
        stroke: 'currentColor',
        'stroke-width': '1.8',
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
      }),
    ],
  )

const s = ref<Stats | null>(null)
const loading = ref(false)
const errorMsg = ref('')

// 层级配色（与命令层 indigo 系列协调，4 层各异以便区分）
const LAYER_COLORS: Record<string, string> = {
  命令层: '#4f46e5', // indigo-600
  特性层: '#0891b2', // cyan-600
  任务层: '#d97706', // amber-600
  业务层: '#059669', // emerald-600
}

// 卡片配置：UI 层 → 组装明细
interface CardConfig {
  title: string
  total: number
  totalLabel: string
  accent: string
  hint: string
  details: StatDetail[]
}

const cards = computed<CardConfig[]>(() => {
  if (!s.value) return []
  const data = s.value
  const out: CardConfig[] = []

  // 命令层 / 特性层 / 任务层：总数 + 按网元 + 按版本(网元/版本)
  for (const layer of ['命令层', '特性层', '任务层'] as const) {
    const total = data.per_layer[layer] ?? 0
    const perNf = data.per_layer_per_nf[layer] ?? {}
    const perVer = data.per_layer_per_nf_per_version[layer] ?? {}

    const details: StatDetail[] = []

    // 按对象类型（命令层: 命令/配置对象；特性层: 特性/license；任务层只有 Task 则跳过）
    const layerTypes = UI_LAYER_TYPES[layer] ?? []
    const typeRows = layerTypes
      .map((t) => ({ label: TYPE_LABELS[t] ?? t, value: data.object_counts_by_type?.[t] ?? 0 }))
      .filter((r) => r.value > 0)
    if (typeRows.length > 1) {
      for (const r of typeRows) details.push(r)
      details.push({ label: '—— 按网元 ——', value: -1 })
    }

    // 按网元（保持后端顺序）
    const nfEntries = Object.entries(perNf)
    for (const [nf, cnt] of nfEntries) {
      details.push({ label: nf, value: cnt })
    }

    // 按版本：仅当该层有版本明细（命令/特性/任务层后端可能填充）
    const verNfs = Object.keys(perVer)
    if (verNfs.length > 0) {
      // 加一个视觉分隔（label = 空时显示细分标题）——用 label 文本区分
      if (nfEntries.length > 0) {
        details.push({ label: '—— 按版本 ——', value: -1 })
      }
      for (const nf of verNfs) {
        const vers = perVer[nf] ?? {}
        for (const [ver, cnt] of Object.entries(vers)) {
          details.push({ label: `${nf} / ${ver}`, value: cnt })
        }
      }
    }

    out.push({
      title: layer,
      total,
      totalLabel: '对象数',
      accent: LAYER_COLORS[layer],
      hint: nfEntries.length ? `${nfEntries.length} 个网元` : '',
      details,
    })
  }

  // 业务层：总数 + 按对象类型(业务域/场景/方案) + 按域
  const bizTotal = data.per_layer['业务层'] ?? 0
  const bizTypes = UI_LAYER_TYPES['业务层'] ?? []
  const bizTypeRows = bizTypes
    .map((t) => ({ label: TYPE_LABELS[t] ?? t, value: data.object_counts_by_type?.[t] ?? 0 }))
    .filter((r) => r.value > 0)
  const domainEntries = Object.entries(data.per_domain)
  const bizDetails: StatDetail[] = []
  if (bizTypeRows.length > 1) {
    for (const r of bizTypeRows) bizDetails.push(r)
    bizDetails.push({ label: '—— 按域 ——', value: -1 })
  }
  for (const [d, cnt] of domainEntries) {
    bizDetails.push({ label: d, value: cnt })
  }
  out.push({
    title: '业务层',
    total: bizTotal,
    totalLabel: '对象数',
    accent: LAYER_COLORS['业务层'],
    hint: domainEntries.length ? `${domainEntries.length} 个域` : '',
    details: bizDetails,
  })

  return out
})

const totalObjects = computed(() => {
  if (!s.value) return 0
  return Object.values(s.value.per_layer).reduce((a, b) => a + b, 0)
})

const distribution = computed(() => {
  if (!s.value) return []
  const order = ['命令层', '特性层', '任务层', '业务层'] as const
  return order.map((layer) => ({
    layer,
    count: s.value?.per_layer[layer] ?? 0,
    color: LAYER_COLORS[layer],
  }))
})

function formatNum(n: number): string {
  return n.toLocaleString('zh-CN')
}

async function load(): Promise<void> {
  loading.value = true
  errorMsg.value = ''
  try {
    s.value = await stats()
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : String(e)
    s.value = null
  } finally {
    loading.value = false
  }
}

// 注册全局刷新钩子（上传完成后 UploadView 会调 window.__refreshStats）
// AppHeader 与 App.vue 也各自注册了同名钩子，后注册的覆盖前者；
// 为了让本视图也能被通知，独立挂一个具名钩子并串联调用。
function setupGlobalRefreshHook(): void {
  const w = window as unknown as {
    __refreshStats?: () => Promise<void>
    __refreshStatsView?: () => Promise<void>
  }
  const prev = w.__refreshStats
  w.__refreshStats = async () => {
    await prev?.()
    await load()
  }
  w.__refreshStatsView = load
}

onMounted(() => {
  void load()
  setupGlobalRefreshHook()
})
</script>

<style scoped>
.stats-view {
  height: 100%;
  overflow: auto;
  padding: var(--space-8) var(--space-6);
}

.stats-container {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}

.page-title {
  font-family: var(--display);
  font-size: 26px;
  font-weight: 700;
  color: var(--text);
  margin: 0;
  letter-spacing: -0.02em;
}

.page-sub {
  margin: var(--space-2) 0 0;
  color: var(--text-muted);
  font-size: 13px;
  max-width: 640px;
  line-height: 1.55;
}

/* 总览条 */
.overview {
  display: flex;
  align-items: center;
  gap: var(--space-5);
  padding: var(--space-4) var(--space-5);
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  flex-wrap: wrap;
}

.ov-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ov-label {
  font-size: 11px;
  color: var(--text-faint);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.ov-val {
  font-family: var(--display);
  font-size: 24px;
  font-weight: 700;
  color: var(--text);
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.ov-sep {
  width: 1px;
  align-self: stretch;
  background: var(--border-faint);
}

.ov-distribution {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  flex: 1;
  min-width: 280px;
}

.ov-bar {
  display: flex;
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: var(--bg-sunken);
  gap: 2px;
}

.ov-seg {
  min-width: 4px;
  height: 100%;
  transition: flex var(--dur) var(--ease);
}

.ov-legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11.5px;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
}

.legend-label {
  color: var(--text-muted);
}

.legend-val {
  color: var(--text);
  font-weight: 600;
}

/* 卡片网格 */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: var(--space-4);
}

/* 空态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-10);
  text-align: center;
  color: var(--text-faint);
}

.empty-title {
  font-family: var(--display);
  font-size: 16px;
  font-weight: 600;
  color: var(--text-muted);
}

.empty-sub {
  font-size: 13px;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: var(--radius-sm);
  color: var(--danger);
  font-size: 12.5px;
}

@media (max-width: 720px) {
  .overview {
    flex-direction: column;
    align-items: stretch;
  }
  .ov-sep {
    display: none;
  }
}
</style>
