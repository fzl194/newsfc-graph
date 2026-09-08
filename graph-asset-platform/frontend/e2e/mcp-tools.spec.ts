import { test, expect } from '@playwright/test'
import { ADMIN, login } from './helpers'

// MCP 工具配置页（admin，v13 三态模型）：公开工具区 3 个 + 兼容工具区 3 个
// （hidden deprecated）；补充说明输入框默认为空（不再预填——canonical 只读展示）。
test('mcp tools page shows public and legacy sections', async ({ page }) => {
  await login(page, ADMIN)
  await page.goto('/mcp-tools')
  await page.waitForSelector('.el-table__row')

  const publicNames = await page
    .locator('.table-card')
    .first()
    .locator('.tool-name')
    .allTextContents()
  // 顺序 = mcp_server 注册序
  expect(publicNames).toEqual(['get_domains', 'get_md', 'search_graph'])

  // 兼容工具区（第二个 table-card）：legacy 三工具 + deprecated 徽标
  const cards = page.locator('.table-card')
  const legacyNames = await cards.nth(1).locator('.tool-name').allTextContents()
  expect(legacyNames).toEqual(['search_objects', 'search_md', 'get_object'])
  expect(await cards.nth(1).locator('.off-badge').count()).toBe(3)

  // 补充说明输入框默认为空（canonical 描述在只读折叠框里，不进输入框）
  for (let i = 0; i < publicNames.length; i++) {
    const val = await cards
      .first()
      .locator('.el-table__row')
      .nth(i)
      .locator('textarea')
      .inputValue()
    expect(val, `${publicNames[i]} 补充说明应为空`).toBe('')
  }
  // 公开区默认 visibility=visible 选择器存在
  expect(await cards.first().locator('.el-select').count()).toBe(3)

  // canonical 描述折叠框可展开且非空
  const box = cards.first().locator('.canonical-box').first()
  await box.locator('summary').click()
  const text = await box.locator('.canonical-pre').textContent()
  expect((text || '').length).toBeGreaterThan(20)

  // 总体说明：canonical 决策树只读 + 补充输入框为空
  const instr = page.locator('.instructions-card textarea')
  expect(await instr.inputValue()).toBe('')
  const instrBox = page.locator('.instructions-card .canonical-box')
  await instrBox.locator('summary').click()
  const instrText = await instrBox.locator('.canonical-pre').textContent()
  expect(instrText || '').toContain('决策树')
})

// 修改 visibility + 补充说明 → 保存 → 生效回显
test('mcp tools page saves visibility and supplement', async ({ page }) => {
  await login(page, ADMIN)
  await page.goto('/mcp-tools')
  await page.waitForSelector('.el-table__row')

  // 给 get_md 填补充说明（注册序 get_domains/get_md/search_graph → nth(1)）
  const firstCard = page.locator('.table-card').first()
  const row = firstCard.locator('.el-table__row').nth(1) // get_md
  await row.locator('textarea').fill('E2E 补充说明测试')

  // 总体说明补一段
  await page.locator('.instructions-card textarea').fill('E2E 总体补充')

  await page.getByRole('button', { name: /保存配置/ }).click()
  await expect(page.locator('.el-message--success')).toBeVisible()

  // 重新加载后回显
  await page.goto('/mcp-tools')
  await page.waitForSelector('.el-table__row')
  const cards = page.locator('.table-card')
  const val = await cards
    .first()
    .locator('.el-table__row')
    .nth(1)
    .locator('textarea')
    .inputValue()
  expect(val).toBe('E2E 补充说明测试')
  expect(await page.locator('.instructions-card textarea').inputValue()).toBe(
    'E2E 总体补充',
  )

  // 清理（避免污染共享 e2e 数据目录）
  await cards.first().locator('.el-table__row').nth(1).locator('textarea').fill('')
  await page.locator('.instructions-card textarea').fill('')
  await page.getByRole('button', { name: /保存配置/ }).click()
  await expect(page.locator('.el-message--success')).toBeVisible()
})

// 小视口/放大场景：内容超高时页面必须出滚动条，滚到底两张表 + 总体说明可达
// （flex 子项 flex-shrink:0 防裁行）。
test('mcp tools page scrolls at small viewport (no clipped rows)', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 600 }) // 模拟高分屏 150% 缩放
  await login(page, ADMIN)
  await page.goto('/mcp-tools')
  await page.waitForSelector('.el-table__row')

  // 6 行工具都在 DOM（不被裁掉）
  expect(await page.locator('.el-table__row .tool-name').count()).toBe(6)

  const scrollable = await page.locator('.mcp-tools-page').evaluate((el) => ({
    sh: el.scrollHeight, ch: el.clientHeight,
  }))
  expect(scrollable.sh).toBeGreaterThan(scrollable.ch)

  await page.locator('.instructions-card textarea').scrollIntoViewIfNeeded()
  await expect(page.locator('.tool-name', { hasText: 'get_object' })).toBeVisible()
  await expect(page.locator('.instructions-card textarea')).toBeVisible()
})
