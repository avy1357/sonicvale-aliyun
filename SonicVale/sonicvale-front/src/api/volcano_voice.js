import request from './config'

export function queryVolcanoVoiceList(ttsProviderId, params = {}) {
  const query = { tts_provider_id: ttsProviderId }
  if (params.pageNumber) query.page_number = params.pageNumber
  if (params.pageSize) query.page_size = params.pageSize
  if (params.state) query.state = params.state
  if (params.speakerIds) query.speaker_ids = params.speakerIds
  if (params.nextToken) query.next_token = params.nextToken
  if (params.maxResults) query.max_results = params.maxResults
  if (params.orderTimeStart) query.order_time_start = params.orderTimeStart
  if (params.orderTimeEnd) query.order_time_end = params.orderTimeEnd
  if (params.expireTimeStart) query.expire_time_start = params.expireTimeStart
  if (params.expireTimeEnd) query.expire_time_end = params.expireTimeEnd
  return request.get('/volcano-voices/list', { params: query })
}

export function orderVolcanoVoices(ttsProviderId, times, quantity, autoUseCoupon, couponId) {
  const data = { tts_provider_id: ttsProviderId, times, quantity }
  if (autoUseCoupon !== undefined) data.auto_use_coupon = autoUseCoupon
  if (couponId) data.coupon_id = couponId
  return request.post('/volcano-voices/order', data)
}

export function renewVolcanoVoices(ttsProviderId, times, speakerIds, autoUseCoupon, couponId) {
  const data = { tts_provider_id: ttsProviderId, times }
  if (speakerIds && speakerIds.length) data.speaker_ids = speakerIds
  if (autoUseCoupon !== undefined) data.auto_use_coupon = autoUseCoupon
  if (couponId) data.coupon_id = couponId
  return request.post('/volcano-voices/renew', data)
}

export function syncVolcanoVoices(ttsProviderId) {
  return request.post('/volcano-voices/sync', null, { params: { tts_provider_id: ttsProviderId } })
}

export function syncVolcanoVoiceSingle(ttsProviderId, speakerId) {
  return request.post('/volcano-voices/sync-single', null, { params: { tts_provider_id: ttsProviderId, speaker_id: speakerId } })
}
