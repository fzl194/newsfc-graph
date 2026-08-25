import { createRouter, createWebHistory } from 'vue-router'
import { getSession } from './auth'

// 三菜单信息架构：图谱浏览（默认）/ 统计 / 上传
export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('./views/LoginView.vue'),
    },
    {
      path: '/',
      name: 'browser',
      component: () => import('./views/BrowserView.vue'),
    },
    {
      path: '/stats',
      name: 'stats',
      component: () => import('./views/StatsView.vue'),
    },
    {
      path: '/upload',
      name: 'upload',
      component: () => import('./views/UploadView.vue'),
    },
    {
      path: '/fs',
      name: 'fs',
      component: () => import('./views/FsBrowserView.vue'),
    },
    // 测试用例管理子系统（独立模块，第 4 菜单）
    {
      path: '/users',
      name: 'users',
      component: () => import('./views/UsersView.vue'),
    },
    {
      path: '/mcp-tools',
      name: 'mcp-tools',
      component: () => import('./views/McpToolsView.vue'),
    },
    {
      path: '/tests',
      name: 'tests',
      component: () => import('./tests-module/views/TestCasesView.vue'),
    },
    {
      path: '/tests/cases/:id',
      name: 'tests-case',
      component: () => import('./tests-module/views/CaseDetailView.vue'),
    },
    {
      path: '/tests/runs/:id',
      name: 'tests-run',
      component: () => import('./tests-module/views/RunDetailView.vue'),
    },
  ],
})

// 守卫：除登录页外，无 KEY → 跳登录
router.beforeEach((to) => {
  if (to.name === 'login') return true
  const s = getSession()
  if (!s) return { name: 'login' }
  if (to.name === 'users' && !s.is_admin) return false // 非 admin 拒绝
  if (to.name === 'mcp-tools' && !s.is_admin) return false // MCP 工具配置面（admin）
  // 资产管理表面（目录 + 上传页）专属 can_assets（默认仅 admin）
  if ((to.name === 'fs' || to.name === 'upload') && !s.can_assets) return false
  return true
})
