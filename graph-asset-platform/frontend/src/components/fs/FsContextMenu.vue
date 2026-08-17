<template>
  <ul ref="el" class="ctx-menu" :style="pos" @contextmenu.prevent>
    <li
      v-for="item in items"
      :key="item.key"
      class="ctx-item"
      :class="{ danger: item.danger, disabled: item.disabled }"
      @click.stop="onSelect(item)"
      @mouseenter="onHover(item)"
    >
      <span v-if="item.icon" class="ctx-icon" v-html="item.icon" />
      <span class="ctx-label">{{ item.label }}</span>
    </li>
  </ul>
</template>

<script lang="ts">
/** 菜单项；放独立 <script> 块以便跨组件 import 类型。 */
export interface CtxItem {
  key: string
  label: string
  icon?: string
  danger?: boolean
  disabled?: boolean
}
</script>

<script setup lang="ts">
/**
 * 通用右键上下文菜单（浮层）。
 * 定位 fixed；首次渲染按视口 + 自身尺寸做边缘翻转防溢出。
 * 关闭：菜单外 mousedown / Esc / 滚动 / 选中某项。
 */
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'

const props = defineProps<{ x: number; y: number; items: CtxItem[] }>()
const emit = defineEmits<{
  (e: 'select', key: string): void
  (e: 'hover', item: CtxItem): void
  (e: 'close'): void
}>()

const el = ref<HTMLElement | null>(null)
const left = ref(props.x)
const top = ref(props.y)
const pos = computed(() => ({ left: left.value + 'px', top: top.value + 'px' }))

async function clamp(): Promise<void> {
  await nextTick()
  const node = el.value
  if (!node) return
  const rect = node.getBoundingClientRect()
  const pad = 8
  let nx = props.x
  let ny = props.y
  if (nx + rect.width + pad > window.innerWidth) nx = window.innerWidth - rect.width - pad
  if (ny + rect.height + pad > window.innerHeight) ny = window.innerHeight - rect.height - pad
  if (nx < pad) nx = pad
  if (ny < pad) ny = pad
  left.value = nx
  top.value = ny
}

function close(): void {
  emit('close')
}
function onSelect(item: CtxItem): void {
  if (item.disabled) return
  emit('select', item.key)
  emit('close')
}
function onHover(item: CtxItem): void {
  if (!item.disabled) emit('hover', item)
}

function onDocMouseDown(e: MouseEvent): void {
  if (el.value && !el.value.contains(e.target as Node)) close()
}
function onKey(e: KeyboardEvent): void {
  if (e.key === 'Escape') close()
}

onMounted(() => {
  void clamp()
  document.addEventListener('mousedown', onDocMouseDown, true)
  window.addEventListener('scroll', close, true)
  window.addEventListener('wheel', close, { passive: true, capture: true })
  document.addEventListener('keydown', onKey)
})
onUnmounted(() => {
  document.removeEventListener('mousedown', onDocMouseDown, true)
  window.removeEventListener('scroll', close, true)
  window.removeEventListener('wheel', close, true)
  document.removeEventListener('keydown', onKey)
})
</script>

<style scoped>
.ctx-menu {
  position: fixed;
  z-index: 3000;
  margin: 0;
  padding: 4px;
  list-style: none;
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-md);
  min-width: 168px;
  user-select: none;
  animation: ctx-in var(--dur-fast) var(--ease) both;
}
@keyframes ctx-in {
  from { opacity: 0; transform: translateY(-2px) scale(0.99); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
.ctx-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 12.5px;
  color: var(--text);
  cursor: pointer;
  transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease);
}
.ctx-item:hover {
  background: var(--accent-soft);
  color: var(--accent-hover);
}
.ctx-item.danger {
  color: var(--danger);
}
.ctx-item.danger:hover {
  background: var(--danger);
  color: #fff;
}
.ctx-item.disabled {
  color: var(--text-faint);
  cursor: not-allowed;
}
.ctx-item.disabled:hover {
  background: transparent;
  color: var(--text-faint);
}
.ctx-icon {
  display: inline-flex;
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  align-items: center;
}
.ctx-icon :deep(svg) {
  width: 14px;
  height: 14px;
}
.ctx-label {
  white-space: nowrap;
}
</style>
