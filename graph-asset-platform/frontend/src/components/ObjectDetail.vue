<template>
  <div class="object-detail">
    <template v-if="!center">
      <div class="detail-empty">
        <div class="empty-title">对象详情</div>
        <div class="empty-sub">在画布上点击节点，或搜索一个对象 id</div>
      </div>
    </template>

    <template v-else>
      <header class="detail-head">
        <div class="head-row">
          <span v-if="center.type" class="badge badge-type">{{ center.type }}</span>
          <span v-if="center.nf" class="badge">{{ center.nf }}</span>
          <span v-if="center.version" class="badge mono">{{ center.version }}</span>
        </div>
        <div class="obj-id mono" :title="center.id">{{ center.id }}</div>
        <div v-if="fmName" class="obj-name">{{ fmName }}</div>
      </header>

      <section v-if="fmEntries.length" class="detail-section">
        <div class="section-title">Frontmatter</div>
        <dl class="fm-grid">
          <template v-for="e in fmEntries" :key="e.k">
            <dt class="fm-key mono">{{ e.k }}</dt>
            <dd class="fm-val mono" :title="e.v">{{ e.v }}</dd>
          </template>
        </dl>
      </section>

      <section v-if="out.length" class="detail-section">
        <div class="section-title">
          出向边 <span class="section-count mono">{{ out.length }}</span>
        </div>
        <ul class="edge-list">
          <li v-for="e in out" :key="'o' + e.relation + e.to" class="edge-row">
            <span class="edge-rel">{{ e.relation }}</span>
            <button class="edge-target mono" @click="$emit('navigate', e.to)" :title="e.to">
              {{ e.to }}
            </button>
          </li>
        </ul>
      </section>

      <section v-if="inEdges.length" class="detail-section">
        <div class="section-title">
          入向边 <span class="section-count mono">{{ inEdges.length }}</span>
        </div>
        <ul class="edge-list">
          <li v-for="e in inEdges" :key="'i' + e.relation + e.from" class="edge-row">
            <span class="edge-rel">{{ e.relation }}</span>
            <button class="edge-target mono" @click="$emit('navigate', e.from)" :title="e.from">
              {{ e.from }}
            </button>
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Edge, ObjectDetail } from '../api'

const props = defineProps<{
  center: ObjectDetail | null
  out: Edge[]
  inEdges: Edge[]
}>()

defineEmits<{ (e: 'navigate', id: string): void }>()

const fmName = computed(() => {
  const fm = props.center?.frontmatter
  const v = fm?.name_zh ?? fm?.name
  return typeof v === 'string' ? v : ''
})

const fmEntries = computed(() => {
  const fm = props.center?.frontmatter
  if (!fm) return []
  return Object.entries(fm)
    .filter(([k]) => !['id', 'type', 'nf', 'version', 'name', 'name_zh'].includes(k))
    .slice(0, 10)
    .map(([k, v]) => ({ k, v: formatVal(v) }))
})

function formatVal(v: unknown): string {
  if (v == null) return ''
  if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') return String(v)
  if (Array.isArray(v)) return v.join(', ')
  return JSON.stringify(v)
}
</script>

<style scoped>
.object-detail {
  height: 100%;
  overflow: auto;
  display: flex;
  flex-direction: column;
}

.detail-empty {
  padding: var(--space-8) var(--space-4);
  text-align: center;
  color: var(--text-faint);
}

.empty-title {
  font-family: var(--display);
  font-weight: 600;
  font-size: 14px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.empty-sub {
  font-size: 12px;
}

.detail-head {
  padding: var(--space-4);
  border-bottom: 1px solid var(--border);
  background: var(--bg-elev);
  position: sticky;
  top: 0;
  z-index: 2;
}

.head-row {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
  flex-wrap: wrap;
}

.badge {
  font-size: 11px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  background: var(--bg-sunken);
  color: var(--text-muted);
  border: 1px solid var(--border);
}

.badge-type {
  background: var(--accent-soft);
  color: var(--accent);
  border-color: transparent;
}

.obj-id {
  font-size: 12.5px;
  color: var(--text);
  word-break: break-all;
  line-height: 1.4;
}

.obj-name {
  margin-top: 4px;
  font-size: 13px;
  color: var(--text-muted);
}

.detail-section {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-faint);
}

.section-title {
  font-family: var(--display);
  font-weight: 600;
  font-size: 11.5px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-faint);
  margin-bottom: var(--space-2);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.section-count {
  text-transform: none;
  letter-spacing: 0;
  font-size: 10.5px;
  background: var(--bg-sunken);
  padding: 0 6px;
  border-radius: 999px;
}

.fm-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 4px var(--space-3);
  margin: 0;
}

.fm-key {
  font-size: 11px;
  color: var(--text-faint);
}

.fm-val {
  font-size: 11.5px;
  color: var(--text);
  word-break: break-all;
  margin: 0;
  max-height: 3.6em;
  overflow: hidden;
}

.edge-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.edge-row {
  display: flex;
  flex-direction: column;
  padding: var(--space-2);
  border-radius: var(--radius-sm);
  gap: 2px;
}

.edge-row:hover {
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
  font-size: 12px;
  font-family: var(--mono);
  color: var(--text);
  word-break: break-all;
}

.edge-target:hover {
  color: var(--accent);
}
</style>
