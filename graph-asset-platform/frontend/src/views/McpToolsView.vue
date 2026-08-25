<template>
  <div class="mcp-tools-page">
    <header class="page-head stagger-in">
      <div>
        <h1 class="page-title">MCP 工具配置</h1>
        <p class="page-sub">
          控制 /mcp 服务对 Agent 暴露的工具与说明——全局生效，保存即生效（无需重启）
        </p>
      </div>
      <el-button type="primary" :loading="saving" :disabled="!dirty" @click="save">
        保存配置{{ dirty ? '（有未保存更改）' : '' }}
      </el-button>
    </header>

    <div class="table-card stagger-in">
      <el-table :data="tools" v-loading="loading" :show-header="true">
        <el-table-column label="工具" width="150">
          <template #default="{ row }">
            <div class="tool-cell">
              <code class="tool-name">{{ row.name }}</code>
              <span v-if="!row.enabled" class="off-badge">已禁用</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-switch v-model="row.enabled" @change="markDirty" />
          </template>
        </el-table-column>
        <el-table-column label="描述（Agent 在 tools/list 看到的说明；清空恢复默认）" min-width="480">
          <template #default="{ row }">
            <el-input
              v-model="row.description"
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 8 }"
              placeholder="留空使用默认描述"
              @input="markDirty"
            />
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="table-card instructions-card stagger-in">
      <div class="card-head">
        <div>
          <div class="card-title">服务总体说明（instructions）</div>
          <div class="card-sub">
            Agent 建立连接时收到的服务说明（推荐查询路径等）。输入框已预填默认值，清空恢复默认。
          </div>
        </div>
        <el-button link size="small" @click="resetInstructions">恢复默认说明</el-button>
      </div>
      <el-input
        v-model="instructions"
        type="textarea"
        :autosize="{ minRows: 3, maxRows: 12 }"
        placeholder="留空使用默认说明"
        @input="markDirty"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElButton, ElInput, ElSwitch, ElTable, ElTableColumn, ElMessage } from 'element-plus'
import { listMcpTools, updateMcpTools, type McpToolRow } from '../api'

const tools = ref<McpToolRow[]>([])
const instructions = ref('')
const defaultInstructions = ref('')
const loading = ref(false)
const saving = ref(false)
const dirty = ref(false)

// 初始快照（脏检查基准）：保存/加载后刷新
let baseline = ''

const snapshot = computed(() =>
  JSON.stringify({
    tools: tools.value.map((t) => ({ name: t.name, enabled: t.enabled, description: t.description })),
    instructions: instructions.value,
  }),
)

function markDirty(): void {
  dirty.value = snapshot.value !== baseline
}

// 恢复默认说明也是一次变更（审查修正：漏 markDirty 会卡死保存按钮）
function resetInstructions(): void {
  instructions.value = defaultInstructions.value
  markDirty()
}

// 展示值 ↔ 存储值：空存储预填默认进输入框；保存时与默认相同则存空（代码默认升级仍能透出）
function displayDesc(t: McpToolRow): string {
  return t.description || t.default_description
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const cfg = await listMcpTools()
    tools.value = cfg.tools
    tools.value.forEach((t) => {
      t.description = displayDesc(t)
    })
    instructions.value = cfg.instructions || cfg.default_instructions
    defaultInstructions.value = cfg.default_instructions
    baseline = snapshot.value
    dirty.value = false
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function save(): Promise<void> {
  saving.value = true
  try {
    const cfg = await updateMcpTools({
      tools: tools.value.map((t) => ({
        name: t.name,
        enabled: t.enabled,
        description: t.description === t.default_description ? '' : t.description,
      })),
      instructions: instructions.value === defaultInstructions.value ? '' : instructions.value,
    })
    tools.value = cfg.tools
    tools.value.forEach((t) => {
      t.description = displayDesc(t)
    })
    instructions.value = cfg.instructions || cfg.default_instructions
    defaultInstructions.value = cfg.default_instructions
    baseline = snapshot.value
    dirty.value = false
    ElMessage.success('已保存，对 Agent 立即生效')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.mcp-tools-page {
  height: 100%;
  overflow: auto;
  padding: var(--space-8) var(--space-6);
  max-width: 1100px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

/* 统一页头（与 UsersView 对齐） */
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}

/* flex 子项禁止压缩（否则 overflow:hidden 卡片被压扁裁行、页面永不出滚动条——
   放大/高分屏下"只见 4/3 个工具"根因，2026-08-25 用户反馈） */
.page-head,
.table-card,
.instructions-card {
  flex-shrink: 0;
}
.page-title {
  font-family: var(--display);
  font-size: 26px;
  font-weight: 700;
  color: var(--text);
  margin: 0;
  letter-spacing: -0.02em;
}
.page-sub {
  margin: var(--space-2) 0 0;
  color: var(--text-muted);
  font-size: 13px;
}

.table-card {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

/* 工具名 + 禁用徽标 */
.tool-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.tool-name {
  font-family: var(--mono);
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text);
  background: var(--bg-sunken);
  border: 1px solid var(--border-faint);
  border-radius: var(--radius-sm);
  padding: 2px 8px;
}
.off-badge {
  font-size: 10.5px;
  font-weight: 600;
  color: var(--danger);
  background: rgba(220, 38, 38, 0.08);
  border: 1px solid rgba(220, 38, 38, 0.2);
  border-radius: 999px;
  padding: 1px 7px;
}

/* 总体说明卡片 */
.instructions-card {
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}
.card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}
.card-sub {
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-muted);
}
</style>
