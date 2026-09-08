<template>
  <div class="mcp-tools-page">
    <header class="page-head stagger-in">
      <div>
        <h1 class="page-title">MCP 工具配置</h1>
        <p class="page-sub">
          控制 /mcp 服务对 Agent 暴露的工具与说明——全局生效，保存即生效（无需重启）。
          工具的接口契约（schema / 错误码 / canonical 描述）由代码固定，此处只能补充说明。
        </p>
      </div>
      <el-button type="primary" :loading="saving" :disabled="!dirty" @click="save">
        保存配置{{ dirty ? '（有未保存更改）' : '' }}
      </el-button>
    </header>

    <div class="table-card stagger-in">
      <div class="section-head">
        <div class="card-title">公开工具（Agent 在 tools/list 看到）</div>
        <div class="card-sub">状态：visible 展示且可调 / hidden 不展示但仍可直调（兼容旧客户端）/ disabled 拦截调用</div>
      </div>
      <el-table :data="publicTools" v-loading="loading" :show-header="true">
        <el-table-column label="工具" width="150">
          <template #default="{ row }">
            <code class="tool-name">{{ row.name }}</code>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="150">
          <template #default="{ row }">
            <el-select v-model="row.visibility" size="small" @change="markDirty">
              <el-option label="visible（展示）" value="visible" />
              <el-option label="hidden（隐藏可调）" value="hidden" />
              <el-option label="disabled（禁用）" value="disabled" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="补充说明（追加在 canonical 描述之后；清空=仅 canonical）" min-width="460">
          <template #default="{ row }">
            <el-input
              v-model="row.supplemental_description"
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 6 }"
              placeholder="留空 = 仅使用代码默认描述"
              @input="markDirty"
            />
            <details class="canonical-box">
              <summary>canonical 描述（只读，不可覆盖）</summary>
              <pre class="canonical-pre">{{ row.default_description }}</pre>
            </details>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="table-card stagger-in">
      <div class="section-head">
        <div class="card-title">兼容工具（已下线，默认 hidden）</div>
        <div class="card-sub">
          不出现在新 Agent 的 tools/list，但已缓存旧 schema 的客户端仍可直调（deprecated）。
          观测一个发布周期调用量为 0 后再考虑 disabled。
        </div>
      </div>
      <el-table :data="legacyTools" v-loading="loading" :show-header="true">
        <el-table-column label="工具" width="150">
          <template #default="{ row }">
            <div class="tool-cell">
              <code class="tool-name">{{ row.name }}</code>
              <span class="off-badge">deprecated</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="150">
          <template #default="{ row }">
            <el-select v-model="row.visibility" size="small" @change="markDirty">
              <el-option label="hidden（隐藏可调）" value="hidden" />
              <el-option label="disabled（禁用）" value="disabled" />
              <el-option label="visible（回滚展示）" value="visible" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="补充说明" min-width="460">
          <template #default="{ row }">
            <el-input
              v-model="row.supplemental_description"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 4 }"
              placeholder="留空 = 仅使用代码默认描述"
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
            Agent 建立连接时收到的服务说明。输入框内容作为<b>补充</b>追加在 canonical
            决策树之后，清空 = 仅 canonical。canonical 不可覆盖。
          </div>
        </div>
        <el-button link size="small" @click="resetInstructions">清空补充</el-button>
      </div>
      <details class="canonical-box">
        <summary>canonical 总体说明（只读）</summary>
        <pre class="canonical-pre">{{ defaultInstructions }}</pre>
      </details>
      <el-input
        v-model="instructions"
        type="textarea"
        :autosize="{ minRows: 2, maxRows: 8 }"
        placeholder="补充说明（追加在 canonical 之后），留空 = 仅 canonical"
        @input="markDirty"
      />
      <div v-if="legacyBackup" class="backup-note">
        检测到旧版全文覆盖说明（升级时已自动备份停用）：
        <el-button link size="small" @click="showBackup = !showBackup">
          {{ showBackup ? '收起' : '查看备份内容' }}
        </el-button>
        <pre v-if="showBackup" class="canonical-pre backup-pre">{{ legacyBackup }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  ElButton, ElInput, ElOption, ElSelect, ElTable, ElTableColumn, ElMessage,
} from 'element-plus'
import { listMcpTools, updateMcpTools, type McpToolRow } from '../api'

const tools = ref<McpToolRow[]>([])
const instructions = ref('')
const defaultInstructions = ref('')
const legacyBackup = ref('')
const showBackup = ref(false)
const loading = ref(false)
const saving = ref(false)
const dirty = ref(false)

// 初始快照（脏检查基准）：保存/加载后刷新
let baseline = ''

const publicTools = computed(() => tools.value.filter((t) => !t.is_legacy))
const legacyTools = computed(() => tools.value.filter((t) => t.is_legacy))

const snapshot = computed(() =>
  JSON.stringify({
    tools: tools.value.map((t) => ({
      name: t.name,
      visibility: t.visibility,
      supplemental_description: t.supplemental_description,
    })),
    instructions: instructions.value,
  }),
)

function markDirty(): void {
  dirty.value = snapshot.value !== baseline
}

function resetInstructions(): void {
  instructions.value = ''
  markDirty()
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const cfg = await listMcpTools()
    tools.value = cfg.tools
    instructions.value = cfg.instructions
    defaultInstructions.value = cfg.default_instructions
    legacyBackup.value = cfg.instructions_legacy_backup || ''
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
        visibility: t.visibility,
        supplemental_description: t.supplemental_description,
      })),
      instructions: instructions.value,
    })
    tools.value = cfg.tools
    instructions.value = cfg.instructions
    defaultInstructions.value = cfg.default_instructions
    legacyBackup.value = cfg.instructions_legacy_backup || ''
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

/* flex 子项禁止压缩（否则 overflow:hidden 卡片被压扁裁行） */
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
.section-head {
  padding: var(--space-4) var(--space-5) var(--space-2);
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

/* 工具名 + deprecated 徽标 */
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
  color: var(--warn, #b45309);
  background: rgba(180, 83, 9, 0.08);
  border: 1px solid rgba(180, 83, 9, 0.2);
  border-radius: 999px;
  padding: 1px 7px;
}

/* canonical 描述折叠框 */
.canonical-box {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-muted);
}
.canonical-box summary {
  cursor: pointer;
  user-select: none;
}
.canonical-pre {
  margin: 6px 0 0;
  padding: var(--space-3);
  max-height: 220px;
  overflow: auto;
  white-space: pre-wrap;
  font-family: var(--mono);
  font-size: 11.5px;
  line-height: 1.55;
  color: var(--text-muted);
  background: var(--bg-sunken);
  border: 1px solid var(--border-faint);
  border-radius: var(--radius-sm);
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
.backup-note {
  font-size: 12px;
  color: var(--text-muted);
}
.backup-pre {
  margin-top: 6px;
}
</style>
