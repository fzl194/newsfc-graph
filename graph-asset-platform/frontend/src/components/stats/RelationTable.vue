<template>
  <div class="rt">
    <div class="rt-head">
      <span class="rt-title">{{ title }}</span>
      <span v-if="hint" class="rt-hint">{{ hint }}</span>
    </div>
    <el-table :data="tableRows" size="small" max-height="360" :default-sort="{ prop: 'count', order: 'descending' }">
      <el-table-column prop="relation" label="关系" min-width="170" sortable />
      <el-table-column prop="count" label="计数" width="110" sortable align="right">
        <template #default="{ row }">
          <span class="mono">{{ fmt(row.count) }}</span>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElTable, ElTableColumn } from 'element-plus'
import { fmt } from './shared'

const props = defineProps<{
  title: string
  rows: [string, number][]
  hint?: string
}>()

const tableRows = computed(() =>
  props.rows.map(([relation, count]) => ({ relation, count })),
)
</script>

<script lang="ts">
export default { name: 'RelationTable' }
</script>

<style scoped>
.rt { display: flex; flex-direction: column; gap: var(--space-2); min-width: 0; }
.rt-head { display: flex; align-items: baseline; gap: var(--space-3); }
.rt-title { font-family: var(--display); font-size: 13.5px; font-weight: 600; color: var(--text); }
.rt-hint { font-size: 11px; color: var(--text-faint); }
</style>
