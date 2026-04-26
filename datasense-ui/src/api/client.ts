import axios from 'axios'

// In dev, Vite proxies /api → http://localhost:8000 (no CORS issues).
// In prod, set VITE_API_URL to your deployed backend URL.
const baseURL = import.meta.env.VITE_API_URL ?? ''

export const client = axios.create({
  baseURL,
  timeout: 120_000,
})

client.interceptors.response.use(
  (res) => res,
  (err) => {
    const detail = err.response?.data?.detail
    const message =
      typeof detail === 'string'
        ? detail
        : typeof detail === 'object' && detail?.error
          ? detail.error
          : err.message
    return Promise.reject(new Error(message))
  },
)
