<template>
  <div class="detail-view">
    <div class="detail-head">
      <button class="back-btn" @click="emit('back')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
          <path d="M15 6l-6 6 6 6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        返回目录
      </button>
      <span class="file-path mono" :title="path">{{ path }}</span>
      <div v-if="canManage" class="detail-actions">
        <button class="action-btn" :disabled="editing" @click="emit('action', { type: 'rename' })">重命名</button>
        <button class="action-btn" :disabled="editing" @click="emit('action', { type: 'move' })">移动</button>
        <button class="action-btn danger" :disabled="editing" @click="emit('action', { type: 'delete' })">删除</button>
      </div>
    </div>

    <div v-if="canManage" class="edit-bar">
      <template v-if="!editing">
        <button class="ghost-btn" @click="startEdit">编辑</button>
      </template>
      <template v-else>
        <button class="primary-btn" :disabled="saving" @click="saveEdit">
          {{ saving ? '保存中…' : '保存' }}
        </button>
        <button class="ghost-btn" :disabled="saving" @click="cancelEdit">取消</button>
      </template>
      <span v-if="editError" class="edit-error">{{ editError }}</span>
    </div>

    <div v-if="loading" class="hint">加载中…</div>
    <textarea
      v-else-if="editing"
      v-model="editText"
      class="edit-area"
      spellcheck="false"
    />
    <div v-else class="preview md-body" v-html="renderedHtml" />
  </div>
</template>

<script setup lang="ts">
/**
 * 文件详情（整页）：返回目录 + 路径 + 操作按钮 + 预览/内联编辑。
 * 编辑在本组件内完成（writeFsFile）；重命名/移动/删除 emit action 交编排器走弹窗。
 * 保存后若文件归位（moved_from 非空）→ emit action {type:'moved', path}，编排器跟随新路径。
 */
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'
import { readFsFile, writeFsFile } from '../../api'

const props = defineProps<{ path: string; canManage: boolean }>()
const emit = defineEmits<{
  (e: 'back'): void
  (e: 'action', a: { type: string; path?: string }): void
}>()

const md = new MarkdownIt({ html: false, linkify: true })

const fileContent = ref('')
const loading = ref(false)
const editing = ref(false)
const editText = ref('')
const saving = ref(false)
const editError = ref('')

async function load(): Promise<void> {
  if (!props.path) {
    fileContent.value = ''
    return
  }
  loading.value = true
  editing.value = false
  editError.value = ''
  try {
    fileContent.value = await readFsFile(props.path)
  } catch {
    fileContent.value = ''
  } finally {
    loading.value = false
  }
}

watch(() => props.path, load, { immediate: true })

const renderedHtml = computed(() => {
  if (!fileContent.value) return ''
  // 脱掉 frontmatter 段再渲染（预览只看正文）
  const body = fileContent.value.replace(/^---\n[\s\S]*?\n---\n/, '')
  return DOMPurify.sanitize(md.render(body))
})

function startEdit(): void {
  editText.value = fileContent.value
  editing.value = true
  editError.value = ''
}
function cancelEdit(): void {
  editing.value = false
  editError.value = ''
}
async function saveEdit(): Promise<void> {
  if (!props.path) return
  saving.value = true
  editError.value = ''
  try {
    const r = await writeFsFile(props.path, editText.value)
    editing.value = false
    if (r.moved_from) {
      ElMessage.success(`已保存，文件归位到 ${r.path}`)
      emit('action', { type: 'moved', path: r.path })
    } else {
      ElMessage.success('已保存')
      fileContent.value = editText.value
    }
    emit('action', { type: 'refresh' })
  } catch (e) {
    editError.value = e instanceof Error ? e.message : String(e)
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.detail-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}
.detail-head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-faint);
  flex-shrink: 0;
  background: var(--bg-elev);
}
.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-family: var(--sans);
  font-size: 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease);
  border: 1px solid var(--border-strong);
  background: var(--bg-elev);
  color: var(--text-muted);
  padding: 4px 10px;
  flex-shrink: 0;
}
.back-btn:hover {
  color: var(--accent);
  border-color: var(--accent);
}
.file-path {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.detail-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
.edit-bar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  border-bottom: 1px solid var(--border-faint);
  flex-shrink: 0;
}
.edit-error {
  color: var(--danger);
  font-size: 12px;
}

.hint {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-faint);
  font-size: 13px;
}
.edit-area {
  flex: 1;
  min-height: 0;
  resize: none;
  border: none;
  border-top: 1px solid var(--border-faint);
  padding: var(--space-4) var(--space-5);
  font-family: var(--mono);
  font-size: 12.5px;
  line-height: 1.6;
  outline: none;
  background: var(--bg-sunken);
}
.preview {
  flex: 1;
  overflow: auto;
  padding: var(--space-5) var(--space-6);
}

.action-btn,
.ghost-btn,
.primary-btn {
  font-family: var(--sans);
  font-size: 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease);
  border: 1px solid var(--border-strong);
  background: var(--bg-elev);
  color: var(--text-muted);
  padding: 4px 10px;
}
.action-btn:hover,
.ghost-btn:hover {
  color: var(--accent);
  border-color: var(--accent);
}
.primary-btn {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
.primary-btn:hover {
  background: var(--accent-hover);
}
.action-btn.danger {
  color: var(--danger);
  border-color: var(--border-strong);
}
.action-btn.danger:hover {
  color: #fff;
  background: var(--danger);
  border-color: var(--danger);
}
.action-btn:disabled,
.primary-btn:disabled,
.ghost-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
