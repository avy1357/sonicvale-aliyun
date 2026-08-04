// src/api/config.js
import axios from 'axios'

const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8200/', // 统一前缀，支持环境变量覆盖
  timeout: 60000
})

// 请求拦截器
service.interceptors.request.use(
  config => {
    // 这里可以加 token
    return config
  },
  error => Promise.reject(error)
)

// 响应拦截器
service.interceptors.response.use(
  response => response.data,
  error => {
    // 仅打印错误日志,不在此处统一弹出 ElMessage,避免每个 API 调用都弹消息造成干扰
    // 业务层应根据各自场景决定是否提示用户
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

export default service
