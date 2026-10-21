import { useState, type FormEvent } from 'react'
import { API_URL, request } from '../lib/api'
import { readAnalysisStream } from '../lib/analysis'
import { SUGGESTIONS_PER_PAGE, contactKey, jobFacetPlace, jobFacetSchedule, jobFacetWorkMode, normalizeCompany } from '../lib/format'
import { ignoredStorageKey, loadIgnored } from '../lib/storage'
import type { CvAnalysis, JobSuggestion, OutreachContact, ProfileAreaEdit, Session } from '../types'

type ToastFns = {
  showToast: (kind: 'success' | 'error' | 'warning', message: string) => void
  askConfirm: (message: string, confirmLabel: string, onConfirm: () => void) => void
}

type OutreachSlice = {
  contacts: OutreachContact[]
  loadContacts: (showRefresh?: boolean) => Promise<OutreachContact[]>
  setSelectedKey: (key: string | null | ((current: string | null) => string | null)) => void
  refreshContactsAfterEnrichment: (idCompany: number, companyName: string) => void
}

export function useJobSearch(
  session: Session,
  toast: ToastFns,
  outreach: OutreachSlice,
  onSessionChange: () => Promise<void>,
) {
  const [cvFile, setCvFile] = useState<File | null>(null)
  const [replacingCv, setReplacingCv] = useState(false)
  const [cvLocation, setCvLocation] = useState('Portugal')
  const [workMode, setWorkMode] = useState('')
  const [schedule, setSchedule] = useState('')
  const [cvAnalysis, setCvAnalysis] = useState<CvAnalysis | null>(null)
  const [cvError, setCvError] = useState<string | null>(null)
  const [isAnalyzingCv, setIsAnalyzingCv] = useState(false)
  const [savingSuggestion, setSavingSuggestion] = useState<string | null>(null)
  const [suggestionPage, setSuggestionPage] = useState(1)
  const [selectedJobUrl, setSelectedJobUrl] = useState<string | null>(null)
  const [ignoredCompanies, setIgnoredCompanies] = useState<string[]>(() => loadIgnored(session.user.email))
  const [placeFilter, setPlaceFilter] = useState('')
  const [sourceFilter, setSourceFilter] = useState('')
  const [workModeFilter, setWorkModeFilter] = useState('')
  const [scheduleFilter, setScheduleFilter] = useState('')
  function updateIgnored(next: string[]) {
    setIgnoredCompanies(next)
    window.localStorage.setItem(ignoredStorageKey(session.user.email), JSON.stringify(next))
  }

  function ignoreCompany(company: string) {
    const name = normalizeCompany(company)
    if (!ignoredCompanies.includes(name)) updateIgnored([...ignoredCompanies, name])
  }

  const listedSuggestions = cvAnalysis
    ? cvAnalysis.suggestions.filter((suggestion) => !ignoredCompanies.includes(normalizeCompany(suggestion.company)))
    : []
  const visibleSuggestions = listedSuggestions.filter((suggestion) => {
    if (placeFilter && jobFacetPlace(suggestion) !== placeFilter) return false
    if (sourceFilter && suggestion.source !== sourceFilter) return false
    if (workModeFilter && jobFacetWorkMode(suggestion) !== workModeFilter) return false
    if (scheduleFilter && jobFacetSchedule(suggestion) !== scheduleFilter) return false
    return true
  })
  const placeFacets = countFacets(listedSuggestions, jobFacetPlace).sort(
    (left, right) => Number(left[0] === 'Remoto') - Number(right[0] === 'Remoto'),
  )
  const sourceFacets = countFacets(listedSuggestions, (suggestion) => suggestion.source)
  const workModeFacets = countFacets(listedSuggestions, jobFacetWorkMode)
  const scheduleFacets = countFacets(listedSuggestions, jobFacetSchedule)
  const listedSuggestionCount = listedSuggestions.length
  const suggestionPages = Math.max(1, Math.ceil(visibleSuggestions.length / SUGGESTIONS_PER_PAGE))
  const currentSuggestionPage = Math.min(suggestionPage, suggestionPages)
  const pagedSuggestions = visibleSuggestions.slice(
    (currentSuggestionPage - 1) * SUGGESTIONS_PER_PAGE,
    currentSuggestionPage * SUGGESTIONS_PER_PAGE,
  )
  const hiddenSuggestionCount = cvAnalysis ? cvAnalysis.suggestions.length - listedSuggestions.length : 0

  function openJob(suggestion: JobSuggestion) {
    if (selectedJobUrl === suggestion.url) {
      setSelectedJobUrl(null)
      outreach.setSelectedKey(null)
      return
    }
    setSelectedJobUrl(suggestion.url)
    const contact = outreach.contacts.find((item) => normalizeCompany(item.name_company) === normalizeCompany(suggestion.company))
    outreach.setSelectedKey(contact ? contactKey(contact) : null)
  }

  async function runAnalysis(send: () => Promise<Response>) {
    setIsAnalyzingCv(true)
    setCvError(null)
    setSelectedJobUrl(null)
    setSuggestionPage(1)
    setPlaceFilter('')
    setSourceFilter('')
    setWorkModeFilter('')
    setScheduleFilter('')

    try {
      await readAnalysisStream(await send(), (next) => setCvAnalysis(next))
      setReplacingCv(false)
      await onSessionChange()
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : 'Não foi possível analisar o CV.'
      setCvError(message === 'Failed to fetch' ? 'Não foi possível ligar à API. Confirma se o backend está ativo.' : message)
    } finally {
      setIsAnalyzingCv(false)
    }
  }

  async function analyzeCv(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!cvFile) return

    const formData = new FormData()
    formData.append('file', cvFile)
    formData.append('location', cvLocation.trim() || 'Portugal')
    formData.append('exclude_companies', JSON.stringify(ignoredCompanies))
    formData.append('work_mode', workMode)
    formData.append('schedule', schedule)
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
      body: JSON.stringify({
        location: cvLocation.trim() || 'Portugal',
        exclude_companies: ignoredCompanies,
        work_mode: workMode,
        schedule,
      }),
    }))
  }

  async function saveProfile(areas: ProfileAreaEdit[]) {
    try {
      await request('/career-profile/profile', { method: 'PUT', body: JSON.stringify({ areas }) })
    } catch (requestError) {
      toast.showToast('error', requestError instanceof Error ? requestError.message : 'Não foi possível guardar o perfil.')
      return false
    }
    await onSessionChange()
    await analyzeStoredCv()
    return true
  }

  function listedContact(company: string) {
    return outreach.contacts.find((item) => normalizeCompany(item.name_company) === normalizeCompany(company)) || null
  }

  async function persistSuggestion(suggestion: JobSuggestion) {
    try {
      const saved = await request<{ already_in_outreach: boolean, id_company: number, id_contact: number, email: string | null }>('/career-profile/suggestions/save', {
        method: 'POST',
        body: JSON.stringify({
          company: suggestion.company,
          title: suggestion.title,
          url: suggestion.url,
          source: suggestion.source,
          email: suggestion.email,
        }),
      })
      const data = await outreach.loadContacts(true)
      const contact = data.find((item) => item.id_company === saved.id_company && item.id_contact === saved.id_contact)
        || data.find((item) => normalizeCompany(item.name_company) === normalizeCompany(suggestion.company))
        || null
      if (contact && !contact.email && !saved.already_in_outreach) {
        outreach.refreshContactsAfterEnrichment(saved.id_company, suggestion.company)
      }
      return contact
    } catch (requestError) {
      toast.showToast('error', requestError instanceof Error ? requestError.message : 'Não foi possível guardar a vaga.')
      return null
    }
  }

  function removeStoredCv() {
    toast.askConfirm(
      'Remover o CV guardado? Os emails deixam de levar o CV anexado.',
      'Remover',
      () => { void confirmRemoveStoredCv() },
    )
  }

  async function confirmRemoveStoredCv() {
    try {
      await request('/career-profile/cv', { method: 'DELETE' })
      await onSessionChange()
      setCvAnalysis(null)
      toast.showToast('success', 'CV removido.')
    } catch (requestError) {
      toast.showToast('error', requestError instanceof Error ? requestError.message : 'Não foi possível remover o CV.')
    }
  }

  return {
    cvFile,
    setCvFile,
    replacingCv,
    setReplacingCv,
    cvLocation,
    setCvLocation,
    workMode,
    setWorkMode,
    schedule,
    setSchedule,
    cvAnalysis,
    setCvAnalysis,
    cvError,
    setCvError,
    isAnalyzingCv,
    savingSuggestion,
    suggestionPage,
    setSuggestionPage,
    selectedJobUrl,
    setSelectedJobUrl,
    ignoredCompanies,
    updateIgnored,
    ignoreCompany,
    visibleSuggestions,
    listedSuggestionCount,
    placeFilter,
    setPlaceFilter,
    sourceFilter,
    setSourceFilter,
    workModeFilter,
    setWorkModeFilter,
    scheduleFilter,
    setScheduleFilter,
    placeFacets,
    sourceFacets,
    workModeFacets,
    scheduleFacets,
    suggestionPages,
    currentSuggestionPage,
    pagedSuggestions,
    hiddenSuggestionCount,
    listedContact,
    openJob,
    analyzeCv,
    analyzeStoredCv,
    saveProfile,
    persistSuggestion,
    setSavingSuggestion,
    removeStoredCv,
  }
}

function countFacets(items: JobSuggestion[], key: (item: JobSuggestion) => string) {
  const counts = new Map<string, number>()
  for (const item of items) {
    const value = key(item)
    if (!value) continue
    counts.set(value, (counts.get(value) || 0) + 1)
  }
  return [...counts.entries()].sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0], 'pt'))
}
