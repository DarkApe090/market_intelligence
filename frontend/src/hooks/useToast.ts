import { useEffect, useState } from 'react'
import type { AppToast, ToastKind } from '../types'
import { googleToast } from '../lib/storage'

export function useToast() {
  const [toast, setToast] = useState<AppToast | null>(googleToast)

  useEffect(() => {
    if (!toast || toast.kind === 'confirm') return
    const ms = toast.kind === 'warning' ? 6400 : 3600
    const timer = window.setTimeout(() => setToast(null), ms)
    return () => window.clearTimeout(timer)
  }, [toast])

  function showToast(kind: ToastKind, message: string) {
    setToast({ kind, message })
  }

  function askConfirm(message: string, confirmLabel: string, onConfirm: () => void) {
    setToast({ kind: 'confirm', message, confirmLabel, onConfirm })
  }

  return { toast, setToast, showToast, askConfirm }
}
