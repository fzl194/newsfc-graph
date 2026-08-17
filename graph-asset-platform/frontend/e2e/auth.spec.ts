import { test, expect } from '@playwright/test'
import { ADMIN, VIEWER, login } from './helpers'

test.describe('登录与权限菜单', () => {
  test('错误 KEY 登录被拒', async ({ page }) => {
    await page.goto('/login')
    await page.getByPlaceholder('用户名').fill('admin')
    await page.getByPlaceholder('访问密钥').fill('wrong-key')
    await page.getByRole('button', { name: '进入平台' }).click()
    await expect(page.getByText('用户名或 KEY 错误')).toBeVisible()
    await expect(page).toHaveURL(/\/login/)
  })

  test('viewer 登录：仅浏览，无资产目录/上传菜单；直连 /fs 被拦', async ({ page }) => {
    await login(page, VIEWER)
    await expect(page.getByRole('link', { name: '图谱浏览' })).toBeVisible()
    await expect(page.getByRole('link', { name: '资产目录' })).toHaveCount(0)
    await expect(page.getByRole('link', { name: '上传' })).toHaveCount(0)
    // 路由守卫：直连 URL 被拦（不渲染目录内容）
    await page.goto('/fs')
    await expect(page.getByText('全部资产')).toHaveCount(0)
    await expect(page.getByRole('button', { name: '🗑 回收站' })).toHaveCount(0)
  })

  test('admin 登录：全菜单（含资产目录/上传/用户）', async ({ page }) => {
    await login(page, ADMIN)
    await expect(page.getByRole('link', { name: '资产目录' })).toBeVisible()
    await expect(page.getByRole('link', { name: '上传' })).toBeVisible()
    await expect(page.getByRole('link', { name: '用户' })).toBeVisible()
  })
})
