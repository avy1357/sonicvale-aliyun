import request from './config'

export function fetchVoiceClones(ttsProviderId) {
  return request.get(`/voice-clones/tts/${ttsProviderId}`)
}

export function getVoiceClone(cloneId) {
  return request.get(`/voice-clones/${cloneId}`)
}

export function createVoiceClone(data) {
  return request.post('/voice-clones', data)
}

export function updateVoiceClone(cloneId, data) {
  return request.put(`/voice-clones/${cloneId}`, data)
}

export function deleteVoiceClone(cloneId) {
  return request.delete(`/voice-clones/${cloneId}`)
}

export function uploadAudio(data) {
  return request.post('/voice-clones/upload', data)
}

export function queryStatus(cloneId) {
  return request.post('/voice-clones/status', null, { params: { clone_id: cloneId } })
}

export function trainAndWait(data) {
  return request.post('/voice-clones/train-and-wait', data)
}
