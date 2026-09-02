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
        <el-button :icon="Refresh" text @click="reloadActive">刷新</el-button>
      </header>

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
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { ElButton, ElMessage, ElTabPane, ElTabs } from 'element-plus'
import { statsFilters, type StatsFilterOptions, type StatsViewKey } from '../api'
import CommandTab from '../components/stats/CommandTab.vue'
import FeatureTab from '../components/stats/FeatureTab.vue'
import BusinessTab from '../components/stats/BusinessTab.vue'

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
const active = ref<StatsViewKey>('command')
const errorMsg = ref('')
const cmdRef = ref<InstanceType<typeof CommandTab> | null>(null)
const featRef = ref<InstanceType<typeof FeatureTab> | null>(null)
const bizRef = ref<InstanceType<typeof BusinessTab> | null>(null)

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

/** 刷新当前 Tab（懒加载语义：切 Tab 由组件 onMounted 自理）。 */
function reloadActive(): void {
  if (active.value === 'command') cmdRef.value?.reload()
  else if (active.value === 'feature') featRef.value?.reload()
  else bizRef.value?.reload()
}

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
    await loadFilters()
    reloadActive()
  }
  w.__refreshStatsView = async () => {
    await loadFilters()
    reloadActive()
  }
}

onMounted(() => {
  void loadFilters()
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
