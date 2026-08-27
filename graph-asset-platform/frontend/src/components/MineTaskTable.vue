<template>
  <div v-if="jobs.length" class="mtt">
    <div class="mtt-head">
      <span class="mtt-title">抽取任务</span>
      <span class="mtt-hint">行展开看差异明细；确认/回退为后台执行；上一任务完结前不可发起下一个</span>
    </div>
    <el-table :data="jobs" size="small" row-key="job_id">
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="mtt-detail">
            <ol class="mtt-steps">
              <li v-for="s in row.steps" :key="s.name" class="mtt-step" :class="`st-${s.status}`">
                <span class="dot">{{ s.status === 'done' ? '✓' : '…' }}</span>
                <span class="name">{{ s.name }}</span>
                <span v-if="s.detail" class="detail">{{ s.detail }}</span>
              </li>
            </ol>
            <div v-if="isAwaiting(J(row)) && modified(J(row)).length" class="mtt-diff">
              <div class="mtt-diff-head">差异文件（{{ modified(J(row)).length }}{{ modified(J(row)).length < num(J(row), 'modified_total') ? ` / 共 ${num(J(row), 'modified_total')}` : '' }}）</div>
              <ul class="mtt-diff-list">
                <li v-for="m in modified(J(row))" :key="m.path" class="mtt-diff-row">
                  <span class="mono path" :title="m.path">{{ m.path }}</span>
                  <span v-if="m.binary" class="mono diff bin">{{ m.old_bytes ?? '?' }}B → {{ m.new_bytes ?? '?' }}B</span>
                  <span v-else class="mono diff"><span class="plus">+{{ m.plus ?? 0 }}</span><span class="minus">−{{ m.minus ?? 0 }}</span></span>
                </li>
              </ul>
            </div>
            <div v-if="row.warnings.length" class="mtt-warns">
              <div class="mtt-diff-head warn">警告（{{ row.warnings.length }}）</div>
              <ul class="mtt-warn-list">
                <li v-for="(w, i) in row.warnings" :key="i" class="mono">{{ w }}</li>
              </ul>
            </div>
            <div v-if="row.status === 'failed'" class="error-banner mono mtt-err">{{ row.error }}</div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="86">
        <template #default="{ row }">
          <span class="pd-status" :class="`pd-${row.status}`">{{ statusLabel(J(row)) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="目标" min-width="150">
        <template #default="{ row }">
          <span class="mono mtt-target">{{ row.nf }}@{{ row.version }}</span>
          <span class="mtt-script">{{ scriptName(J(row)) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="摘要" min-width="190">
        <template #default="{ row }">
          <span class="mtt-summary" :title="summaryTitle(J(row))">{{ summary(J(row)) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="时间" width="140">
        <template #default="{ row }">{{ fmtTs(row.started_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="250" align="right">
        <template #default="{ row }">
          <template v-if="isAwaiting(J(row))">
            <button class="link-btn danger" :disabled="actingId === row.job_id" @click="doCancel(J(row))">撤销</button>
            <button
              class="link-btn warn"
              :disabled="actingId === row.job_id || !num(J(row), 'new_total')"
              :title="num(J(row), 'new_total') ? undefined : '无新增文件'"
              @click="doConfirm(J(row), 'new_only')"
            >只新增</button>
            <button
              class="link-btn primary"
              :disabled="actingId === row.job_id || !(num(J(row), 'new_total') + num(J(row), 'modified_total'))"
              @click="doConfirm(J(row), 'overwrite')"
            >一键覆盖</button>
          </template>
          <template v-else>
            <button v-if="canRevert(J(row))" class="link-btn warn" :disabled="actingId === row.job_id" @click="doRevert(J(row))">移除产出</button>
            <button
              v-if="!['processing', 'awaiting'].includes(row.status)"
              class="link-btn"
              :disabled="actingId === row.job_id"
              @click="doDelete(J(row))"
            >删除</button>
            <span v-if="row.status === 'processing'" class="mtt-busy mono">执行中…</span>
          </template>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElTable, ElTableColumn, ElMessage, ElMessageBox } from 'element-plus'
import {
  cancelExtract,
  confirmExtract,
  deleteImportJob,
  revertExtract,
  type GateModified,
  type ImportJob,
} from '../api'

defineProps<{ jobs: ImportJob[] }>()
const emit = defineEmits<{ (e: 'changed'): void }>()

const actingId = ref('')

/** el-table 插槽 row 类型为 DefaultRow——统一转 ImportJob */
function J(row: unknown): ImportJob {
  return row as ImportJob
}

// ---- 展示 ----

function res(row: ImportJob): Record<string, unknown> {
  return (row.result ?? {}) as Record<string, unknown>
}
function num(row: ImportJob, k: string): number {
  return typeof res(row)[k] === 'number' ? (res(row)[k] as number) : 0
}
function isAwaiting(row: ImportJob): boolean {
  return row.status === 'awaiting'
}
function modified(row: ImportJob): GateModified[] {
  return (res(row).modified as GateModified[] | undefined) ?? []
}
function scriptName(row: ImportJob): string {
  return (res(row).script_name as string | undefined) ?? (res(row).script as string | undefined) ?? ''
}
function statusLabel(row: ImportJob): string {
  switch (row.status) {
    case 'processing':
      return res(row).stage === 'applying' ? '入库中' : res(row).stage === 'reverting' ? '回退中' : '抽取中'
    case 'awaiting': return '待确认'
    case 'done': return res(row).reverted_at ? '已回退' : '完成'
    case 'failed': return '失败'
    case 'cancelled': return '已撤销'
    default: return row.status
  }
}
function summary(row: ImportJob): string {
  if (isAwaiting(row)) {
    return `新 ${num(row, 'new_total')} · 同 ${num(row, 'identical_total')} · 异 ${num(row, 'modified_total')}`
  }
  if (row.status === 'processing') {
    if (res(row).stage === 'applying') return '入库执行中（后台）…'
    if (res(row).stage === 'reverting') return '回退执行中（后台）…'
    const done = row.steps.filter((s) => s.status === 'done').length
    return `${done}/${row.steps.length || '—'} 步`
  }
  if (row.status === 'done') {
    if (res(row).reverted_at) {
      const rv = (res(row).revert ?? {}) as Record<string, unknown>
      const skipped = Array.isArray(rv.skipped) ? (rv.skipped as unknown[]).length : 0
      return `已移除产出（软删 ${rv.soft_deleted ?? 0} · 还原 ${rv.restored ?? 0}${skipped ? ` · 跳过 ${skipped}` : ''}）`
    }
    return `入库 ${num(row, 'total')} 个`
  }
  if (row.status === 'failed') return (row.error || '').split('\n')[0].slice(0, 48)
  if (row.status === 'cancelled') return '未入库（已撤销）'
  return ''
}
function summaryTitle(row: ImportJob): string {
  return row.status === 'failed' ? row.error : summary(row)
}
function canRevert(row: ImportJob): boolean {
  return row.status === 'done' && !!res(row).script && !res(row).reverted_at
}
function fmtTs(ts: number): string {
  return ts ? new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false }) : ''
}

// ---- 操作（确认/回退立即返回，后台执行；父组件轮询刷新） ----

function errMsg(e: unknown): string {
  const detail = (e as { detail?: unknown }).detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object' && 'message' in detail) {
    return String((detail as { message: unknown }).message)
  }
  return e instanceof Error ? e.message : String(e)
}

async function withActing(jobId: string, fn: () => Promise<void>): Promise<void> {
  actingId.value = jobId
  try {
    await fn()
  } catch (e) {
    ElMessage.error(errMsg(e))
  } finally {
    actingId.value = ''
  }
}

function doConfirm(row: ImportJob, action: 'overwrite' | 'new_only'): void {
  void withActing(row.job_id, async () => {
    await confirmExtract(row.job_id, action)
    ElMessage.success(action === 'overwrite' ? '已提交入库（后台执行，覆盖旧版已备份）' : '已提交入库（后台执行，只新增）')
    emit('changed')
  })
}

function doCancel(row: ImportJob): void {
  void withActing(row.job_id, async () => {
    await ElMessageBox.confirm('撤销后本次产出不入库，正式资产无任何改动。继续？', '撤销抽取', { type: 'warning' })
    await cancelExtract(row.job_id)
    ElMessage.info('已撤销——未入库')
    emit('changed')
  })
}

function doRevert(row: ImportJob): void {
  void withActing(row.job_id, async () => {
    await ElMessageBox.confirm(
      '将软删除本次新增的文件（进回收站）、还原本次覆盖的文件；已被后续任务改动的自动跳过。后台执行。继续？',
      '移除本次产出', { type: 'warning' })
    await revertExtract(row.job_id)
    ElMessage.success('已提交回退（后台执行）')
    emit('changed')
  })
}

function doDelete(row: ImportJob): void {
  void withActing(row.job_id, async () => {
    if (canRevert(row)) {
      await ElMessageBox.confirm(
        '删除后该任务的「移除产出」回退能力随之丧失（旧版备份一并清理）。继续？',
        '删除抽取任务', { type: 'warning' })
    }
    await deleteImportJob(row.job_id)
    ElMessage.success('已删除任务')
    emit('changed')
  })
}
</script>

<style scoped>
.mtt { border-top: 1px solid var(--border-faint); padding-top: var(--space-4); display: flex; flex-direction: column; gap: var(--space-2); }
.mtt-head { display: flex; align-items: baseline; gap: var(--space-3); flex-wrap: wrap; }
.mtt-title { font-family: var(--display); font-weight: 600; font-size: 13.5px; }
.mtt-hint { font-size: 11px; color: var(--text-faint); }
.mtt-target { color: var(--text); font-weight: 600; font-size: 12px; }
.mtt-script { color: var(--text-faint); font-size: 11px; margin-left: 6px; }
.mtt-summary { font-size: 12px; color: var(--text-muted); }
.mtt-busy { color: var(--accent); font-size: 11px; }
.mtt-detail { padding: var(--space-2) var(--space-4); display: flex; flex-direction: column; gap: var(--space-3); }
.mtt-steps { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.mtt-step { display: flex; align-items: baseline; gap: 8px; font-size: 12px; color: var(--text-muted); }
.mtt-step.st-done { color: var(--text); }
.mtt-step .dot { width: 16px; text-align: center; color: var(--success); flex-shrink: 0; }
.mtt-step .detail { font-size: 11px; color: var(--text-faint); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mtt-diff-head { font-size: 12px; font-weight: 600; color: var(--warn); margin-bottom: var(--space-1); }
.mtt-diff-head.warn { color: var(--warn); }
.mtt-diff-list, .mtt-warn-list { list-style: none; margin: 0; padding: 0; max-height: 240px; overflow: auto; border: 1px solid var(--border-faint); border-radius: var(--radius-sm); }
.mtt-diff-row { display: flex; align-items: center; gap: var(--space-3); padding: 5px var(--space-3); border-bottom: 1px solid var(--border-faint); font-size: 12px; }
.mtt-diff-row:last-child { border-bottom: none; }
.mtt-diff-row .path { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text); }
.mtt-diff-row .diff { flex-shrink: 0; font-size: 11.5px; }
.mtt-diff-row .diff .plus { color: var(--success); }
.mtt-diff-row .diff .minus { color: var(--danger); }
.mtt-diff-row .diff.bin { color: var(--text-muted); }
.mtt-warn-list { padding: var(--space-2); display: flex; flex-direction: column; gap: 4px; }
.mtt-warn-list li { font-size: 11px; color: var(--text-muted); word-break: break-all; background: var(--bg-sunken); padding: var(--space-1) var(--space-2); border-radius: var(--radius-sm); }
.mtt-err { white-space: pre-wrap; word-break: break-all; }
.pd-status { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
.pd-processing { background: var(--accent-soft); color: var(--accent); }
.pd-awaiting { background: rgba(245, 158, 11, 0.14); color: var(--warn); }
.pd-done { background: rgba(16, 185, 129, 0.12); color: var(--success); }
.pd-failed { background: #fef2f2; color: var(--danger); }
.pd-cancelled { background: var(--bg-sunken); color: var(--text-faint); }
.error-banner { background: #fef2f2; border: 1px solid #fecaca; color: var(--danger); padding: var(--space-2) var(--space-3); border-radius: var(--radius-sm); font-size: 12px; }
.link-btn { background: none; border: none; font-size: 11.5px; cursor: pointer; padding: 0; margin-left: 10px; color: var(--accent); }
.link-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.link-btn.primary { font-weight: 600; }
.link-btn.warn { color: var(--warn); }
.link-btn.danger { color: var(--danger); }
</style>
