// API 客户端：全部走 /api/v1/*。
// id 含 @ 与空格，路径段必须 encodeURIComponent（@→%40、空格→%20）。
// 统一 _req 封装错误：404 时后端返回 detail.message + available_versions（版本缺失），
// 或 detail: "对象不存在: ..."（id 完全不存在）→ 抛出 ApiError 带 status/detail/payload。

import { getKey, clearSession } from './auth'

const BASE = '/api/v1'

export interface ApiError extends Error {
  status: number
  detail: unknown
}

/** 带响应头的请求（需要读 X-Total-Count 等头时用）。 */
async function _reqFull<T>(url: string, init?: RequestInit): Promise<{ data: T; headers: Headers }> {
  const headers = new Headers(init?.headers)
  const k = getKey()
  if (k) headers.set('X-API-Key', k)
  headers.set('X-Client', 'web')
  const resp = await fetch(url, { ...init, headers })
  if (resp.status === 401) {
    clearSession()
    // window.location 最稳，绕开 router 实例（避免 api.ts ↔ router.ts 循环依赖）
    if (!window.location.pathname.startsWith('/login')) {
      window.location.assign('/login')
    }
    throw new Error('未授权，已跳转登录')
  }
  if (resp.status === 403) {
    throw Object.assign(new Error('权限不足'), { status: 403 })
  }
  if (!resp.ok) {
    let detail: unknown
    try {
      detail = await resp.json()
    } catch {
      detail = await resp.text().catch(() => '')
    }
    const msg =
      (detail && typeof detail === 'object' && 'detail' in detail
        ? JSON.stringify((detail as { detail: unknown }).detail)
        : String(detail)) || `HTTP ${resp.status}`
    const err = new Error(`API ${resp.status}: ${msg}`) as ApiError
    err.status = resp.status
    err.detail = detail
    throw err
  }
  // md 接口返回 text/markdown
  const ct = resp.headers.get('content-type') || ''
  const data = ct.includes('application/json')
    ? ((await resp.json()) as T)
    : ((await resp.text()) as unknown as T)
  return { data, headers: resp.headers }
}

async function _req<T>(url: string, init?: RequestInit): Promise<T> {
  return (await _reqFull<T>(url, init)).data
}

// 登录：username+key → 用户信息（含全部权限位）
export interface LoginUser {
  username: string
  can_frontend: boolean
  can_assets: boolean
  can_upload: boolean
  can_test: boolean
  can_skill: boolean
  is_admin: boolean
}
export const login = (username: string, key: string): Promise<LoginUser> =>
  _req<LoginUser>(`${BASE}/users/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, key }),
  })

// SKILL 取用频次聚合（统计页 TelemetrySection 用）
export interface TelemetryStats {
  total: number
  by_type: Record<string, number>
  top_ids: { id: string; type: string; count: number }[]
  timeline: { date: string; count: number }[]
  by_user: Record<string, number>
  by_operator: Record<string, number>
}

export const fetchTelemetryStats = (days = 30): Promise<TelemetryStats> =>
  _req<TelemetryStats>(`${BASE}/telemetry/stats?days=${days}`)

// ---------- 用户管理（admin）----------
export interface UserRow {
  username: string
  key: string
  can_frontend: boolean
  can_assets: boolean
  can_upload: boolean
  can_test: boolean
  can_skill: boolean
  is_admin: boolean
  created_at?: string
}

export const listUsers = (): Promise<UserRow[]> => _req(`${BASE}/users`)

export const createUser = (b: {
  username: string
  can_frontend?: boolean
  can_assets?: boolean
  can_upload?: boolean
  can_test?: boolean
  can_skill?: boolean
  is_admin?: boolean
}): Promise<UserRow> =>
  _req(`${BASE}/users`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(b),
  })

export const updateUser = (name: string, b: Record<string, unknown>): Promise<UserRow> =>
  _req(`${BASE}/users/${encodeURIComponent(name)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(b),
  })

export const deleteUser = (name: string): Promise<{ ok: boolean }> =>
  _req(`${BASE}/users/${encodeURIComponent(name)}`, { method: 'DELETE' })

export const userActivity = (
  name: string,
  days = 30,
): Promise<{ ts: string; endpoint: string; caller: string; operator: string }[]> =>
  _req(`${BASE}/users/${encodeURIComponent(name)}/activity?days=${days}`)

function qs(p: Record<string, string | number | undefined>): string {
  const entries = Object.entries(p).filter(([, v]) => v !== undefined && v !== '')
  if (entries.length === 0) return ''
  return '?' + entries.map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&')
}

// ---------- 类型（与后端 routers 序列化对齐） ----------

export interface ObjectRow {
  id: string
  type: string
  layer?: string
  nf?: string
  domain?: string
  scenario?: string
  name?: string | null
  versions: string[]
}

export interface ObjectDetail {
  id: string
  type: string
  layer?: string
  scope?: string
  nf?: string
  version?: string
  domain?: string
  scenario?: string
  frontmatter: Record<string, unknown>
  body_md: string
  source_path?: string
  versions: string[]
  out_edges: Edge[]
}

export interface Edge {
  from: string
  from_version?: string
  relation: string
  to: string
}

export interface Neighbors {
  center: ObjectDetail
  out: Edge[]
  in: Edge[]
}

export interface Stats {
  object_counts_by_type: Record<string, number>
  edge_count: number
  nfs: string[]
  versions_per_nf: Record<string, string[]>
  // UI 层聚合（4 层：命令层/特性层/任务层/业务层）
  per_layer: Record<string, number>
  per_layer_per_nf: Record<string, Record<string, number>>
  per_layer_per_nf_per_version: Record<
    string,
    Record<string, Record<string, number>>
  >
  per_domain: Record<string, number>
  per_domain_scenario: Record<string, Record<string, number>>
}

// ---------- API ----------

/** 列表结果：rows = 当前页；total = X-Total-Count（过滤后、分页前总数）。 */
export interface ObjectListResult {
  rows: ObjectRow[]
  total: number
}

export const listObjects = async (p: {
  type?: string
  layer?: string
  q?: string
  nf?: string
  version?: string
  domain?: string
  scenario?: string
  page?: number
  size?: number
} = {}): Promise<ObjectListResult> => {
  const { data, headers } = await _reqFull<ObjectRow[]>(`${BASE}/objects${qs(p)}`)
  const total = Number(headers.get('X-Total-Count'))
  return { rows: data, total: Number.isFinite(total) ? total : data.length }
}

export const getObject = (id: string, version?: string): Promise<ObjectDetail> =>
  _req<ObjectDetail>(`${BASE}/objects/${encodeURIComponent(id)}${qs({ version })}`)

// id→name 映射（供正文 [[ID]] 渲染可读名）；进程内缓存，首次后只命中内存
let _nameMap: Map<string, string> | null = null
let _nameMapPromise: Promise<Map<string, string>> | null = null

export async function getNameMap(): Promise<Map<string, string>> {
  if (_nameMap) return _nameMap
  if (!_nameMapPromise) {
    _nameMapPromise = _req<Record<string, string>>(`${BASE}/names`).then((d) => {
      _nameMap = new Map(Object.entries(d || {}))
      return _nameMap
    })
  }
  return _nameMapPromise
}

export const neighbors = (
  id: string,
  version?: string,
  hops: number = 1,
): Promise<Neighbors> =>
  _req<Neighbors>(
    `${BASE}/objects/${encodeURIComponent(id)}/neighbors${qs({ hops, version })}`,
  )

export const getMd = (id: string, version?: string): Promise<string> =>
  _req<string>(`${BASE}/objects/${encodeURIComponent(id)}/md${qs({ version })}`)

export const stats = (): Promise<Stats> => _req<Stats>(`${BASE}/stats`)

export const exportUrl = (f: {
  nf?: string
  version?: string
  domain?: string
  scenario?: string
}): string => `${BASE}/export${qs(f)}`

export const subgraph = (p: {
  center: string
  hops?: number
  type?: string
  version?: string
}): Promise<{
  nodes: { id: string; type?: string; label?: string }[]
  edges: { source: string; target: string; relation: string }[]
}> => _req(`${BASE}/subgraph${qs(p)}`)

// 解析 404 detail（版本缺失时带 available_versions）
export function availableVersionsFromError(e: unknown): string[] | null {
  if (!e || typeof e !== 'object' || !('detail' in e)) return null
  const d = (e as { detail: unknown }).detail
  // 后端包装层：fetch.json() 返回 { detail: {...} }
  const inner =
    d && typeof d === 'object' && 'detail' in d
      ? (d as { detail: unknown }).detail
      : d
  if (inner && typeof inner === 'object' && 'available_versions' in inner) {
    return (inner as { available_versions: string[] }).available_versions
  }
  return null
}

// ---------- 资产目录（fs）文件浏览器 + 指定层上传 ----------

export interface FsEntry {
  name: string
  path: string
  is_dir: boolean
  size?: number
}

export interface FsUploadResult {
  added: number
  updated: number
  skipped: number
  warnings: string[]
}

export const listFsChildren = (path: string = ''): Promise<FsEntry[]> =>
  _req<FsEntry[]>(`${BASE}/fs/children${qs({ path })}`)

export const readFsFile = (path: string): Promise<string> =>
  _req<string>(`${BASE}/fs/file${qs({ path })}`)

export const writeFsFile = (
  path: string,
  content: string,
): Promise<{ ok: boolean; path: string; moved_from: string | null }> =>
  _req(`${BASE}/fs/file${qs({ path })}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })

export const deleteFsFile = (path: string): Promise<{ ok: boolean }> =>
  _req(`${BASE}/fs/file${qs({ path })}`, { method: 'DELETE' })

export const mkdirFs = (path: string): Promise<{ ok: boolean; path: string }> =>
  _req(`${BASE}/fs/mkdir`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  })

export const moveFsFile = (b: {
  src: string
  target_dir: string
  nf?: string
  version?: string
  domain?: string
  scenario?: string
}): Promise<{ ok: boolean; new_path: string; moved: boolean }> =>
  _req(`${BASE}/fs/move`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(b),
  })

export const renameFsFile = (b: {
  path: string
  new_id: string
  dry_run?: boolean
}): Promise<{
  dry_run?: boolean
  ok?: boolean
  old_id?: string
  new_id?: string
  affected?: number
  affected_files?: string[]
  new_path?: string
}> =>
  _req(`${BASE}/fs/rename`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(b),
  })

export const uploadToDir = (
  targetDir: string,
  files: File[],
  overrides?: { nf?: string; version?: string; domain?: string; scenario?: string },
): Promise<FsUploadResult> => {
  const fd = new FormData()
  fd.append('target_dir', targetDir)
  if (overrides) {
    if (overrides.nf) fd.append('nf', overrides.nf)
    if (overrides.version) fd.append('version', overrides.version)
    if (overrides.domain) fd.append('domain', overrides.domain)
    if (overrides.scenario) fd.append('scenario', overrides.scenario)
  }
  for (const f of files) fd.append('files', f)
  return _req<FsUploadResult>(`${BASE}/fs/upload`, { method: 'POST', body: fd })
}

// ---------- 产品文档两步流水线（解压留存 / 图谱挖掘）+ 原始文档浏览 ----------

export interface ImportJobStep {
  name: string
  status: string
  detail: string
}

export interface ImportJob {
  job_id: string
  kind: string // import | product_doc_extract | product_doc_mine
  status: string // processing | done | failed
  nf: string
  version: string
  steps: ImportJobStep[]
  result: Record<string, number | null | Record<string, number>>
  warnings: string[]
  error: string
  added: number
  started_at: number
  finished_at: number
}

/** 步骤①：上传解压（只解压转换留存，不构建；同 nf+version 自动覆盖旧包）。 */
export const uploadProductDoc = (
  nf: string,
  version: string,
  file: File,
): Promise<{ job_id: string; nf: string; version: string; size: number }> => {
  const fd = new FormData()
  fd.append('nf', nf)
  fd.append('version', version)
  fd.append('file', file)
  return _req(`${BASE}/import/product-doc`, { method: 'POST', body: fd })
}

/** 已解压产品文档包（抽取页数据源）。assets=该 nf+version 四层资产是否已存在。 */
export interface DocBundle {
  nf: string
  version: string
  dir: string
  status: string
  legacy: boolean
  uploaded_at: string
  uploaded_by: string
  source_name: string
  md_count: number | null
  convert_failed: number
  mode_id: string
  assets: Record<string, boolean>
}

export const listBundles = (): Promise<DocBundle[]> =>
  _req<DocBundle[]>(`${BASE}/import/bundles`)

export interface ModeOption {
  id: string
  name: string
}

export const listModes = (): Promise<ModeOption[]> =>
  _req<ModeOption[]>(`${BASE}/import/modes`)

export interface LocateRole {
  recommended: string | null
  candidates: string[]
  note: string
}

export type LocateResult = Record<string, LocateRole>

export const locateBundle = (nf: string, version: string, mode: string): Promise<LocateResult> =>
  _req<LocateResult>(
    `${BASE}/import/bundles/${encodeURIComponent(nf)}/${encodeURIComponent(version)}/locate${qs({ mode })}`,
  )

/** 步骤②：图谱挖掘（响应 scope=依赖强制后的最终范围，notes=补选说明）。 */
export const startMine = (b: {
  nf: string
  version: string
  mode: string
  dirs: Record<string, string>
  scope: string[]
  force: boolean
}): Promise<{ job_id: string; scope: string[]; notes: string[]; force: boolean }> =>
  _req(`${BASE}/import/mine`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(b),
  })

export const getImportJob = (id: string): Promise<ImportJob> =>
  _req<ImportJob>(`${BASE}/import/jobs/${id}`)

/** 历史导入任务（后端持久化，跨重启；含 processing）。 */
export const listImportJobs = (): Promise<ImportJob[]> =>
  _req<ImportJob[]>(`${BASE}/import/jobs`)

/** 删除历史任务（解析进行中后端 400 拒绝）。 */
export const deleteImportJob = (id: string): Promise<{ ok: boolean; job_id: string }> =>
  _req(`${BASE}/import/jobs/${id}`, { method: 'DELETE' })

export const listDocsChildren = (path: string = ''): Promise<FsEntry[]> =>
  _req<FsEntry[]>(`${BASE}/docs/children${qs({ path })}`)

export const readDocsFile = (path: string): Promise<string> =>
  _req<string>(`${BASE}/docs/file${qs({ path })}`)

// ---------- md 正文图片相对引用 → raw 端点 URL（预览渲染用） ----------

export const rawFsUrl = (path: string): string =>
  `${BASE}/fs/raw?path=${encodeURIComponent(path)}`

export const rawDocsUrl = (path: string): string =>
  `${BASE}/docs/raw?path=${encodeURIComponent(path)}`

/**
 * 把 md 正文里的 `![alt](相对路径)` 图片引用改写为后端 raw 端点 URL。
 * dir = 该 md 所在目录（相对 assets/docs 根的正斜杠路径）；外链 / data URI 原样保留。
 */
export const resolveImgUrls = (
  body: string,
  dir: string,
  base: 'fs' | 'docs' = 'fs',
): string => {
  const toUrl = base === 'fs' ? rawFsUrl : rawDocsUrl
  return body.replace(/(!\[[^\]]*\])\(([^)\s]+)\)/g, (m, alt: string, url: string) => {
    if (/^(https?:|\/\/|data:|mailto:|#)/i.test(url)) return m
    const clean = url.split('#')[0]
    if (!clean) return m
    return `${alt}(${toUrl(dir ? `${dir}/${clean}` : clean)})`
  })
}

// ---------- 回收站（软删除）----------

export interface TrashItem {
  id: string
  original_path: string
  is_dir: boolean
  md_count: number
  deleted_at: string
  deleted_by: string
}

export const listTrash = (): Promise<TrashItem[]> => _req<TrashItem[]>(`${BASE}/fs/trash`)

export const restoreTrash = (id: string): Promise<{ ok: boolean; path: string }> =>
  _req(`${BASE}/fs/trash/restore`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id }),
  })

export const purgeTrash = (id: string): Promise<{ ok: boolean }> =>
  _req(`${BASE}/fs/trash/${encodeURIComponent(id)}`, { method: 'DELETE' })

export const emptyTrash = (): Promise<{ ok: boolean; purged: number }> =>
  _req(`${BASE}/fs/trash`, { method: 'DELETE' })
