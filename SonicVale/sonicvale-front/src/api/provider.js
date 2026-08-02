import request from './config'

/**
 * LLM Providers
 */

// 敏感字段列表(脱敏用)
const SENSITIVE_KEYS = ['api_key', 'x_api_key', 'access_key_id', 'access_key_secret']

// 将敏感字符串脱敏为掩码,如 sk-***1234
function maskSecret(val) {
  if (val == null) return val
  const s = String(val)
  if (s.length <= 8) return '***'
  return s.slice(0, 3) + '***' + s.slice(-4)
}

// 对 provider 列表中的敏感字段做脱敏(仅列表展示用,编辑时需单独请求完整数据)
function maskProviderSecrets(list) {
  if (!Array.isArray(list)) return list
  return list.map(item => {
    if (!item || typeof item !== 'object') return item
    const masked = { ...item }
    SENSITIVE_KEYS.forEach(k => {
      if (masked[k] != null && masked[k] !== '') {
        masked[k] = maskSecret(masked[k])
      }
    })
    return masked
  })
}

// 获取 LLM 提供商列表(敏感字段已脱敏)
export function fetchLLMProviders() {
  return request.get('/llm_providers/').then(res => {
    if (res.code === 200) {
      return maskProviderSecrets(res.data)
    }
    return []
  })
}

// 创建 LLM 提供商
export function createLLMProvider(payload) {
  // payload: { name, api_base_url, api_key?, model_list?, status? }
  return request.post('/llm_providers/', payload)
}

// 更新 LLM 提供商
export function updateLLMProvider(id, payload) {
  return request.put(`/llm_providers/${id}`, payload)
}

// 删除 LLM 提供商
export function deleteLLMProvider(id) {
  return request.delete(`/llm_providers/${id}`)
}
// 测试 LLM 提供商
export function testLLMProvider(data) {
  return request.post('/llm_providers/test', data)
}

/**
 * TTS Provider
 */

// 获取 TTS 提供商列表(敏感字段已脱敏)
export function fetchTTSProviders() {
  return request.get('/tts_providers').then(res => {
    if (res.code === 200) {
      return maskProviderSecrets(res.data)
    }

    // 如果后端暂时没实现接口，就返回默认值，以避免前端报错
  })
}

// 创建 TTS 提供商
export function createTTSProvider(payload) {
  return request.post('/tts_providers/', payload)
}

// 更新 TTS 提供商
export function updateTTSProvider(id, payload) {
  return request.put(`/tts_providers/${id}`, payload)
}

// 删除 TTS 提供商
export function deleteTTSProvider(id) {
  return request.delete(`/tts_providers/${id}`)
}


// 测试 TTS 引擎
export function testTTSProvider(data) {
  return request.post('/tts_providers/test', data)
}

