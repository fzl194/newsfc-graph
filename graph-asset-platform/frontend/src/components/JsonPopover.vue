<template>
  <el-popover placement="left" :width="520" trigger="click">
    <template #reference>
      <span class="jp-preview mono" title="点击查看完整 JSON">{{ preview }}</span>
    </template>
    <pre class="jp-pre mono">{{ pretty }}</pre>
  </el-popover>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElPopover } from 'element-plus'

const props = defineProps<{ value: unknown }>()

// 单行预览（表格内保持紧凑，点击弹层看完整格式化 JSON）
const preview = computed((): string => {
  const v = props.value
  if (v === undefined || v === null || v === '') return '—'
  return typeof v === 'string' ? v : JSON.stringify(v)
})

const pretty = computed((): string => {
  try {
    const v = typeof props.value === 'string' ? JSON.parse(props.value) : props.value
    return JSON.stringify(v, null, 2)
  } catch {
    return String(props.value)
  }
})
</script>

<style scoped>
.jp-preview {
  font-size: 11px;
  color: var(--text-muted);
  display: inline-block;
  max-width: 340px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
  cursor: pointer;
  border-bottom: 1px dashed var(--border);
}
.jp-pre {
  margin: 0;
  max-height: 360px;
  overflow: auto;
  font-size: 11.5px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--text);
}
</style>
