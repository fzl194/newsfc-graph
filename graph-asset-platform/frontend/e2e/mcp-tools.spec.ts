import { test, expect } from '@playwright/test'
import { ADMIN, login } from './helpers'

// MCP 工具配置页（admin）：5 工具全量展示 + 描述输入框预填默认值（2026-08-25 用户反馈）
test('mcp tools page shows 5 tools with prefilled descriptions', async ({ page }) => {
  await login(page, ADMIN)
  await page.goto('/mcp-tools')
  await page.waitForSelector('.el-table__row')

  const rows = page.locator('.el-table__row')
  const names = await rows.locator('.tool-name').allTextContents()
  expect(names).toEqual([
    'get_domains', 'get_md', 'search_objects', 'search_md', 'get_object',
  ])

  // 每行描述输入框预填了默认描述（非空、非 placeholder）
  for (let i = 0; i < names.length; i++) {
    const val = await rows.nth(i).locator('textarea').inputValue()
    expect(val.length, `${names[i]} 描述应预填`).toBeGreaterThan(20)
  }

  // 总体说明输入框同样预填默认
  const instr = page.locator('.instructions-card textarea')
  expect((await instr.inputValue()).length).toBeGreaterThan(10)
})

// 小视口/放大场景（用户反馈：放大后只见 4/3 个工具且无滚动条）：
// 内容超高时页面必须出滚动条，滚到底 5 行工具 + 总体说明全部可达。
// 根因：flex 子项带 overflow:hidden 被压缩裁行——已加 flex-shrink:0。
test('mcp tools page scrolls at small viewport (no clipped rows)', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 600 }) // 模拟高分屏 150% 缩放下的有效视口
  await login(page, ADMIN)
  await page.goto('/mcp-tools')
  await page.waitForSelector('.el-table__row')

  // 5 行都在 DOM（不被裁掉）
  expect(await page.locator('.el-table__row .tool-name').count()).toBe(5)

  // 页面容器确实可滚动（scrollHeight 超过 clientHeight 才有滚动条）
  const scrollable = await page.locator('.mcp-tools-page').evaluate((el) => ({
    sh: el.scrollHeight, ch: el.clientHeight,
  }))
  expect(scrollable.sh).toBeGreaterThan(scrollable.ch)

  // 滚到底：第 5 个工具与总体说明输入框都可见
  await page.locator('.instructions-card textarea').scrollIntoViewIfNeeded()
  await expect(page.locator('.tool-name', { hasText: 'get_object' })).toBeVisible()
  await expect(page.locator('.instructions-card textarea')).toBeVisible()
})
