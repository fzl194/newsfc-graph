<template>
  <div v-loading="loading" class="tab">
    <div class="cards">
      <StatCard title="特性数量" :total="d?.totals.feature_codes ?? 0" total-label="特性编号数（C1）"
        :details="[{ label: '特性知识条数（C3）', value: d?.totals.feature_knowledge ?? 0 }]"
        accent="#4f46e5" hint="feature_code 去重（按网元+版本）" />
      <StatCard title="License 数量" :total="d?.totals.license_codes ?? 0" total-label="License 编号数（C2）"
        :details="[{ label: 'License 知识条数（C4）', value: d?.totals.license_knowledge ?? 0 }]"
        accent="#0ea5e9" hint="license_code 去重（按网元+版本）" />
      <StatCard title="知识关联出边" :total="d?.edges.merged_total ?? 0" total-label="合并边数（C5）"
        :details="mergedDetails" accent="#8b5cf6" hint="包含子文档/属于特性 合并取大" />
      <StatCard title="特性业务类型" :total="d?.prefixes.length ?? 0" total-label="前缀类（C6）"
        accent="#f59e0b" hint="WSFD/WHFD/GWFD/IPFD/SFFD/NPFD…" />
    </div>

    <section v-if="d?.prefixes.length" class="blk">
      <h3 class="blk-title">feature_code 前缀（C6）</h3>
      <div class="prefix-tags">
        <span v-for="p in d.prefixes" :key="p" class="prefix-tag mono">{{ p }}</span>
      </div>
    </section>

    <section class="blk">
      <h3 class="blk-title">下钻 · 网元 × 版本（四列矩阵）</h3>
      <el-table :data="d?.matrix ?? []" size="small" :default-sort="{ prop: 'feature_knowledge', order: 'descending' }">
        <el-table-column prop="nf_display" label="网元" width="90" sortable />
        <el-table-column prop="version_display" label="版本" width="140" sortable />
        <el-table-column prop="feature_codes" label="特性编号数（C1）" sortable align="right">
          <template #default="{ row }"><span class="mono">{{ fmt(row.feature_codes) }}</span></template>
        </el-table-column>
        <el-table-column prop="feature_knowledge" label="特性知识条数（C3）" sortable align="right">
          <template #default="{ row }"><span class="mono">{{ fmt(row.feature_knowledge) }}</span></template>
        </el-table-column>
        <el-table-column prop="license_codes" label="License 编号数（C2）" sortable align="right">
          <template #default="{ row }"><span class="mono">{{ fmt(row.license_codes) }}</span></template>
        </el-table-column>
        <el-table-column prop="license_knowledge" label="License 知识条数（C4）" sortable align="right">
          <template #default="{ row }"><span class="mono">{{ fmt(row.license_knowledge) }}</span></template>
        </el-table-column>
      </el-table>
    </section>

    <div class="edges-grid">
      <RelationTable title="出边按关系 · 合并取大" :rows="d?.edges.merged ?? []"
        hint="使用命令 / 依赖特性 / 所需License 等" />
      <RelationTable title="出边按关系 · 原始方向" :rows="d?.edges.raw ?? []" hint="edges 原始行计数" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElTable, ElTableColumn } from 'element-plus'
import StatCard from '../StatCard.vue'
import RelationTable from './RelationTable.vue'
import { fmt } from './shared'
import type { FeatureStats } from '../../api'

const props = defineProps<{ data: FeatureStats | null; loading: boolean }>()
const d = computed(() => props.data)

const mergedDetails = computed(() =>
  (d.value?.edges.merged ?? []).slice(0, 6).map(([label, value]) => ({ label, value })))
</script>

<style scoped>
@import './tab.css';

.prefix-tags { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.prefix-tag {
  padding: 3px 10px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--bg-sunken);
  font-size: 11.5px;
  color: var(--text-muted);
}
</style>
