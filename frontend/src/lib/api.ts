export const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

function apiErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== 'object' || !('detail' in payload)) return fallback
  const detail = (payload as { detail: unknown }).detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const messages = detail.flatMap((item) => {
      if (typeof item === 'string') return item
      if (item && typeof item === 'object' && 'msg' in item) {
        return String((item as { msg: unknown }).msg).replace(/^Value error,\s*/i, '')
      }
      return []
    })
    if (messages.length) return messages.join(' ')
  }
  return fallback
}

export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })

  if (!response.ok) {
    if (response.status === 401 && path !== '/auth/me') window.dispatchEvent(new Event('ponto:unauthorized'))
    const detail = await response.json().catch(() => null)
    throw new Error(apiErrorMessage(detail, `Pedido falhou (${response.status})`))
  }

  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}
