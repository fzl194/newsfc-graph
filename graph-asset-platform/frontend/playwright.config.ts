import { defineConfig } from '@playwright/test'
import path from 'node:path'

// e2e 双 server：后端（seed 脚本 + uvicorn，独立数据目录）+ 前端 dev（proxy 指向后端）
// 端口避开常驻 dev（5173/8000）
const BACKEND_PORT = 8001
const FRONTEND_PORT = 5199
const DATA_DIR = path.resolve(__dirname, '../e2e-data')

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  // 共享同一套后端数据 → 串行执行最稳
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: { baseURL: `http://localhost:${FRONTEND_PORT}` },
  webServer: [
    {
      // seed 固定语料/账号（幂等，含清库）→ uvicorn（首启从 md 全量建库）
      command: 'python scripts/e2e_server.py',
      cwd: path.resolve(__dirname, '../backend'),
      env: { ...process.env, GAP_DATA_DIR: DATA_DIR, E2E_PORT: String(BACKEND_PORT) },
      port: BACKEND_PORT,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `npm run dev -- --port ${FRONTEND_PORT} --strictPort`,
      url: `http://localhost:${FRONTEND_PORT}`,
      env: { ...process.env, VITE_API_TARGET: `http://localhost:${BACKEND_PORT}` },
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
