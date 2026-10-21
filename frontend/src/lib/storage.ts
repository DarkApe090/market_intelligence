import type { AppToast, DraftLanguage } from '../types'

const LANGUAGE_STORAGE_KEY = 'ponto.draftLanguage'

export function ignoredStorageKey(email: string): string {
  return `ponto.ignoredCompanies.${email}`
}

export function loadIgnored(email: string): string[] {
  try {
    const stored = window.localStorage.getItem(ignoredStorageKey(email))
    return stored ? JSON.parse(stored) as string[] : []
  } catch {
    return []
  }
}

export function loadDraftLanguage(): DraftLanguage {
  return window.localStorage.getItem(LANGUAGE_STORAGE_KEY) === 'en' ? 'en' : 'pt'
}

export function saveDraftLanguage(language: DraftLanguage) {
  window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language)
}

export function googleToast(): AppToast | null {
  const result = new URLSearchParams(window.location.search).get('google')
  if (result === 'connected') return { kind: 'success', message: 'Conta Google ligada.' }
  if (result) return { kind: 'error', message: 'Não foi possível ligar a conta Google.' }
  return null
}
