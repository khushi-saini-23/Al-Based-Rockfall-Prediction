import axios from 'axios'

const api = axios.create({baseURL: import.meta.env.VITE_API_URL || '', timeout: 8000})
export const get = (path) => api.get(path).then(r => r.data)
export const post = (path, data) => api.post(path, data).then(r => r.data)
export const patch = (path, data) => api.patch(path, data).then(r => r.data)
export const upload = (path, file, zoneId) => {
  const body = new FormData(); body.append('file', file)
  return api.post(`${path}?zone_id=${encodeURIComponent(zoneId)}`, body).then(r => r.data)
}
