// 测试子系统 API 客户端（自包含，不引用图谱前端代码）。
// 全部走 /api/v1/tests/*；id 含 @ 与空格时路径段 encodeURIComponent。
// "涉及对象" autocomplete 另调图谱 /api/v1/names（只读跨子系统，后端两侧零耦合）。

import { getKey, clearSession } from '../auth'

const BASE = '/api/v1'

export interface ApiError extends Error {
  status: number
  detail: unknown
}

async function _req<T>(url: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  const k = getKey()
  if (k) headers.set('X-API-Key', k)
  headers.set('X-Client', 'web')
  const resp = await fetch(url, { ...init, headers })
  if (resp.status === 401) {
    clearSession()
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
  const ct = resp.headers.get('content-type') || ''
  if (ct.includes('application/json')) return (await resp.json()) as T
  return (await resp.text()) as unknown as T
}

function qs(p: Record<string, string | undefined>): string {
  const entries = Object.entries(p).filter(([, v]) => v !== undefined && v !== '')
  if (entries.length === 0) return ''
  return '?' + entries.map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&')
}

// ---------- 类型（与后端 routers/tests.py 对齐） ----------

export interface Problem {
  description: string
  attribution: string[] // 归因多选（图谱知识/配置流程/其他…）
  objects: string[] // 涉及图谱对象 id 列表（多选 tag）
}

export interface TestCaseRow {
  id: string
  name: string
  domain: string
  scenario: string
  status: string
  file_count: number
  run_count: number
  latest_verdict: string
}

export interface CaseDetail {
  id: string
  name: string
  domain: string
  scenario: string
  status: string
  solution: string
  author: string
  frontmatter: Record<string, unknown>
  body_md: string
  raw_md: string
  files: string[]
  runs: RunRow[]
}

export interface RunRow {
  id: string
  runner: string
  run_at: string
  status: string
  artifact_count: number
  verdict: string
  review_count: number
}

export interface RunDetail {
  id: string
  case: string
  name: string
  runner: string
  run_at: string
  status: string
  artifacts: string[]
  frontmatter: Record<string, unknown>
  body_md: string
  reviews: ReviewDetail[]
}

export interface ReviewDetail {
  id: string
  run: string
  reviewer: string
  reviewed_at: string
  verdict: string
  problem_count: number
  problems: Problem[]
  body_md: string
  raw_md: string
}

export interface TestStats {
  case_count: number
  run_count: number
  review_count: number
  cases_by_domain: Record<string, number>
  cases_by_domain_scenario: Record<string, number>
  verdict_distribution: Record<string, number>
  warnings: string[]
}

export interface ReviewWriteBody {
  run: string
  reviewer?: string
  verdict: string
  conclusion?: string
  problems: { desc: string; attribution: string[]; objects: string[] }[]
}

// ---------- API ----------

export const listCases = (p: { domain?: string; scenario?: string; q?: string } = {}): Promise<TestCaseRow[]> =>
  _req<TestCaseRow[]>(`${BASE}/tests/cases${qs(p)}`)

export const getCase = (id: string): Promise<CaseDetail> =>
  _req<CaseDetail>(`${BASE}/tests/cases/${encodeURIComponent(id)}`)

// Phase 1：前端建用例（multipart：意图正文 + 可选上传输入/参考配置文件）
export async function createCase(data: {
  name: string
  intent: string
  domain?: string
  scenario?: string
  solution?: string
  slug?: string
  author?: string
  inputFiles?: File[]
  referenceFiles?: File[]
}): Promise<CaseDetail> {
  const fd = new FormData()
  fd.append('name', data.name)
  fd.append('intent', data.intent)
  if (data.domain) fd.append('domain', data.domain)
  if (data.scenario) fd.append('scenario', data.scenario)
  if (data.solution) fd.append('solution', data.solution)
  if (data.slug) fd.append('slug', data.slug)
  if (data.author) fd.append('author', data.author)
  ;(data.inputFiles || []).forEach((f) => fd.append('input_files', f))
  ;(data.referenceFiles || []).forEach((f) => fd.append('reference_files', f))
  return _req<CaseDetail>(`${BASE}/tests/cases`, { method: 'POST', body: fd })
}

export const downloadCaseURL = (id: string): string =>
  `${BASE}/tests/cases/${encodeURIComponent(id)}/download`

export const getRun = (id: string): Promise<RunDetail> =>
  _req<RunDetail>(`${BASE}/tests/runs/${encodeURIComponent(id)}`)

// Phase 2：上传运行结果 zip → 解包成 Run 文件夹
export async function uploadRun(
  caseId: string,
  file: File,
  opts?: { slug?: string; name?: string; runner?: string },
): Promise<RunDetail> {
  const fd = new FormData()
  fd.append('case', caseId)
  fd.append('file', file)
  if (opts?.slug) fd.append('slug', opts.slug)
  if (opts?.name) fd.append('name', opts.name)
  if (opts?.runner) fd.append('runner', opts.runner)
  return _req<RunDetail>(`${BASE}/tests/runs`, { method: 'POST', body: fd })
}

export interface RunInfo {
  name?: string
  runner?: string
  run_at?: string
  status?: string
  notes?: string
}

export const updateRun = (id: string, info: RunInfo): Promise<RunDetail> =>
  _req<RunDetail>(`${BASE}/tests/runs/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(info),
  })

export const deleteRun = (id: string): Promise<{ ok: boolean }> =>
  _req<{ ok: boolean }>(`${BASE}/tests/runs/${encodeURIComponent(id)}`, { method: 'DELETE' })

// 编辑用例（multipart：元数据/意图/增删附件）
export async function updateCase(
  id: string,
  data: {
    name?: string
    intent?: string
    domain?: string
    scenario?: string
    solution?: string
    status?: string
    removeFiles?: string[]
    inputFiles?: File[]
    referenceFiles?: File[]
  },
): Promise<CaseDetail> {
  const fd = new FormData()
  if (data.name) fd.append('name', data.name)
  if (data.intent !== undefined) fd.append('intent', data.intent)
  if (data.domain) fd.append('domain', data.domain)
  if (data.scenario !== undefined) fd.append('scenario', data.scenario)
  if (data.solution !== undefined) fd.append('solution', data.solution)
  if (data.status) fd.append('status', data.status)
  if (data.removeFiles?.length) fd.append('remove_files', data.removeFiles.join(','))
  ;(data.inputFiles || []).forEach((f) => fd.append('input_files', f))
  ;(data.referenceFiles || []).forEach((f) => fd.append('reference_files', f))
  return _req<CaseDetail>(`${BASE}/tests/cases/${encodeURIComponent(id)}`, { method: 'PATCH', body: fd })
}

export const deleteCase = (id: string): Promise<{ ok: boolean }> =>
  _req<{ ok: boolean }>(`${BASE}/tests/cases/${encodeURIComponent(id)}`, { method: 'DELETE' })

export const downloadRunURL = (id: string): string =>
  `${BASE}/tests/runs/${encodeURIComponent(id)}/download`

// 取用例附件文件内容（txt 预览用）
export const getCaseFile = (caseId: string, name: string): Promise<string> =>
  _req<string>(`${BASE}/tests/cases/${encodeURIComponent(caseId)}/file/${name.split('/').map(encodeURIComponent).join('/')}`)

export const getArtifact = (runId: string, name: string): Promise<string> =>
  _req<string>(`${BASE}/tests/runs/${encodeURIComponent(runId)}/artifact/${encodeURIComponent(name)}`)

export const listReviews = (run?: string): Promise<ReviewDetail[]> =>
  _req<ReviewDetail[]>(`${BASE}/tests/reviews${qs({ run })}`)

export const testsStats = (): Promise<TestStats> => _req<TestStats>(`${BASE}/tests/stats`)

export const createReview = (body: ReviewWriteBody): Promise<ReviewDetail> =>
  _req<ReviewDetail>(`${BASE}/tests/reviews`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

export const updateReview = (id: string, body: ReviewWriteBody): Promise<ReviewDetail> =>
  _req<ReviewDetail>(`${BASE}/tests/reviews/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

export const deleteReview = (id: string): Promise<{ ok: boolean }> =>
  _req<{ ok: boolean }>(`${BASE}/tests/reviews/${encodeURIComponent(id)}`, { method: 'DELETE' })

export const reindexTests = (): Promise<{ ok: boolean; case_count: number; run_count: number; review_count: number }> =>
  _req(`${BASE}/tests/reindex`, { method: 'POST' })

// ---------- 涉及对象 autocomplete：调图谱 /names（只读） ----------

let _nameMap: Map<string, string> | null = null
let _namePromise: Promise<Map<string, string>> | null = null

export async function getNameMap(): Promise<Map<string, string>> {
  if (_nameMap) return _nameMap
  if (!_namePromise) {
    _namePromise = _req<Record<string, string>>(`${BASE}/names`)
      .then((d) => {
        _nameMap = new Map(Object.entries(d || {}))
        return _nameMap
      })
      .catch(() => {
        _namePromise = null
        return new Map<string, string>()
      })
  }
  return _namePromise
}

// 输入前缀 → 候选 [{id, name}]（按 name/id 子串匹配，限 20 条）
export async function suggestObjects(prefix: string): Promise<{ id: string; name: string }[]> {
  const m = await getNameMap()
  const p = prefix.trim().toLowerCase()
  if (!p) return []
  const out: { id: string; name: string }[] = []
  for (const [id, name] of m.entries()) {
    if (id.toLowerCase().includes(p) || String(name || '').toLowerCase().includes(p)) {
      out.push({ id, name: String(name || id) })
      if (out.length >= 20) break
    }
  }
  return out
}

// ---------- 图谱业务层只读查询（建用例时下拉关联图谱，跨子系统只读，后端隔离不破）----------

interface GraphObjectRow {
  id: string
  type: string
  domain?: string | null
  scenario?: string | null
  name?: string | null
}

// 业务域：value=域 slug，label=可读名
export async function fetchBusinessDomains(): Promise<{ slug: string; name: string }[]> {
  const rows = await _req<GraphObjectRow[]>(`${BASE}/objects?type=BusinessDomain&size=200`)
  return rows.map((r) => ({ slug: String(r.domain || r.id.split('@')[1] || r.id), name: String(r.name || r.id) }))
}

// 场景（按域过滤）：value=场景 slug，label=可读名
export async function fetchScenarios(domain: string): Promise<{ slug: string; name: string }[]> {
  if (!domain) return []
  const rows = await _req<GraphObjectRow[]>(
    `${BASE}/objects?type=NetworkScenario&domain=${encodeURIComponent(domain)}&size=200`,
  )
  return rows.map((r) => ({ slug: String(r.scenario || ''), name: String(r.name || r.id) })).filter((r) => r.slug)
}

// 方案（按域+场景过滤）：value=ConfigurationSolution id，label=id
export async function fetchSolutions(domain: string, scenario: string): Promise<{ id: string; name: string }[]> {
  if (!domain || !scenario) return []
  const rows = await _req<GraphObjectRow[]>(
    `${BASE}/objects?type=ConfigurationSolution&domain=${encodeURIComponent(domain)}&scenario=${encodeURIComponent(scenario)}&size=300`,
  )
  return rows.map((r) => ({ id: r.id, name: String(r.name || r.id) }))
}

// 图谱层 → 类型映射（多选对象选择器用）
export const LAYER_TYPES: Record<string, string[]> = {
  业务层: ['BusinessDomain', 'NetworkScenario', 'ConfigurationSolution'],
  任务层: ['AtomTask', 'CompoundTask', 'FeatureTask'],
  特性层: ['Feature', 'License'],
  命令层: ['MMLCommand', 'ConfigObject'],
}

// 图谱对象搜索（层/类型 + 关键词，返回 id+中文名）
export async function fetchGraphObjects(
  type: string,
  q: string,
): Promise<{ id: string; name: string }[]> {
  const params = new URLSearchParams()
  if (type) params.set('type', type)
  if (q) params.set('q', q)
  params.set('size', '50')
  const rows = await _req<GraphObjectRow[]>(`${BASE}/objects?${params.toString()}`)
  return rows.map((r) => ({ id: r.id, name: String(r.name || r.id) }))
}
