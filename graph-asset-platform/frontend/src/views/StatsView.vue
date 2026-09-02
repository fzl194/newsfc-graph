<template>
  <div class="stats-view">
    <div class="stats-container">
      <header class="page-head stagger-in">
        <div>
          <h1 class="page-title">统计</h1>
          <p class="page-sub">
            三图谱视图：命令 / 特性 / 业务——按网元、版本（国内/海外）、对象/关系/规则类型、业务域筛选，支持导出
          </p>
        </div>
        <div class="head-actions">
          <button
            v-for="f in EXPORTS" :key="f.key" class="exp-btn" type="button"
            :disabled="exporting" @click="doExport(f.key)"
          >{{ f.label }}</button>
          <el-button :icon="Refresh" :loading="anyLoading" text @click="reload">
            刷新
          </el-button>
        </div>
      </header>

      <div v-if="ruleTablesMissing" class="warn-banner">
        AIMML 历史规则表未导入（B_AI_* 表为空）——命令图谱的「命令数量 / 参数数量 / 五类规则」将为 0。
        内网请先运行 dump_rule_tables_to_platform.py 灌数。
      </div>

      <StatsFilterBar
        v-if="filterOpts" v-model="filters" :options="filterOpts" :view="active"
        @reset="filters = emptyFilters()"
      />

      <div v-if="errorMsg" class="error-banner">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.8" />
          <path d="M12 7v6m0 3v.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
        </svg>
        <span class="mono">{{ errorMsg }}</span>
      </div>

      <el-tabs v-model="active" class="stats-tabs">
        <el-tab-pane label="命令图谱" name="command">
          <CommandTab :data="cmd" :loading="loadings.command" />
        </el-tab-pane>
        <el-tab-pane label="特性图谱" name="feature">
          <FeatureTab :data="feat" :loading="loadings.feature" />
        </el-tab-pane>
        <el-tab-pane label="业务图谱" name="business">
          <BusinessTab :data="biz" :loading="loadings.business" />
        </el-tab-pane>
      </el-tabs>

      <!-- 知识取用频次（取用打点聚合，独立于三视图） -->
      <TelemetrySection />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref, watch } from 'vue'
import { ElButton, ElMessage, ElTabs, ElTabPane } from 'element-plus'
import {
  downloadStatsExport, statsBusiness, statsCommand, statsFeature, statsFilters,
  type BusinessStats, type CommandStats, type FeatureStats,
  type StatsFilterOptions, type StatsViewKey,
} from '../api'
import TelemetrySection from '../components/TelemetrySection.vue'
import StatsFilterBar from '../components/stats/StatsFilterBar.vue'
import CommandTab from '../components/stats/CommandTab.vue'
import FeatureTab from '../components/stats/FeatureTab.vue'
import BusinessTab from '../components/stats/BusinessTab.vue'
import { emptyFilters, type StatsFilterState } from '../components/stats/shared'

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

const EXPORTS = [
  { key: 'csv' as const, label: '导出 CSV' },
  { key: 'xlsx' as const, label: '导出 Excel' },
  { key: 'md' as const, label: '导出 Markdown' },
]

const filters = ref<StatsFilterState>(emptyFilters())
const filterOpts = ref<StatsFilterOptions | null>(null)
const active = ref<StatsViewKey>('command')
const cmd = ref<CommandStats | null>(null)
const feat = ref<FeatureStats | null>(null)
const biz = ref<BusinessStats | null>(null)
const loadings = reactive({ command: false, feature: false, business: false })
const errorMsg = ref('')
const exporting = ref(false)

const anyLoading = computed(() => loadings[active.value])
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
  }
}

async function loadView(view: StatsViewKey): Promise<void> {
  loadings[view] = true
  errorMsg.value = ''
  try {
    if (view === 'command') cmd.value = await statsCommand(filters.value)
    else if (view === 'feature') feat.value = await statsFeature(filters.value)
    else biz.value = await statsBusiness(filters.value)
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : String(e)
  } finally {
    loadings[view] = false
  }
}

async function reload(): Promise<void> {
  await loadFilters()
  await loadView(active.value)
}

async function doExport(format: 'csv' | 'xlsx' | 'md'): Promise<void> {
  exporting.value = true
  try {
    await downloadStatsExport(active.value, format, filters.value)
    ElMessage.success(`已导出（${VIEW_LABEL[active.value]} · ${format.toUpperCase()}）`)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  } finally {
    exporting.value = false
  }
}

const VIEW_LABEL: Record<StatsViewKey, string> = {
  command: '命令图谱', feature: '特性图谱', business: '业务图谱',
}

// 筛选变化 → 重载当前视图（切 Tab 时 watch(active) 拉取该视图）
watch(filters, () => void loadView(active.value), { deep: true })
watch(active, (v) => void loadView(v))

// 注册全局刷新钩子（上传完成后 UploadView 会调 window.__refreshStats）；
// AppHeader / App.vue 也各自注册同名钩子——串联调用不覆盖。
function setupGlobalRefreshHook(): void {
  const w = window as unknown as {
    __refreshStats?: () => Promise<void>
    __refreshStatsView?: () => Promise<void>
  }
  const prev = w.__refreshStats
  w.__refreshStats = async () => {
    await prev?.()
    reload()
  }
  w.__refreshStatsView = reload
}

onMounted(() => {
  void loadFilters()
  void loadView('command')
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

.head-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

.exp-btn {
  border: 1px solid var(--border);
  background: var(--bg-elev);
  color: var(--text-muted);
  font-size: 12px;
  padding: 5px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease);
}

.exp-btn:hover:not(:disabled) {
  color: var(--accent);
  border-color: var(--accent);
}

.exp-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

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
</style>
