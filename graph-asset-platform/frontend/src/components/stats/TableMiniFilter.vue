<template>
  <div class="tmf">
    <el-select
      :model-value="model.nfs" multiple collapse-tags collapse-tags-tooltip clearable filterable
      size="small" placeholder="网元" class="tmf-sel" @update:model-value="set('nfs', $event as string[])"
    >
      <el-option v-for="n in options.nfs" :key="n" :label="n" :value="n" />
    </el-select>
    <el-select
      :model-value="model.versions" multiple collapse-tags collapse-tags-tooltip clearable filterable
      size="small" placeholder="版本" class="tmf-sel" @update:model-value="set('versions', $event as string[])"
    >
      <el-option v-for="v in options.versions" :key="v" :label="v" :value="v" />
    </el-select>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElOption, ElSelect } from 'element-plus'
import type { StatsFilterOptions } from '../../api'

const props = defineProps<{
  modelValue: { nfs: string[]; versions: string[] }
  options: StatsFilterOptions
}>()

const model = computed(() => props.modelValue)
const emit = defineEmits<{ (e: 'update:modelValue', v: { nfs: string[]; versions: string[] }): void }>()

function set<K extends 'nfs' | 'versions'>(key: K, val: string[]): void {
  emit('update:modelValue', { ...props.modelValue, [key]: val })
}
</script>

<style scoped>
.tmf { display: flex; align-items: center; gap: var(--space-2); }
.tmf-sel { width: 130px; }
</style>
