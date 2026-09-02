<template>
  <div class="tab">
    <!-- ① 统计值卡片（视图级筛选联动；命令/参数卡已删，数值在规则表类型维度） -->
    <div v-loading="sumLoading" class="cards">
      <StatCard title="知识维度" :total="sum?.knowledge.points ?? 0" total-label="总计知识条数"
        :details="[
          { label: '命令知识条数（A1）', value: sum?.knowledge.MMLCommand ?? 0 },
          { label: '配置对象知识条数（A2）', value: sum?.knowledge.ConfigObject ?? 0 },
        ]" accent="#4f46e5" hint="objects 行数，多版本各计一次" />
      <StatCard title="知识关联边" :total="sum?.edges.merged_total ?? 0" total-label="合并边数（A4）"
        :details="mergedDetails" accent="#0ea5e9"
        hint="成对方向合并取大；跨图谱边归出边方，三图谱合计=全库边" />
      <StatCard title="五类核查规则" :total="sum?.five_total ?? 0" total-label="合计（B8）"
        :details="ruleDetails" accent="#10b981" hint="图/重复/MOD/SET/删除 各表行数" />
    </div>

    <!-- ② 筛选条（卡片与两表共用基准） -->
    <StatsFilterBar v-model="card" :options="options" with-logical-ne @reset="resetCard" />

    <!-- ③ 知识统计表（边统计已并入：出边/入边列） -->
    <section class="blk">
      <div class="blk-head">
        <h3 class="blk-title">知识统计（网元 × 版本）</h3>
        <div class="blk-tools">
          <TableMiniFilter v-model="knowFilter" :options="options" />
          <el-pagination small layout="total, prev, pager, next" :total="knowTotal"
            :page-size="knowSize" :current-page="knowPage" @current-change="onKnowPage" />
        </div>
      </div>
      <el-table v-loading="knowLoading" :data="know.rows" size="small">
        <el-table-column prop="nf_display" label="网元" width="90" sortable="custom" />
        <el-table-column prop="version_display" label="版本" width="140" sortable="custom" />
        <el-table-column prop="cmd_knowledge" label="命令知识条数" sortable="custom" align="right">
          <template #default="{ row }"><span class="mono">{{ fmt(row.cmd_knowledge) }}</span></template>
        </el-table-column>
        <el-table-column prop="cfg_knowledge" label="配置对象知识条数" sortable="custom" align="right">
          <template #default="{ row }"><span class="mono">{{ fmt(row.cfg_knowledge) }}</span></template>
        </el-table-column>
        <el-table-column prop="total_knowledge" label="总计知识条数" sortable="custom" align="right">
          <template #default="{ row }"><span class="mono strong">{{ fmt(row.total_knowledge) }}</span></template>
        </el-table-column>
        <el-table-column prop="out_edges" label="出边数" sortable="custom" align="right">
          <template #default="{ row }"><span class="mono">{{ fmt(row.out_edges) }}</span></template>
        </el-table-column>
        <el-table-column prop="in_edges" label="入边数" sortable="custom" align="right">
          <template #default="{ row }">
            <span class="mono" :title="'按目标槽位计入（同 id 多版本分别计）'">{{ fmt(row.in_edges) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <!-- ④ 规则统计总表（长表：类型含命令/参数数量 + 逻辑网元维度） -->
    <section class="blk">
      <div class="blk-head">
        <h3 class="blk-title">规则统计（网元 · 逻辑网元 · 版本 · 类型 · 数量）</h3>
        <div class="blk-tools">
          <el-radio-group v-model="ruleMode" size="small" @change="onRuleModeChange">
            <el-radio-button value="ne_version">网元×版本</el-radio-button>
            <el-radio-button value="ne">仅网元</el-radio-button>
            <el-radio-button value="version">仅版本</el-radio-button>
            <el-radio-button value="all">总计</el-radio-button>
          </el-radio-group>
          <el-select v-model="ruleFilter.rule_types" multiple collapse-tags clearable filterable
            size="small" placeholder="类型" class="type-sel" @change="reloadRules">
            <el-option v-for="r in options.rule_types" :key="r.key" :label="r.label" :value="r.key" />
          </el-select>
          <el-select v-model="ruleFilter.nfs" multiple collapse-tags clearable filterable
            size="small" placeholder="网元" class="mini-sel" @change="reloadRules">
            <el-option v-for="n in options.nfs" :key="n" :label="n" :value="n" />
          </el-select>
          <el-select v-model="ruleFilter.versions" multiple collapse-tags clearable filterable
            size="small" placeholder="版本" class="mini-sel" @change="reloadRules">
            <el-option v-for="v in options.versions" :key="v" :label="v" :value="v" />
          </el-select>
          <el-select v-model="ruleFilter.logical_ne" clearable filterable size="small"
            placeholder="逻辑网元" class="mini-sel" @change="reloadRules">
            <el-option v-for="l in logicalOptions" :key="l" :label="l" :value="l" />
          </el-select>
          <el-pagination small layout="total, prev, pager, next" :total="ruleTotal"
            :page-size="ruleSize" :current-page="rulePage" @current-change="onRulePage" />
        </div>
      </div>
      <el-table v-loading="ruleLoading" :data="rules.rows" size="small">
        <el-table-column prop="ne" label="网元" min-width="110" sortable="custom">
          <template #default="{ row }">
            <span :class="{ faint: !row.ne }">{{ row.ne || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="logical" label="逻辑网元" width="110" sortable="custom">
          <template #header>
            <span title="语法类行按逻辑网元映射分行（仅网元×版本模式）；'—' 为物理网元整体">逻辑网元</span>
          </template>
          <template #default="{ row }">
            <span :class="{ faint: !row.logical }">{{ row.logical || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="version_display" label="版本" width="140" sortable="custom">
          <template #default="{ row }">
            <span :class="{ faint: !row.version }">{{ row.version || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="type" label="类型" width="130" sortable="custom">
          <template #header>
            <span title="命令数量=语法表各(网元,版本)组命令数求和（不去重，同命令跨版本重复计）；参数数量=语法表行数；五类=各规则表行数">类型</span>
          </template>
        </el-table-column>
        <el-table-column prop="count" label="数量" sortable="custom" align="right">
          <template #default="{ row }"><span class="mono strong">{{ fmt(row.count) }}</span></template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  ElOption, ElPagination, ElRadioButton, ElRadioGroup, ElSelect, ElTable, ElTableColumn,
} from 'element-plus'
import StatCard from '../StatCard.vue'
import StatsFilterBar from './StatsFilterBar.vue'
import TableMiniFilter from './TableMiniFilter.vue'
import {
  RULE_LABELS, emptyCardFilter, fmt, mergeMulti, mergeSingle, toParams,
  type CardFilterState,
} from './shared'
import {
  statsCommandKnowledge, statsCommandRules, statsCommandSummary,
  type CommandSummary, type KnowledgeRow, type PagedResult, type RuleGroupMode,
  type RuleRow, type StatsFilterOptions,
} from '../../api'

const props = defineProps<{ options: StatsFilterOptions }>()

const card = ref<CardFilterState>(emptyCardFilter())
const sum = ref<CommandSummary | null>(null)
const sumLoading = ref(false)

// 知识表（分页 + 本地筛选：网元/版本）。⚠ 必须用 ref：reactive 常量上的
// v-model 整对象赋值会断开 watch（曾致"筛选无反应"bug，2026-09-02 修复）
const know = ref<PagedResult<KnowledgeRow>>({ rows: [], total: 0 })
const knowLoading = ref(false)
const knowPage = ref(1)
const knowSize = 20
const knowFilter = ref({ nfs: [] as string[], versions: [] as string[] })
const knowTotal = computed(() => know.value.total)

// 规则表（分页 + 汇总方式 + 本地筛选：类型/网元/版本/逻辑网元）
const rules = ref<PagedResult<RuleRow>>({ rows: [], total: 0 })
const ruleLoading = ref(false)
const rulePage = ref(1)
const ruleSize = 20
const ruleMode = ref<RuleGroupMode>('ne_version')
const ruleFilter = ref({
  nfs: [] as string[], versions: [] as string[],
  logical_ne: '', rule_types: [] as string[],
})
const ruleTotal = computed(() => rules.value.total)

const mergedDetails = computed(() =>
  (sum.value?.edges.merged ?? []).slice(0, 6).map(([label, value]) => ({ label, value })))
const ruleDetails = computed(() => {
  const r = sum.value?.rules ?? {}
  return (['graph', 'repeat', 'mod', 'set', 'delete'] as const)
    .filter((k) => typeof r[k] === 'number')
    .map((k) => ({ label: RULE_LABELS[k], value: r[k] as number }))
})
const logicalOptions = computed(() => {
  const src = props.options.logical_nes
  const keys = card.value.nfs.length ? card.value.nfs : Object.keys(src)
  const s = new Set<string>()
  keys.forEach((k) => (src[k] ?? []).forEach((v) => s.add(v)))
  return [...s].sort()
})

// ---- 加载 ----

async function loadSummary(): Promise<void> {
  sumLoading.value = true
  try {
    sum.value = await statsCommandSummary(toParams(card.value))
  } finally {
    sumLoading.value = false
  }
}

function knowParams() {
  return {
    ...toParams(card.value),
    nfs: mergeMulti(card.value.nfs, knowFilter.value.nfs),
    versions: mergeMulti(card.value.versions, knowFilter.value.versions),
    logical_ne: '', // 知识表不受逻辑网元影响（口径）
  }
}

async function loadKnowledge(): Promise<void> {
  knowLoading.value = true
  try {
    know.value = await statsCommandKnowledge(knowParams(), knowPage.value, knowSize)
  } finally {
    knowLoading.value = false
  }
}

function ruleParams() {
  return {
    ...toParams(card.value),
    nfs: mergeMulti(card.value.nfs, ruleFilter.value.nfs),
    versions: mergeMulti(card.value.versions, ruleFilter.value.versions),
    logical_ne: mergeSingle(card.value.logical_ne, ruleFilter.value.logical_ne),
    rule_types: ruleFilter.value.rule_types,
  }
}

async function loadRules(): Promise<void> {
  ruleLoading.value = true
  try {
    rules.value = await statsCommandRules(ruleParams(), ruleMode.value, rulePage.value, ruleSize)
  } finally {
    ruleLoading.value = false
  }
}

function reloadAll(): void {
  knowPage.value = 1
  rulePage.value = 1
  void loadSummary()
  void loadKnowledge()
  void loadRules()
}

function resetCard(): void {
  card.value = emptyCardFilter()
}

function onKnowPage(p: number): void {
  knowPage.value = p
  void loadKnowledge()
}

function onRulePage(p: number): void {
  rulePage.value = p
  void loadRules()
}

function onRuleModeChange(): void {
  rulePage.value = 1
  void loadRules()
}

function reloadRules(): void {
  rulePage.value = 1
  void loadRules()
}

watch(card, reloadAll, { deep: true })
watch(knowFilter, () => {
  knowPage.value = 1
  void loadKnowledge()
}, { deep: true })

defineExpose({ reload: reloadAll })

onMounted(reloadAll)
</script>

<style scoped>
@import './tab.css';

.blk-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); flex-wrap: wrap; }
.blk-tools { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.mini-sel { width: 130px; }
.type-sel { width: 150px; }
.faint { color: var(--text-faint); }
</style>
