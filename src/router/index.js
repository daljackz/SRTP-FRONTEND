// 【极致优化的企业级写法】
const routes = [
  // 大屏是首页，必须直接加载
  { path: '/', component: () => import('../') },
  // 其他页面，只有当用户真正点击网址时，才会去下载对应的 .vue 代码
  { path: '/info', component: () => import('../views/DispatchInfo.vue') },
  { path: '/logs', component: () => import('../views/Logs.vue') },
  { path: '/profile', component: () => import('../views/Profile.vue') },
  { path: '/about', component: () => import('../views/About.vue') }
]