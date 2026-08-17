<template>
  <div class="browser-view">
    <Splitpanes class="browser-panes" @resize="onPaneResize">
      <Pane :size="24" :min-size="16" :max-size="40">
        <LayerNav />
      </Pane>
      <Pane :size="42" :min-size="24">
        <MdPreview :object-id="selectedId" @navigate="onNavigate" />
      </Pane>
      <Pane :size="34" :min-size="18" :max-size="50">
        <NeighborPane :object-id="selectedId" />
      </Pane>
    </Splitpanes>
  </div>
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Splitpanes, Pane } from 'splitpanes'
import 'splitpanes/dist/splitpanes.css'
import LayerNav from '../components/LayerNav.vue'
import MdPreview from '../components/MdPreview.vue'
import NeighborPane from '../components/NeighborPane.vue'
import { useNav } from '../composables/useNav'

const { selectedId, viewVersion, syncTo } = useNav()
const route = useRoute()
const router = useRouter()

// 跨栏跳转：中栏 md 点 wiki 链接 / 右栏点邻居 → syncTo（左栏切层+选择器+高亮，中右栏自动切）
function onNavigate(id: string): void {
  if (!id) return
  void syncTo(id)
}

// splitpanes resize 仅触发 vis-network 重绘（通过 window resize 事件间接触发）
// 这里留空占位，GraphCanvas 已监听 window resize；splitpanes 改尺寸会触发容器 resize
function onPaneResize(): void {
  window.dispatchEvent(new Event('resize'))
}

// ---- URL 同步 ?o={id}&version= ----
// 挂载时：若有 ?o 则 syncTo（恢复分享链接 / 浏览器刷新；?version= 显式恢复版本上下文）
onMounted(() => {
  const o = typeof route.query.o === 'string' ? route.query.o : ''
  const v = typeof route.query.version === 'string' ? route.query.version : ''
  if (o) {
    void syncTo(o, v || undefined)
  }
})

// selectedId 变化 → router.replace 更新 ?o（避免污染历史，可前进后退）
let suppressUrlUpdate = false
watch(
  selectedId,
  (id) => {
    if (suppressUrlUpdate) return
    if (!id) return
    const version = viewVersion.value || undefined
    const query: Record<string, string> = { o: id }
    if (version) query.version = version
    // 仅当 query 真正变化时 replace
    const cur = route.query
    if (cur.o !== id || (cur.version ?? '') !== (version ?? '')) {
      suppressUrlUpdate = true
      router.replace({ query }).finally(() => {
        suppressUrlUpdate = false
      })
    }
  },
)
</script>

<style scoped>
.browser-view {
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

/* splitpanes 主题适配（融入工程风） */
.browser-panes {
  height: 100%;
}

:deep(.splitpanes__splitter) {
  background: var(--border);
  position: relative;
  flex-shrink: 0;
}

:deep(.splitpanes--vertical > .splitpanes__splitter) {
  width: 5px;
  cursor: col-resize;
  transition: background var(--dur-fast) var(--ease);
}

:deep(.splitpanes--vertical > .splitpanes__splitter::before) {
  content: '';
  position: absolute;
  inset: 0 2px;
  background: transparent;
  border-radius: 2px;
  transition: background var(--dur-fast) var(--ease);
}

:deep(.splitpanes--vertical > .splitpanes__splitter:hover::before) {
  background: var(--accent-ring);
}

:deep(.splitpanes__pane) {
  background: var(--bg-elev);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
</style>
