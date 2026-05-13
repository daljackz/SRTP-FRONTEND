import { createRouter, createWebHistory } from 'vue-router'

// 1. 【路线图】（你刚才写的极致优化版）
const routes = [
  { path: '/', component: () => import('../views/Dashboard.vue') },
  { path: '/info', component: () => import('../views/DispatchInfo.vue') },
  { path: '/logs', component: () => import('../views/Logs.vue') },
  { path: '/profile', component: () => import('../views/Profile.vue') },
  { path: '/about', component: () => import('../views/About.vue') }
]

// 2. 【制造引擎】用上面的路线图，创建一个真正的路由引擎
const router = createRouter({
  history: createWebHistory(),
  routes: routes
})

// 3. 【发货】把造好的引擎导出去，让 main.js 能接收到！
export default router