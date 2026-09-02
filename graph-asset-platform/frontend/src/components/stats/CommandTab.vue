<template>
  <div v-loading="loading" class="tab">
    <div class="cards">
      <StatCard title="知识维度" :total="d?.knowledge.points ?? 0" total-label="点（A3）"
        :details="[
          { label: '命令知识条数（A1）', value: d?.knowledge.MMLCommand ?? 0 },
          { label: '配置对象知识条数（A2）', value: d?.knowledge.ConfigObject ?? 0 },
        ]" accent="#4f46e5" hint="objects 行数，多版本各计一次" />
      <StatCard title="知识关联出边" :total="d?.edges.merged_total ?? 0" total-label="合并边数（A4）"
        :details="mergedDetails" accent="#0ea5e9" hint="成对方向合并取大（§7.1）" />
      <StatCard title="被引用入边" :total="inboundTotal" total-label="跨图谱入边（A5）"
        :details="inboundDetails" accent="#8b5cf6" hint="特性/任务指向命令图谱" />
      <StatCard v-if="d?.rules.syntax" title="命令 / 参数" :total="d.rules.syntax.cmd_count"
        total-label="命令数量（B1）"
        :details="[
          { label: '参数数量（B2）', value: d.rules.syntax.param_count },
          { label: '命令数·分组求和口径', value: d.rules.syntax.cmd_count_by_group_sum },
        ]" accent="#f59e0b" hint="语法规则表 DISTINCT CMD_NAME / 行数" />
      <StatCard title="五类核查规则" :total="d?.five_total ?? 0" total-label="合计（B8）"
        :details="ruleDetails" accent="#10b981" hint="图/重复/MOD/SET/删除 各表行数" />
    </div>

    <section class="blk">
      <h3 class="blk-title">知识下钻 · 网元 × 版本</h3>
      <el-table :data="d?.matrix ?? []" size="small" :default-sort="{ prop: 'total', order: 'descending' }">
        <el-table-column prop="nf_display" label="网元" width="90" sortable />
        <el-table-column prop="version_display" label="版本" width="130" sortable />
        <el-table-column prop="MMLCommand" label="命令知识条数" sortable align="right">
          <template #default="{ row }"><span class="mono">{{ fmt(row.MMLCommand) }}</span></template>
        </el-table-column>
        <el-table-column prop="ConfigObject" label="配置对象知识条数" sortable align="right">
          <template #default="{ row }"><span class="mono">{{ fmt(row.ConfigObject) }}</span></template>
        </el-table-column>
        <el-table-column prop="total" label="点" sortable align="right">
          <template #default="{ row }"><span class="mono strong">{{ fmt(row.total) }}</span></template>
        </el-table-column>
      </el-table>
    </section>

    <section v-if="d?.rules.syntax" class="blk">
      <h3 class="blk-title">语法规则下钻 · 命令 / 参数（按网元 × 版本）</h3>
      <el-table :data="d.syntax_matrix" size="small" :default-sort="{ prop: 'param_count', order: 'descending' }">
        <el-table-column prop="ne" label="网元（表内命名）" min-width="130" sortable />
        <el-table-column prop="version_display" label="版本" width="130" sortable />
        <el-table-column prop="cmd_count" label="命令数（B1）" sortable align="right">
          <template #default="{ row }"><span class="mono">{{ fmt(row.cmd_count) }}</span></template>
        </el-table-column>
        <el-table-column prop="param_count" label="参数数（B2）" sortable align="right">
          <template #default="{ row }"><span class="mono">{{ fmt(row.param_count) }}</span></template>
        </el-table-column>
      </el-table>
    </section>

    <section class="blk">
      <h3 class="blk-title">五类规则下钻（按网元 × 版本）</h3>
      <el-table :data="ruleRows" size="small" :default-sort="{ prop: 'count', order: 'descending' }">
        <el-table-column prop="label" label="规则类型" width="130" sortable />
        <el-table-column prop="ne" label="网元" min-width="110" sortable />
        <el-table-column prop="version_display" label="版本" width="130" sortable />
        <el-table-column prop="count" label="规则数" sortable align="right">
          <template #default="{ row }"><span class="mono">{{ fmt(row.count) }}</span></template>
        </el-table-column>
      </el-table>
    </section>

    <div class="edges-grid">
      <RelationTable title="出边按关系 · 合并取大" :rows="d?.edges.merged ?? []"
        hint="成对方向关系只计一次（取大）" />
      <RelationTable title="出边按关系 · 原始方向" :rows="d?.edges.raw ?? []" hint="edges 原始行计数" />
      <RelationTable title="被引用入边（跨图谱）" :rows="d?.inbound.raw ?? []"
        hint="使用命令 / 对应命令 / 复用命令等" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElTable, ElTableColumn } from 'element-plus'
import StatCard from '../StatCard.vue'
import RelationTable from './RelationTable.vue'
import { RULE_LABELS, fmt } from './shared'
import type { CommandStats } from '../../api'

type Detail = { label: string; value: number }

const props = defineProps<{ data: CommandStats | null; loading: boolean }>()
const d = computed(() => props.data)

const mergedDetails = computed<Detail[]>(() =>
  (d.value?.edges.merged ?? []).slice(0, 6).map(([relation, value]) => ({ label: relation, value })))
const inbound = computed(() => d.value?.inbound.raw ?? [])
const inboundTotal = computed(() => inbound.value.reduce((s, [, v]) => s + v, 0))
const inboundDetails = computed<Detail[]>(() =>
  inbound.value.slice(0, 6).map(([label, value]) => ({ label, value })))
const ruleDetails = computed<Detail[]>(() => {
  const r = d.value?.rules ?? {}
  return (['graph', 'repeat', 'mod', 'set', 'delete'] as const)
    .filter((k) => typeof r[k] === 'number')
    .map((k) => ({ label: RULE_LABELS[k], value: r[k] as number }))
})
const ruleRows = computed(() =>
  Object.entries(d.value?.rule_matrix ?? {}).flatMap(([key, rows]) =>
    rows.map((r) => ({ label: RULE_LABELS[key] ?? key, ne: r.ne, version_display: r.version_display, count: r.count }))))
</script>

<style scoped>
@import './tab.css';
</style>
