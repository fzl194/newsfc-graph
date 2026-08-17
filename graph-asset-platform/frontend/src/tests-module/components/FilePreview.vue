<template>
  <div class="file-preview">
    <div class="fp-head">
      <span class="fp-name">{{ name }}</span>
      <span v-if="loading" class="fp-state">加载中…</span>
      <span v-else-if="!previewable" class="fp-state">（非 txt，不预览）</span>
      <span v-else-if="totalLines > PREVIEW_LINES" class="fp-toggle" @click="expanded = !expanded">
        {{ expanded ? '收起' : `展开全部（${totalLines} 行）` }}
      </span>
    </div>
    <pre v-if="previewable && content" class="fp-code">{{ shown }}</pre>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { getCaseFile } from '../api'

const props = defineProps<{ caseId: string; name: string }>()
const PREVIEW_LINES = 8

const content = ref('')
const loading = ref(false)
const expanded = ref(false)

const previewable = computed(() => /\.(txt|md|cfg|ini|conf)$/i.test(props.name) || !props.name.includes('.'))
const lines = computed(() => (content.value ? content.value.replace(/\r/g, '').split('\n') : []))
const totalLines = computed(() => lines.value.length)
const shown = computed(() =>
  expanded.value || totalLines.value <= PREVIEW_LINES
    ? content.value
    : lines.value.slice(0, PREVIEW_LINES).join('\n') + `\n…（还有 ${totalLines.value - PREVIEW_LINES} 行）`,
)

async function load(): Promise<void> {
  if (!previewable.value) {
    content.value = ''
    return
  }
  loading.value = true
  try {
    content.value = await getCaseFile(props.caseId, props.name)
  } catch {
    content.value = '（加载失败）'
  } finally {
    loading.value = false
  }
}

watch(() => [props.caseId, props.name], load, { immediate: true })
</script>

<style scoped>
.file-preview {
  background: var(--bg-sunken);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-3);
  margin-bottom: 6px;
}
.fp-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.fp-name {
  font-size: 12px;
  font-family: var(--mono);
  color: var(--text);
  font-weight: 600;
}
.fp-state {
  font-size: 11px;
  color: var(--text-faint);
}
.fp-toggle {
  font-size: 11px;
  color: var(--accent);
  cursor: pointer;
  margin-left: auto;
}
.fp-code {
  margin: 0;
  font-family: var(--mono);
  font-size: 12px;
  line-height: 1.55;
  color: var(--text);
  white-space: pre-wrap;
  max-height: 420px;
  overflow: auto;
}
</style>
