import { useEffect, useState } from 'react'
import { API_URL, request } from '../lib/api'
import type { GoogleStatus, Session } from '../types'

export function useGoogleAccount(session: Session) {
  const [googleStatus, setGoogleStatus] = useState<GoogleStatus | null>(session.google)
  const needsReplyAccess = Boolean(session.google?.connected && session.google.can_follow_replies === false)
  const [googleReturn] = useState(() => new URLSearchParams(window.location.search).has('google'))
  const [googlePanelOpen, setGooglePanelOpen] = useState(googleReturn)

  useEffect(() => {
    if (googleReturn) {
      window.history.replaceState({}, '', `${window.location.pathname}${window.location.hash}`)
    }
  }, [googleReturn])

  function connectGoogle() {
    window.location.href = `${API_URL}/google/connect`
  }

  async function reconnectGoogle() {
    await request('/google/disconnect', { method: 'POST' }).catch(() => undefined)
    connectGoogle()
  }

  async function disconnectGoogle() {
    setGoogleStatus(await request<GoogleStatus>('/google/disconnect', { method: 'POST' }))
  }

  return {
    googleStatus,
    needsReplyAccess,
    googlePanelOpen,
    setGooglePanelOpen,
    connectGoogle,
    reconnectGoogle,
    disconnectGoogle,
  }
}
