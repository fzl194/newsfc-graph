<template>
  <div v-if="jobs.length" class="pd-history">
    <div class="pd-history-head">
      <span class="pd-job-title">历史任务</span>
      <span class="hint">点击查看详情；完成/失败可删除，进行中不可</span>
    </div>
    <ul class="pd-hlist">
      <li
        v-for="j in jobs"
        :key="j.job_id"
        class="pd-hrow"
        :class="{ cur: j.job_id === activeId }"
        @click="emit('view', j)"
      >
        <span class="pd-status" :class="`pd-${j.status}`">
          {{ j.status === 'processing' ? '进行中' : j.status === 'done' ? '完成' : '失败' }}
        </span>
        <span class="pd-hnf mono">{{ j.nf }} {{ j.version }}</span>
        <span class="pd-htime">{{ fmtTs(j.started_at) }}</span>
        <span class="pd-hsteps mono">
          {{ j.steps.filter((s) => s.status === 'done').length }}/{{ j.steps.length || '—' }} 步
        </span>
        <button
          v-if="j.status !== 'processing'"
          class="link-btn pd-del"
          @click.stop="emit('remove', j)"
        >删除</button>
        <span v-else class="pd-running-tag mono">处理中…</span>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import type { ImportJob } from '../api'

defineProps<{ jobs: ImportJob[]; activeId?: string }>()
const emit = defineEmits<{
  (e: 'view', j: ImportJob): void
  (e: 'remove', j: ImportJob): void
}>()

function fmtTs(ts: number): string {
  return ts ? new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false }) : ''
}
</script>

<style scoped>
.pd-history { border-top: 1px solid var(--border-faint); padding-top: var(--space-4); display: flex; flex-direction: column; gap: var(--space-2); }
.pd-history-head { display: flex; align-items: baseline; gap: var(--space-3); }
.pd-job-title { font-family: var(--display); font-weight: 600; font-size: 13.5px; }
.hint { font-size: 11px; color: var(--text-faint); }
.pd-hlist { list-style: none; margin: 0; padding: 0; }
.pd-hrow { display: flex; align-items: center; gap: var(--space-3); padding: 7px 10px; border-bottom: 1px solid var(--border-faint); cursor: pointer; font-size: 12px; transition: background var(--dur-fast) var(--ease); }
.pd-hrow:hover { background: var(--bg-hover); }
.pd-hrow.cur { background: var(--accent-soft); }
.pd-status { font-size: 11px; font-weight: 600; padding: 2px 10px; border-radius: 999px; flex-shrink: 0; }
.pd-processing { background: var(--accent-soft); color: var(--accent); }
.pd-done { background: rgba(16, 185, 129, 0.12); color: var(--success); }
.pd-failed { background: #fef2f2; color: var(--danger); }
.pd-hnf { color: var(--text); min-width: 110px; }
.pd-htime { color: var(--text-faint); font-size: 11px; flex: 1; }
.pd-hsteps { color: var(--text-faint); font-size: 11px; }
.pd-running-tag { color: var(--accent); font-size: 11px; }
.pd-del { flex-shrink: 0; }
.link-btn { background: none; border: none; color: var(--accent); font-size: 11.5px; cursor: pointer; padding: 0; }
</style>
