<template>
  <div class="edge-list">
    <template v-if="!objectId">
      <div class="edge-empty">
        <span class="edge-empty-title">关联关系</span>
        <span class="edge-empty-sub">选中对象后展示其出向关系</span>
      </div>
    </template>

    <template v-else-if="loading">
      <div class="edge-empty"><span class="edge-empty-sub">加载中…</span></div>
    </template>

    <template v-else-if="edges.length === 0">
      <div class="edge-empty">
        <span class="edge-empty-title">关联关系</span>
        <span class="edge-empty-sub">该对象无出向边</span>
      </div>
    </template>

    <template v-else>
      <div class="edge-header">
        <span class="edge-title">出向关系</span>
        <span class="edge-count mono">{{ edges.length }}</span>
      </div>
      <ul class="edge-items">
        <li v-for="e in edges" :key="e.relation + e.to" class="edge-item">
          <span class="edge-rel">{{ e.relation }}</span>
          <button class="edge-target mono" :title="e.to" @click="$emit('navigate', e.to)">
            {{ e.to }}
          </button>
        </li>
      </ul>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { getObject, type Edge } from '../api'

const props = defineProps<{ objectId: string | null }>()
defineEmits<{ (e: 'navigate', id: string): void }>()

const edges = ref<Edge[]>([])
const loading = ref(false)

watch(
  () => props.objectId,
  async (id) => {
    edges.value = []
    if (!id) return
    loading.value = true
    try {
      const obj = await getObject(id)
      edges.value = obj.out_edges ?? []
    } catch {
      edges.value = []
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)
</script>

<style scoped>
.edge-list {
  padding: var(--space-4);
  height: 100%;
  overflow: auto;
}

.edge-empty {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: var(--space-6) var(--space-2);
  text-align: center;
}

.edge-empty-title {
  font-family: var(--display);
  font-weight: 600;
  font-size: 13px;
  color: var(--text-muted);
}

.edge-empty-sub {
  font-size: 12px;
  color: var(--text-faint);
}

.edge-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding-bottom: var(--space-2);
  margin-bottom: var(--space-2);
  border-bottom: 1px solid var(--border);
}

.edge-title {
  font-family: var(--display);
  font-weight: 600;
  font-size: 13px;
  color: var(--text);
}

.edge-count {
  font-size: 11px;
  color: var(--text-faint);
  background: var(--bg-sunken);
  padding: 1px 7px;
  border-radius: 999px;
}

.edge-items {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.edge-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-2);
  border-radius: var(--radius-sm);
  transition: background var(--dur-fast) var(--ease);
}

.edge-item:hover {
  background: var(--bg-sunken);
}

.edge-rel {
  font-size: 10.5px;
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
  font-size: 12px;
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
