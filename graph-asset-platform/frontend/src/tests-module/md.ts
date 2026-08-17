// 轻量 md 渲染（复用 markdown-it + dompurify 依赖，不引用图谱前端组件）。
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'

const md = new MarkdownIt({ html: false, breaks: false, linkify: true })

export function renderMd(text: string): string {
  if (!text) return ''
  return DOMPurify.sanitize(md.render(text))
}
