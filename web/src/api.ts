export class ApiError extends Error {
  code: string
  constructor(code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.code = code
  }
}

type ErrorBody = {
  status?: string
  error?: { code?: string; message?: string }
}

export async function api<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers = new Headers(opts.headers)
  const isForm = opts.body instanceof FormData
  if (opts.body && !isForm && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const locale = localStorage.getItem('locale') || 'en'
  if (!headers.has('Accept-Language')) {
    headers.set('Accept-Language', locale)
  }
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
    throw new ApiError(body?.error?.code || `http_${res.status}`, body?.error?.message || res.statusText)
  }
  return data as T
}
