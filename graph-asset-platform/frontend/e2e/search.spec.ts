import { test, expect } from '@playwright/test'
import { ADMIN, login } from './helpers'

test.describe('搜索框', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, ADMIN)
  })

  test('中文名（name_zh）搜索命中 + 总数展示', async ({ page }) => {
    // 「演示命令」是 ACT DEMO 的 name_zh（修复前中文搜索 0 命中）
    await page.getByPlaceholder('搜索 id / 名称 / 中文名').fill('演示命令')
    // 300ms debounce + 请求 → 结果
    await expect(
      page.locator('.cell-id', { hasText: 'UDG@MMLCommand@ACT DEMO' }).first(),
    ).toBeVisible()
    await expect(page.locator('.footer-text').first()).toContainText('共 1 项')
  })

  test('清空搜索恢复全部', async ({ page }) => {
    const search = page.getByPlaceholder('搜索 id / 名称 / 中文名')
    await search.fill('演示命令')
    await expect(page.locator('.footer-text').first()).toContainText('共 1 项')
    await search.fill('')
    // 恢复后总数 > 1（语料 7 对象去重后 ≥ 5）
    await expect(page.locator('.footer-text').first()).toContainText(/共 [2-9]\d* 项/)
  })
})
