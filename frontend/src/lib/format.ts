import type { AppPage, ContactForm, JobSuggestion, OutreachContact, OutreachStatus, Schedule, WorkMode } from '../types'

export const SUGGESTIONS_PER_PAGE = 5
export const MAX_PROFILE_AREAS = 3

export const statusLabels: Record<OutreachStatus, string> = {
  to_contact: 'Por contactar',
  sent: 'Enviado',
  replied: 'Respondeu',
  no_email: 'Sem email',
  rejected: 'Não selecionado',
}

export const contactTypeLabels: Record<string, string> = {
  careers: 'Carreiras',
  recruitment: 'Recrutamento',
  general: 'Geral',
}

export const emptyForm: ContactForm = {
  name_company: '',
  name_contact: '',
  role_contact: '',
  contact_type: 'careers',
  email: '',
  source_url: '',
}

export function pageFromHash(): AppPage {
  const hash = window.location.hash.replace('#', '')
  if (hash === 'contactos' || hash === 'perfil') return hash
  return 'vagas'
}

export function personInitials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return 'P'
  const first = parts[0].slice(0, 1)
  const last = parts.length > 1 ? parts[parts.length - 1].slice(0, 1) : ''
  return `${first}${last}`.toLocaleUpperCase('pt-PT')
}

export function legalFromHash(): 'termos' | 'privacidade' | null {
  const page = window.location.hash.replace('#', '')
  return page === 'termos' || page === 'privacidade' ? page : null
}

export function normalizeCompany(name: string): string {
  return name.trim().toLocaleLowerCase('pt-PT')
}

export function contactKey(contact: OutreachContact) {
  return `${contact.id_company}:${contact.id_contact}`
}

export function applyJobAction(status: OutreachStatus | undefined): { label: string, done: boolean } {
  if (status === 'sent' || status === 'replied') return { label: 'Candidatado', done: true }
  if (status === 'rejected') return { label: 'Não selecionado', done: true }
  return { label: 'Candidatar', done: false }
}

export const workModeLabels: Record<WorkMode, string> = {
  onsite: 'Presencial',
  hybrid: 'Híbrido',
  remote: 'Remoto',
}

export const scheduleLabels: Record<Schedule, string> = {
  full_time: 'Tempo inteiro',
  part_time: 'Tempo parcial',
}

export const workModeChoices: [string, string][] = [
  ['', 'Todos'],
  ['onsite', 'Presencial'],
  ['hybrid', 'Híbrido'],
  ['remote', 'Remoto'],
]

export const scheduleChoices: [string, string][] = [
  ['', 'Todos'],
  ['full_time', 'Tempo inteiro'],
  ['part_time', 'Tempo parcial'],
]

export function daysAgo(date: string): string {
  const days = Math.floor((Date.now() - new Date(date).getTime()) / 86_400_000)
  if (days <= 0) return 'hoje'
  if (days === 1) return 'ontem'
  return `há ${days} dias`
}

export function jobPlace(location: string) {
  return location.split(/[,;(]/)[0].trim()
}

export function locationShort(location: string) {
  const parts = location.split(/[,;]/).map((part) => part.trim()).filter(Boolean)
  if (parts.length <= 2) return parts.join(', ')
  return `${parts[0]} +${parts.length - 1}`
}

export function jobPills(suggestion: JobSuggestion): string[] {
  return [
    locationShort(suggestion.location) || 'Local por confirmar',
    suggestion.posted_at ? daysAgo(suggestion.posted_at) : 'Data por confirmar',
    suggestion.source,
    suggestion.salary || 'Salário não indicado',
    suggestion.schedule ? scheduleLabels[suggestion.schedule] : 'Horário não indicado',
  ]
}

export function jobFacts(suggestion: JobSuggestion): { label: string, value: string }[] {
  return [
    { label: 'Local', value: suggestion.location || 'Por confirmar' },
    { label: 'Regime', value: suggestion.work_mode ? workModeLabels[suggestion.work_mode] : 'Não indicado' },
    { label: 'Horário', value: suggestion.schedule ? scheduleLabels[suggestion.schedule] : 'Não indicado' },
    { label: 'Contrato', value: suggestion.contract || 'Não indicado' },
    { label: 'Nível', value: suggestion.seniority || 'Não indicado' },
    { label: 'Salário', value: suggestion.salary || 'Não indicado' },
    { label: 'Publicada', value: suggestion.posted_at ? daysAgo(suggestion.posted_at) : 'Não indicado' },
    { label: 'Fonte', value: suggestion.source },
    { label: 'Categoria', value: suggestion.tags?.[0] || 'Não indicada' },
  ]
}

export function jobBlurb(suggestion: JobSuggestion): string {
  const summary = suggestion.summary.trim()
  if (!summary) return ''
  const known = [suggestion.schedule, suggestion.contract, suggestion.seniority, suggestion.area, ...(suggestion.tags || [])]
  if (known.some((item) => item === summary)) return ''
  const joined = [suggestion.schedule, suggestion.contract].filter(Boolean).join(' · ')
  if (joined && summary === joined) return ''
  return summary
}

export function ratingLabel(rating: number, reviews?: number) {
  const score = rating.toLocaleString('pt-PT', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
  if (!reviews) return score
  return `${score} · ${reviews} ${reviews === 1 ? 'opinião' : 'opiniões'}`
}

export function isRemoteSuggestion(suggestion: JobSuggestion): boolean {
  return suggestion.work_mode === 'remote' || suggestion.location_priority === 3
}

export function jobFacetWorkMode(suggestion: JobSuggestion): string {
  return suggestion.work_mode ? workModeLabels[suggestion.work_mode] : 'Não indicado'
}

export function jobFacetSchedule(suggestion: JobSuggestion): string {
  return suggestion.schedule ? scheduleLabels[suggestion.schedule] : 'Não indicado'
}

export function usesRemoteBoards(workMode: string) {
  return workMode !== 'onsite' && workMode !== 'hybrid'
}

export function jobFacetPlace(suggestion: JobSuggestion): string {
  if (isRemoteSuggestion(suggestion)) return 'Remoto'
  const place = jobPlace(suggestion.location)
  if (/remoto|remote|worldwide|anywhere|global/i.test(place)) return 'Remoto'
  return place
}

export function loginNotice(): string | null {
  const result = new URLSearchParams(window.location.search).get('auth')
  if (result === 'denied') return 'O login foi cancelado.'
  if (result === 'error') return 'Não foi possível iniciar sessão. Tenta de novo.'
  return null
}
