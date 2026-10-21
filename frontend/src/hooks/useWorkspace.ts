import { useEffect } from 'react'
import { contactKey, normalizeCompany } from '../lib/format'
import type { JobSuggestion, OutreachContact, Session } from '../types'
import { useComposer } from './useComposer'
import { useGoogleAccount } from './useGoogleAccount'
import { useHashPage } from './useHashPage'
import { useJobSearch } from './useJobSearch'
import { useOutreach } from './useOutreach'
import { useToast } from './useToast'

export function useWorkspace(session: Session, onSessionChange: () => Promise<void>) {
  const page = useHashPage()
  const toast = useToast()
  const google = useGoogleAccount(session)
  const outreach = useOutreach(toast)
  const jobs = useJobSearch(session, toast, outreach, onSessionChange)
  const composer = useComposer(session, toast, google, outreach)

  const selectedSuggestion = page === 'vagas'
    ? jobs.visibleSuggestions.find((suggestion) => suggestion.url === jobs.selectedJobUrl) || null
    : null
  const selectedContact = (
    (outreach.selectedKey && outreach.contacts.find((contact) => contactKey(contact) === outreach.selectedKey))
    || (selectedSuggestion && outreach.contacts.find((contact) => normalizeCompany(contact.name_company) === normalizeCompany(selectedSuggestion.company)))
    || null
  )

  const { selectedKey, setSelectedKey, markJobSeen } = outreach
  const { selectedJobUrl, setSelectedJobUrl } = jobs

  useEffect(() => {
    if (!selectedKey && !selectedJobUrl) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSelectedKey(null)
        setSelectedJobUrl(null)
      }
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [selectedKey, selectedJobUrl, setSelectedKey, setSelectedJobUrl])

  useEffect(() => {
    if (!selectedContact?.id_jobPosting || selectedContact.job_seen_at) return
    void markJobSeen(selectedContact.id_jobPosting)
  }, [selectedContact?.id_jobPosting, selectedContact?.job_seen_at, markJobSeen])

  function closePanel() {
    setSelectedKey(null)
    setSelectedJobUrl(null)
  }

  async function saveAndOpen(suggestion: JobSuggestion) {
    jobs.setSavingSuggestion(suggestion.url)
    try {
      const contact = await jobs.persistSuggestion(suggestion)
      if (contact) {
        jobs.setSelectedJobUrl(suggestion.url)
        outreach.setSelectedKey(contactKey(contact))
      }
      return contact
    } finally {
      jobs.setSavingSuggestion(null)
    }
  }

  async function saveJob(suggestion: JobSuggestion) {
    const contact = await saveAndOpen(suggestion)
    if (!contact) return
    toast.showToast('success', contact.email
      ? `${suggestion.company} guardada em Contactos.`
      : `${suggestion.company} guardada em Contactos. Vamos procurar o email no site da empresa.`)
  }

  async function applyToJob(suggestion: JobSuggestion) {
    const listed = jobs.listedContact(suggestion.company)
    if (listed && (listed.outreach_status === 'sent' || listed.outreach_status === 'replied' || listed.outreach_status === 'rejected')) {
      return
    }
    if (!session.cv) {
      toast.showToast('error', 'Analisa o teu CV primeiro para a IA redigir a candidatura.')
      return
    }
    const contact = await saveAndOpen(suggestion)
    if (!contact) return
    if (!contact.email) toast.showToast('warning', 'Ainda não há email de carreiras. Cola-o no painel para enviar.')
    if (composer.contactDraft?.key !== contactKey(contact)) await composer.draftForContact(contact)
  }

  function dismissJob(suggestion: JobSuggestion) {
    jobs.ignoreCompany(suggestion.company)
    if (jobs.selectedJobUrl === suggestion.url) closePanel()
  }

  function removeFromList(contact: OutreachContact) {
    outreach.removeCompany(contact, jobs.ignoreCompany)
  }

  return {
    session,
    page,
    toast,
    google,
    outreach,
    jobs,
    composer,
    selectedSuggestion,
    selectedContact,
    saveJob,
    applyToJob,
    dismissJob,
    closePanel,
    removeFromList,
  }
}

export type Workspace = ReturnType<typeof useWorkspace>
