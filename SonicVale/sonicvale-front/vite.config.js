import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  // 关键设置:让资源路径相对,Tauri 生产环境加载 dist/index.html 需要
  base: './',
  plugins: [vue()],
  // Tauri 推荐配置
  clearScreen: false,
  server: {
    strictPort: true
  }
})
