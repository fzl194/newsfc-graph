import { test, expect } from '@playwright/test'
import { ADMIN, login } from './helpers'

test.describe('资产目录（/fs）', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, ADMIN)
    await page.goto('/fs')
  })

  test('目录浏览：面包屑导航逐层进入', async ({ page }) => {
    await expect(page.locator('.crumb', { hasText: '全部资产' })).toBeVisible()
    await expect(page.locator('.fname', { hasText: 'Command' })).toBeVisible()

    // Command → UDG → 20.15.2 → md 文件
    await page.locator('.frow', { hasText: 'Command' }).click()
    await expect(page.locator('.fname', { hasText: 'UDG' })).toBeVisible()
    await page.locator('.frow', { hasText: 'UDG' }).click()
    await expect(page.locator('.fname', { hasText: '20.15.2' })).toBeVisible()
    await page.locator('.frow', { hasText: '20.15.2' }).click()
    await expect(
      page.locator('.fname', { hasText: 'UDG@MMLCommand@ACT DEMO.md' }),
    ).toBeVisible()
  })

  test('软删除 → 回收站可见 → 还原', async ({ page }) => {
    // 进入目标目录
    await page.locator('.frow', { hasText: 'Command' }).click()
    await page.locator('.frow', { hasText: 'UDG' }).click()
    await page.locator('.frow', { hasText: '20.15.2' }).click()
    const target = page.locator('.frow', { hasText: 'UDG@MMLCommand@OLD ONLY.md' })
    await expect(target).toBeVisible()

    // 勾选 → 批量删除 → 确认
    await target.locator('input[type="checkbox"]').check()
    await expect(page.getByText('已选', { exact: false }).first()).toBeVisible()
    await page.getByRole('button', { name: '批量删除' }).click()
    await page.locator('.el-message-box').getByRole('button', { name: '确定' }).click()
    await expect(target).toHaveCount(0)

    // 回收站可见该条目（列表项，非表格行）
    await page.getByRole('button', { name: '🗑 回收站' }).click()
    const dialog = page.locator('.el-dialog', { hasText: '回收站' })
    await expect(dialog).toBeVisible()
    const trashItem = dialog.locator('li', { hasText: 'OLD ONLY' })
    await expect(trashItem).toBeVisible()

    // 还原 → 文件回来
    await trashItem.getByRole('button', { name: '还原' }).click()
    await expect(page.locator('.fname', { hasText: 'UDG@MMLCommand@OLD ONLY.md' })).toBeVisible()
  })
})
