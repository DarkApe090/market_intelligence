import { useEffect, useRef, useState, type FormEvent } from 'react'
import { request } from '../lib/api'
import { contactKey, emptyForm, normalizeCompany, statusLabels } from '../lib/format'
import type { Company, Contact, ContactForm, MailReply, OutreachContact, OutreachStatus, StatusFilter } from '../types'

type ToastFns = {
  showToast: (kind: 'success' | 'error' | 'warning', message: string) => void
  askConfirm: (message: string, confirmLabel: string, onConfirm: () => void) => void
}

export function useOutreach(toast: ToastFns) {
  const [contacts, setContacts] = useState<OutreachContact[]>([])
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [activeFilter, setActiveFilter] = useState<StatusFilter>('all')
  const [search, setSearch] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [formOpen, setFormOpen] = useState(false)
  const [form, setForm] = useState<ContactForm>(emptyForm)
  const [error, setError] = useState<string | null>(null)
  const [websiteDraft, setWebsiteDraft] = useState<{ idCompany: number, value: string }>({ idCompany: 0, value: '' })
  const [isSearchingEmail, setIsSearchingEmail] = useState(false)
  const [mailReply, setMailReply] = useState<{ key: string, isLoading: boolean, error: string | null, message: MailReply | null } | null>(null)
  const enrichmentTimers = useRef<number[]>([])

  useEffect(() => () => {
    enrichmentTimers.current.forEach((id) => window.clearTimeout(id))
  }, [])

  async function loadContacts(showRefresh = false) {
    if (showRefresh) setIsRefreshing(true)
    else setIsLoading(true)
    setError(null)

    try {
      const data = await request<OutreachContact[]>('/companies/outreach/contacts')
      setContacts(data)
      setSelectedKey((current) => current && data.some((item) => contactKey(item) === current) ? current : null)
      return data
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Não foi possível carregar os contactos.')
      return []
    } finally {
      setIsLoading(false)
      setIsRefreshing(false)
    }
  }

  useEffect(() => {
    let isActive = true

    request<OutreachContact[]>('/companies/outreach/contacts')
      .then((data) => {
        if (!isActive) return
        setContacts(data)
      })
      .catch((requestError: unknown) => {
        if (isActive) {
          setError(requestError instanceof Error ? requestError.message : 'Não foi possível carregar os contactos.')
        }
      })
      .finally(() => {
        if (isActive) setIsLoading(false)
      })

    return () => {
      isActive = false
    }
  }, [])

  function refreshContactsAfterEnrichment(idCompany: number, companyName: string) {
    enrichmentTimers.current.forEach((id) => window.clearTimeout(id))
    enrichmentTimers.current = []
    let settled = false

    ;[6000, 15000, 30000, 60000].forEach((delay, index, delays) => {
      const timer = window.setTimeout(() => {
        if (settled) return
        request<OutreachContact[]>('/companies/outreach/contacts')
          .then((data) => {
            setContacts(data)
            if (settled) return
            const contact = data.find((item) => item.id_company === idCompany)
            if (contact?.email) {
              settled = true
              toast.showToast('success', `Email de ${companyName} encontrado.`)
              return
            }
            if (contact?.outreach_status === 'no_email' || index === delays.length - 1) {
              settled = true
              toast.showToast('warning', `Não encontrámos o email de ${companyName}. Procura no site da empresa e cola-o no painel.`)
            }
          })
          .catch(() => undefined)
      }, delay)
      enrichmentTimers.current.push(timer)
    })
  }

  async function markJobSeen(idJobPosting: number) {
    try {
      const updated = await request<{ seen_at: string | null }>(`/user-jobpostings/${idJobPosting}/seen`, {
        method: 'PATCH',
      })
      setContacts((current) => current.map((item) => item.id_jobPosting === idJobPosting
        ? { ...item, job_seen_at: updated.seen_at }
        : item))
    } catch {
      return
    }
  }

  async function findEmail(contact: OutreachContact, event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const websiteInput = websiteDraft.idCompany === contact.id_company ? websiteDraft.value : ''
    setIsSearchingEmail(true)
    setError(null)

    try {
      const result = await request<{ email?: string }>(`/companies/${contact.id_company}/find-email`, {
        method: 'POST',
        body: JSON.stringify({ website_url: websiteInput.trim() || null }),
      })
      if (result.email) {
        setWebsiteDraft({ idCompany: 0, value: '' })
        await loadContacts(true)
        toast.showToast('success', `Email de ${contact.name_company} guardado.`)
      } else {
        toast.showToast('success', `A procurar o email de ${contact.name_company}…`)
        refreshContactsAfterEnrichment(contact.id_company, contact.name_company)
      }
    } catch (requestError) {
      toast.showToast('error', requestError instanceof Error ? requestError.message : 'Não foi possível iniciar a pesquisa.')
    } finally {
      setIsSearchingEmail(false)
    }
  }

  async function loadReply(contact: OutreachContact) {
    const key = contactKey(contact)
    if (contact.outreach_status !== 'replied' && contact.outreach_status !== 'rejected') {
      setMailReply(null)
      return
    }
    setMailReply({ key, isLoading: true, error: null, message: null })
    try {
      const message = await request<MailReply>(`/companies/${contact.id_company}/contacts/${contact.id_contact}/reply`)
      setMailReply({ key, isLoading: false, error: null, message })
      if (message.outreach_status && message.outreach_status !== contact.outreach_status) {
        setContacts((current) => current.map((item) => contactKey(item) === key
          ? { ...item, outreach_status: message.outreach_status }
          : item))
      }
    } catch (requestError) {
      setMailReply({
        key,
        isLoading: false,
        error: requestError instanceof Error ? requestError.message : 'Não foi possível ler a resposta.',
        message: null,
      })
    }
  }

  async function updateStatus(contact: OutreachContact, outreachStatus: OutreachStatus) {
    setError(null)
    try {
      await request(`/companies/${contact.id_company}/contacts/${contact.id_contact}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ outreach_status: outreachStatus }),
      })
      setContacts((current) => current.map((item) => contactKey(item) === contactKey(contact)
        ? { ...item, outreach_status: outreachStatus }
        : item))
      toast.showToast('success', `Estado atualizado: ${statusLabels[outreachStatus].toLocaleLowerCase('pt-PT')}.`)
    } catch (requestError) {
      toast.showToast('error', requestError instanceof Error ? requestError.message : 'Não foi possível atualizar o estado.')
    }
  }

  function removeCompany(contact: OutreachContact, onRemoved: (name: string) => void) {
    toast.askConfirm(
      `Retirar ${contact.name_company} da lista? Os contactos desta empresa serão apagados.`,
      'Retirar',
      () => { void confirmRemoveCompany(contact, onRemoved) },
    )
  }

  async function confirmRemoveCompany(contact: OutreachContact, onRemoved: (name: string) => void) {
    setError(null)
    try {
      await request(`/companies/${contact.id_company}/outreach`, { method: 'DELETE' })
      onRemoved(normalizeCompany(contact.name_company))
      setContacts((current) => current.filter((item) => item.id_company !== contact.id_company))
      setSelectedKey((current) => (current && current.startsWith(`${contact.id_company}:`) ? null : current))
      toast.showToast('success', `${contact.name_company} foi retirada da lista.`)
    } catch (requestError) {
      toast.showToast('error', requestError instanceof Error ? requestError.message : 'Não foi possível retirar a empresa.')
    }
  }

  async function createContact(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsSaving(true)
    setError(null)

    try {
      const companies = await request<Company[]>('/companies/')
      const existingCompany = companies.find((company) =>
        company.name_company.trim().toLocaleLowerCase('pt-PT') === form.name_company.trim().toLocaleLowerCase('pt-PT'))
      const company = existingCompany || await request<Company>('/companies/', {
        method: 'POST',
        body: JSON.stringify({ name_company: form.name_company.trim() }),
      })
      const contact = await request<Contact>('/contacts/', {
        method: 'POST',
        body: JSON.stringify({
          name_contact: form.name_contact.trim() || null,
          role_contact: form.role_contact.trim() || null,
          contact_type: form.contact_type,
          email: form.email.trim() || null,
          source_url: form.source_url.trim() || null,
        }),
      })
      await request(`/companies/${company.id_company}/contacts/${contact.id_contact}`, {
        method: 'POST',
      })

      setForm(emptyForm)
      setFormOpen(false)
      await loadContacts(true)
      if (form.email.trim()) {
        toast.showToast('success', 'Contacto adicionado à lista.')
      } else {
        toast.showToast('success', `A procurar o email de ${company.name_company}…`)
        refreshContactsAfterEnrichment(company.id_company, company.name_company)
      }
    } catch (requestError) {
      toast.showToast('error', requestError instanceof Error ? requestError.message : 'Não foi possível guardar o contacto.')
    } finally {
      setIsSaving(false)
    }
  }

  const counts = {
    all: contacts.length,
    to_contact: contacts.filter((contact) => contact.outreach_status === 'to_contact').length,
    sent: contacts.filter((contact) => contact.outreach_status === 'sent').length,
    replied: contacts.filter((contact) => contact.outreach_status === 'replied').length,
    rejected: contacts.filter((contact) => contact.outreach_status === 'rejected').length,
    no_email: contacts.filter((contact) => contact.outreach_status === 'no_email').length,
  }

  const visibleContacts = contacts.filter((contact) => {
    const matchesStatus = activeFilter === 'all' || contact.outreach_status === activeFilter
    const searchable = [
      contact.name_company,
      contact.name_contact,
      contact.role_contact,
      contact.email,
      contact.contact_type,
    ].join(' ').toLocaleLowerCase('pt-PT')
    return matchesStatus && searchable.includes(search.trim().toLocaleLowerCase('pt-PT'))
  })

  return {
    contacts,
    setContacts,
    selectedKey,
    setSelectedKey,
    activeFilter,
    setActiveFilter,
    search,
    setSearch,
    isLoading,
    isRefreshing,
    isSaving,
    formOpen,
    setFormOpen,
    form,
    setForm,
    error,
    setError,
    websiteDraft,
    setWebsiteDraft,
    isSearchingEmail,
    mailReply,
    counts,
    visibleContacts,
    loadContacts,
    loadReply,
    markJobSeen,
    findEmail,
    updateStatus,
    removeCompany,
    createContact,
    refreshContactsAfterEnrichment,
  }
}
