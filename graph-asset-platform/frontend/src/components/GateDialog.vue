<template>
  <el-dialog
    :model-value="visible"
    title="入库门禁 · 差异确认"
    width="720px"
    :close-on-click-modal="false"
    @update:model-value="(v: boolean) => emit('update:visible', v)"
  >
    <div v-if="job" class="gate-body">
      <div class="gate-meta mono">
        {{ targetLabel }} · 抽取器 {{ scriptName }}
      </div>

      <div class="stat-grid gate-stats">
        <div class="stat gate-new">
          <div class="stat-val">{{ newTotal }}</div>
          <div class="stat-label">纯新增</div>
        </div>
        <div class="stat gate-same">
          <div class="stat-val">{{ identicalTotal }}</div>
          <div class="stat-label">内容一致</div>
        </div>
        <div class="stat gate-mod">
          <div class="stat-val">{{ modifiedTotal }}</div>
          <div class="stat-label">有差异</div>
        </div>
      </div>

      <div v-if="newByLayer.length" class="gate-layers">
        新增分布：
        <span v-for="l in newByLayer" :key="l.k" class="gate-chip mono">{{ l.k }} +{{ l.v }}</span>
      </div>

      <div v-if="modifiedTotal" class="gate-mod-block">
        <div class="gate-mod-head">
          差异文件（前 {{ modifiedList.length }}{{ modifiedList.length < modifiedTotal ? ` / 共 ${modifiedTotal}` : '' }}）
        </div>
        <ul class="gate-mod-list">
          <li v-for="m in modifiedList" :key="m.path" class="gate-mod-row">
            <span class="mono gate-path" :title="m.path">{{ m.path }}</span>
            <span v-if="m.binary" class="gate-diff mono bin">
              二进制 {{ m.old_bytes ?? '?' }}B → {{ m.new_bytes ?? '?' }}B
            </span>
            <span v-else class="gate-diff mono">
              <span class="plus">+{{ m.plus ?? 0 }}</span>
              <span class="minus">−{{ m.minus ?? 0 }}</span>
            </span>
          </li>
        </ul>
      </div>
      <div v-else class="hint">无内容差异——重抽同目录的常见形态（产出与现有完全一致）。</div>

      <div class="gate-note">
        涉及层：{{ layersLabel }}；内容一致的文件不会重复写入；
        覆盖的旧版会自动备份（历史任务可「移除产出」回退）。`_` 前缀构建清单自动同步。
      </div>
    </div>

    <template #footer>
      <div class="gate-footer">
        <button class="ghost-btn2" :disabled="acting" @click="doCancel">撤销（不入库）</button>
        <button
          class="ghost-btn2 gate-btn-new"
          :disabled="acting || !r.new_total"
          :title="r.new_total ? undefined : '无新增文件'"
          @click="doConfirm('new_only')"
        >只新增（重复保留现有）</button>
        <button
          class="primary-btn"
          :disabled="acting || !(newTotal + modifiedTotal)"
          @click="doConfirm('overwrite')"
        >{{ acting ? '执行中…' : '一键覆盖' }}</button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElDialog, ElMessage } from 'element-plus'
import { cancelExtract, confirmExtract, type GateModified, type ImportJob } from '../api'

const props = defineProps<{ visible: boolean; job: ImportJob | null }>()
const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'resolved', action: 'overwrite' | 'new_only' | 'cancel'): void
}>()

const acting = ref(false)

interface GateResult {
  stage?: string
  script?: string
  script_name?: string
  bundle?: string
  target_nf?: string
  target_version?: string
  layers?: string[]
  new_total?: number
  new_by_layer?: Record<string, number>
  identical_total?: number
  modified_total?: number
  modified?: GateModified[]
}

const r = computed<GateResult>(() => ((props.job?.result ?? {}) as GateResult))
const targetLabel = computed(() => `${r.value.target_nf ?? '?'}@${r.value.target_version ?? '?'}`)
const scriptName = computed(() => r.value.script_name ?? r.value.script ?? '?')
const newByLayer = computed(() =>
  Object.entries(r.value.new_by_layer ?? {}).map(([k, v]) => ({ k, v })))
// 模板用非空形态（result 缺键时按 0/空渲染）
const newTotal = computed(() => r.value.new_total ?? 0)
const identicalTotal = computed(() => r.value.identical_total ?? 0)
const modifiedTotal = computed(() => r.value.modified_total ?? 0)
const modifiedList = computed<GateModified[]>(() => r.value.modified ?? [])
const layersLabel = computed(() => (r.value.layers ?? []).join(' + '))

function errMsg(e: unknown): string {
  const detail = (e as { detail?: unknown }).detail
  if (detail && typeof detail === 'object' && 'message' in detail) {
    return String((detail as { message: unknown }).message)
  }
  return e instanceof Error ? e.message : String(e)
}

async function doConfirm(action: 'overwrite' | 'new_only'): Promise<void> {
  if (!props.job) return
  acting.value = true
  try {
    await confirmExtract(props.job.job_id, action)
    emit('resolved', action)
    emit('update:visible', false)
  } catch (e) {
    ElMessage.error(errMsg(e)) // 保持弹窗——确认失败可重试/改选
  } finally {
    acting.value = false
  }
}

async function doCancel(): Promise<void> {
  if (!props.job) return
  acting.value = true
  try {
    await cancelExtract(props.job.job_id)
    emit('resolved', 'cancel')
    emit('update:visible', false)
  } catch (e) {
    ElMessage.error(errMsg(e))
  } finally {
    acting.value = false
  }
}
</script>

<style scoped>
.gate-body { display: flex; flex-direction: column; gap: var(--space-3); }
.gate-meta { font-size: 12px; color: var(--text-muted); }
.stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-3); }
.stat { display: flex; flex-direction: column; align-items: center; gap: 4px; padding: var(--space-3); border: 1px solid var(--border); border-radius: var(--radius-sm); }
.stat-val { font-family: var(--display); font-size: 26px; font-weight: 700; line-height: 1; }
.stat-label { font-size: 11.5px; color: var(--text-muted); }
.gate-new .stat-val { color: var(--success); }
.gate-same .stat-val { color: var(--text-faint); }
.gate-mod .stat-val { color: var(--warn); }
.gate-layers { font-size: 12px; color: var(--text-muted); display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.gate-chip { background: var(--bg-sunken); border-radius: 4px; padding: 1px 8px; font-size: 11px; }
.gate-mod-block { border: 1px solid var(--border-faint); border-radius: var(--radius-sm); overflow: hidden; }
.gate-mod-head { font-size: 12px; font-weight: 600; color: var(--warn); padding: var(--space-2) var(--space-3); background: var(--bg-sunken); }
.gate-mod-list { list-style: none; margin: 0; padding: 0; max-height: 300px; overflow: auto; }
.gate-mod-row { display: flex; align-items: center; gap: var(--space-3); padding: 6px var(--space-3); border-bottom: 1px solid var(--border-faint); font-size: 12px; }
.gate-mod-row:last-child { border-bottom: none; }
.gate-path { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text); }
.gate-diff { flex-shrink: 0; font-size: 11.5px; }
.gate-diff .plus { color: var(--success); }
.gate-diff .minus { color: var(--danger); }
.gate-diff.bin { color: var(--text-muted); }
.gate-note { font-size: 11px; color: var(--text-faint); line-height: 1.6; background: var(--bg-sunken); border-radius: var(--radius-sm); padding: var(--space-2) var(--space-3); }
.hint { font-size: 12px; color: var(--text-faint); }
.gate-footer { display: flex; justify-content: flex-end; gap: var(--space-3); align-items: center; }
.ghost-btn2 { font-size: 12.5px; border: 1px solid var(--border-strong); background: var(--bg-elev); color: var(--text-muted); border-radius: var(--radius-sm); padding: 6px 14px; cursor: pointer; }
.ghost-btn2:hover:not(:disabled) { color: var(--accent); border-color: var(--accent); }
.ghost-btn2:disabled { opacity: 0.5; cursor: not-allowed; }
.gate-btn-new { color: var(--warn); border-color: var(--warn); }
.gate-btn-new:hover:not(:disabled) { color: var(--warn); border-color: var(--warn); }
.primary-btn { font-size: 13px; border-radius: var(--radius-sm); cursor: pointer; background: var(--accent); border: 1px solid var(--accent); color: #fff; padding: 6px 18px; }
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
