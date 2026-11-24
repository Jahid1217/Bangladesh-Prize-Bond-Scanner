const SERVER_KEY = 'pbs.serverUrl'

export class ApiError extends Error {
  constructor(message, status = 0, detail = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export function getServerUrl() {
  return (localStorage.getItem(SERVER_KEY) || '').trim().replace(/\/+$/, '')
}

export function setServerUrl(url) {
  const clean = (url || '').trim().replace(/\/+$/, '')
  if (clean) localStorage.setItem(SERVER_KEY, clean)
  else localStorage.removeItem(SERVER_KEY)
}

export function apiUrl(path) {
  const base = import.meta.env.VITE_API_BASE || getServerUrl()
  return `${base || ''}${path}`
}

export function isNativePlatform() {
  return Boolean(window.Capacitor?.isNativePlatform?.())
}

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(apiUrl(path), {
      headers: { Accept: 'application/json', ...(options.headers || {}) },
      ...options,
    })
  } catch {
    throw new ApiError(
      'Cannot reach the scanner backend. Check Wi-Fi and the server address.',
      0,
    )
  }

  const type = response.headers.get('content-type') || ''
  const payload = type.includes('application/json')
    ? await response.json().catch(() => null)
    : await response.text()

  if (!response.ok) {
    const detail = payload?.detail ?? payload
    const message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((item) => item?.msg || String(item)).join('; ')
          : detail?.message || `Request failed (${response.status})`
    throw new ApiError(message, response.status, detail)
  }
  return payload
}

export const api = {
  health: () => request('/api/health'),
  stats: () => request('/api/stats'),
  scans: (limit = 12) => request(`/api/scans?limit=${limit}`),
  bonds: (search = '', limit = 20) =>
    request(`/api/bonds?limit=${limit}&search=${encodeURIComponent(search)}`),
  createBond: (body) =>
    request('/api/bonds', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  updateBond: (id, body) =>
    request(`/api/bonds/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  corrections: (id) => request(`/api/bonds/${id}/corrections`),
  preview: async (blob) => {
    const form = new FormData()
    form.append('file', blob, 'frame.jpg')
    return request('/api/ocr/preview', { method: 'POST', body: form })
  },
  scan: async (blob) => {
    const form = new FormData()
    form.append('file', blob, 'frame.jpg')
    return request('/api/scans/frame', { method: 'POST', body: form })
  },
}

export const exportUrl = {
  xlsx: () => apiUrl('/api/exports/xlsx'),
  csv: () => apiUrl('/api/exports/csv'),
}

export const imageUrl = (attemptId) => apiUrl(`/api/scans/${attemptId}/image`)
