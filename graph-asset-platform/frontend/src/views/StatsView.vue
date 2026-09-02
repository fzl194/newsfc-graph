<template>
  <div class="stats-view">
    <div class="stats-container">
      <header class="page-head stagger-in">
        <div>
          <h1 class="page-title">统计</h1>
          <p class="page-sub">
            三图谱视图：命令 / 特性 / 业务——卡片、表格分区分层，表格独立筛选与分页
          </p>
        </div>
        <div class="head-actions">
          <button v-if="admin" class="ov-edit-btn" type="button" @click="openEdit">编辑总览</button>
          <el-button :icon="Refresh" :loading="cacheBuilding" text @click="updateCache">
            {{ cacheBuilding ? '缓存构建中…' : '更新缓存' }}
          </el-button>
        </div>
      </header>

      <!-- 三层图谱进展总览（stats_overview.json 手动维护；管理员可编辑） -->
      <section v-if="overview?.available && overview.config" class="overview stagger-in">
        <p v-if="overview.config.description" class="ov-desc">
          {{ overview.config.description }}
          <span v-if="overview.config.updated_at" class="ov-meta">
            更新于 {{ overview.config.updated_at }}<template v-if="overview.config.updated_by"> · {{ overview.config.updated_by }}</template>
          </span>
        </p>
        <div class="ov-cards">
          <div
            v-for="c in overview.config.cards" :key="c.title"
            class="ov-card" :style="{ '--ov-accent': c.accent || '#4f46e5' }"
          >
            <h3 class="ov-card-title">{{ c.title }}</h3>
            <div v-for="(m, i) in c.metrics" :key="i" class="ov-metric">
              <div class="ov-metric-head">
                <span class="ov-label">{{ m.label }}</span>
                <span class="ov-value mono">{{ m.value }}</span>
              </div>
              <el-progress v-if="typeof m.progress === 'number'" :percentage="m.progress"
                :stroke-width="6" :show-text="false" class="ov-bar" />
            </div>
          </div>
        </div>
      </section>
      <div v-else-if="admin && overview && !overview.available" class="warn-banner">
        三层图谱进展总览未配置{{ overview.error ? `（${overview.error}）` : '' }}——点击右上「编辑总览」，
        或在服务器 platform-data 下创建 stats_overview.json。
      </div>

      <div v-if="cacheBuilding" class="warn-banner">
        统计缓存重建中——期间展示的仍是旧数据，完成后自动刷新（数据量大时约几十秒）。
      </div>

      <div v-if="ruleTablesMissing" class="warn-banner">
        AIMML 历史规则表未导入（B_AI_* 表为空）——命令图谱的「命令数量 / 参数数量 / 五类规则」将为 0。
        内网请先运行 dump_rule_tables_to_platform.py 灌数。
      </div>

      <div v-if="errorMsg" class="error-banner">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.8" />
          <path d="M12 7v6m0 3v.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
        </svg>
        <span class="mono">{{ errorMsg }}</span>
      </div>

      <el-tabs v-model="active" class="stats-tabs">
        <el-tab-pane label="命令图谱" name="command">
          <CommandTab v-if="filterOpts" ref="cmdRef" :options="filterOpts" />
        </el-tab-pane>
        <el-tab-pane label="特性图谱" name="feature">
          <FeatureTab v-if="filterOpts" ref="featRef" :options="filterOpts" />
        </el-tab-pane>
        <el-tab-pane label="业务图谱" name="business">
          <BusinessTab ref="bizRef" />
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>

  <!-- 管理员：总览编辑（JSON，等价手改 stats_overview.json） -->
  <el-dialog v-model="editVisible" title="编辑三层图谱进展总览" width="720px">
    <p class="edit-hint">
      完整 JSON 直接改（等价手改服务器 platform-data/stats_overview.json）。
      cards 数量不限（建议 3 张对应三图谱）；每条指标 value 支持数字或文本，
      带 <code>progress</code>（0~100）会渲染进度条。保存时服务端校验。
    </p>
    <el-input v-model="editText" type="textarea" :rows="18" class="edit-json mono"
      :placeholder="TEMPLATE" spellcheck="false" />
    <template #footer>
      <el-button @click="editVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="doSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, ref } from 'vue'
import { ElButton, ElDialog, ElInput, ElMessage, ElProgress, ElTabPane, ElTabs } from 'element-plus'
import {
  fetchStatsOverview, refreshStatsCache, saveStatsOverview, statsFilters,
  type StatsFilterOptions, type StatsOverview, type StatsOverviewConfig, type StatsViewKey,
} from '../api'
import { isAdmin } from '../auth'
import CommandTab from '../components/stats/CommandTab.vue'
import FeatureTab from '../components/stats/FeatureTab.vue'
import BusinessTab from '../components/stats/BusinessTab.vue'

const admin = isAdmin()

// 空配置模板（编辑弹窗 placeholder，也是首次配置的起点）
const TEMPLATE = JSON.stringify({
  description: '三层图谱建设进展总览（手动维护）。',
  updated_at: '2026-09-03',
  cards: [
    {
      title: '命令图谱',
      accent: '#4f46e5',
      metrics: [
        { label: '知识条数', value: 126880 },
        { label: '覆盖网元版本', value: '18 / 22', progress: 81.8 },
      ],
    },
    {
      title: '特性图谱',
      accent: '#0ea5e9',
      metrics: [
        { label: '覆盖特性编号', value: 1139 },
        { label: '覆盖率', value: '60.0%', progress: 60 },
      ],
    },
    {
      title: '业务图谱',
      accent: '#8b5cf6',
      metrics: [
        { label: '方案数', value: 31 },
        { label: '覆盖率', value: '45.5%', progress: 45.5 },
      ],
    },
  ],
}, null, 2)

// Element Plus Refresh 图标（内联 SVG，避免引 @element-plus/icons-vue 依赖膨胀）
const Refresh = () =>
  h('svg', { width: '14', height: '14', viewBox: '0 0 24 24', fill: 'none' }, [
    h('path', {
      d: 'M3 12a9 9 0 0 1 15.5-6.3M21 4v4h-4',
      stroke: 'currentColor', 'stroke-width': '1.8',
      'stroke-linecap': 'round', 'stroke-linejoin': 'round',
    }),
    h('path', {
      d: 'M21 12a9 9 0 0 1-15.5 6.3M3 20v-4h4',
      stroke: 'currentColor', 'stroke-width': '1.8',
      'stroke-linecap': 'round', 'stroke-linejoin': 'round',
    }),
  ])

const filterOpts = ref<StatsFilterOptions | null>(null)
const overview = ref<StatsOverview | null>(null)
const active = ref<StatsViewKey>('command')
const errorMsg = ref('')
const cacheBuilding = ref(false)
let cachePollTimer: number | null = null
const cmdRef = ref<InstanceType<typeof CommandTab> | null>(null)
const featRef = ref<InstanceType<typeof FeatureTab> | null>(null)
const bizRef = ref<InstanceType<typeof BusinessTab> | null>(null)

// 编辑弹窗
const editVisible = ref(false)
const editText = ref('')
const saving = ref(false)

const ruleTablesMissing = computed(() => {
  const rows = filterOpts.value?.table_rows ?? {}
  const vals = Object.values(rows)
  return vals.length > 0 && vals.every((v) => v <= 0)
})

async function loadFilters(): Promise<void> {
  try {
    filterOpts.value = await statsFilters()
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : String(e)
    ElMessage.error(errorMsg.value)
  }
}

async function loadOverview(): Promise<void> {
  try {
    overview.value = await fetchStatsOverview()
  } catch {
    /* 总览容错：加载失败不阻断页面 */
  }
}

function openEdit(): void {
  editText.value = overview.value?.config
    ? JSON.stringify(overview.value.config, null, 2)
    : TEMPLATE
  editVisible.value = true
}

async function doSave(): Promise<void> {
  let cfg: StatsOverviewConfig
  try {
    cfg = JSON.parse(editText.value) as StatsOverviewConfig
  } catch (e: unknown) {
    ElMessage.error(`JSON 解析失败：${e instanceof Error ? e.message : String(e)}`)
    return
  }
  saving.value = true
  try {
    await saveStatsOverview(cfg)
    ElMessage.success('总览已保存')
    editVisible.value = false
    await loadOverview()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  } finally {
    saving.value = false
  }
}

/** 刷新当前 Tab（懒加载语义：切 Tab 由组件 onMounted 自理）。 */
function reloadActive(): void {
  if (active.value === 'command') cmdRef.value?.reload()
  else if (active.value === 'feature') featRef.value?.reload()
  else bizRef.value?.reload()
}

/** 「更新缓存」：后台重建预聚合缓存，期间服务旧数据；完成/轮询到就绪后刷新视图。 */
async function updateCache(): Promise<void> {
  try {
    await refreshStatsCache()
    cacheBuilding.value = true
    if (cachePollTimer !== null) window.clearInterval(cachePollTimer)
    cachePollTimer = window.setInterval(async () => {
      try {
        const opts = await statsFilters()
        filterOpts.value = opts
        const building = opts.cache?.building ?? false
        cacheBuilding.value = building
        if (!building) {
          if (cachePollTimer !== null) window.clearInterval(cachePollTimer)
          cachePollTimer = null
          reloadActive()
        }
      } catch {
        /* 轮询容错：下个周期重试 */
      }
    }, 2000)
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : String(e)
  }
}

// 注册全局刷新钩子（上传完成后 UploadView 会调 window.__refreshStats）
function setupGlobalRefreshHook(): void {
  const w = window as unknown as {
    __refreshStats?: () => Promise<void>
    __refreshStatsView?: () => Promise<void>
  }
  const prev = w.__refreshStats
  w.__refreshStats = async () => {
    await prev?.()
    await loadFilters()
    reloadActive()
  }
  w.__refreshStatsView = async () => {
    await loadFilters()
    reloadActive()
  }
}

onUnmounted(() => {
  if (cachePollTimer !== null) window.clearInterval(cachePollTimer)
})

onMounted(() => {
  void loadFilters()
  void loadOverview()
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
  gap: var(--space-5);
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
  max-width: 680px;
  line-height: 1.55;
}

.head-actions { display: flex; align-items: center; gap: var(--space-2); flex-shrink: 0; }

.ov-edit-btn {
  border: 1px solid var(--border);
  background: var(--bg-elev);
  color: var(--text-muted);
  font-size: 12px;
  padding: 5px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
}
.ov-edit-btn:hover { color: var(--accent); border-color: var(--accent); }

/* ---- 三层图谱进展总览 ---- */
.overview {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
}

.ov-desc {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.6;
}

.ov-meta { margin-left: var(--space-3); font-size: 11px; color: var(--text-faint); }

.ov-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: var(--space-4);
}

.ov-card {
  position: relative;
  padding: var(--space-4) var(--space-4) var(--space-3);
  background: var(--bg);
  border: 1px solid var(--border-faint);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.ov-card::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: var(--ov-accent, var(--accent));
  opacity: 0.85;
}

.ov-card-title {
  font-family: var(--display);
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  margin: 0 0 var(--space-2);
}

.ov-metric { display: flex; flex-direction: column; gap: 3px; padding: 4px 0; }

.ov-metric-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
}

.ov-label { font-size: 12px; color: var(--text-muted); }

.ov-value { font-size: 15px; font-weight: 600; color: var(--text); font-variant-numeric: tabular-nums; }

.ov-bar { margin-top: 1px; }

.warn-banner {
  padding: var(--space-3) var(--space-4);
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.35);
  border-radius: var(--radius-sm);
  color: var(--warn);
  font-size: 12.5px;
  line-height: 1.6;
}

.stats-tabs :deep(.el-tabs__header) {
  margin-bottom: var(--space-4);
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

.edit-hint { margin: 0 0 var(--space-3); font-size: 12px; color: var(--text-muted); line-height: 1.6; }
.edit-hint code { font-family: var(--mono); background: var(--bg-sunken); padding: 1px 5px; border-radius: 4px; }
.edit-json :deep(textarea) { font-family: var(--mono); font-size: 12px; line-height: 1.55; }
</style>
