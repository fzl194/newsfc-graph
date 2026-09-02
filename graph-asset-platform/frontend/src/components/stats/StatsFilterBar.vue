<template>
  <div class="sfb">
    <div class="sfb-row">
      <div class="sfb-item">
        <span class="sfb-l">物理网元</span>
        <el-select
          :model-value="model.nfs" multiple filterable clearable collapse-tags collapse-tags-tooltip
          size="small" placeholder="全部" class="sfb-sel" @update:model-value="set('nfs', $event as string[])"
        >
          <el-option v-for="n in options.nfs" :key="n" :label="n" :value="n" />
        </el-select>
      </div>
      <div v-if="view !== 'business'" class="sfb-item">
        <span class="sfb-l">版本</span>
        <el-select
          :model-value="model.versions" multiple filterable clearable collapse-tags collapse-tags-tooltip
          size="small" placeholder="全部（国内号）" class="sfb-sel" @update:model-value="set('versions', $event as string[])"
        >
          <el-option v-for="v in options.versions" :key="v" :label="v" :value="v" />
        </el-select>
      </div>
      <div v-if="view === 'command'" class="sfb-item">
        <span class="sfb-l">逻辑网元</span>
        <el-select
          :model-value="model.logical_ne" filterable clearable size="small"
          placeholder="不限（仅命令/参数指标）" class="sfb-sel"
          @update:model-value="set('logical_ne', String($event ?? ''))"
        >
          <el-option v-for="l in logicalOptions" :key="l" :label="l" :value="l" />
        </el-select>
      </div>
      <div class="sfb-item">
        <span class="sfb-l">对象类型</span>
        <el-select
          :model-value="model.object_types" multiple filterable clearable collapse-tags collapse-tags-tooltip
          size="small" placeholder="全部" class="sfb-sel" @update:model-value="set('object_types', $event as string[])"
        >
          <el-option v-for="t in options.object_types" :key="t" :label="t" :value="t" />
        </el-select>
      </div>
      <div class="sfb-item">
        <span class="sfb-l">关系类型</span>
        <el-select
          :model-value="model.relations" multiple filterable clearable collapse-tags collapse-tags-tooltip
          size="small" placeholder="全部" class="sfb-sel" @update:model-value="set('relations', $event as string[])"
        >
          <el-option v-for="r in options.relations" :key="r" :label="r" :value="r" />
        </el-select>
      </div>
      <div v-if="view === 'command'" class="sfb-item">
        <span class="sfb-l">规则类型</span>
        <el-select
          :model-value="model.rule_types" multiple filterable clearable collapse-tags collapse-tags-tooltip
          size="small" placeholder="全部" class="sfb-sel" @update:model-value="set('rule_types', $event as string[])"
        >
          <el-option v-for="r in options.rule_types" :key="r.key" :label="r.label" :value="r.key" />
        </el-select>
      </div>
      <template v-if="view === 'business'">
        <div class="sfb-item">
          <span class="sfb-l">业务域</span>
          <el-select
            :model-value="model.domain" filterable clearable size="small" placeholder="全部"
            class="sfb-sel sfb-narrow" @update:model-value="onDomain(String($event ?? ''))"
          >
            <el-option v-for="dm in options.domains" :key="dm" :label="dm" :value="dm" />
          </el-select>
        </div>
        <div class="sfb-item">
          <span class="sfb-l">场景</span>
          <el-select
            :model-value="model.scenario" filterable clearable size="small" placeholder="全部"
            class="sfb-sel sfb-narrow" @update:model-value="onScenario(String($event ?? ''))"
          >
            <el-option v-for="sc in options.scenarios" :key="sc" :label="sc" :value="sc" />
          </el-select>
        </div>
        <div class="sfb-item">
          <span class="sfb-l">方案</span>
          <el-select
            :model-value="model.solution" filterable clearable size="small" placeholder="全部"
            class="sfb-sel" @update:model-value="set('solution', String($event ?? ''))"
          >
            <el-option
              v-for="s in solutionOptions" :key="`${s.domain}/${s.scenario}/${s.name}`"
              :label="s.name" :value="s.name"
            />
          </el-select>
        </div>
      </template>
      <button class="sfb-reset" type="button" @click="emit('reset')">清空筛选</button>
    </div>
    <div class="sfb-foot">
      <el-switch
        :model-value="model.overseas" size="small" active-text="显示国外版本"
        @update:model-value="set('overseas', Boolean($event))"
      />
      <span class="sfb-hint">筛选/分组恒用国内版本号，开关仅切换展示值；UPCF = 平台内 PCF</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElOption, ElSelect, ElSwitch } from 'element-plus'
import type { StatsFilterOptions, StatsViewKey } from '../../api'
import type { StatsFilterState } from './shared'

const props = defineProps<{
  modelValue: StatsFilterState
  options: StatsFilterOptions
  view: StatsViewKey
}>()

const model = computed(() => props.modelValue)
const emit = defineEmits<{
  (e: 'update:modelValue', v: StatsFilterState): void
  (e: 'reset'): void
}>()

/** 不可变更新：整对象替换（子组件不直接改父状态）。 */
function set<K extends keyof StatsFilterState>(key: K, val: StatsFilterState[K]): void {
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

const solutionOptions = computed(() =>
  props.options.solutions.filter(
    (s) =>
      (!props.modelValue.domain || s.domain === props.modelValue.domain) &&
      (!props.modelValue.scenario || s.scenario === props.modelValue.scenario),
  ),
)

/** 域/场景级联：改上级时清空下级，避免留下失效组合。 */
function onDomain(v: string): void {
  emit('update:modelValue', { ...props.modelValue, domain: v, scenario: '', solution: '' })
}
function onScenario(v: string): void {
  emit('update:modelValue', { ...props.modelValue, scenario: v, solution: '' })
}
</script>

<style scoped>
.sfb {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.sfb-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3) var(--space-4);
}
.sfb-item { display: flex; align-items: center; gap: var(--space-2); }
.sfb-l { font-size: 12px; color: var(--text-muted); white-space: nowrap; }
.sfb-sel { width: 200px; }
.sfb-narrow { width: 150px; }
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
.sfb-foot { display: flex; align-items: center; gap: var(--space-3); border-top: 1px solid var(--border-faint); padding-top: var(--space-2); }
.sfb-hint { font-size: 11px; color: var(--text-faint); }
</style>
