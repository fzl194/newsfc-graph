<template>
  <div class="tab">
    <!-- 统计卡片（无筛选；D7/D7b 已按用户要求删除） -->
    <div v-loading="loading" class="cards">
      <StatCard title="业务主线" :total="d?.counts.solutions ?? 0" total-label="方案数（D3）"
        :details="[
          { label: '业务域数（D1）', value: d?.counts.domains ?? 0 },
          { label: '场景数（D2）', value: d?.counts.scenarios ?? 0 },
        ]" accent="#4f46e5" hint="业务域 → 场景 → 方案" />
      <StatCard title="任务资产" :total="taskTotal" total-label="任务知识条数（D4-D6）"
        :details="[
          { label: '原子任务 AtomTask（D4）', value: d?.counts.atom_tasks ?? 0 },
          { label: '特性任务 FeatureTask（D5）', value: d?.counts.feature_tasks ?? 0 },
          { label: '步骤任务 CompoundTask（D6）', value: d?.counts.compound_tasks ?? 0 },
        ]" accent="#0ea5e9" />
      <StatCard title="知识关联边" :total="d?.edges.merged_total ?? 0" total-label="合并边数"
        :details="groupDetails" accent="#8b5cf6"
        hint="上下游/场景/域 成对合并取大；跨图谱边归出边方，三图谱合计=全库边" />
    </div>

    <section class="blk">
      <h3 class="blk-title">业务域 → 场景 → 方案</h3>
      <el-table :data="d?.solutions_matrix ?? []" size="small" :default-sort="{ prop: 'count', order: 'descending' }">
        <el-table-column prop="domain_name" label="业务域" min-width="150" sortable>
          <template #default="{ row }">
            <span :title="row.domain">{{ row.domain_name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="scenario_name" label="场景" min-width="140" sortable>
          <template #default="{ row }">
            <span :title="row.scenario">{{ row.scenario_name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="count" label="方案数" width="90" sortable align="right">
          <template #default="{ row }"><span class="mono strong">{{ fmt(row.count) }}</span></template>
        </el-table-column>
        <el-table-column label="方案" min-width="320">
          <template #default="{ row }">
            <span v-for="s in row.solutions" :key="s" class="sol-tag">{{ s }}</span>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="blk">
      <h3 class="blk-title">任务资产 · 类型 × 网元</h3>
      <el-table :data="d?.tasks_matrix ?? []" size="small" :default-sort="{ prop: 'count', order: 'descending' }">
        <el-table-column prop="type" label="任务类型" min-width="140" sortable />
        <el-table-column prop="nf" label="网元" width="110" sortable />
        <el-table-column prop="count" label="知识条数" sortable align="right">
          <template #default="{ row }"><span class="mono">{{ fmt(row.count) }}</span></template>
        </el-table-column>
      </el-table>
    </section>

    <!-- MOP 动网变更场景统计（Excel 底表，不走库） -->
    <MopTable />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElTable, ElTableColumn } from 'element-plus'
import StatCard from '../StatCard.vue'
import MopTable from './MopTable.vue'
import { fmt } from './shared'
import { statsBusinessOverview, type BusinessOverview } from '../../api'

const d = ref<BusinessOverview | null>(null)
const loading = ref(false)

const taskTotal = computed(() =>
  (d.value?.counts.atom_tasks ?? 0) + (d.value?.counts.feature_tasks ?? 0)
  + (d.value?.counts.compound_tasks ?? 0))
const groupDetails = computed(() =>
  Object.entries(d.value?.edges.groups ?? {}).map(([label, value]) => ({ label, value })))

async function load(): Promise<void> {
  loading.value = true
  try {
    d.value = await statsBusinessOverview()
  } finally {
    loading.value = false
  }
}

defineExpose({ reload: load })

onMounted(load)
</script>

<style scoped>
@import './tab.css';

.sol-tag {
  display: inline-block;
  margin: 2px 6px 2px 0;
  padding: 2px 9px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-sunken);
  font-size: 11.5px;
  color: var(--text-muted);
}
</style>
