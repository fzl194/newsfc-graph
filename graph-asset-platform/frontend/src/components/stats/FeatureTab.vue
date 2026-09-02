<template>
  <div class="tab">
    <!-- ① 统计值卡片 -->
    <div v-loading="sumLoading" class="cards">
      <StatCard title="特性数量" :total="sum?.feature_count ?? 0" total-label="特性知识条数"
        :details="[{ label: '覆盖特性编号（跨版本合并计）', value: sum?.feature_codes ?? 0 }]"
        accent="#4f46e5" hint="多版本/多子文档各计一条；编号跨版本合并后去重" />
      <StatCard title="License 数量" :total="sum?.license_count ?? 0" total-label="License 知识条数"
        :details="[{ label: '覆盖 License 编号（跨版本合并计）', value: sum?.license_codes ?? 0 }]"
        accent="#0ea5e9" hint="多版本各计一条；编号跨版本合并后去重" />
      <StatCard title="知识关联出边" :total="sum?.edges.merged_total ?? 0" total-label="合并边数（C5）"
        :details="mergedDetails" accent="#8b5cf6" hint="包含子文档/属于特性 合并取大" />
    </div>

    <!-- ② 筛选条 -->
    <StatsFilterBar v-model="card" :options="options" @reset="card = emptyCardFilter()" />

    <!-- ③ 下钻矩阵（四列 + 分页 + 表级筛选） -->
    <section class="blk">
      <div class="blk-head">
        <h3 class="blk-title">下钻 · 网元 × 版本</h3>
        <div class="blk-tools">
          <TableMiniFilter v-model="tableFilter" :options="options" />
          <el-pagination small layout="total, prev, pager, next" :total="matrix.total"
            :page-size="size" :current-page="page" @current-change="onPage" />
        </div>
      </div>
      <el-table v-loading="loading" :data="matrix.rows" size="small">
        <el-table-column prop="nf_display" label="网元" width="90" sortable="custom" />
        <el-table-column prop="version_display" label="版本" width="150" sortable="custom" />
        <el-table-column prop="feature_codes" label="特性编号数（C1）" sortable="custom" align="right">
          <template #default="{ row }"><span class="mono">{{ fmt(row.feature_codes) }}</span></template>
        </el-table-column>
        <el-table-column prop="feature_knowledge" label="特性知识条数（C3）" sortable="custom" align="right">
          <template #default="{ row }"><span class="mono strong">{{ fmt(row.feature_knowledge) }}</span></template>
        </el-table-column>
        <el-table-column prop="license_codes" label="License 编号数（C2）" sortable="custom" align="right">
          <template #default="{ row }"><span class="mono">{{ fmt(row.license_codes) }}</span></template>
        </el-table-column>
        <el-table-column prop="license_knowledge" label="License 知识条数（C4）" sortable="custom" align="right">
          <template #default="{ row }"><span class="mono">{{ fmt(row.license_knowledge) }}</span></template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElPagination, ElTable, ElTableColumn } from 'element-plus'
import StatCard from '../StatCard.vue'
import StatsFilterBar from './StatsFilterBar.vue'
import TableMiniFilter from './TableMiniFilter.vue'
import { emptyCardFilter, fmt, mergeMulti, toParams, type CardFilterState } from './shared'
import {
  statsFeatureMatrix, statsFeatureSummary,
  type FeatureMatrixRow, type FeatureSummary, type PagedResult, type StatsFilterOptions,
} from '../../api'

defineProps<{ options: StatsFilterOptions }>()

const card = ref<CardFilterState>(emptyCardFilter())
const sum = ref<FeatureSummary | null>(null)
const sumLoading = ref(false)
const matrix = ref<PagedResult<FeatureMatrixRow>>({ rows: [], total: 0 })
const loading = ref(false)
const page = ref(1)
const size = 20
// ⚠ 必须用 ref：reactive 常量上的 v-model 整对象赋值会断开 watch（筛选无反应 bug）
const tableFilter = ref({ nfs: [] as string[], versions: [] as string[] })

const mergedDetails = computed(() =>
  (sum.value?.edges.merged ?? []).slice(0, 6).map(([label, value]) => ({ label, value })))

async function loadSummary(): Promise<void> {
  sumLoading.value = true
  try {
    sum.value = await statsFeatureSummary(toParams(card.value))
  } finally {
    sumLoading.value = false
  }
}

async function loadMatrix(): Promise<void> {
  loading.value = true
  try {
    matrix.value = await statsFeatureMatrix({
      ...toParams(card.value),
      nfs: mergeMulti(card.value.nfs, tableFilter.value.nfs),
      versions: mergeMulti(card.value.versions, tableFilter.value.versions),
      logical_ne: '',
    }, page.value, size)
  } finally {
    loading.value = false
  }
}

function reloadAll(): void {
  page.value = 1
  void loadSummary()
  void loadMatrix()
}

function onPage(p: number): void {
  page.value = p
  void loadMatrix()
}

watch(card, reloadAll, { deep: true })
watch(tableFilter, () => {
  page.value = 1
  void loadMatrix()
}, { deep: true })

defineExpose({ reload: reloadAll })

onMounted(reloadAll)
</script>

<style scoped>
@import './tab.css';

.blk-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); flex-wrap: wrap; }
.blk-tools { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
</style>
