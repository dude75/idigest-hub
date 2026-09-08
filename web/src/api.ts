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

function parseJson(text: string): unknown {
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
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

    if (onProgress) {
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) onProgress(e.loaded, e.total)
      })
    }

    xhr.onload = () => {
      const data = parseJson(xhr.responseText)
      const errBody = data as ErrorBody | null
      if (xhr.status < 200 || xhr.status >= 300) {
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
