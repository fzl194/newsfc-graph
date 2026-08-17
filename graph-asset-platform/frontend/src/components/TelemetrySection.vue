<template>
  <section class="telemetry-section stagger-in">
    <header class="ts-head">
      <div>
        <h2 class="ts-title">SKILL 取用频次</h2>
        <p class="ts-sub">只统计 SKILL 的 /domains + /md（按对象）</p>
      </div>
      <div class="ts-controls">
        <div class="days-tabs">
          <button
            v-for="d in [1, 7, 30, 90]"
            :key="d"
            :class="['days-tab', { 'days-tab--active': days === d }]"
            @click="days = d; load()"
          >{{ d === 1 ? '今天' : `近 ${d} 天` }}</button>
        </div>
        <span class="ts-total">共 {{ formatNum(stats?.total ?? 0) }} 次取用</span>
      </div>
    </header>

    <div v-if="err" class="ts-err">
      <svg class="state-icon" width="18" height="18" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.8" />
        <path d="M12 7v6m0 3v.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
      </svg>
      <span class="mono">{{ err }}</span>
    </div>
    <div v-else-if="!stats || stats.total === 0" class="ts-empty">
      <svg class="state-icon" width="28" height="28" viewBox="0 0 24 24" fill="none">
        <path d="M3 14a9 9 0 1 1 18 0" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity="0.4" />
        <rect x="9" y="13" width="6" height="7" rx="1.5" stroke="currentColor" stroke-width="1.5" />
        <path d="M10.5 16h3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
      </svg>
      <div class="empty-title">暂无取用记录</div>
      <div class="empty-sub">SKILL 调用 /domains 或 /md 后，取用频次将在此聚合展示</div>
    </div>

    <div v-else class="ts-grid">
      <!-- 按 type 横条 -->
      <div class="ts-block">
        <div class="block-title">按类型</div>
        <div class="type-rows">
          <div v-for="r in typeRows" :key="r.type" class="type-row">
            <span class="type-label">{{ typeLabel(r.type) }}</span>
            <div class="type-bar-wrap">
              <div class="type-bar" :style="{ width: r.pct + '%' }" />
            </div>
            <span class="type-count mono">{{ formatNum(r.count) }}</span>
          </div>
        </div>
      </div>

      <!-- 热门对象 top-N -->
      <div class="ts-block">
        <div class="block-title">热门对象 Top {{ stats.top_ids.length }}</div>
        <ol class="top-list">
          <li
            v-for="(t, i) in stats.top_ids"
            :key="t.id"
            class="top-item top-item--link"
            :title="`在图谱中查看 ${t.id}`"
            @click="goObject(t.id)"
          >
            <span class="top-rank">{{ i + 1 }}</span>
            <span class="top-id mono">{{ t.id }}</span>
            <span class="top-type">{{ typeLabel(t.type) }}</span>
            <span class="top-count mono">{{ formatNum(t.count) }}</span>
          </li>
        </ol>
      </div>

      <!-- 按用户（SKILL） -->
      <div class="ts-block ts-block--user">
        <div class="block-title">
          <svg class="block-ic" width="13" height="13" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="8" r="3.2" stroke="currentColor" stroke-width="1.7" />
            <path d="M5 20c0-3.3 3.1-6 7-6s7 2.7 7 6" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
          </svg>
          按用户（SKILL）
        </div>
        <div class="type-rows">
          <div v-for="(c, u) in stats.by_user" :key="u" class="type-row type-row--kv">
            <span class="type-label">{{ u }}</span>
            <span class="type-count mono">{{ formatNum(c) }}</span>
          </div>
          <div v-if="!Object.keys(stats.by_user).length" class="block-mini-empty">无记录</div>
        </div>
      </div>

      <!-- 按工号（SKILL 使用者） -->
      <div class="ts-block ts-block--operator">
        <div class="block-title">
          <svg class="block-ic" width="13" height="13" viewBox="0 0 24 24" fill="none">
            <rect x="4" y="5" width="16" height="14" rx="2" stroke="currentColor" stroke-width="1.7" />
            <path d="M8 10h8M8 13h5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
          </svg>
          按工号（SKILL 使用者）
        </div>
        <div class="type-rows">
          <div v-for="(c, op) in stats.by_operator" :key="op" class="type-row type-row--kv">
            <span class="type-label">{{ op }}</span>
            <span class="type-count mono">{{ formatNum(c) }}</span>
          </div>
          <div v-if="!Object.keys(stats.by_operator).length" class="block-mini-empty">无记录</div>
        </div>
      </div>

      <!-- 时间趋势（按小时，echarts 圆滑曲线 + Y 轴 + tooltip） -->
      <div class="ts-block ts-block-wide">
        <div class="block-title">时间趋势（按小时）</div>
        <v-chart
          v-if="stats.timeline.length >= 1"
          class="trend-chart"
          :option="chartOption"
          autoresize
        />
        <div v-else class="trend-empty">暂无取用记录</div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { fetchTelemetryStats, type TelemetryStats } from '../api'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent])

const stats = ref<TelemetryStats | null>(null)
const days = ref(1) // 默认今天
const err = ref('')
const router = useRouter()

// 点热门对象 → 跳图谱浏览页定位该对象（BrowserView 读 ?o=id 自动定位）
function goObject(id: string): void {
  router.push({ path: '/', query: { o: id } })
}

const TYPE_LABELS: Record<string, string> = {
  MMLCommand: '命令', ConfigObject: '配置对象', Feature: '特性', License: 'License',
  AtomTask: '原子Task', CompoundTask: '步骤Task', FeatureTask: '特性Task', Task: '任务',
  BusinessDomain: '业务域', NetworkScenario: '场景', ConfigurationSolution: '方案',
}

function typeLabel(t: string): string {
  return TYPE_LABELS[t] ?? t
}
function formatNum(n: number): string {
  return n.toLocaleString('zh-CN')
}

const typeRows = computed(() => {
  if (!stats.value) return []
  const entries = Object.entries(stats.value.by_type).sort((a, b) => b[1] - a[1])
  const max = entries[0]?.[1] || 1
  return entries.map(([type, count]) => ({ type, count, pct: Math.round((count / max) * 100) }))
})

// echarts 配置：圆滑曲线（smooth）+ 面积渐变 + X/Y 轴 + tooltip
const chartOption = computed(() => {
  const tl = stats.value?.timeline ?? []
  return {
    grid: { left: 40, right: 18, top: 18, bottom: 30 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: tl.map((p) => p.date),
      axisLabel: { fontSize: 10, color: '#a8a29e', hideOverlap: true },
      axisLine: { lineStyle: { color: '#e7e5e4' } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { fontSize: 10, color: '#a8a29e' },
      splitLine: { lineStyle: { color: '#efeeec' } },
    },
    series: [
      {
        type: 'line',
        smooth: true,
        data: tl.map((p) => p.count),
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { color: '#4f46e5', width: 2 },
        itemStyle: { color: '#4f46e5' },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(79,70,229,0.22)' },
              { offset: 1, color: 'rgba(79,70,229,0.02)' },
            ],
          },
        },
      },
    ],
  }
})

async function load(): Promise<void> {
  err.value = ''
  try {
    stats.value = await fetchTelemetryStats(days.value)
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : String(e)
    stats.value = null
  }
}

onMounted(load)
</script>

<style scoped>
.telemetry-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-5);
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
}
.ts-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-3);
}
.ts-title {
  font-size: 16px;
  font-weight: 700;
  margin: 0;
}
.ts-sub {
  font-size: 12.5px;
  color: var(--text-muted);
  margin: 2px  0 0;
}
.ts-controls {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: nowrap;
  flex-shrink: 0;
}
.ts-total {
  font-size: 12.5px;
  color: var(--text-muted);
  white-space: nowrap;
}
.ts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}
.ts-block-wide {
  grid-column: 1 / -1;
}

.ts-block {
  padding: var(--space-4);
  background: var(--bg);
  border: 1px solid var(--border-faint);
  border-radius: var(--radius-sm);
  transition: border-color var(--dur-fast) var(--ease), background var(--dur-fast) var(--ease);
}
.ts-block:hover {
  border-color: var(--border);
  background: var(--bg-elev);
}
.ts-block--user {
  border-left: 3px solid var(--accent);
}
.ts-block--operator {
  border-left: 3px solid #0891b2;
}

.block-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-faint);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: var(--space-3);
}
.block-ic {
  color: var(--text-faint);
  flex-shrink: 0;
}
.ts-block--user .block-ic {
  color: var(--accent);
}
.ts-block--operator .block-ic {
  color: #0891b2;
}

.type-rows {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.type-row {
  display: grid;
  grid-template-columns: 70px 1fr 50px;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
}
.type-row--kv {
  grid-template-columns: 1fr auto;
  padding: 3px 0;
}
.type-bar-wrap {
  height: 8px;
  background: var(--bg-sunken);
  border-radius: 999px;
  overflow: hidden;
}
.type-bar {
  height: 100%;
  background: var(--accent);
  border-radius: 999px;
  transition: width var(--dur) var(--ease);
}
.type-count {
  text-align: right;
  color: var(--text);
  font-weight: 600;
}
.type-label {
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.top-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.top-item {
  display: grid;
  grid-template-columns: 24px 1fr auto auto;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  padding: 3px 6px;
  margin: 0 -6px;
}
.top-item--link {
  cursor: pointer;
  border-radius: 4px;
  transition: background var(--dur-fast) var(--ease);
}
.top-item--link:hover {
  background: var(--accent-soft);
}
.top-item--link:hover .top-id {
  color: var(--accent);
}
.top-rank {
  color: var(--text-faint);
  font-weight: 600;
}
.top-id {
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.top-type {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-sunken);
  padding: 1px 6px;
  border-radius: 4px;
}
.top-count {
  color: var(--text);
  font-weight: 600;
}

/* echarts 时间趋势 */
.trend-chart {
  width: 100%;
  height: 200px;
}
.trend-empty {
  height: 200px;
  display: grid;
  place-items: center;
  font-size: 12px;
  color: var(--text-faint);
  background: var(--bg-sunken);
  border-radius: var(--radius-sm);
}

.block-mini-empty {
  font-size: 11.5px;
  color: var(--text-faint);
  padding: var(--space-2) 0;
  text-align: center;
}

.ts-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-8) var(--space-4);
  text-align: center;
}
.ts-empty .state-icon {
  color: var(--text-faint);
  opacity: 0.55;
  margin-bottom: var(--space-1);
}
.empty-title {
  font-family: var(--display);
  font-size: 14px;
  font-weight: 600;
  color: var(--text-muted);
}
.empty-sub {
  font-size: 12.5px;
  color: var(--text-faint);
  max-width: 360px;
  line-height: 1.55;
}

.ts-err {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 12.5px;
  color: var(--danger);
  padding: var(--space-3) var(--space-4);
  background: rgba(220, 38, 38, 0.06);
  border: 1px solid rgba(220, 38, 38, 0.18);
  border-radius: var(--radius-sm);
}
.ts-err .state-icon {
  flex-shrink: 0;
}

@media (max-width: 720px) {
  .ts-grid {
    grid-template-columns: 1fr;
  }
}

.days-tabs {
  display: inline-flex;
  background: var(--bg-sunken);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 2px;
  gap: 2px;
  flex-shrink: 0;
}
.days-tab {
  border: none;
  background: transparent;
  font-size: 12px;
  font-family: var(--sans);
  color: var(--text-muted);
  padding: 4px 12px;
  border-radius: 4px;
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease);
}
.days-tab:hover {
  color: var(--text);
}
.days-tab--active {
  background: var(--bg-elev);
  color: var(--accent);
  font-weight: 600;
  box-shadow: var(--shadow-sm);
}
</style>
