<template>
  <div v-if="job" class="pd-job">
    <div class="pd-job-head">
      <span class="pd-job-title">任务进度</span>
      <span class="mono pd-job-id">{{ job.job_id }} · {{ job.nf }} {{ job.version }}</span>
      <span class="pd-status" :class="`pd-${job.status}`">
        {{ job.status === 'processing' ? '进行中' : job.status === 'done' ? '完成' : '失败' }}
      </span>
    </div>
    <ol class="pd-steps">
      <li v-for="s in job.steps" :key="s.name" class="pd-step" :class="`pd-${s.status}`">
        <span class="pd-step-dot">{{ s.status === 'done' ? '✓' : s.status === 'processing' ? '…' : '·' }}</span>
        <span class="pd-step-name">{{ s.name }}</span>
        <span v-if="s.detail" class="pd-step-detail">{{ s.detail }}</span>
      </li>
    </ol>
    <div v-if="job.status === 'done' && statRows.length" class="stat-grid pd-stats">
      <div v-for="r in statRows" :key="r.k" class="stat">
        <div class="stat-val">{{ r.v }}</div>
        <div class="stat-label">{{ r.k }}</div>
      </div>
    </div>
    <div v-if="job.status === 'done'" class="pd-done-hint">{{ doneHint }}</div>
    <div v-if="job.warnings.length" class="warnings">
      <div class="warn-head">警告 ({{ job.warnings.length }})</div>
      <ul class="warn-list">
        <li v-for="(w, i) in job.warnings" :key="i" class="warn-item mono">{{ w }}</li>
      </ul>
    </div>
    <div v-if="job.status === 'failed'" class="error-banner mono pd-err">{{ job.error }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ImportJob } from '../api'

const props = defineProps<{
  job: ImportJob | null
  /** 结果统计取值键与展示名；mine 模式嵌套在 result.layers 里，两处都找 */
  statsLabels: Array<{ k: string; label: string }>
  doneHint: string
}>()

defineEmits<{ (e: 'refresh-history'): void }>()

const statRows = computed(() => {
  const r = (props.job?.result ?? {}) as Record<string, unknown>
  const layers = (r.layers ?? {}) as Record<string, number>
  return props.statsLabels
    .filter(({ k }) => (typeof r[k] === 'number' && r[k] !== null) || typeof layers[k] === 'number')
    .map(({ k, label }) => {
      const v = typeof r[k] === 'number' ? (r[k] as number) : layers[k]
      return { k: label, v }
    })
})
</script>

<style scoped>
.pd-job { border-top: 1px solid var(--border-faint); padding-top: var(--space-4); display: flex; flex-direction: column; gap: var(--space-3); }
.pd-job-head { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
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
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(90px, 1fr)); gap: var(--space-3); }
.stat { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.stat-val { font-family: var(--display); font-size: 24px; font-weight: 700; line-height: 1; color: var(--accent); }
.stat-label { font-size: 11.5px; color: var(--text-muted); }
.pd-done-hint { font-size: 12px; color: var(--text-muted); background: var(--bg-sunken); border-radius: var(--radius-sm); padding: var(--space-2) var(--space-3); }
.warnings { border-top: 1px solid var(--border-faint); padding-top: var(--space-3); }
.warn-head { font-size: 12px; font-weight: 600; color: var(--warn); margin-bottom: var(--space-2); }
.warn-list { list-style: none; margin: 0; padding: 0; max-height: 160px; overflow: auto; display: flex; flex-direction: column; gap: 4px; }
.warn-item { font-size: 11px; color: var(--text-muted); background: var(--bg-sunken); padding: var(--space-2) var(--space-3); border-radius: var(--radius-sm); word-break: break-all; }
.error-banner { background: #fef2f2; border: 1px solid #fecaca; color: var(--danger); padding: var(--space-3) var(--space-4); border-radius: var(--radius-sm); font-size: 12.5px; }
.pd-err { white-space: pre-wrap; word-break: break-all; }
</style>
