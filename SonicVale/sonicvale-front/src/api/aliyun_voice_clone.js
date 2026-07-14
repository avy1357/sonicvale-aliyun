import request from './config'

/**
 * 查询阿里云音色列表
 */
export function queryAliyunVoiceList(ttsProviderId, pageIndex = 0, pageSize = 10, prefix) {
  const params = {
    tts_provider_id: ttsProviderId,
    page_index: pageIndex,
    page_size: pageSize
  }
  if (prefix) params.prefix = prefix
  return request.get('/aliyun-voices/list', { params })
}

/**
 * 获取阿里云音色详情
 */
export function getAliyunVoiceDetail(ttsProviderId, voiceId) {
  return request.get('/aliyun-voices/detail', {
    params: { tts_provider_id: ttsProviderId, voice_id: voiceId }
  })
}

/**
 * 创建阿里云音色
 */
export function createAliyunVoice(data) {
  return request.post('/aliyun-voices/create', data)
}

/**
 * 更新阿里云音色
 */
export function updateAliyunVoice(data) {
  return request.put('/aliyun-voices/update', data)
}

/**
 * 删除阿里云音色
 */
export function deleteAliyunVoice(ttsProviderId, voiceId) {
  return request.delete('/aliyun-voices/delete', {
    params: { tts_provider_id: ttsProviderId, voice_id: voiceId }
  })
}

/**
 * 批量同步阿里云音色到本地
 */
export function syncAliyunVoices(ttsProviderId) {
  return request.post('/aliyun-voices/sync', null, {
    params: { tts_provider_id: ttsProviderId }
  })
}

/**
 * 同步单个阿里云音色到本地
 */
export function syncAliyunVoiceSingle(ttsProviderId, voiceId) {
  return request.post('/aliyun-voices/sync-single', null, {
    params: { tts_provider_id: ttsProviderId, voice_id: voiceId }
  })
}
