// 三视图统计共享：筛选状态形状 / 数字格式化 / 规则类型标签。
// 口径见后端 app/stats/spec.py 与《统计页面需求说明书》。

import type { StatsFilterParams } from '../../api'

/** 视图级（卡片）筛选：命令=网元+版本+逻辑网元；特性=网元+版本（2026-09-02 收窄） */
export interface CardFilterState {
  nfs: string[]
  versions: string[]
  logical_ne: string
  overseas: boolean
}

export const emptyCardFilter = (): CardFilterState => ({
  nfs: [],
  versions: [],
  logical_ne: '',
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

/** 千分位（与 StatCard 一致）。 */
export function fmt(n: number | undefined | null): string {
  return (n ?? 0).toLocaleString('zh-CN')
}

/** 表级筛选与卡片筛选合并：两侧都选 → 交集（表在卡片范围内再收窄）。 */
export function mergeMulti<T>(base: T[], local: T[]): T[] {
  if (!local.length) return base
  if (!base.length) return local
  return local.filter((v) => base.includes(v))
}

export function mergeSingle(base: string, local: string): string {
  return local || base
}

/** CardFilterState → API 参数（缺省字段由后端默认）。 */
export function toParams(f: CardFilterState): StatsFilterParams {
  return { nfs: f.nfs, versions: f.versions, logical_ne: f.logical_ne, overseas: f.overseas }
}
