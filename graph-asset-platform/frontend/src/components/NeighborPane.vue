<template>
  <div class="neighbor-pane">
    <!-- 空态 -->
    <div v-if="!objectId" class="pane-empty">
      <div class="empty-icon">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none">
          <circle cx="6" cy="7" r="2.2" stroke="currentColor" stroke-width="1.5" />
          <circle cx="18" cy="7" r="2.2" stroke="currentColor" stroke-width="1.5" />
          <circle cx="12" cy="17" r="2.2" stroke="currentColor" stroke-width="1.5" />
          <path
            d="M7.8 8.3 16.2 8.3 M7 8.7 10.8 15 M17 8.7 13.2 15"
            stroke="currentColor"
            stroke-width="1.3"
            opacity="0.55"
          />
        </svg>
      </div>
      <div class="empty-title">邻居图谱</div>
      <div class="empty-sub">从左栏选一个对象，此处展示其单跳邻居</div>
    </div>

    <template v-else>
      <!-- 图谱区（上） -->
      <div class="graph-section" v-loading="loading">
        <div class="section-head">
          <span class="section-title">单跳邻居图谱</span>
          <span v-if="neighborCount > 0" class="section-count mono">{{ neighborCount }}</span>
        </div>
        <div class="graph-host">
          <GraphCanvas :focus="focusPayload" @node-click="onNodeClick" />
        </div>
      </div>

      <!-- 边清单区（下） -->
      <div class="edges-section">
        <div class="section-head">
          <span class="section-title">关联关系</span>
          <span class="section-count mono">{{ outEdges.length + inEdges.length }}</span>
        </div>
        <div class="edges-body">
          <div v-if="loading" class="edges-loading">加载中…</div>
          <div
            v-else-if="outEdges.length === 0 && inEdges.length === 0"
            class="edges-empty"
          >
            该对象无关联关系
          </div>
          <template v-else>
            <!-- 出向分组 -->
            <div v-if="outEdges.length" class="edge-group">
              <div class="edge-group-head">
                <span class="edge-group-label">出向</span>
                <span class="edge-group-count mono">{{ outEdges.length }}</span>
              </div>
              <ul class="edge-group-list">
                <li
                  v-for="e in outEdges"
                  :key="'o::' + e.relation + '::' + e.to"
                  class="edge-group-item"
                >
                  <span class="edge-rel">{{ e.relation }}</span>
                  <button
                    class="edge-target mono"
                    :title="e.to"
                    @click="onEdgeNavigate(e.to)"
                  >
                    {{ e.to }}
                  </button>
                </li>
              </ul>
            </div>
            <!-- 入向分组 -->
            <div v-if="inEdges.length" class="edge-group">
              <div class="edge-group-head">
                <span class="edge-group-label">入向</span>
                <span class="edge-group-count mono">{{ inEdges.length }}</span>
              </div>
              <ul class="edge-group-list">
                <li
                  v-for="e in inEdges"
                  :key="'i::' + e.relation + '::' + e.from"
                  class="edge-group-item"
                >
                  <span class="edge-rel">{{ e.relation }}</span>
                  <button
                    class="edge-target mono"
                    :title="e.from"
                    @click="onEdgeNavigate(e.from)"
                  >
                    {{ e.from }}
                  </button>
                </li>
              </ul>
            </div>
          </template>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import GraphCanvas from './GraphCanvas.vue'
import { neighbors as fetchNeighbors, type Edge } from '../api'
import { useNav } from '../composables/useNav'

const props = defineProps<{ objectId: string | null }>()
const { selectedId, viewVersion } = useNav()

const loading = ref(false)
const outEdges = ref<Edge[]>([])
const inEdges = ref<Edge[]>([])
const centerId = ref<string>('')

interface FocusPayload {
  centerId: string
  centerDetail: { id: string; type?: string; frontmatter?: Record<string, unknown> } | null
  out: Edge[]
  in: Edge[]
  version?: string
  isOverview?: boolean
}

const focusPayload = computed<FocusPayload | null>(() => {
  if (!centerId.value) return null
  return {
    centerId: centerId.value,
    centerDetail: null,
    out: outEdges.value,
    in: inEdges.value,
    version: viewVersion.value || undefined,
    isOverview: false,
  }
})

const neighborCount = computed(() => {
  const ids = new Set<string>()
  for (const e of outEdges.value) {
    if (e.to !== centerId.value) ids.add(e.to)
    if (e.from !== centerId.value) ids.add(e.from)
  }
  for (const e of inEdges.value) {
    if (e.to !== centerId.value) ids.add(e.to)
    if (e.from !== centerId.value) ids.add(e.from)
  }
  return ids.size
})

async function load(id: string): Promise<void> {
  loading.value = true
  outEdges.value = []
  inEdges.value = []
  centerId.value = id
  try {
    const version = viewVersion.value || undefined
    const data = await fetchNeighbors(id, version, 1)
    outEdges.value = data.out ?? []
    inEdges.value = data.in ?? []
  } catch {
    outEdges.value = []
    inEdges.value = []
  } finally {
    loading.value = false
  }
}

watch(
  () => props.objectId,
  (id) => {
    if (id) void load(id)
    else {
      outEdges.value = []
      inEdges.value = []
      centerId.value = ''
    }
  },
  { immediate: true },
)

// 版本上下文变化（左栏切版本 / 中栏详情切版本）→ 右栏邻居按新版本重取
watch(viewVersion, () => {
  if (props.objectId) void load(props.objectId)
})

// 点邻居节点：更新右栏自身聚焦（立即响应）+ 触发左栏/中栏同步
function onNodeClick(id: string): void {
  if (!id || id === props.objectId) return
  void load(id)
  selectedId.value = id
}

// 点边清单项：触发全栏同步（左栏切层+选择器+高亮，中栏切换）
function onEdgeNavigate(id: string): void {
  if (!id) return
  selectedId.value = id
}
</script>

<style scoped>
.neighbor-pane {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-elev);
  border-left: 1px solid var(--border);
  min-width: 0;
}

/* ---- 空态 ---- */
.pane-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  color: var(--text-faint);
  padding: var(--space-6);
}

.empty-icon {
  color: var(--text-faint);
  opacity: 0.6;
  margin-bottom: var(--space-1);
}

.empty-title {
  font-family: var(--display);
  font-size: 14px;
  font-weight: 600;
  color: var(--text-muted);
}

.empty-sub {
  font-size: 12px;
}

/* ---- 图谱区（上） ---- */
.graph-section {
  display: flex;
  flex-direction: column;
  flex: 1.6 1 0;
  min-height: 160px;
  border-bottom: 1px solid var(--border);
}

.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-faint);
  background: var(--bg-sunken);
  flex-shrink: 0;
}

.section-title {
  font-family: var(--display);
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
}

.section-count {
  font-size: 11px;
  color: var(--text-faint);
  background: var(--bg-elev);
  border: 1px solid var(--border);
  padding: 1px 7px;
  border-radius: 999px;
}

.graph-host {
  flex: 1;
  min-height: 0;
}

/* ---- 边清单区（下） ---- */
.edges-section {
  display: flex;
  flex-direction: column;
  flex: 1 1 0;
  min-height: 120px;
}

.edges-body {
  flex: 1;
  overflow: auto;
  padding: var(--space-2);
}

.edges-loading,
.edges-empty {
  padding: var(--space-4);
  text-align: center;
  color: var(--text-faint);
  font-size: 12px;
}

/* ---- 边分组 ---- */
.edge-group {
  margin-bottom: var(--space-3);
}

.edge-group-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 0 var(--space-1) var(--space-1);
}

.edge-group-label {
  font-size: 10.5px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--accent);
}

.edge-group-count {
  font-size: 10.5px;
  color: var(--text-faint);
}

.edge-group-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.edge-group-item {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
  transition: background var(--dur-fast) var(--ease);
}

.edge-group-item:hover {
  background: var(--bg-sunken);
}

.edge-rel {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--accent);
}

.edge-target {
  background: none;
  border: none;
  padding: 0;
  text-align: left;
  cursor: pointer;
  font-size: 11.5px;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--mono);
}

.edge-target:hover {
  color: var(--accent);
}
</style>
