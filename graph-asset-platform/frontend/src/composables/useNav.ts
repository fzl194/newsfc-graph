// 全局导航状态：UI 层 Tab + 各层选择器 + 列表分页缓存 + 跨栏同步。
//
// 后端把 6 个 registry 层聚合成 4 个 UI 层（见后端 app/ui_layers.py），
// 前端在此镜像一份常量，供 LayerNav 的 Tab 与 /objects?layer= 过滤共用。
//
// 关键能力：
// - selectLayer(l)：切层，保留各层已缓存的选择器与列表（不重拉）。
// - loadList()：按当前层 + 选择器调 listObjects，命中缓存不请求。
// - syncTo(id)：跨栏跳转——根据对象 type 反推 UI 层，设选择器后 loadList + 高亮。

import { reactive, ref } from 'vue'
import { getObject, listObjects, type ObjectRow } from '../api'

/** 4 个 UI 层（镜像后端 UI_LAYERS）。 */
export const UI_LAYERS = ['命令层', '特性层', '任务层', '业务层'] as const
export type UiLayer = (typeof UI_LAYERS)[number]

/** 对象 type → UI 层（镜像后端 REGISTRY_TO_UI / UI_LAYER_TYPES）。 */
export const TYPE_TO_UI: Record<string, UiLayer> = {
  MMLCommand: '命令层',
  ConfigObject: '命令层',
  Feature: '特性层',
  License: '特性层',
  AtomTask: '任务层',
  CompoundTask: '任务层',
  FeatureTask: '任务层',
  Task: '任务层',
  BusinessDomain: '业务层',
  NetworkScenario: '业务层',
  ConfigurationSolution: '业务层',
}

/** UI 层 → 该层包含的对象 type（供类型选择器等使用）。 */
export const UI_LAYER_TYPES: Record<UiLayer, string[]> = {
  命令层: ['MMLCommand', 'ConfigObject'],
  特性层: ['Feature', 'License'],
  任务层: ['AtomTask', 'CompoundTask', 'FeatureTask', 'Task'],
  业务层: ['BusinessDomain', 'NetworkScenario', 'ConfigurationSolution'],
}

/** 单层选择器集合。 */
export interface LayerSelector {
  nf: string
  version: string
  type: string
  domain: string
  scenario: string
  q: string
}

function emptySelector(): LayerSelector {
  return { nf: '', version: '', type: '', domain: '', scenario: '', q: '' }
}

/** 列表缓存条目。 */
interface CacheEntry {
  rows: ObjectRow[]
  /** 该选择器组合下的对象总数（用于"是否还有更多"提示）。 */
  total: number
}

interface NavState {
  /** 当前激活的 UI 层。 */
  activeLayer: UiLayer
  /** 各层独立的选择器（切层不丢失）。 */
  selectors: Record<UiLayer, LayerSelector>
  /** key = `层|nf|version|type|domain|scenario|q|page` → {rows,total}。 */
  listCache: Map<string, CacheEntry>
  /** 各层当前分页页码。 */
  pages: Record<UiLayer, number>
}

function createState(): NavState {
  return {
    activeLayer: '命令层',
    selectors: {
      命令层: emptySelector(),
      特性层: emptySelector(),
      任务层: emptySelector(),
      业务层: emptySelector(),
    },
    listCache: new Map(),
    pages: { 命令层: 1, 特性层: 1, 任务层: 1, 业务层: 1 },
  }
}

// 模块级单例：跨组件全局共享。
const state = reactive(createState()) as NavState

/** 当前选中的对象 id（联动中栏 md + 右栏邻居图谱）。 */
const selectedId = ref<string>('')

/**
 * 当前查看版本（版本上下文，中栏详情与右栏邻居共用）：
 * - 左栏切版本 / 跨栏 syncTo 跳转时 = 左栏选择器的 version；
 * - 中栏详情版本下拉切换时 = 所选版本；
 * - 空 = 不带 version（后端落到该 id 最新现存版本）。
 */
const viewVersion = ref<string>('')

/** 正在加载列表（供 UI 显示 loading）。 */
const loading = ref<boolean>(false)

/** 最近一次列表请求错误（供 UI 显示）。 */
const loadError = ref<string>('')

const PAGE_SIZE = 100

/** 构造缓存 key（含分页；选择器全量参与）。 */
function cacheKey(layer: UiLayer, sel: LayerSelector, page: number): string {
  return [layer, sel.nf, sel.version, sel.type, sel.domain, sel.scenario, sel.q, String(page)].join(
    '|',
  )
}

/**
 * 拉取当前层 + 选择器对应的对象列表（带分页），写入缓存。
 * 命中缓存则跳过请求。返回当前页的 rows。
 */
async function loadList(): Promise<ObjectRow[]> {
  const layer = state.activeLayer
  const sel = state.selectors[layer]
  const page = state.pages[layer]
  const key = cacheKey(layer, sel, page)

  const cached = state.listCache.get(key)
  if (cached) {
    return cached.rows
  }

  loading.value = true
  loadError.value = ''
  try {
    const { rows, total } = await listObjects({
      layer,
      type: sel.type || undefined,
      nf: sel.nf || undefined,
      version: sel.version || undefined,
      domain: sel.domain || undefined,
      scenario: sel.scenario || undefined,
      q: sel.q || undefined,
      page,
      size: PAGE_SIZE,
    })
    const entry: CacheEntry = { rows, total }
    state.listCache.set(key, entry)
    return rows
  } catch (e: unknown) {
    loadError.value = e instanceof Error ? e.message : String(e)
    return []
  } finally {
    loading.value = false
  }
}

/** 切层：保留各层已缓存的选择器与列表（不重拉）。 */
function selectLayer(layer: UiLayer): void {
  if (!UI_LAYERS.includes(layer)) return
  state.activeLayer = layer
}

/** 清空全部缓存（导入新数据后调用，强制下次 loadList 重拉）。 */
function invalidateCache(): void {
  state.listCache.clear()
}

/**
 * 跨栏跳转：根据对象 type 反推 UI 层，设对应选择器后 loadList + 高亮。
 *
 * **跳转版本决策（用户决策 2026-08-19）**：
 * - 起点有版本、终点有版本（命令/配置对象/特性/License 间）→ **同版本优先**；
 * - 起点无版本（任务层/业务层出发）、终点有版本 → 最新现存版本；
 * - 终点无版本（任务/业务对象）→ 不带版本（落它唯一节点），版本上下文清空。
 * 另：``forceVersion``（URL ?version= 恢复）显式指定时优先于上述规则。
 */
async function syncTo(id: string, forceVersion?: string): Promise<void> {
  loadError.value = ''
  const srcVersion = viewVersion.value || '' // 起点版本上下文（跳转时机捕获）
  try {
    const obj = await getObject(id)
    const layer = TYPE_TO_UI[obj.type] ?? '命令层'
    state.activeLayer = layer
    const sel = state.selectors[layer]

    if (layer === '业务层') {
      sel.domain = obj.domain ?? ''
      sel.scenario = obj.scenario ?? ''
      sel.nf = ''
      sel.version = ''
      viewVersion.value = ''
    } else {
      // 目标版本决策：无版本对象（Task 层 versions=[null]）→ 空；否则同版本优先，缺失落最新
      const vs = (obj.versions ?? []).filter((v): v is string => !!v)
      let targetVersion = ''
      if (vs.length > 0) {
        if (forceVersion && vs.includes(forceVersion)) {
          targetVersion = forceVersion
        } else if (srcVersion && vs.includes(srcVersion)) {
          targetVersion = srcVersion // 同版本跳转（版本内闭环）
        } else {
          targetVersion = vs[vs.length - 1] // 起点无版本/同版本缺失 → 最新现存
        }
      }
      // 首次取回的是最新版节点；同版本命中且不同 → 二次取该版本
      let node = obj
      if (targetVersion && obj.version !== targetVersion) {
        node = await getObject(id, targetVersion)
      }
      sel.nf = node.nf ?? ''
      sel.version = targetVersion // 决策结果（''=无版本对象，列表不过滤）
      sel.domain = ''
      sel.scenario = ''
      viewVersion.value = targetVersion
    }
    sel.type = ''
    sel.q = ''
    state.pages[layer] = 1

    await loadList()
    // 选 id 放在 loadList 之后：accumulatedRows(computed) 此时已含目标行，
    // selectedId watch 的高亮+scrollToRow 才能定位到它。
    selectedId.value = id
  } catch (e: unknown) {
    loadError.value = e instanceof Error ? e.message : String(e)
  }
}

/** 当前层、当前选择器、当前页对应的列表（响应式：缓存写入后自动更新视图）。 */
function currentRows(): ObjectRow[] {
  const layer = state.activeLayer
  const sel = state.selectors[layer]
  const page = state.pages[layer]
  return state.listCache.get(cacheKey(layer, sel, page))?.rows ?? []
}

export function useNav() {
  return {
    // 状态
    state,
    selectedId,
    viewVersion,
    loading,
    loadError,
    // 常量
    UI_LAYERS,
    UI_LAYER_TYPES,
    TYPE_TO_UI,
    // 操作
    selectLayer,
    loadList,
    syncTo,
    invalidateCache,
    currentRows,
  }
}
