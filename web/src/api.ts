export class ApiError extends Error {
  code: string
  retryAfter?: number
  constructor(code: string, message: string, retryAfter?: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.retryAfter = retryAfter
  }
}

type ErrorBody = {
  status?: string
  error?: { code?: string; message?: string }
}

/** Last token from GET/PATCH /me (matches hub_csrf cookie when cookies are readable). */
let cachedCsrf: string | undefined

export function rememberCsrfToken(data: unknown): void {
  if (!data || typeof data !== 'object') return
  const token = (data as { csrf_token?: unknown }).csrf_token
  if (typeof token === 'string' && token) cachedCsrf = token
}

function csrfFromCookie(): string | undefined {
  const match = document.cookie.match(/(?:^|; )hub_csrf=([^;]*)/)
  return match ? decodeURIComponent(match[1]) : undefined
}

function csrfToken(): string | undefined {
  return cachedCsrf || csrfFromCookie()
}

function applyCsrfHeader(headers: Headers, method: string): void {
  const normalized = method.toUpperCase()
  if (!['POST', 'PUT', 'PATCH', 'DELETE'].includes(normalized)) return
  const token = csrfToken()
  if (token && !headers.has('X-CSRF-Token')) {
    headers.set('X-CSRF-Token', token)
  }
}

export async function api<T>(path: string, opts: RequestInit = {}, retried = false): Promise<T> {
  const headers = new Headers(opts.headers)
  const isForm = opts.body instanceof FormData
  if (opts.body && !isForm && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const locale = localStorage.getItem('locale') || 'en'
  if (!headers.has('Accept-Language')) {
    headers.set('Accept-Language', locale)
  }
  applyCsrfHeader(headers, opts.method || 'GET')
  const res = await fetch(`/api/v1${path}`, {
    ...opts,
    credentials: 'include',
    headers,
  })
  const text = await res.text()
  let data: unknown = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = null
    }
  }
  const body = data as ErrorBody | null
  if (!res.ok) {
    const code = body?.error?.code || `http_${res.status}`
    if (!retried && code === 'csrf_invalid' && path !== '/me') {
      cachedCsrf = undefined
      try {
        await api<{ csrf_token?: string }>('/me')
        return api<T>(path, opts, true)
      } catch {
        /* fall through */
      }
    }
    const retryRaw = res.headers.get('Retry-After')
    const retryAfter = retryRaw ? Number.parseInt(retryRaw, 10) : undefined
    throw new ApiError(
      code,
      body?.error?.message || res.statusText,
      Number.isFinite(retryAfter) && retryAfter! > 0 ? retryAfter : undefined,
    )
  }
  rememberCsrfToken(data)
  return data as T
}

function parseJson(text: string): unknown {
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

function filenameFromDisposition(header: string | null): string | undefined {
  if (!header) return undefined
  const star = header.match(/filename\*=UTF-8''([^;]+)/i)
  if (star) {
    try {
      return decodeURIComponent(star[1])
    } catch {
      return star[1]
    }
  }
  const plain = header.match(/filename="([^"]+)"/i)
  return plain?.[1]
}

export async function apiDownload(path: string, filename?: string): Promise<void> {
  const locale = localStorage.getItem('locale') || 'en'
  const res = await fetch(`/api/v1${path}`, {
    credentials: 'include',
    headers: { 'Accept-Language': locale },
  })
  if (!res.ok) {
    const text = await res.text()
    let data: unknown = null
    if (text) {
      try {
        data = JSON.parse(text)
      } catch {
        data = null
      }
    }
    const body = data as ErrorBody | null
    throw new ApiError(body?.error?.code || `http_${res.status}`, body?.error?.message || res.statusText)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || filenameFromDisposition(res.headers.get('Content-Disposition')) || 'download'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export function apiUpload<T>(
  path: string,
  body: FormData,
  onProgress?: (loaded: number, total: number) => void,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `/api/v1${path}`)
    xhr.withCredentials = true
    const locale = localStorage.getItem('locale') || 'en'
    xhr.setRequestHeader('Accept-Language', locale)
    const csrf = csrfToken()
    if (csrf) xhr.setRequestHeader('X-CSRF-Token', csrf)

    if (onProgress) {
      let lastTotal = 0
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          lastTotal = e.total
          onProgress(e.loaded, e.total)
        }
      })
      xhr.upload.addEventListener('load', () => {
        if (lastTotal > 0) onProgress(lastTotal, lastTotal)
      })
    }

    xhr.onload = () => {
      const data = parseJson(xhr.responseText)
      rememberCsrfToken(data)
      const errBody = data as ErrorBody | null
      if (xhr.status < 200 || xhr.status >= 300) {
        if (xhr.status === 403 && errBody?.error?.code === 'csrf_invalid') {
          api<T>('/me')
            .then(() => apiUpload<T>(path, body, onProgress).then(resolve).catch(reject))
            .catch(() => reject(new ApiError('csrf_invalid', errBody?.error?.message || xhr.statusText)))
          return
        }
        reject(new ApiError(errBody?.error?.code || `http_${xhr.status}`, errBody?.error?.message || xhr.statusText))
        return
      }
      resolve(data as T)
    }
    xhr.onerror = () => reject(new ApiError('network_error', 'Network error'))
    xhr.onabort = () => reject(new ApiError('aborted', 'Upload aborted'))
    xhr.send(body)
  })
}
