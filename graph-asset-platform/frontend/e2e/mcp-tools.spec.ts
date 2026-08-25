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
