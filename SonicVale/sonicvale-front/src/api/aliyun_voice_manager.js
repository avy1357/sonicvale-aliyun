import request from './config'

/**
 * 阿里云音色管理 API
 * 对应后端路由: /aliyun-voice-manager
 */

/**
 * 查询阿里云音色列表
 */
export function queryAliyunVoiceManagerList(ttsProviderId, pageIndex = 0, pageSize = 10, prefix) {
  const params = {
    tts_provider_id: ttsProviderId,
    page_index: pageIndex,
    page_size: pageSize
  }
  if (prefix) params.prefix = prefix
  return request.get('/aliyun-voice-manager/list', { params })
}

/**
 * 获取阿里云音色详情
 */
export function getAliyunVoiceManagerDetail(ttsProviderId, voiceId) {
  return request.get('/aliyun-voice-manager/detail', {
    params: { tts_provider_id: ttsProviderId, voice_id: voiceId }
  })
}

/**
 * 创建阿里云音色（声音复刻）
 */
export function createAliyunVoiceManager(data) {
  return request.post('/aliyun-voice-manager/create', data)
}

/**
 * 更新阿里云音色
 */
export function updateAliyunVoiceManager(data) {
  return request.put('/aliyun-voice-manager/update', data)
}

/**
 * 删除阿里云音色
 * @param {object} data - { tts_provider_id, voice_id, delete_local }
 */
export function deleteAliyunVoiceManager(data) {
  return request.delete('/aliyun-voice-manager/delete', { data })
}

/**
 * 批量同步阿里云音色到本地
 */
export function syncAliyunVoiceManagerAll(ttsProviderId) {
  return request.post('/aliyun-voice-manager/sync', null, {
    params: { tts_provider_id: ttsProviderId }
  })
}

/**
 * 同步单个阿里云音色到本地
 */
export function syncAliyunVoiceManagerSingle(ttsProviderId, voiceId) {
  return request.post('/aliyun-voice-manager/sync-single', null, {
    params: { tts_provider_id: ttsProviderId, voice_id: voiceId }
  })
}
