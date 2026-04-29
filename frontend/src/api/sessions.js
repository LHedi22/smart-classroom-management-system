import client from './client'

export const getSessions  = ()   => client.get('/sessions').then(r => r.data)
export const getSession   = (id) => client.get(`/sessions/${id}`).then(r => r.data)
