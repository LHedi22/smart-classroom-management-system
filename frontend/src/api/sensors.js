import client from './client'

export const getSessionSensorsLatest  = (sessionId) =>
  client.get(`/sessions/${sessionId}/sensors/latest`).then(r => r.data)

export const getSessionSensorsSummary = (sessionId) =>
  client.get(`/sessions/${sessionId}/sensors/summary`).then(r => r.data)
