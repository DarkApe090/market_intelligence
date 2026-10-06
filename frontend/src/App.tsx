import { useEffect, useState, type FormEvent } from 'react'
import {
  ArrowUpRight,
  Building2,
  Check,
  ChevronDown,
  CircleAlert,
  ClipboardList,
  Clock3,
  Copy,
  ExternalLink,
  FileText,
  LogOut,
  Mail,
  MailX,
  MapPin,
  Plus,
  RefreshCw,
  Reply,
  Search,
  Send,
  Sparkles,
  Trash2,
  Upload,
  Users,
  X,
} from 'lucide-react'
import './dashboard.css'

const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

type OutreachStatus = 'to_contact' | 'sent' | 'replied' | 'no_email'
type StatusFilter = 'all' | OutreachStatus

interface OutreachContact {
  id_company: number
  name_company: string
  job_title: string | null
  id_contact: number
  name_contact: string | null
  role_contact: string | null
  contact_type: string | null
  cellphone: string | null
  telephone: string | null
  email: string | null
  source_url: string | null
  website_url: string | null
  outreach_status: OutreachStatus
}

interface Company {
  id_company: number
  name_company: string
}

interface Contact {
  id_contact: number
}

interface CvEvidence {
  text: string
  section: string
}

interface CvArea {
  key: string
  name: string
  search_query: string
  matched_skills: string[]
  confidence: 'high' | 'medium' | 'low'
  evidence: CvEvidence[]
}

interface JobSuggestion {
  company: string
  title: string
  location: string
  email: string | null
  location_priority: number
  url: string
  area: string
  source: string
  matched_skills: string[]
}

interface DraftResult {
  fit_score: number
  fit_reason: string
  subject: string | null
  body: string | null
  skipped: boolean
}

interface DraftState {
  isLoading: boolean
  result?: DraftResult
}

type DraftLanguage = 'en' | 'pt'

interface CandidateProfile {
  name: string | null
  skills: string[]
}

interface ContactDraft {
  key: string
  isLoading: boolean
  fitScore?: number
  fitReason?: string
  skipped?: boolean
  subject: string
  body: string
}

const LANGUAGE_STORAGE_KEY = 'ponto.draftLanguage'

function ignoredStorageKey(email: string): string {
  return `ponto.ignoredCompanies.${email}`
}

function normalizeCompany(name: string): string {
  return name.trim().toLocaleLowerCase('pt-PT')
}

function loadIgnored(email: string): string[] {
  try {
    const stored = window.localStorage.getItem(ignoredStorageKey(email))
    return stored ? JSON.parse(stored) as string[] : []
  } catch {
    return []
  }
}

function loadDraftLanguage(): DraftLanguage {
  return window.localStorage.getItem(LANGUAGE_STORAGE_KEY) === 'en' ? 'en' : 'pt'
}

interface GoogleStatus {
  configured: boolean
  connected: boolean
  email: string | null
}

interface StoredCv {
  filename: string
  candidate_name: string | null
  skills: string[]
  uploaded_at: string | null
}

interface Session {
  user: { email: string, name: string | null, picture: string | null }
  cv: StoredCv | null
  google: GoogleStatus
}

interface CvAnalysis {
  candidate_name: string | null
  areas: CvArea[]
  suggestions: JobSuggestion[]
  search_errors: string[]
  excluded_location_count: number
  cv_saved: boolean
  location_priority_order: string[]
}

const locationPriorityLabels = [
  'Localização exata',
  'Também aceita a localização escolhida',
  'Região compatível',
  'Remoto/global',
  'Localização por confirmar',
]

interface ContactForm {
  name_company: string
  name_contact: string
  role_contact: string
  contact_type: string
  email: string
  source_url: string
}

const statusLabels: Record<OutreachStatus, string> = {
  to_contact: 'Por contactar',
  sent: 'Enviado',
  replied: 'Respondeu',
  no_email: 'Sem email',
}

const contactTypeLabels: Record<string, string> = {
  careers: 'Carreiras',
  recruitment: 'Recrutamento',
  general: 'Geral',
}

const emptyForm: ContactForm = {
  name_company: '',
  name_contact: '',
  role_contact: '',
  contact_type: 'careers',
  email: '',
  source_url: '',
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
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
    throw new Error(detail?.detail || `Pedido falhou (${response.status})`)
  }

  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

function contactKey(contact: OutreachContact) {
  return `${contact.id_company}:${contact.id_contact}`
}

function Dashboard({ session, onSessionChange, onLogout }: { session: Session, onSessionChange: () => Promise<void>, onLogout: () => void }) {
  const [contacts, setContacts] = useState<OutreachContact[]>([])
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [activeFilter, setActiveFilter] = useState<StatusFilter>('all')
  const [search, setSearch] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isAnalyzingCv, setIsAnalyzingCv] = useState(false)
  const [savingSuggestion, setSavingSuggestion] = useState<string | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [cvFile, setCvFile] = useState<File | null>(null)
  const [cvLocation, setCvLocation] = useState('Portugal')
  const [cvAnalysis, setCvAnalysis] = useState<CvAnalysis | null>(null)
  const [drafts, setDrafts] = useState<Record<string, DraftState>>({})
  const profile: CandidateProfile | null = session.cv ? { name: session.cv.candidate_name, skills: session.cv.skills } : null
  const [ignoredCompanies, setIgnoredCompanies] = useState<string[]>(() => loadIgnored(session.user.email))
  const [draftLanguage, setDraftLanguage] = useState<DraftLanguage>(loadDraftLanguage)
  const [contactDraft, setContactDraft] = useState<ContactDraft | null>(null)
  const [googleStatus, setGoogleStatus] = useState<GoogleStatus | null>(session.google)
  const [googlePanelOpen, setGooglePanelOpen] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const [cvError, setCvError] = useState<string | null>(null)
  const [websiteDraft, setWebsiteDraft] = useState<{ idCompany: number, value: string }>({ idCompany: 0, value: '' })
  const [isSearchingEmail, setIsSearchingEmail] = useState(false)
  const [form, setForm] = useState<ContactForm>(emptyForm)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(() => {
    const result = new URLSearchParams(window.location.search).get('google')
    if (!result) return null
    return result === 'connected' ? 'Conta Google ligada.' : 'Não foi possível ligar a conta Google.'
  })
  const [googleReturn] = useState(() => new URLSearchParams(window.location.search).has('google'))

  async function loadContacts(showRefresh = false) {
    if (showRefresh) setIsRefreshing(true)
    else setIsLoading(true)
    setError(null)

    try {
      const data = await request<OutreachContact[]>('/companies/outreach/contacts')
      setContacts(data)
      setSelectedKey((current) => current && data.some((item) => contactKey(item) === current) ? current : null)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Não foi possível carregar os contactos.')
    } finally {
      setIsLoading(false)
      setIsRefreshing(false)
    }
  }

  useEffect(() => {
    if (!selectedKey) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setSelectedKey(null)
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [selectedKey])

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

  const counts = {
    all: contacts.length,
    to_contact: contacts.filter((contact) => contact.outreach_status === 'to_contact').length,
    sent: contacts.filter((contact) => contact.outreach_status === 'sent').length,
    replied: contacts.filter((contact) => contact.outreach_status === 'replied').length,
    no_email: contacts.filter((contact) => contact.outreach_status === 'no_email').length,
    withEmail: contacts.filter((contact) => Boolean(contact.email)).length,
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

  const selectedContact = contacts.find((contact) => contactKey(contact) === selectedKey) || null
  const visibleSuggestions = cvAnalysis ? cvAnalysis.suggestions.filter((suggestion) => !ignoredCompanies.includes(normalizeCompany(suggestion.company))) : []
  const hiddenSuggestionCount = cvAnalysis ? cvAnalysis.suggestions.length - visibleSuggestions.length : 0

  function updateIgnored(next: string[]) {
    setIgnoredCompanies(next)
    window.localStorage.setItem(ignoredStorageKey(session.user.email), JSON.stringify(next))
  }

  const inListNames = new Set(contacts.map((contact) => contact.name_company.trim().toLocaleLowerCase('pt-PT')))

  async function findEmail(contact: OutreachContact, event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const websiteInput = websiteDraft.idCompany === contact.id_company ? websiteDraft.value : ''
    setIsSearchingEmail(true)
    setError(null)

    try {
      await request(`/companies/${contact.id_company}/find-email`, {
        method: 'POST',
        body: JSON.stringify({ website_url: websiteInput.trim() || null }),
      })
      setNotice(`A procurar o email de ${contact.name_company}…`)
      refreshContactsAfterEnrichment()
      window.setTimeout(() => setNotice(null), 3200)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Não foi possível iniciar a pesquisa.')
    } finally {
      setIsSearchingEmail(false)
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
      setNotice(`Estado atualizado: ${statusLabels[outreachStatus].toLocaleLowerCase('pt-PT')}.`)
      window.setTimeout(() => setNotice(null), 2600)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Não foi possível atualizar o estado.')
    }
  }

  async function removeCompany(contact: OutreachContact) {
    if (!window.confirm(`Retirar "${contact.name_company}" da lista? Os contactos desta empresa serão apagados.`)) return
    setError(null)
    try {
      await request(`/companies/${contact.id_company}/outreach`, { method: 'DELETE' })
      const ignoredName = normalizeCompany(contact.name_company)
      if (!ignoredCompanies.includes(ignoredName)) updateIgnored([...ignoredCompanies, ignoredName])
      setContacts((current) => current.filter((item) => item.id_company !== contact.id_company))
      setSelectedKey((current) => (current && current.startsWith(`${contact.id_company}:`) ? null : current))
      setNotice(`${contact.name_company} foi retirada da lista.`)
      window.setTimeout(() => setNotice(null), 2600)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Não foi possível retirar a empresa.')
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
      setNotice('Contacto adicionado à lista.')
      window.setTimeout(() => setNotice(null), 2600)
      await loadContacts(true)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Não foi possível guardar o contacto.')
    } finally {
      setIsSaving(false)
    }
  }

  async function analyzeCv(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!cvFile) return

    const formData = new FormData()
    formData.append('file', cvFile)
    formData.append('location', cvLocation.trim() || 'Portugal')
    await runAnalysis(() => fetch(`${API_URL}/career-profile/analyze`, {
      method: 'POST',
      credentials: 'include',
      body: formData,
    }))
    setCvFile(null)
  }

  async function analyzeStoredCv() {
    await runAnalysis(() => fetch(`${API_URL}/career-profile/analyze-stored`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ location: cvLocation.trim() || 'Portugal' }),
    }))
  }

  async function runAnalysis(send: () => Promise<Response>) {
    setIsAnalyzingCv(true)
    setCvError(null)
    setCvAnalysis(null)

    try {
      const response = await send()

      if (!response.ok) {
        const detail = await response.json().catch(() => null)
        throw new Error(detail?.detail || `Análise falhou (${response.status})`)
      }

      setCvAnalysis(await response.json() as CvAnalysis)
      await onSessionChange()
    } catch (requestError) {
      setCvError(requestError instanceof Error ? requestError.message : 'Não foi possível analisar o CV.')
    } finally {
      setIsAnalyzingCv(false)
    }
  }

  function refreshContactsAfterEnrichment() {
    // A pesquisa do email corre em segundo plano; volta a ler a lista sem mostrar loading.
    for (const delay of [6000, 15000, 30000]) {
      window.setTimeout(() => {
        request<OutreachContact[]>('/companies/outreach/contacts')
          .then(setContacts)
          .catch(() => undefined)
      }, delay)
    }
  }

  async function saveSuggestion(suggestion: JobSuggestion) {
    setSavingSuggestion(suggestion.url)
    setError(null)

    try {
      const saved = await request<{ already_in_outreach: boolean }>('/career-profile/suggestions/save', {
        method: 'POST',
        body: JSON.stringify({
          company: suggestion.company,
          title: suggestion.title,
          url: suggestion.url,
          source: suggestion.source,
        }),
      })

      setNotice(saved.already_in_outreach
        ? `${suggestion.company} já estava na lista de prospeção; a vaga foi guardada.`
        : `${suggestion.company} adicionada à lista para procurar o contacto de carreiras.`)
      await loadContacts(true)
      refreshContactsAfterEnrichment()
      window.setTimeout(() => setNotice(null), 3200)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Não foi possível guardar a empresa.')
    } finally {
      setSavingSuggestion(null)
    }
  }

  async function draftApplication(suggestion: JobSuggestion) {
    if (!cvAnalysis) return
    setError(null)
    setDrafts((current) => ({ ...current, [suggestion.url]: { isLoading: true } }))
    try {
      const result = await request<DraftResult>('/career-profile/suggestions/draft', {
        method: 'POST',
        body: JSON.stringify({
          company: suggestion.company,
          title: suggestion.title,
          area: suggestion.area,
          matched_skills: suggestion.matched_skills,
          cv_skills: profile?.skills ?? [],
          language: draftLanguage,
          candidate_name: profile?.name ?? null,
        }),
      })
      setDrafts((current) => ({ ...current, [suggestion.url]: { isLoading: false, result } }))
    } catch (requestError) {
      setDrafts((current) => Object.fromEntries(Object.entries(current).filter(([url]) => url !== suggestion.url)))
      setError(requestError instanceof Error ? requestError.message : 'Não foi possível gerar o rascunho.')
    }
  }

  function changeDraftLanguage(language: DraftLanguage) {
    setDraftLanguage(language)
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language)
  }

  async function draftForContact(contact: OutreachContact) {
    if (!profile) return
    const key = contactKey(contact)
    setError(null)
    setContactDraft({ key, isLoading: true, subject: '', body: '' })
    try {
      const result = await request<DraftResult>('/career-profile/suggestions/draft', {
        method: 'POST',
        body: JSON.stringify({
          company: contact.name_company,
          title: contact.job_title || 'Software Engineer',
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
      setError(requestError instanceof Error ? requestError.message : 'Não foi possível gerar o email.')
    }
  }

  useEffect(() => {
    if (googleReturn) {
      window.history.replaceState({}, '', window.location.pathname)
      const timer = window.setTimeout(() => setNotice(null), 3500)
      return () => window.clearTimeout(timer)
    }
  }, [googleReturn])

  async function connectGoogle() {
    setError(null)
    try {
      const { url } = await request<{ url: string }>('/google/auth-url')
      window.location.href = url
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Não foi possível ligar a Google.')
    }
  }

  async function disconnectGoogle() {
    setGoogleStatus(await request<GoogleStatus>('/google/disconnect', { method: 'POST' }))
  }

  async function removeStoredCv() {
    if (!window.confirm('Remover o CV guardado? Os emails deixam de levar o CV anexado.')) return
    try {
      await request('/career-profile/cv', { method: 'DELETE' })
      await onSessionChange()
      setCvAnalysis(null)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Não foi possível remover o CV.')
    }
  }

  async function sendWithGmail(contact: OutreachContact, draft: ContactDraft) {
    if (!contact.email) return
    const attachment = session.cv ? ` com o CV anexado (${session.cv.filename})` : ' sem CV anexado'
    if (!window.confirm(`Enviar este email para ${contact.email}${attachment}?`)) return

    setIsSending(true)
    setError(null)
    try {
      await request('/google/send', {
        method: 'POST',
        body: JSON.stringify({ to: contact.email, subject: draft.subject, body: draft.body, attach_cv: true }),
      })
      await updateStatus(contact, 'sent')
      setNotice(`Email enviado para ${contact.email}.`)
      window.setTimeout(() => setNotice(null), 4000)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Não foi possível enviar o email.')
    } finally {
      setIsSending(false)
    }
  }

  function openInMailClient(contact: OutreachContact, draft: ContactDraft) {
    if (!contact.email) return
    const link = `mailto:${contact.email}?subject=${encodeURIComponent(draft.subject)}&body=${encodeURIComponent(draft.body)}`
    window.location.href = link
    setNotice('Email aberto na tua aplicação de email. Anexa o CV e envia; depois marca como "Enviado".')
    window.setTimeout(() => setNotice(null), 5000)
  }

  async function copyDraft(draft: DraftResult) {
    try {
      await navigator.clipboard.writeText(`Assunto: ${draft.subject ?? ''}\n\n${draft.body ?? ''}`)
      setNotice('Rascunho copiado.')
      window.setTimeout(() => setNotice(null), 2200)
    } catch {
      setError('Não foi possível copiar o rascunho neste browser.')
    }
  }

  async function copyEmail(email: string) {
    try {
      await navigator.clipboard.writeText(email)
      setNotice('Email copiado.')
      window.setTimeout(() => setNotice(null), 2200)
    } catch {
      setError('Não foi possível copiar o email neste browser.')
    }
  }

  return (
    <div className="app-shell">
      <aside className="rail" aria-label="Navegação principal">
        <a className="brand-mark" href="#top" aria-label="Ponto de partida">
          <span>p</span>
        </a>
        <button className="rail-link is-active" type="button" title="Prospeção" aria-label="Prospeção">
          <ClipboardList size={19} strokeWidth={1.8} />
        </button>
        <div className="rail-spacer" />
        <span className="rail-avatar" aria-label={session.user.email} title={session.user.email}>{(session.user.name || session.user.email).charAt(0).toUpperCase()}</span>
      </aside>

      <main className="workspace" id="top">
        <header className="topbar">
          <div className="breadcrumb"><span>Área de trabalho</span><span className="breadcrumb-separator">/</span><strong>Prospeção</strong></div>
          <div className="topbar-actions">
            <button className={`google-chip ${googleStatus?.connected ? 'is-connected' : ''}`} type="button" aria-expanded={googlePanelOpen} onClick={() => setGooglePanelOpen((open) => !open)}>
              <Mail size={14} />{googleStatus?.connected ? (googleStatus.email || 'Gmail ligado') : 'Ligar Gmail'}
            </button>
            {googlePanelOpen && (
              <div className="google-panel" role="dialog" aria-label="Conta Google">
                <div className="google-panel-heading"><strong>Envio por Gmail</strong><button className="icon-button" type="button" aria-label="Fechar" onClick={() => setGooglePanelOpen(false)}><X size={15} /></button></div>
                {!googleStatus ? <p>A API não respondeu.</p> : !googleStatus.configured ? (
                  <p>Define <code>GOOGLE_CLIENT_ID</code> e <code>GOOGLE_CLIENT_SECRET</code> em <code>backend/.env</code> (ver README) e reinicia o backend.</p>
                ) : googleStatus.connected ? (
                  <>
                    <p>Ligado como <strong>{googleStatus.email || 'conta Google'}</strong>. Os emails só são enviados depois de confirmares.</p>
                    <button className="button button-outline" type="button" onClick={() => void disconnectGoogle()}>Desligar conta</button>
                  </>
                ) : (
                  <>
                    <p>Liga a tua conta para enviar candidaturas daqui. A app só tem permissão para enviar emails.</p>
                    <button className="button button-primary" type="button" onClick={() => void connectGoogle()}>Ligar conta Google</button>
                  </>
                )}
              </div>
            )}
          </div>
          <div className="topbar-meta"><span className={`sync-dot ${error && !isLoading ? 'is-offline' : ''}`} />{isLoading ? 'A ligar à API' : error ? 'API indisponível' : 'API ligada'}<button className="link-button logout-button" type="button" onClick={onLogout}><LogOut size={13} />Sair</button></div>
        </header>

        <div className="page-content">
          <section className="page-heading">
            <div>
              <p className="eyebrow">CANDIDATURAS · FASE MANUAL</p>
              <h1>Lista de prospeção</h1>
              <p className="page-subtitle">Empresas e contactos para preparar os próximos envios.</p>
            </div>
            <button className="button button-primary" type="button" onClick={() => setFormOpen(true)}>
              <Plus size={17} /> Novo contacto
            </button>
          </section>

          <section className="cv-search-section" aria-labelledby="cv-search-title">
            <div className="cv-search-heading">
              <div>
                <p className="eyebrow">PESQUISA PERSONALIZADA</p>
                <h2 id="cv-search-title">Descobrir empresas para o teu CV</h2>
                <p>As áreas e competências vêm do CV; a localização define a prioridade das vagas.</p>
              </div>
            </div>
            <div className="cv-steps" aria-label="Etapas da pesquisa">
              <span className="is-current"><b>01</b> Currículo</span>
              <span className={cvAnalysis ? 'is-complete' : ''}><b>02</b> Perfil detetado</span>
              <span className={cvAnalysis ? 'is-current' : ''}><b>03</b> Empresas</span>
            </div>
            {session.cv && (
              <div className="stored-cv">
                <FileText size={16} />
                <span className="stored-cv-copy"><strong>{session.cv.filename}</strong><small>CV guardado{session.cv.candidate_name ? ` · ${session.cv.candidate_name}` : ''}</small></span>
                <button className="button button-primary" type="button" disabled={isAnalyzingCv} onClick={() => void analyzeStoredCv()}>
                  {isAnalyzingCv ? <RefreshCw className="spin" size={16} /> : <Search size={16} />}
                  {isAnalyzingCv ? 'A pesquisar...' : 'Procurar novas vagas'}
                </button>
                <button className="link-button" type="button" onClick={() => void removeStoredCv()}>Remover CV</button>
              </div>
            )}
            <form className="cv-upload-form" onSubmit={(event) => void analyzeCv(event)}>
              <label className={`cv-file-picker ${cvFile ? 'has-file' : ''}`}>
                <span className="cv-upload-icon"><Upload size={17} /></span>
                <span className="cv-file-copy"><strong>{cvFile ? cvFile.name : 'Selecionar currículo'}</strong><small>{cvFile ? `${(cvFile.size / (1024 * 1024)).toFixed(2)} MB · pronto para análise` : 'PDF ou DOCX · máximo 5 MB'}</small></span>
                <span className="cv-file-action">Procurar ficheiro</span>
                <input
                  type="file"
                  accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  onChange={(event) => {
                    setCvFile(event.target.files?.[0] || null)
                    setCvAnalysis(null)
                    setCvError(null)
                  }}
                  aria-label="Selecionar currículo PDF ou DOCX"
                />
              </label>
              <div className="cv-search-controls">
                <label className="cv-location-field"><MapPin size={16} /><span><small>LOCALIZAÇÃO DA VAGA</small><input value={cvLocation} onChange={(event) => setCvLocation(event.target.value)} aria-label="Localização da vaga" placeholder="Ex.: Portugal" /></span></label>
                <button className="button button-primary cv-analyze-button" type="submit" disabled={!cvFile || isAnalyzingCv}>
                  {isAnalyzingCv ? <RefreshCw className="spin" size={16} /> : <Search size={16} />}
                  {isAnalyzingCv ? 'A analisar CV...' : 'Analisar e procurar empresas'}
                </button>
              </div>
            </form>
            <div className="cv-footnote"><FileText size={13} /><span>O CV fica guardado na tua conta para anexar aos emails e repetir a pesquisa.</span><span className="cv-footnote-divider" /><span>Vagas ordenadas pela localização escolhida</span></div>
            {cvError && <div className="notice notice-error cv-error" role="alert"><span>{cvError}</span><button className="icon-button" type="button" aria-label="Fechar aviso" onClick={() => setCvError(null)}><X size={16} /></button></div>}

            {cvAnalysis && (
              <div className="cv-results" aria-live="polite">
                <div className="cv-areas-block">
                  <div className="results-heading-row"><h3>Perfil detetado</h3><span>{cvAnalysis.areas.length} {cvAnalysis.areas.length === 1 ? 'área' : 'áreas'}</span></div>
                  {cvAnalysis.areas.length ? (
                    <div className="detected-areas">
                      {cvAnalysis.areas.map((area) => (
                        <article className="detected-area" key={area.key}>
                          <div className="detected-area-title"><strong>{area.name}</strong><span className={`confidence confidence-${area.confidence}`}>{area.confidence === 'high' ? 'Forte' : area.confidence === 'medium' ? 'Média' : 'Inicial'}</span></div>
                          <p>{area.matched_skills.length ? area.matched_skills.join(' · ') : 'Cargo ou formação identificados no CV'}</p>
                          <details><summary>Ver evidências</summary><ul>{area.evidence.map((item, index) => <li key={`${area.key}-${index}`}><span>{item.section === 'experiencia' ? 'Experiência' : item.section === 'formacao' ? 'Formação' : item.section === 'competencias' ? 'Competências' : 'Perfil'}</span>{item.text}</li>)}</ul></details>
                        </article>
                      ))}
                    </div>
                  ) : <p className="cv-no-areas">Não foram identificadas áreas com confiança suficiente. Revê o texto do CV ou tenta um PDF/DOCX com texto selecionável.</p>}
                </div>

                <div className="suggestions-block">
                  <div className="results-heading-row"><h3>Empresas com ofertas relacionadas</h3><span>{visibleSuggestions.length} · prioridade por localização</span><div className="language-toggle" role="group" aria-label="Idioma do rascunho"><button type="button" className={draftLanguage === 'pt' ? 'is-active' : ''} aria-pressed={draftLanguage === 'pt'} onClick={() => changeDraftLanguage('pt')}>PT</button><button type="button" className={draftLanguage === 'en' ? 'is-active' : ''} aria-pressed={draftLanguage === 'en'} onClick={() => changeDraftLanguage('en')}>EN</button></div></div>
                  {hiddenSuggestionCount > 0 && <p className="search-warning hidden-note">{hiddenSuggestionCount} {hiddenSuggestionCount === 1 ? 'empresa ocultada' : 'empresas ocultadas'} por as teres retirado da lista. <button type="button" className="link-button" onClick={() => updateIgnored([])}>Mostrar de novo</button></p>}
                  {cvAnalysis.search_errors.length > 0 && <p className="search-warning">A pesquisa de vagas falhou para: {cvAnalysis.search_errors.join(', ')}.</p>}
                  {visibleSuggestions.length ? (
                    <div className="job-suggestions">
                      {visibleSuggestions.map((suggestion) => (
                        <article className="job-suggestion" key={`${suggestion.company}-${suggestion.url}`}>
                          <div className="suggestion-company-mark">{suggestion.company.slice(0, 1).toLocaleUpperCase('pt-PT')}</div>
                          <div className="suggestion-copy"><strong>{suggestion.company}</strong><span>{suggestion.title}</span><small>{suggestion.area} · {suggestion.source}</small><span className="suggestion-location"><MapPin size={11} />{cvAnalysis.location_priority_order[suggestion.location_priority] || locationPriorityLabels[suggestion.location_priority]} · {suggestion.location}</span>{suggestion.email ? <a className="suggestion-email" href={`mailto:${suggestion.email}`}><Mail size={12} />{suggestion.email}</a> : <span className="suggestion-no-email"><MailX size={12} />Sem email</span>}</div>
                          <a className="suggestion-open" href={suggestion.url} target="_blank" rel="noreferrer" aria-label={`Ver oferta de ${suggestion.company} na ${suggestion.source}`} title={`Ver na ${suggestion.source}`}><ExternalLink size={14} /><span>Ver na {suggestion.source}</span></a>
                          {inListNames.has(suggestion.company.trim().toLocaleLowerCase('pt-PT')) ? (
                            <button className="button button-outline suggestion-save" type="button" disabled>
                              <Check size={14} />
                              <span>Na lista</span>
                            </button>
                          ) : (
                          <button className="button button-outline suggestion-save" type="button" disabled={savingSuggestion === suggestion.url} onClick={() => void saveSuggestion(suggestion)}>
                            {savingSuggestion === suggestion.url ? <RefreshCw className="spin" size={14} /> : <Plus size={14} />}
                            <span>Guardar empresa</span>
                          </button>
                          )}
                          <button className="button button-outline suggestion-save" type="button" disabled={drafts[suggestion.url]?.isLoading} onClick={() => void draftApplication(suggestion)} title="Avaliar a vaga e gerar um rascunho de email com IA">
                            {drafts[suggestion.url]?.isLoading ? <RefreshCw className="spin" size={14} /> : <Sparkles size={14} />}
                            <span>{drafts[suggestion.url]?.isLoading ? 'A gerar…' : 'Rascunho IA'}</span>
                          </button>
                          {drafts[suggestion.url]?.result && (
                            <div className="suggestion-draft">
                              <div className="draft-score"><strong>Afinidade {drafts[suggestion.url].result!.fit_score}/100</strong><span>{drafts[suggestion.url].result!.fit_reason}</span></div>
                              {drafts[suggestion.url].result!.skipped ? (
                                <p className="draft-skipped">Afinidade baixa: não foi gerado rascunho.</p>
                              ) : (
                                <>
                                  <p className="draft-subject">{drafts[suggestion.url].result!.subject}</p>
                                  <pre className="draft-body">{drafts[suggestion.url].result!.body}</pre>
                                  <button className="button button-outline suggestion-save" type="button" onClick={() => void copyDraft(drafts[suggestion.url].result!)}><Copy size={14} /><span>Copiar rascunho</span></button>
                                </>
                              )}
                            </div>
                          )}
                        </article>
                      ))}
                    </div>
                  ) : (
                    <div className="cv-no-areas">
                      <strong>Sem vagas confirmadas para {cvLocation || 'esta localização'}</strong>
                      <span>Foram procuradas ofertas na localização exata ou remotas sem restrição de país.</span>
                      {cvAnalysis.excluded_location_count > 0 && <small>{cvAnalysis.excluded_location_count} vagas em regiões amplas, países mistos ou locais incompatíveis foram omitidas.</small>}
                    </div>
                  )}
                </div>
              </div>
            )}
          </section>

          <section className="summary-strip" aria-label="Resumo da lista">
            <div className="summary-item summary-total">
              <span className="summary-label">Na lista</span>
              <strong>{counts.all.toString().padStart(2, '0')}</strong>
              <span className="summary-note">contactos guardados</span>
            </div>
            <div className="summary-item">
              <span className="summary-label"><Clock3 size={14} /> Por contactar</span>
              <strong>{counts.to_contact.toString().padStart(2, '0')}</strong>
            </div>
            <div className="summary-item">
              <span className="summary-label"><Send size={14} /> Enviados</span>
              <strong>{counts.sent.toString().padStart(2, '0')}</strong>
            </div>
            <div className="summary-item">
              <span className="summary-label"><Reply size={14} /> Respostas</span>
              <strong>{counts.replied.toString().padStart(2, '0')}</strong>
            </div>
            <div className="summary-footnote"><Mail size={15} /> {counts.withEmail} com email</div>
          </section>

          <section className="list-section" aria-label="Contactos de prospeção">
            <div className="list-toolbar">
              <div className="filter-tabs" role="tablist" aria-label="Filtrar por estado">
                {([
                  ['all', 'Todos'],
                  ['to_contact', 'Por contactar'],
                  ['sent', 'Enviados'],
                  ['replied', 'Respostas'],
                  ['no_email', 'Sem email'],
                ] as [StatusFilter, string][]).map(([filter, label]) => (
                  <button
                    className={`filter-tab ${activeFilter === filter ? 'is-selected' : ''}`}
                    key={filter}
                    type="button"
                    role="tab"
                    aria-selected={activeFilter === filter}
                    onClick={() => setActiveFilter(filter)}
                  >
                    {label}<span>{counts[filter]}</span>
                  </button>
                ))}
              </div>
              <div className="list-actions">
                <label className="search-field">
                  <Search size={16} />
                  <input
                    type="search"
                    placeholder="Pesquisar empresa, email..."
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    aria-label="Pesquisar contactos"
                  />
                  <kbd>/</kbd>
                </label>
                <button
                  className="icon-button refresh-button"
                  type="button"
                  aria-label="Atualizar lista"
                  title="Atualizar lista"
                  onClick={() => void loadContacts(true)}
                  disabled={isRefreshing}
                >
                  <RefreshCw size={16} className={isRefreshing ? 'spin' : ''} />
                </button>
              </div>
            </div>

            {error && contacts.length > 0 && (
              <div className="notice notice-error" role="alert">
                <span><strong>Não foi possível concluir o pedido.</strong> {error}</span>
                <button className="icon-button" type="button" aria-label="Fechar aviso" onClick={() => setError(null)}><X size={16} /></button>
              </div>
            )}

            <div className="table-scroll">
              <table className="contact-table">
                <thead>
                  <tr>
                    <th scope="col">Empresa / contacto</th>
                    <th scope="col">Email</th>
                    <th scope="col">Tipo</th>
                    <th scope="col">Estado</th>
                    <th scope="col">Fonte</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleContacts.map((contact) => (
                    <tr
                      className={selectedKey === contactKey(contact) ? 'is-current' : ''}
                      key={contactKey(contact)}
                      onClick={() => setSelectedKey((current) => (current === contactKey(contact) ? null : contactKey(contact)))}
                    >
                      <td>
                        <div className="company-cell">
                          <span className="company-monogram">{contact.name_company.slice(0, 1).toLocaleUpperCase('pt-PT')}</span>
                          <span className="company-copy">
                            <strong>{contact.name_company}</strong>
                            <small>{contact.name_contact || contact.role_contact || (contact.email ? 'Email disponível' : 'Contacto por identificar')}</small>
                          </span>
                        </div>
                      </td>
                      <td>
                        {contact.email ? (
                          <a className="email-link" href={`mailto:${contact.email}`} onClick={(event) => event.stopPropagation()}>
                            {contact.email}
                          </a>
                        ) : <span className="muted-cell">Sem email</span>}
                      </td>
                      <td><span className="type-label">{contactTypeLabels[contact.contact_type || ''] || 'Geral'}</span></td>
                      <td onClick={(event) => event.stopPropagation()}>
                        <label className={`status-select status-${contact.outreach_status}`}>
                          <span className="status-dot" />
                          <select
                            value={contact.outreach_status}
                            aria-label={`Estado de ${contact.name_company}`}
                            onChange={(event) => void updateStatus(contact, event.target.value as OutreachStatus)}
                          >
                            {Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                          </select>
                          <ChevronDown size={13} />
                        </label>
                      </td>
                      <td className="source-cell">
                        {contact.source_url ? (
                          <a className="source-button" href={contact.source_url} target="_blank" rel="noreferrer" title="Abrir fonte" aria-label={`Abrir fonte de ${contact.name_company}`} onClick={(event) => event.stopPropagation()}>
                            <ExternalLink size={15} />
                          </a>
                        ) : <span className="source-missing">—</span>}
                        <button className="source-button write-button" type="button" title="Escrever email" aria-label={`Escrever email para ${contact.name_company}`} onClick={(event) => { event.stopPropagation(); setSelectedKey(contactKey(contact)) }}>
                          <Mail size={15} />
                        </button>
                        <button className="source-button remove-button" type="button" title="Retirar da lista" aria-label={`Retirar ${contact.name_company} da lista`} onClick={(event) => { event.stopPropagation(); void removeCompany(contact) }}>
                          <Trash2 size={15} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {isLoading && <div className="table-message"><RefreshCw className="spin" size={18} /> A carregar a lista...</div>}
              {!isLoading && error && contacts.length === 0 && (
                <div className="empty-state">
                  <div className="empty-icon"><CircleAlert size={21} /></div>
                  <h2>Não foi possível ligar à API</h2>
                  <p>Confirma se o backend está ativo em localhost:8000 e tenta novamente.</p>
                  <button className="button button-outline" type="button" onClick={() => void loadContacts(true)} disabled={isRefreshing}>
                    <RefreshCw size={15} className={isRefreshing ? 'spin' : ''} /> Tentar novamente
                  </button>
                </div>
              )}
              {!isLoading && !error && visibleContacts.length === 0 && (
                <div className="empty-state">
                  <div className="empty-icon"><Users size={21} /></div>
                  <h2>{contacts.length ? 'Sem resultados para esta pesquisa' : 'A lista começa aqui'}</h2>
                  <p>{contacts.length ? 'Experimenta outro termo ou estado.' : 'Adiciona uma empresa e o respetivo contacto de carreiras.'}</p>
                  {!contacts.length && <button className="button button-outline" type="button" onClick={() => setFormOpen(true)}><Plus size={16} /> Adicionar primeiro contacto</button>}
                </div>
              )}
            </div>
            <footer className="table-footer">
              <span>A mostrar {visibleContacts.length} de {contacts.length} contactos</span>
              <span>Os envios são feitos manualmente</span>
            </footer>
          </section>
        </div>
      </main>

      {selectedContact && (
        <aside className="detail-panel" aria-label="Detalhes do contacto selecionado">
          <div className="detail-topline"><span>DETALHE DO CONTACTO</span><button className="icon-button detail-close" type="button" onClick={() => setSelectedKey(null)} aria-label="Fechar detalhe"><X size={17} /></button></div>
          <div className="detail-company-mark">{selectedContact.name_company.slice(0, 1).toLocaleUpperCase('pt-PT')}</div>
          <h2>{selectedContact.name_company}</h2>
          <p className="detail-contact-name">{selectedContact.name_contact || (selectedContact.email ? 'Email disponível' : 'Contacto por identificar')}</p>
          {selectedContact.role_contact && <p className="detail-role">{selectedContact.role_contact}</p>}

          <div className="detail-divider" />
          <div className="detail-field">
            <span className="detail-label"><Mail size={14} /> Email</span>
            {selectedContact.email ? (
              <div className="detail-email-row">
                <a href={`mailto:${selectedContact.email}`}>{selectedContact.email}</a>
                <button className="icon-button" type="button" title="Copiar email" aria-label="Copiar email" onClick={() => void copyEmail(selectedContact.email!)}><Copy size={15} /></button>
              </div>
            ) : (
              <span className="detail-empty">
                {selectedContact.outreach_status === 'no_email'
                  ? 'Não encontrado automaticamente. Indica o site da empresa e tenta de novo.'
                  : 'Ainda não encontrado'}
              </span>
            )}
          </div>
          <div className="detail-field">
            <span className="detail-label"><Building2 size={14} /> Categoria</span>
            <span>{contactTypeLabels[selectedContact.contact_type || ''] || 'Geral'}</span>
          </div>
          {(selectedContact.cellphone || selectedContact.telephone) && (
            <div className="detail-field">
              <span className="detail-label"><MapPin size={14} /> Telefone</span>
              <span>{selectedContact.cellphone || selectedContact.telephone}</span>
            </div>
          )}
          <div className="detail-field">
            <span className="detail-label"><ExternalLink size={14} /> Fonte</span>
            {selectedContact.source_url ? <a className="source-detail-link" href={selectedContact.source_url} target="_blank" rel="noreferrer">Abrir página de origem <ArrowUpRight size={14} /></a> : <span className="detail-empty">Fonte não registada</span>}
          </div>

          {!selectedContact.email && (
            <form className="detail-website-form" key={selectedContact.id_company} onSubmit={(event) => void findEmail(selectedContact, event)}>
              <label className="detail-label" htmlFor="detail-website"><ExternalLink size={14} /> Site da empresa</label>
              <input
                id="detail-website"
                type="text"
                inputMode="url"
                placeholder={selectedContact.website_url || 'exemplo.com'}
                value={websiteDraft.idCompany === selectedContact.id_company ? websiteDraft.value : ''}
                onChange={(event) => setWebsiteDraft({ idCompany: selectedContact.id_company, value: event.target.value })}
              />
              <button className="button button-outline" type="submit" disabled={isSearchingEmail}>
                {isSearchingEmail ? <RefreshCw className="spin" size={14} /> : <Search size={14} />}
                Procurar email
              </button>
            </form>
          )}

          <div className="detail-divider" />
          <div className="email-composer">
            <div className="composer-heading">
              <span className="detail-label"><Mail size={14} /> Email de candidatura</span>
              <div className="language-toggle" role="group" aria-label="Idioma do email">
                <button type="button" className={draftLanguage === 'pt' ? 'is-active' : ''} aria-pressed={draftLanguage === 'pt'} onClick={() => changeDraftLanguage('pt')}>PT</button>
                <button type="button" className={draftLanguage === 'en' ? 'is-active' : ''} aria-pressed={draftLanguage === 'en'} onClick={() => changeDraftLanguage('en')}>EN</button>
              </div>
            </div>
            {!profile ? (
              <p className="composer-hint">Analisa o teu CV primeiro para o email usar o teu nome e competências.</p>
            ) : (
              <button
                className="button button-outline composer-generate"
                type="button"
                disabled={contactDraft?.key === selectedKey && contactDraft.isLoading}
                onClick={() => void draftForContact(selectedContact)}
              >
                {contactDraft?.key === selectedKey && contactDraft.isLoading ? <RefreshCw className="spin" size={14} /> : <Sparkles size={14} />}
                {contactDraft?.key === selectedKey && contactDraft.isLoading ? 'A gerar…' : contactDraft?.key === selectedKey ? 'Gerar de novo' : 'Gerar email com IA'}
              </button>
            )}
            {contactDraft?.key === selectedKey && !contactDraft.isLoading && (
              <>
                <p className="composer-fit"><strong>Afinidade {contactDraft.fitScore}/100</strong> {contactDraft.fitReason}</p>
                {contactDraft.skipped ? (
                  <p className="composer-hint">Afinidade baixa: não foi gerado email para esta vaga.</p>
                ) : (
                  <>
                    <input
                      className="composer-subject"
                      aria-label="Assunto"
                      value={contactDraft.subject}
                      onChange={(event) => setContactDraft({ ...contactDraft, subject: event.target.value })}
                    />
                    <textarea
                      className="composer-body"
                      aria-label="Corpo do email"
                      rows={9}
                      value={contactDraft.body}
                      onChange={(event) => setContactDraft({ ...contactDraft, body: event.target.value })}
                    />
                    <div className="composer-actions">
                      {googleStatus?.connected && (
                        <button
                          className="button button-primary"
                          type="button"
                          disabled={!selectedContact.email || isSending}
                          title={selectedContact.email ? 'Enviar com a tua conta Google' : 'Esta empresa ainda não tem email'}
                          onClick={() => void sendWithGmail(selectedContact, contactDraft)}
                        >
                          {isSending ? <RefreshCw className="spin" size={14} /> : <Send size={14} />} Enviar
                        </button>
                      )}
                      <button
                        className={`button ${googleStatus?.connected ? 'button-outline' : 'button-primary'}`}
                        type="button"
                        disabled={!selectedContact.email}
                        title={selectedContact.email ? 'Abrir na tua aplicação de email' : 'Esta empresa ainda não tem email'}
                        onClick={() => openInMailClient(selectedContact, contactDraft)}
                      >
                        <Send size={14} /> Abrir no email
                      </button>
                      <button
                        className="button button-outline"
                        type="button"
                        onClick={() => void copyDraft({ fit_score: 0, fit_reason: '', skipped: false, subject: contactDraft.subject, body: contactDraft.body })}
                      >
                        <Copy size={14} /> Copiar
                      </button>
                    </div>
                  </>
                )}
              </>
            )}
          </div>

          <div className="detail-divider" />
          <label className="detail-label status-detail-label" htmlFor="detail-status">Estado da prospeção</label>
          <select
            className="detail-status-control"
            id="detail-status"
            value={selectedContact.outreach_status}
            onChange={(event) => void updateStatus(selectedContact, event.target.value as OutreachStatus)}
          >
            {Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <button className="button button-outline detail-remove" type="button" onClick={() => void removeCompany(selectedContact)}>
            <Trash2 size={14} /> Retirar da lista
          </button>
          <div className="detail-tip"><FileText size={15} /><span>O email abre na tua aplicação de email, onde anexas o CV e envias. Depois marca o estado como «Enviado».</span></div>
        </aside>
      )}

      {notice && <div className="toast" role="status"><Check size={16} /> {notice}</div>}

      {formOpen && (
        <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setFormOpen(false) }}>
          <section className="contact-modal" role="dialog" aria-modal="true" aria-labelledby="contact-form-title">
            <div className="modal-heading">
              <div><p className="eyebrow">NOVA ENTRADA</p><h2 id="contact-form-title">Adicionar contacto</h2></div>
              <button className="icon-button" type="button" aria-label="Fechar formulário" onClick={() => setFormOpen(false)}><X size={18} /></button>
            </div>
            <p className="modal-description">Liga uma pessoa ou equipa de recrutamento a uma empresa.</p>
            <form className="contact-form" onSubmit={(event) => void createContact(event)}>
              <label>Empresa <span>*</span><input required maxLength={150} value={form.name_company} onChange={(event) => setForm({ ...form, name_company: event.target.value })} placeholder="Nome da empresa" /></label>
              <div className="form-row">
                <label>Nome do contacto<input maxLength={150} value={form.name_contact} onChange={(event) => setForm({ ...form, name_contact: event.target.value })} placeholder="Pessoa ou equipa" /></label>
                <label>Função<input maxLength={150} value={form.role_contact} onChange={(event) => setForm({ ...form, role_contact: event.target.value })} placeholder="Ex.: Talent Acquisition" /></label>
              </div>
              <div className="form-row">
                <label>Email<input type="email" maxLength={320} value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} placeholder="carreiras@empresa.pt" /></label>
                <label>Categoria<select value={form.contact_type} onChange={(event) => setForm({ ...form, contact_type: event.target.value })}><option value="careers">Carreiras</option><option value="recruitment">Recrutamento</option><option value="general">Geral</option></select></label>
              </div>
              <label>URL da fonte<input type="url" maxLength={1000} value={form.source_url} onChange={(event) => setForm({ ...form, source_url: event.target.value })} placeholder="https://empresa.pt/carreiras" /></label>
              <div className="modal-actions"><button className="button button-quiet" type="button" onClick={() => setFormOpen(false)}>Cancelar</button><button className="button button-primary" type="submit" disabled={isSaving}>{isSaving ? <RefreshCw className="spin" size={16} /> : <Plus size={16} />}{isSaving ? 'A guardar...' : 'Guardar contacto'}</button></div>
            </form>
          </section>
        </div>
      )}
    </div>
  )
}

function LoginScreen({ notice }: { notice: string | null }) {
  const [error, setError] = useState<string | null>(notice)
  const [isLoading, setIsLoading] = useState(false)

  async function signIn() {
    setIsLoading(true)
    setError(null)
    try {
      const { url } = await request<{ url: string }>('/auth/login-url')
      window.location.href = url
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Não foi possível iniciar o login.')
      setIsLoading(false)
    }
  }

  return (
    <main className="login-screen">
      <section className="login-card">
        <span className="brand-mark"><span>p</span></span>
        <p className="eyebrow">PONTO · LISTA DE PROSPEÇÃO</p>
        <h1>Entra para continuar</h1>
        <p>Cada conta tem a sua lista de empresas, o seu CV guardado e o seu Gmail.</p>
        <button className="button button-primary" type="button" disabled={isLoading} onClick={() => void signIn()}>
          {isLoading ? <RefreshCw className="spin" size={16} /> : <Mail size={16} />}Entrar com Google
        </button>
        {error && <div className="notice notice-error" role="alert"><span>{error}</span></div>}
      </section>
    </main>
  )
}

function loginNotice(): string | null {
  const result = new URLSearchParams(window.location.search).get('auth')
  if (result === 'denied') return 'O login foi cancelado.'
  if (result === 'error') return 'Não foi possível iniciar sessão. Tenta de novo.'
  return null
}

function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [isChecking, setIsChecking] = useState(true)
  const [notice] = useState(loginNotice)

  async function refreshSession() {
    setSession(await request<Session>('/auth/me'))
  }

  useEffect(() => {
    let isActive = true
    request<Session>('/auth/me')
      .then((data) => { if (isActive) setSession(data) })
      .catch(() => undefined)
      .finally(() => { if (isActive) setIsChecking(false) })

    const expire = () => setSession(null)
    window.addEventListener('ponto:unauthorized', expire)
    return () => {
      isActive = false
      window.removeEventListener('ponto:unauthorized', expire)
    }
  }, [])

  async function logout() {
    await request('/auth/logout', { method: 'POST' }).catch(() => undefined)
    setSession(null)
  }

  if (isChecking) return <main className="login-screen"><RefreshCw className="spin" size={22} /></main>
  if (!session) return <LoginScreen notice={notice} />
  return <Dashboard key={session.user.email} session={session} onSessionChange={refreshSession} onLogout={() => void logout()} />
}

export default App
