<template>
  <div class="md-preview">
    <div v-if="!objectId" class="empty">
      <div class="empty-icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
          <path
            d="M6 2h8l5 5v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Z"
            stroke="currentColor"
            stroke-width="1.2"
            stroke-linejoin="round"
            opacity="0.4"
          />
          <path d="M14 2v5h5" stroke="currentColor" stroke-width="1.2" opacity="0.4" />
          <path
            d="M8 13h8M8 16h5"
            stroke="currentColor"
            stroke-width="1.2"
            stroke-linecap="round"
            opacity="0.3"
          />
        </svg>
      </div>
      <div class="empty-title">未选择对象</div>
      <div class="empty-sub">从左侧目录选择一个文件以预览其内容</div>
    </div>

    <template v-else>
      <div class="meta-bar">
        <div class="meta-left">
          <span v-if="detail?.type" class="badge badge-type">{{ detail.type }}</span>
          <span v-if="detail?.nf" class="badge">{{ detail.nf }}</span>
          <span v-if="detail?.version" class="badge badge-ver mono">{{ detail.version }}</span>
          <span class="meta-id mono" :title="objectId">{{ objectId }}</span>
        </div>
        <div class="meta-right">
          <el-select
            v-if="versions.length > 1"
            v-model="selectedVersion"
            size="small"
            class="ver-select"
            @change="onVersionChange"
          >
            <el-option
              v-for="v in versions"
              :key="v"
              :label="v"
              :value="v"
            />
          </el-select>
        </div>
      </div>

      <div class="md-scroll" v-loading="loading">
        <!-- 结构化 frontmatter 面板（正文上方卡片） -->
        <section v-if="detail && (coreBadges.length || fmRows.length)" class="fm-panel">
          <header class="fm-panel-head">
            <span class="fm-panel-title">元信息</span>
            <span class="fm-panel-sub mono">{{ coreBadges.length + fmRows.length }} 项</span>
          </header>
          <div class="fm-badges" v-if="coreBadges.length">
            <span
              v-for="b in coreBadges"
              :key="b.k"
              class="fm-badge"
              :class="{ 'fm-badge-accent': b.accent }"
            >
              <span class="fm-badge-k mono">{{ b.k }}</span>
              <span class="fm-badge-v mono" :title="b.v">{{ b.v }}</span>
            </span>
          </div>
          <dl class="fm-grid">
            <template v-for="r in fmRows" :key="r.k">
              <dt class="fm-key mono">{{ r.k }}</dt>
              <dd class="fm-val">
                <pre v-if="r.isMulti" class="fm-val-pre mono">{{ r.v }}</pre>
                <span v-else class="fm-val-inline mono" :title="r.v">{{ r.v }}</span>
              </dd>
            </template>
          </dl>
        </section>

        <article
          v-if="html"
          class="md-body"
          v-html="html"
          @click="onBodyClick"
        ></article>
        <div v-else-if="!loading" class="empty small">
          <div class="empty-sub">无内容</div>
        </div>

        <!-- 关系（边）区块：正文下方，点击跳转 -->
        <section v-if="edgeRows.length" class="rel-section">
          <header class="rel-head">
            <span class="rel-title">关系（边）</span>
            <span class="rel-count mono">{{ edgeRows.length }}</span>
          </header>
          <ul class="rel-list">
            <li
              v-for="e in edgeRows"
              :key="e.relation + '::' + e.to"
              class="rel-row"
              @click="emit('navigate', e.to)"
            >
              <span class="rel-name">{{ e.relation }}</span>
              <span class="rel-arrow">→</span>
              <span class="rel-to mono" :title="e.to">{{ e.to }}</span>
            </li>
          </ul>
        </section>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import { getObject, getNameMap, availableVersionsFromError, resolveImgUrls, type Edge, type ObjectDetail } from '../api'
import { useNav } from '../composables/useNav'

const { viewVersion } = useNav()

const props = defineProps<{ objectId: string | null }>()
const emit = defineEmits<{ (e: 'navigate', id: string): void }>()

const md = new MarkdownIt({
  // html:true 让源 md 单元格里的 <br>（命令参数表大量使用）渲染成换行；
  // 渲染结果会再经 DOMPurify 消毒，安全。
  html: true,
  linkify: true,
  breaks: false,
  typographer: false,
})

// 允许 a.wiki-link / span.wiki-link 上的 data-wiki-id 属性通过净化
DOMPurify.addHook('uponSanitizeAttribute', (_node, data) => {
  if (
    (data.attrName === 'data-wiki-id' || data.attrName === 'class') &&
    data.attrValue != null &&
    /wiki-link|data-wiki-id/.test(data.attrValue + (data.attrName === 'class' ? '' : ''))
  ) {
    data.keepAttr = true
  }
})
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.nodeType === 1 && node.classList?.contains('wiki-link')) {
    node.setAttribute('target', '_self')
  }
})

const detail = ref<ObjectDetail | null>(null)
const html = ref('')
const loading = ref(false)
const selectedVersion = ref<string>('')

const versions = computed(() => detail.value?.versions ?? [])

// 核心字段（badge 突出）
const CORE_FIELDS = ['id', 'type', 'nf', 'version', 'domain', 'scenario', 'status', 'source']
const CORE_ACCENT = new Set(['type', 'status'])

const coreBadges = computed(() => {
  const fm = detail.value?.frontmatter
  if (!fm) return []
  const out: { k: string; v: string; accent: boolean }[] = []
  for (const k of CORE_FIELDS) {
    if (!(k in fm)) continue
    const v = formatScalar(fm[k])
    if (v === '') continue
    out.push({ k, v, accent: CORE_ACCENT.has(k) })
  }
  return out
})

// 普通 key-value 行（不含核心字段、不含 name）
const fmRows = computed(() => {
  const fm = detail.value?.frontmatter
  if (!fm) return []
  const rows: { k: string; v: string; isMulti: boolean }[] = []
  for (const [k, v] of Object.entries(fm)) {
    if (CORE_FIELDS.includes(k)) continue
    if (k === 'name' || k === 'name_zh') continue
    if (v == null) continue
    const formatted = formatValue(v)
    if (formatted.text === '') continue
    rows.push({ k, v: formatted.text, isMulti: formatted.isMulti })
  }
  return rows
})

const edgeRows = computed<Edge[]>(() => detail.value?.out_edges ?? [])

function formatScalar(v: unknown): string {
  if (v == null) return ''
  if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') {
    return String(v)
  }
  return ''
}

function formatValue(v: unknown): { text: string; isMulti: boolean } {
  if (v == null) return { text: '', isMulti: false }
  if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') {
    return { text: String(v), isMulti: false }
  }
  if (Array.isArray(v)) {
    // 每行一个，便于阅读
    if (v.every((x) => typeof x === 'string' || typeof x === 'number')) {
      return { text: v.map((x) => String(x)).join('\n'), isMulti: true }
    }
    return { text: JSON.stringify(v, null, 2), isMulti: true }
  }
  // 嵌套对象 → 美化 JSON
  return { text: JSON.stringify(v, null, 2), isMulti: true }
}

// 把 body_md 里的内联 [[X]] 预处理成可点击占位
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function escapeAttr(s: string): string {
  return s.replace(/"/g, '&quot;').replace(/&/g, '&amp;').replace(/</g, '&lt;')
}

async function load(id: string, ver?: string): Promise<void> {
  loading.value = true
  html.value = ''
  try {
    // 只用 getObject：body_md 已去 frontmatter 与 ## 边（纯正文）
    const obj = await getObject(id, ver)
    detail.value = obj
    selectedVersion.value = obj.version ?? ver ?? ''
    // body_md 已由后端 md_parser 归一化换行 + 折叠表格内部空行（纯正文，干净 LF）。
    const body = (obj.body_md || '').replace(/\r/g, '')
    // ![](assets/x.png) 相对引用 → /fs/raw 端点（dir = 本 md 在资产库中的所在目录）
    const dir = (obj.source_path || '').split('/').slice(0, -1).join('/')
    const rendered = md.render(resolveImgUrls(body, dir))
    // 正文 [[ID]] 替换为可点击 a，显示文本查目标 name（无则显 ID）
    const names = await getNameMap()
    const finalHtml = inlineLinksIntoHtml(rendered, names)
    html.value = DOMPurify.sanitize(finalHtml, {
      ADD_ATTR: ['data-wiki-id', 'target', 'rel'],
    })
  } catch (e: unknown) {
    const avail = availableVersionsFromError(e)
    detail.value = null
    if (avail && avail.length) {
      html.value = `<p style="color:var(--text-muted)">该版本缺失，可用版本：<code>${avail.join(
        ', ',
      )}</code></p>`
    } else {
      const msg = e instanceof Error ? e.message : String(e)
      html.value = `<p style="color:var(--danger)">加载失败：${escapeHtml(msg)}</p>`
    }
  } finally {
    loading.value = false
  }
}

// 把 markdown-it 渲染后的 HTML 里的 [[X]]（出现在纯文本节点里）替换成可点击 a。
// markdown-it 对 [[ 不做特殊处理，原样保留在文本里。
function inlineLinksIntoHtml(rendered: string, names: Map<string, string>): string {
  // 对每个 [[X]]，整体替换为 a 标签。X 不含 ] 与换行。
  // 显示文本 = 目标 name（查 names 映射），无则显 ID 本身；title 保留 ID。
  return rendered.replace(/\[\[([^\]\n]+?)\]\]/g, (_m, id: string) => {
    const t = id.trim()
    const display = names.get(t) || t
    const safeAttr = escapeAttr(t)
    return `<a class="wiki-link" data-wiki-id="${safeAttr}" href="#" rel="wikilink" title="${escapeAttr(
      t,
    )}">${escapeHtml(display)}</a>`
  })
}

function onBodyClick(ev: MouseEvent): void {
  const target = ev.target as HTMLElement | null
  if (!target) return
  const link = target.closest('.wiki-link') as HTMLAnchorElement | null
  if (!link) return
  ev.preventDefault()
  const id = link.getAttribute('data-wiki-id')
  if (id) emit('navigate', id)
}

function onVersionChange(v: string): void {
  // 版本上下文联动：中栏切换版本 → 右栏邻居图也切到同一版本
  viewVersion.value = v
  if (props.objectId) load(props.objectId, v)
}

watch(
  () => props.objectId,
  (id) => {
    if (id) load(id, viewVersion.value || undefined)
  },
  { immediate: true },
)
</script>

<style scoped>
.md-preview {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-elev);
}

.empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  color: var(--text-faint);
}

.empty.small {
  padding: var(--space-10);
}

.empty-icon {
  color: var(--text-faint);
  margin-bottom: var(--space-2);
}

.empty-title {
  font-family: var(--display);
  font-size: 16px;
  font-weight: 600;
  color: var(--text-muted);
}

.empty-sub {
  font-size: 13px;
}

.meta-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-5);
  border-bottom: 1px solid var(--border);
  background: var(--bg-elev);
  flex-wrap: wrap;
  flex-shrink: 0;
}

.meta-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  flex: 1;
}

.meta-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

.badge {
  display: inline-flex;
  align-items: center;
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

.badge-ver {
  font-size: 10.5px;
}

.meta-id {
  font-size: 12px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.ver-select {
  width: 130px;
}

.md-scroll {
  flex: 1;
  overflow: auto;
  padding: var(--space-5) var(--space-6);
}

/* ---- 结构化 frontmatter 面板 ---- */
.fm-panel {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elev);
  padding: var(--space-4) var(--space-5);
  margin-bottom: var(--space-6);
  box-shadow: var(--shadow-sm);
}

.fm-panel-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}

.fm-panel-title {
  font-family: var(--display);
  font-size: 12.5px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-faint);
}

.fm-panel-sub {
  font-size: 11px;
  color: var(--text-faint);
}

.fm-badges {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-faint);
  margin-bottom: var(--space-3);
}

.fm-badge {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  padding: 3px 9px;
  border-radius: var(--radius-sm);
  background: var(--bg-sunken);
  border: 1px solid var(--border);
  min-width: 0;
}

.fm-badge-accent {
  background: var(--accent-soft);
  border-color: transparent;
}

.fm-badge-k {
  font-size: 10.5px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-faint);
  flex-shrink: 0;
}

.fm-badge-v {
  font-size: 11.5px;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 240px;
}

.fm-badge-accent .fm-badge-v {
  color: var(--accent);
  font-weight: 500;
}

.fm-grid {
  display: grid;
  grid-template-columns: minmax(120px, auto) 1fr;
  gap: var(--space-1) var(--space-4);
  margin: 0;
}

.fm-key {
  font-size: 11.5px;
  color: var(--text-faint);
  align-self: start;
  padding-top: 2px;
}

.fm-val {
  margin: 0;
  min-width: 0;
}

.fm-val-inline {
  font-size: 12px;
  color: var(--text);
  word-break: break-all;
}

.fm-val-pre {
  font-size: 11.5px;
  color: var(--text);
  background: var(--bg-sunken);
  border: 1px solid var(--border-faint);
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-3);
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 12em;
  overflow: auto;
}

/* ---- 关系（边）区块 ---- */
.rel-section {
  margin-top: var(--space-8);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elev);
  overflow: hidden;
}

.rel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  background: var(--bg-sunken);
  border-bottom: 1px solid var(--border);
}

.rel-title {
  font-family: var(--display);
  font-size: 12.5px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
}

.rel-count {
  font-size: 11px;
  color: var(--text-faint);
  background: var(--bg-elev);
  border: 1px solid var(--border);
  padding: 1px 8px;
  border-radius: 999px;
}

.rel-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.rel-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  cursor: pointer;
  border-bottom: 1px solid var(--border-faint);
  transition: background var(--dur-fast) var(--ease);
}

.rel-row:last-child {
  border-bottom: none;
}

.rel-row:hover {
  background: var(--bg-hover);
}

.rel-name {
  font-size: 10.5px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--accent);
  flex-shrink: 0;
}

.rel-arrow {
  color: var(--text-faint);
  font-size: 11px;
}

.rel-to {
  font-size: 12px;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.rel-row:hover .rel-to {
  color: var(--accent);
}
</style>
