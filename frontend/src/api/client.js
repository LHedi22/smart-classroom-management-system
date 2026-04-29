import axios from 'axios'

const client = axios.create({ baseURL: '/api' })

// Inject JWT from localStorage into every request that has a token stored.
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('sc_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export default client
