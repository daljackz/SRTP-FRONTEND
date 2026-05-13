import { createApp } from 'vue'
import './style.css'
import App from './App.vue'

// 引入 Element Plus 的核心和样式
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import { ro } from 'element-plus/es/locale/index.mjs'

const app = createApp(App)

// 告诉 Vue 引擎，我们要使用 Element Plus 这个配件库
app.use(ElementPlus)
app.use(router)

app.mount('#app')