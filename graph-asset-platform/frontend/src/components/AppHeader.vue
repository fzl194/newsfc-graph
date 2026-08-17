<template>
  <header class="app-header">
    <div class="brand">
      <div class="brand-mark" aria-hidden="true">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
          <circle cx="6" cy="6" r="2.4" fill="currentColor" />
          <circle cx="18" cy="6" r="2.4" fill="currentColor" opacity="0.55" />
          <circle cx="12" cy="18" r="2.4" fill="currentColor" opacity="0.75" />
          <path
            d="M6 6 L18 6 M6 6 L12 18 M18 6 L12 18"
            stroke="currentColor"
            stroke-width="1.2"
            opacity="0.4"
          />
        </svg>
      </div>
      <div class="brand-text">
        <span class="brand-title">图谱资产平台</span>
      </div>
    </div>

    <nav class="tabs">
      <RouterLink
        v-for="t in tabs"
        :key="t.to"
        :to="t.to"
        class="tab"
        active-class="tab--active"
      >
        <component :is="t.icon" class="tab-icon" />
        <span>{{ t.label }}</span>
      </RouterLink>
    </nav>

    <div class="stats-chips">
      <div v-if="totalObjects !== null" class="chip">
        <span class="chip-label">对象</span>
        <span class="chip-val mono">{{ totalObjects.toLocaleString() }}</span>
      </div>
      <div v-if="edgeCount !== null" class="chip">
        <span class="chip-label">边</span>
        <span class="chip-val mono">{{ edgeCount.toLocaleString() }}</span>
      </div>
      <div class="chip user-chip">
        <span class="chip-label">{{ session?.username }}</span>
        <button class="logout-link" @click="logout">登出</button>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { stats, type Stats } from '../api'
import { getSession, clearSession } from '../auth'

const globalStats = ref<Stats | null>(null)
const session = getSession()

function logout(): void {
  clearSession()
  window.location.assign('/login')
}

async function load(): Promise<void> {
  try {
    globalStats.value = await stats()
  } catch {
    /* header chip 容错，不打断用户 */
  }
}

// 简单内联 SVG 图标（避免引依赖）
const GraphIcon = () =>
  h(
    'svg',
    { width: '15', height: '15', viewBox: '0 0 24 24', fill: 'none' },
    [
      h('circle', { cx: '6', cy: '7', r: '2.2', stroke: 'currentColor', 'stroke-width': '1.7' }),
      h('circle', { cx: '18', cy: '7', r: '2.2', stroke: 'currentColor', 'stroke-width': '1.7' }),
      h('circle', { cx: '12', cy: '17', r: '2.2', stroke: 'currentColor', 'stroke-width': '1.7' }),
      h('path', {
        d: 'M7.8 8.3 16.2 8.3 M7 8.7 10.8 15 M17 8.7 13.2 15',
        stroke: 'currentColor',
        'stroke-width': '1.5',
        opacity: '0.7',
      }),
    ],
  )
const StatsIcon = () =>
  h(
    'svg',
    { width: '15', height: '15', viewBox: '0 0 24 24', fill: 'none' },
    [
      h('rect', {
        x: '3',
        y: '11',
        width: '4',
        height: '9',
        rx: '1',
        stroke: 'currentColor',
        'stroke-width': '1.7',
      }),
      h('rect', {
        x: '10',
        y: '6',
        width: '4',
        height: '14',
        rx: '1',
        stroke: 'currentColor',
        'stroke-width': '1.7',
      }),
      h('rect', {
        x: '17',
        y: '3',
        width: '4',
        height: '17',
        rx: '1',
        stroke: 'currentColor',
        'stroke-width': '1.7',
      }),
    ],
  )
const UploadIcon = () =>
  h(
    'svg',
    { width: '15', height: '15', viewBox: '0 0 24 24', fill: 'none' },
    [
      h('path', {
        d: 'M12 16V4m0 0L7 9m5-5 5 5',
        stroke: 'currentColor',
        'stroke-width': '1.7',
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
      }),
      h('path', {
        d: 'M4 17v2a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-2',
        stroke: 'currentColor',
        'stroke-width': '1.7',
        'stroke-linecap': 'round',
      }),
    ],
  )
const TestIcon = () =>
  h(
    'svg',
    { width: '15', height: '15', viewBox: '0 0 24 24', fill: 'none' },
    [
      h('path', {
        d: 'M4 5h16v11H4z',
        stroke: 'currentColor',
        'stroke-width': '1.7',
        'stroke-linejoin': 'round',
      }),
      h('path', {
        d: 'M8 9h3M8 12h6',
        stroke: 'currentColor',
        'stroke-width': '1.5',
        'stroke-linecap': 'round',
      }),
      h('path', {
        d: 'M9 20h6M12 16v4',
        stroke: 'currentColor',
        'stroke-width': '1.7',
        'stroke-linecap': 'round',
      }),
    ],
  )

const UserIcon = () =>
  h(
    'svg',
    { width: '15', height: '15', viewBox: '0 0 24 24', fill: 'none' },
    [
      h('circle', { cx: '12', cy: '8', r: '3.2', stroke: 'currentColor', 'stroke-width': '1.7' }),
      h('path', {
        d: 'M5 20c0-3.3 3.1-6 7-6s7 2.7 7 6',
        stroke: 'currentColor',
        'stroke-width': '1.7',
        'stroke-linecap': 'round',
      }),
    ],
  )

const FolderIcon = () =>
  h(
    'svg',
    { width: '15', height: '15', viewBox: '0 0 24 24', fill: 'none' },
    [
      h('path', {
        d: 'M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',
        stroke: 'currentColor',
        'stroke-width': '1.7',
        'stroke-linejoin': 'round',
      }),
    ],
  )

const tabs = computed(() => {
  const s = getSession()
  const base = [
    { to: '/', label: '图谱浏览', icon: GraphIcon },
    { to: '/stats', label: '统计', icon: StatsIcon },
  ]
  if (s?.can_assets) base.push({ to: '/fs', label: '资产目录', icon: FolderIcon })
  if (s?.can_assets) base.push({ to: '/upload', label: '上传', icon: UploadIcon })
  if (s?.can_test) base.push({ to: '/tests', label: '测试', icon: TestIcon })
  if (s?.is_admin) base.push({ to: '/users', label: '用户', icon: UserIcon })
  return base
})

const totalObjects = computed(() =>
  globalStats.value
    ? Object.values(globalStats.value.object_counts_by_type).reduce(
        (a, b) => a + b,
        0,
      )
    : null,
)
const edgeCount = computed(() => globalStats.value?.edge_count ?? null)

onMounted(load)

// 监听全局刷新（上传后触发）
;(window as unknown as { __refreshStats?: () => Promise<void> }).__refreshStats =
  load
</script>

<style scoped>
.app-header {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: var(--space-6);
  height: 56px;
  padding: 0 var(--space-6);
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(12px) saturate(140%);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 100;
  flex-shrink: 0;
}

.brand {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 9px;
  background: linear-gradient(145deg, var(--accent), #6366f1);
  color: #fff;
  box-shadow: 0 4px 12px rgba(79, 70, 229, 0.28);
}

.brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.15;
}

.brand-title {
  font-family: var(--display);
  font-weight: 700;
  font-size: 15px;
  color: var(--text);
  letter-spacing: -0.01em;
}

.brand-sub {
  font-size: 10.5px;
  color: var(--text-faint);
  letter-spacing: 0.02em;
}

.tabs {
  display: flex;
  gap: var(--space-1);
  justify-self: center;
  background: var(--bg-sunken);
  padding: 4px;
  border-radius: var(--radius);
  border: 1px solid var(--border-faint);
}

.tab {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px 14px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  text-decoration: none;
  border-radius: var(--radius-sm);
  transition: all var(--dur-fast) var(--ease);
}

.tab:hover {
  color: var(--text);
  background: var(--bg-hover);
}

.tab--active {
  color: var(--accent);
  background: var(--bg-elev);
  box-shadow: var(--shadow-sm), 0 0 0 1px var(--border);
}

.tab-icon {
  display: inline-flex;
}

.stats-chips {
  display: flex;
  gap: var(--space-2);
}

.chip {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  padding: 5px 11px;
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 12px;
}

.chip-label {
  color: var(--text-faint);
}

.chip-val {
  color: var(--text);
  font-weight: 600;
  font-size: 12.5px;
}

@media (max-width: 720px) {
  .app-header {
    grid-template-columns: auto 1fr;
    gap: var(--space-3);
  }
  .stats-chips {
    display: none;
  }
  .brand-sub {
    display: none;
  }
}

.user-chip {
  align-items: center;
}
.logout-link {
  background: none;
  border: none;
  color: var(--accent);
  font-size: 11px;
  cursor: pointer;
  padding: 0;
  margin-left: 6px;
}
.logout-link:hover {
  text-decoration: underline;
}
</style>
