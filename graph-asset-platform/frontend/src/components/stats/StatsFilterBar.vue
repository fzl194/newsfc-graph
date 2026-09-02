<template>
  <div class="sfb">
    <div class="sfb-item">
      <span class="sfb-l">物理网元</span>
      <el-select
        :model-value="model.nfs" multiple filterable clearable collapse-tags collapse-tags-tooltip
        size="small" placeholder="全部" class="sfb-sel"
        @update:model-value="set('nfs', $event as string[])"
      >
        <el-option v-for="n in options.nfs" :key="n" :label="n" :value="n" />
      </el-select>
    </div>
    <div class="sfb-item">
      <span class="sfb-l">版本</span>
      <el-select
        :model-value="model.versions" multiple filterable clearable collapse-tags collapse-tags-tooltip
        size="small" placeholder="全部（国内号）" class="sfb-sel"
        @update:model-value="set('versions', $event as string[])"
      >
        <el-option v-for="v in options.versions" :key="v" :label="v" :value="v" />
      </el-select>
    </div>
    <div v-if="withLogicalNe" class="sfb-item">
      <span class="sfb-l">逻辑网元</span>
      <el-select
        :model-value="model.logical_ne" filterable clearable size="small"
        placeholder="不限（仅命令/参数指标）" class="sfb-sel"
        @update:model-value="set('logical_ne', String($event ?? ''))"
      >
        <el-option v-for="l in logicalOptions" :key="l" :label="l" :value="l" />
      </el-select>
    </div>
    <el-switch
      :model-value="model.overseas" size="small" active-text="显示国外版本"
      @update:model-value="set('overseas', Boolean($event))"
    />
    <button class="sfb-reset" type="button" @click="emit('reset')">清空</button>
    <span class="sfb-hint">筛选联动卡片与下方表格；UPCF = 平台内 PCF</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElOption, ElSelect, ElSwitch } from 'element-plus'
import type { StatsFilterOptions } from '../../api'
import type { CardFilterState } from './shared'

const props = defineProps<{
  modelValue: CardFilterState
  options: StatsFilterOptions
  withLogicalNe?: boolean
}>()

const model = computed(() => props.modelValue)
const emit = defineEmits<{
  (e: 'update:modelValue', v: CardFilterState): void
  (e: 'reset'): void
}>()

/** 不可变更新：整对象替换（子组件不直接改父状态）。 */
function set<K extends keyof CardFilterState>(key: K, val: CardFilterState[K]): void {
  emit('update:modelValue', { ...props.modelValue, [key]: val })
}

/** 逻辑网元选项：按所选物理网元收窄（未选=全部物理网元的并集）。 */
const logicalOptions = computed(() => {
  const src = props.options.logical_nes
  const keys = props.modelValue.nfs.length ? props.modelValue.nfs : Object.keys(src)
  const s = new Set<string>()
  keys.forEach((k) => (src[k] ?? []).forEach((v) => s.add(v)))
  return [...s].sort()
})
</script>

<style scoped>
.sfb {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3) var(--space-4);
  padding: var(--space-3) var(--space-4);
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.sfb-item { display: flex; align-items: center; gap: var(--space-2); }
.sfb-l { font-size: 12px; color: var(--text-muted); white-space: nowrap; }
.sfb-sel { width: 190px; }
.sfb-reset {
  margin-left: auto;
  background: none;
  border: none;
  font-size: 11.5px;
  color: var(--text-faint);
  cursor: pointer;
  padding: 2px 4px;
}
.sfb-reset:hover { color: var(--accent); }
.sfb-hint { font-size: 11px; color: var(--text-faint); }
</style>
