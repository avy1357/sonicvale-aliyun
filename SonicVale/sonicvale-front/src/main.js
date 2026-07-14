import { createApp } from 'vue'
import App from './App.vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import router from './router'
// 挂载 Tauri 兼容层,提供 window.native 全局对象(替代原 Electron preload)
import './utils/nativeBridge.js'

createApp(App).use(router).use(ElementPlus).mount('#app')
