import type { Page } from '@playwright/test'
import { expect } from '@playwright/test'

/** 固定测试账号（backend/scripts/seed_e2e.py 写入 users.json）。 */
export const ADMIN = { username: 'admin', key: 'e2e-admin-key' }
export const VIEWER = { username: 'viewer', key: 'e2e-viewer-key' }

/** 登录并等待进入主界面。 */
export async function login(page: Page, u: { username: string; key: string }): Promise<void> {
  await page.goto('/login')
  await page.getByPlaceholder('用户名').fill(u.username)
  await page.getByPlaceholder('访问密钥').fill(u.key)
  await page.getByRole('button', { name: '进入平台' }).click()
  await page.waitForURL((url) => !url.pathname.startsWith('/login'))
}

/**
 * Element Plus el-select 选值（左栏选择器区）：点开第 selectIndex 个 .el-select →
 * 在（可见的）下拉浮层里点选项。Element Plus 的 placeholder 是覆盖层 span 而非
 * input placeholder（选中后消失），故按索引定位：命令层 0=网元 1=版本 2=类型。
 * 下拉 teleport 到 body，可能有多个隐藏浮层，必须 :visible 过滤。
 */
export async function pickSelect(page: Page, selectIndex: number, option: string): Promise<void> {
  const select = page.locator('.selectors .el-select').nth(selectIndex)
  await select.locator('input').click()
  await page
    .locator('.el-select-dropdown:visible .el-select-dropdown__item', { hasText: option })
    .first()
    .click()
}
