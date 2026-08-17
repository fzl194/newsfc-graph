<template>
  <section class="stat-card stagger-in" :style="{ '--accent-bar': accent }">
    <header class="card-head">
      <span class="dot" :style="{ background: accent }" aria-hidden="true" />
      <h2 class="card-title">{{ title }}</h2>
      <span v-if="hint" class="card-hint">{{ hint }}</span>
    </header>

    <div class="card-total">
      <span class="total-num mono">{{ formatNum(total) }}</span>
      <span class="total-label">{{ totalLabel }}</span>
    </div>

    <div v-if="details.length" class="card-details">
      <div v-for="(d, i) in details" :key="i" class="detail-row">
        <span class="detail-label" :title="d.label">{{ d.label }}</span>
        <span class="detail-val mono">{{ formatNum(d.value) }}</span>
      </div>
    </div>

    <div v-if="!total && !details.length" class="card-empty">暂无数据</div>
  </section>
</template>

<script setup lang="ts">
// 通用统计卡：大数字总数 + 小字明细列表。前期纯数字展示，图表留后期。
export interface StatDetail {
  label: string
  value: number
}

interface Props {
  title: string
  total: number
  totalLabel?: string
  details?: StatDetail[]
  // 顶部色条 / 圆点强调色（CSS 颜色值，默认走强调色）
  accent?: string
  // 辅助说明（标题右侧小字）
  hint?: string
}

const props = withDefaults(defineProps<Props>(), {
  totalLabel: '总数',
  details: () => [],
  accent: '#4f46e5',
  hint: '',
})

function formatNum(n: number): string {
  return n.toLocaleString('zh-CN')
}

// 显式声明 details 用于模板（props 默认值在 withDefaults 下已保证非空，这里只是让模板读取更直接）
void props
</script>

<style scoped>
.stat-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-5);
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.stat-card::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: var(--accent-bar);
  opacity: 0.85;
}

.card-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 22px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.card-title {
  font-family: var(--display);
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  margin: 0;
  letter-spacing: -0.01em;
}

.card-hint {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-faint);
}

.card-total {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  padding: var(--space-1) 0;
}

.total-num {
  font-family: var(--display);
  font-size: 36px;
  font-weight: 700;
  line-height: 1;
  color: var(--text);
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums;
}

.total-label {
  font-size: 12px;
  color: var(--text-faint);
}

.card-details {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-faint);
  max-height: 220px;
  overflow-y: auto;
}

.detail-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: 3px 0;
  font-size: 12.5px;
}

.detail-label {
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.detail-val {
  color: var(--text);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

.card-empty {
  font-size: 12.5px;
  color: var(--text-faint);
  padding: var(--space-2) 0;
}
</style>
