import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'

// 字体（@fontsource：本地打包，无外网请求，build 后自包含）
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/inter/700.css'
import '@fontsource/space-grotesk/500.css'
import '@fontsource/space-grotesk/600.css'
import '@fontsource/space-grotesk/700.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'

import App from './App.vue'
import { router } from './router'
import './styles/tokens.css'

const app = createApp(App)
// 中文 locale：ElMessageBox/分页等组件内置文案（确定/取消、共 N 条…）
app.use(ElementPlus, { locale: zhCn })
app.use(router)
app.mount('#app')
