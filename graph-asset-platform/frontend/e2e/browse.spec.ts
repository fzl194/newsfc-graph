import { test, expect } from '@playwright/test'
import { ADMIN, login, pickSelect } from './helpers'

/**
 * 图谱浏览：多版本切换（核心回归——修复前选旧版本列表为空）。
 * 语料见 backend/scripts/seed_e2e.py：
 *   ACT DEMO（20.15.2 + 20.16.2 双版本）/ OLD ONLY（仅 20.15.2）
 */
test.describe('图谱浏览 · 版本切换', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, ADMIN)
  })

  test('默认层列表加载并显示总数', async ({ page }) => {
    await expect(page.getByRole('button', { name: /命令层/ })).toBeVisible()
    // footer 显示「共 N 项」（X-Total-Count）
    await expect(page.locator('.footer-text').first()).toContainText(/共 \d+ 项/)
  })

  test('选旧版本 20.15.2：双版本对象可见（回归），点开中栏版本一致', async ({ page }) => {
    await pickSelect(page, 0, 'UDG')
    await pickSelect(page, 1, '20.15.2')
    // 双版本对象 + 仅旧版本对象都在旧版本下列表可见
    await expect(page.locator('.cell-id', { hasText: 'UDG@MMLCommand@ACT DEMO' }).first()).toBeVisible()
    await expect(page.locator('.cell-id', { hasText: 'UDG@MMLCommand@OLD ONLY' }).first()).toBeVisible()
    // 点行 → 中栏详情按所选版本打开（版本上下文一致）
    await page.locator('.cell-id', { hasText: 'UDG@MMLCommand@ACT DEMO' }).first().click()
    await expect(page.locator('.badge-ver')).toHaveText('20.15.2')
  })

  test('切到 20.16.2：仅旧版本对象消失，双版本对象仍在', async ({ page }) => {
    await pickSelect(page, 0, 'UDG')
    await pickSelect(page, 1, '20.15.2')
    await expect(page.locator('.cell-id', { hasText: 'UDG@MMLCommand@OLD ONLY' }).first()).toBeVisible()
    await pickSelect(page, 1, '20.16.2')
    await expect(page.locator('.cell-id', { hasText: 'UDG@MMLCommand@ACT DEMO' }).first()).toBeVisible()
    await expect(page.locator('.cell-id', { hasText: 'UDG@MMLCommand@OLD ONLY' })).toHaveCount(0)
  })

  test('中栏详情版本下拉切换：版本上下文联动', async ({ page }) => {
    await pickSelect(page, 0, 'UDG')
    await pickSelect(page, 1, '20.15.2')
    await page.locator('.cell-id', { hasText: 'UDG@MMLCommand@ACT DEMO' }).first().click()
    await expect(page.locator('.badge-ver')).toHaveText('20.15.2')
    // 详情内切到 20.16.2 → 中栏版本 badge 跟随
    await page.locator('.ver-select').click()
    await page
      .locator('.el-select-dropdown:visible .el-select-dropdown__item', { hasText: '20.16.2' })
      .first()
      .click()
    await expect(page.locator('.badge-ver')).toHaveText('20.16.2')
  })

  test('语义版本陷阱：SEM TRAP 默认落 20.15.2 而非 20.9.10', async ({ page }) => {
    await pickSelect(page, 0, 'UNC')
    // 不选版本 → 点对象，后端应落语义最新 20.15.2
    await page.locator('.cell-id', { hasText: 'UNC@MMLCommand@SEM TRAP' }).first().click()
    await expect(page.locator('.badge-ver')).toHaveText('20.15.2')
  })

  test('URL 同步 ?o= + ?version= 刷新可恢复', async ({ page }) => {
    await pickSelect(page, 0, 'UDG')
    await pickSelect(page, 1, '20.15.2')
    await page.locator('.cell-id', { hasText: 'UDG@MMLCommand@ACT DEMO' }).first().click()
    await expect(page.locator('.badge-ver')).toHaveText('20.15.2')
    await page.reload()
    await expect(page.locator('.badge-ver')).toHaveText('20.15.2')
  })
})
