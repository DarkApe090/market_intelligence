import { useState } from 'react'
import { request } from '../lib/api'
import { contactKey } from '../lib/format'
import { loadDraftLanguage, saveDraftLanguage } from '../lib/storage'
import type { ContactDraft, DraftLanguage, DraftResult, OutreachContact, Session } from '../types'

type ToastFns = {
  showToast: (kind: 'success' | 'error' | 'warning', message: string) => void
  askConfirm: (message: string, confirmLabel: string, onConfirm: () => void) => void
}

type GoogleSlice = {
  googleStatus: { connected: boolean } | null
  setGooglePanelOpen: (open: boolean | ((current: boolean) => boolean)) => void
  connectGoogle: () => void
}

type OutreachSlice = {
  setContacts: (update: OutreachContact[] | ((current: OutreachContact[]) => OutreachContact[])) => void
}

export function useComposer(session: Session, toast: ToastFns, google: GoogleSlice, outreach: OutreachSlice) {
  const profile = session.cv ? { name: session.cv.candidate_name, skills: session.cv.skills } : null
  const [draftLanguage, setDraftLanguage] = useState<DraftLanguage>(loadDraftLanguage)
  const [contactDraft, setContactDraft] = useState<ContactDraft | null>(null)
  const [isSending, setIsSending] = useState(false)

  function changeDraftLanguage(language: DraftLanguage) {
    setDraftLanguage(language)
    saveDraftLanguage(language)
  }

  async function draftForContact(contact: OutreachContact) {
    if (!profile || contact.outreach_status === 'rejected') return
    const key = contactKey(contact)
    setContactDraft({ key, isLoading: true, subject: '', body: '' })
    try {
      const result = await request<DraftResult>('/career-profile/suggestions/draft', {
        method: 'POST',
        body: JSON.stringify({
          company: contact.name_company,
          title: contact.job_title || '',
          cv_skills: profile.skills,
          language: draftLanguage,
          candidate_name: profile.name,
          force: true,
        }),
      })
      setContactDraft({
        key,
        isLoading: false,
        fitScore: result.fit_score,
        fitReason: result.fit_reason,
        skipped: result.skipped,
        subject: result.subject ?? '',
        body: result.body ?? '',
      })
    } catch (requestError) {
      setContactDraft(null)
      toast.showToast('error', requestError instanceof Error ? requestError.message : 'Não foi possível gerar o email.')
    }
  }

  function sendApplication(contact: OutreachContact) {
    const draft = contactDraft
    if (draft?.key !== contactKey(contact) || draft.isLoading) return
    if (!google.googleStatus?.connected) {
      google.setGooglePanelOpen(true)
      toast.showToast('warning', 'Liga o Gmail no topo para enviar a candidatura.')
      return
    }

    const attachment = session.cv ? ` com o CV anexado (${session.cv.filename})` : ' sem CV anexado'
    toast.askConfirm(
      `Enviar este email para ${contact.email}${attachment}?`,
      'Enviar',
      () => { void submitApplication(contact, draft.subject, draft.body) },
    )
  }

  async function submitApplication(contact: OutreachContact, subject: string, body: string) {
    setIsSending(true)
    try {
      const result = await request<{ to: string }>(
        `/companies/${contact.id_company}/contacts/${contact.id_contact}/apply`,
        { method: 'POST', body: JSON.stringify({ subject, body }) },
      )
      const key = contactKey(contact)
      outreach.setContacts((current) => current.map((item) => contactKey(item) === key
        ? { ...item, outreach_status: 'sent', sent_at: new Date().toISOString() }
        : item))
      toast.showToast('success', `Candidatura enviada para ${result.to}.`)
    } catch (requestError) {
      toast.showToast('error', requestError instanceof Error ? requestError.message : 'Não foi possível enviar a candidatura.')
    } finally {
      setIsSending(false)
    }
  }

  async function copyEmail(email: string) {
    try {
      await navigator.clipboard.writeText(email)
      toast.showToast('success', 'Email copiado.')
    } catch {
      toast.showToast('error', 'Não foi possível copiar o email neste browser.')
    }
  }

  return {
    profile,
    draftLanguage,
    changeDraftLanguage,
    contactDraft,
    setContactDraft,
    isSending,
    draftForContact,
    sendApplication,
    copyEmail,
  }
}
