import { Check, CircleAlert, X } from 'lucide-react'
import type { AppToast } from '../types'

export function Toast({ toast, onClose }: { toast: AppToast, onClose: () => void }) {
  return (
    <div className={`toast toast-${toast.kind}`} role={toast.kind === 'confirm' ? 'alertdialog' : 'status'}>
      {toast.kind === 'success' ? <Check size={16} /> : <CircleAlert size={16} />}
      <span>{toast.message}</span>
      {toast.kind === 'confirm' ? (
        <div className="toast-actions">
          <button className="button button-outline" type="button" onClick={onClose}>Cancelar</button>
          <button
            className="button button-primary"
            type="button"
            onClick={() => {
              const action = toast.onConfirm
              onClose()
              action?.()
            }}
          >
            {toast.confirmLabel || 'Confirmar'}
          </button>
        </div>
      ) : (
        <button className="icon-button" type="button" aria-label="Fechar aviso" onClick={onClose}><X size={16} /></button>
      )}
    </div>
  )
}
