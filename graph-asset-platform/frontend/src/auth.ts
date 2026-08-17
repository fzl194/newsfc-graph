// 鉴权 session（username + key + 全部权限位），sessionStorage 存储。
const SESSION = 'gap_session'

export interface Session {
  username: string
  key: string
  can_frontend: boolean
  can_assets: boolean
  can_upload: boolean
  can_test: boolean
  can_skill: boolean
  is_admin: boolean
}

export function getSession(): Session | null {
  const raw = sessionStorage.getItem(SESSION)
  if (!raw) return null
  try {
    const s = JSON.parse(raw) as Session
    // 旧版 session（权限位变更前登录，缺 can_assets）→ 判失效，强制重新登录拿新权限快照
    return typeof s.can_assets === 'boolean' ? s : null
  } catch {
    return null
  }
}
export function setSession(s: Session): void {
  sessionStorage.setItem(SESSION, JSON.stringify(s))
}
export function clearSession(): void {
  sessionStorage.removeItem(SESSION)
}
export function getKey(): string {
  return getSession()?.key || ''
}
export function isAdmin(): boolean {
  return !!getSession()?.is_admin
}
export function hasKey(): boolean {
  return !!getSession()
}
