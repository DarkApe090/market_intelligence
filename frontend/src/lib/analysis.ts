import type { CvAnalysis, CvArea, JobSuggestion } from '../types'

export function emptyAnalysis(): CvAnalysis {
  return {
    candidate_name: null,
    areas: [],
    suggestions: [],
    search_errors: [],
    excluded_location_count: 0,
    cv_saved: false,
    llm_used: false,
    already_in_list_count: 0,
    location_priority_order: [],
  }
}

export function applyAnalysisEvent(current: CvAnalysis, event: Record<string, unknown>): CvAnalysis {
  if (event.type === 'profile') {
    return {
      ...current,
      candidate_name: typeof event.candidate_name === 'string' ? event.candidate_name : null,
      areas: Array.isArray(event.areas) ? event.areas as CvArea[] : [],
      llm_used: Boolean(event.llm_used),
      cv_saved: Boolean(event.cv_saved),
      location_priority_order: Array.isArray(event.location_priority_order)
        ? event.location_priority_order as string[]
        : current.location_priority_order,
    }
  }
  if (event.type === 'jobs') {
    return {
      ...current,
      suggestions: Array.isArray(event.suggestions) ? event.suggestions as JobSuggestion[] : [],
    }
  }
  if (event.type === 'done') {
    return {
      ...current,
      search_errors: Array.isArray(event.search_errors) ? event.search_errors as string[] : [],
      already_in_list_count: Number(event.already_in_list_count) || 0,
      excluded_location_count: Number(event.excluded_location_count) || 0,
    }
  }
  return current
}

export async function readAnalysisStream(
  response: Response,
  onUpdate: (analysis: CvAnalysis) => void,
): Promise<CvAnalysis> {
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event('ponto:unauthorized'))
    const detail = await response.json().catch(() => null)
    throw new Error(detail?.detail || `Análise falhou (${response.status})`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('A análise não devolveu resultados.')

  const decoder = new TextDecoder()
  let buffer = ''
  let analysis = emptyAnalysis()

  const consume = (chunk: string) => {
    buffer += chunk.replace(/\r\n/g, '\n')
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''
    for (const part of parts) {
      const line = part.split('\n').find((item) => item.startsWith('data: '))
      if (!line) continue
      const event = JSON.parse(line.slice(6)) as Record<string, unknown>
      if (event.type === 'error') throw new Error(String(event.detail || 'Análise falhou.'))
      analysis = applyAnalysisEvent(analysis, event)
      onUpdate({ ...analysis })
    }
  }

  while (true) {
    const { value, done } = await reader.read()
    if (value) consume(decoder.decode(value, { stream: true }))
    if (done) {
      consume(decoder.decode())
      if (buffer.trim()) consume('\n\n')
      break
    }
  }

  return analysis
}
