// 三视图统计共享：筛选状态形状 / 数字格式化 / 规则类型标签。
// 口径见后端 app/stats/spec.py 与《统计页面需求说明书》。

import type { StatsViewKey } from '../../api'

export interface StatsFilterState {
  nfs: string[]
  versions: string[]
  logical_ne: string
  object_types: string[]
  relations: string[]
  rule_types: string[]
  domain: string
  scenario: string
  solution: string
  overseas: boolean
}

export const emptyFilters = (): StatsFilterState => ({
  nfs: [],
  versions: [],
  logical_ne: '',
  object_types: [],
  relations: [],
  rule_types: [],
  domain: '',
  scenario: '',
  solution: '',
  overseas: false,
})

export const RULE_LABELS: Record<string, string> = {
  syntax: '语法规则',
  graph: '图规则',
  repeat: '重复检查规则',
  mod: 'MOD 规则',
  set: 'SET 规则',
  delete: '删除规则',
}

export const VIEW_TITLES: Record<StatsViewKey, string> = {
  command: '命令图谱',
  feature: '特性图谱',
  business: '业务图谱',
}

/** 千分位（与 StatCard 一致）。 */
export function fmt(n: number | undefined | null): string {
  return (n ?? 0).toLocaleString('zh-CN')
}
