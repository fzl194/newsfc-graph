import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// dev/preview proxy: /api → 后端（默认 8000；e2e 用 VITE_API_TARGET 覆盖）
// build 产物 dist/ 由后端 main.py 静态托管（SPA 兜底）。
const apiTarget = process.env.VITE_API_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [vue()],
  server: { proxy: { '/api': apiTarget } },
  preview: { proxy: { '/api': apiTarget } },
  build: { outDir: 'dist' },
})
