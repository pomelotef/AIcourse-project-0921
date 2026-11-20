export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  let res: Response
  try {
    res = await fetch(url, {
      method,
      credentials: 'same-origin',
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(0, '無法連線到伺服器，請確認後端已啟動')
  }
  const text = await res.text()
  let data: any = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    if (!res.ok) throw new ApiError(res.status, `伺服器錯誤（${res.status}），請稍後再試`)
    throw new ApiError(res.status, '伺服器回應格式錯誤')
  }
  if (!res.ok) {
    const detail = data && typeof data.detail === 'string' ? data.detail : `請求失敗（${res.status}）`
    if (res.status === 401) window.dispatchEvent(new Event('labpulse:unauthorized'))
    throw new ApiError(res.status, detail)
  }
  return data as T
}

export const api = {
  get: <T>(url: string) => request<T>('GET', url),
  post: <T>(url: string, body: unknown = {}) => request<T>('POST', url, body),
  patch: <T>(url: string, body: unknown) => request<T>('PATCH', url, body),
  del: <T>(url: string) => request<T>('DELETE', url),
}
