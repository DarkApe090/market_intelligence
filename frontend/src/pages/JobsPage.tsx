import { Bookmark, ChevronDown, FileText, RefreshCw, Search, Send, Star, Upload, X } from 'lucide-react'
import { LocationField } from '../components/LocationField'
import { ProfilePeek } from '../components/ProfileCard'
import { useWorkspaceContext } from '../hooks/useWorkspaceContext'
import { applyJobAction, jobPills, ratingLabel, scheduleChoices, usesRemoteBoards, workModeChoices } from '../lib/format'
import type { JobSuggestion } from '../types'

export function JobsPage() {
  const { session, jobs } = useWorkspaceContext()
  const readyName = session.cv?.candidate_name || session.user.name || session.user.email

  return (
    <section className="search-panel" aria-label="Procurar vagas">
      <div className={`page-intro ${session.cv && !jobs.replacingCv ? 'is-compact' : ''}`}>
        {!(session.cv && !jobs.replacingCv) && (
        <div className="page-intro-lead">
          <span className="page-intro-mark" aria-hidden="true"><Search size={20} /></span>
          <p>O CV define o tipo de vaga. Escolhe o sítio e procura ofertas alinhadas ao perfil.</p>
        </div>
        )}
        {session.cv && !jobs.replacingCv ? (
        <div className="search-row">
          <a className="cv-chip" href="#perfil"><FileText size={16} /><span>{session.cv.candidate_name || session.cv.filename}</span></a>
          <LocationField value={jobs.cvLocation} onChange={jobs.setCvLocation} />
          <ChoiceSelect label="Local" value={jobs.workMode} options={workModeChoices} onChange={jobs.setWorkMode} />
          <ChoiceSelect label="Horário" value={jobs.schedule} options={scheduleChoices} onChange={jobs.setSchedule} />
          <button className="button button-primary" type="button" disabled={jobs.isAnalyzingCv} onClick={() => void jobs.analyzeStoredCv()}>
            {jobs.isAnalyzingCv ? <RefreshCw className="spin" size={16} /> : <Search size={16} />}
            {jobs.isAnalyzingCv ? 'A procurar…' : 'Procurar'}
          </button>
          <button className="button button-outline" type="button" onClick={() => jobs.setReplacingCv(true)}>Trocar CV</button>
          <button className="button button-outline" type="button" onClick={() => void jobs.removeStoredCv()}>Remover</button>
        </div>
      ) : (
        <form className="search-row" onSubmit={(event) => void jobs.analyzeCv(event)}>
          <label className={`cv-file-picker ${jobs.cvFile ? 'has-file' : ''}`}>
            <Upload size={16} />
            <span>{jobs.cvFile ? jobs.cvFile.name : 'PDF, Word, JPG ou texto'}</span>
            <input
              type="file"
              accept=".pdf,.docx,.odt,.rtf,.txt,.md,.html,.htm,.jpg,.jpeg,.png,.webp,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.oasis.opendocument.text,application/rtf,text/plain,text/markdown,text/html,image/jpeg,image/png,image/webp"
              onChange={(event) => {
                jobs.setCvFile(event.target.files?.[0] || null)
                jobs.setCvAnalysis(null)
                jobs.setCvError(null)
              }}
              aria-label="Selecionar currículo em PDF, Word, JPG ou texto"
            />
          </label>
          <LocationField value={jobs.cvLocation} onChange={jobs.setCvLocation} />
          <ChoiceSelect label="Local" value={jobs.workMode} options={workModeChoices} onChange={jobs.setWorkMode} />
          <ChoiceSelect label="Horário" value={jobs.schedule} options={scheduleChoices} onChange={jobs.setSchedule} />
          <button className="button button-primary" type="submit" disabled={!jobs.cvFile || jobs.isAnalyzingCv}>
            {jobs.isAnalyzingCv ? <RefreshCw className="spin" size={16} /> : <Search size={16} />}
            {jobs.isAnalyzingCv ? 'A analisar…' : 'Analisar'}
          </button>
          {session.cv && <button className="button button-outline" type="button" onClick={() => { jobs.setReplacingCv(false); jobs.setCvFile(null) }}>Cancelar</button>}
        </form>
      )}
      </div>
      {jobs.cvError && <div className="notice notice-error" role="alert"><span>{jobs.cvError}</span><button className="button button-quiet" type="button" aria-label="Fechar aviso" onClick={() => jobs.setCvError(null)}><X size={16} /></button></div>}

      {!jobs.cvAnalysis && !jobs.isAnalyzingCv && (
        <div className="cv-results">
          {session.cv && !jobs.replacingCv && session.cv.areas.length > 0 ? (
            <div className="jobs-stage">
              <ProfilePeek name={readyName} picture={session.user.picture} areas={session.cv.areas} />
              <div className="jobs-stage-plan">
                <p className="profile-kicker">Pesquisa</p>
                <h2>Ofertas alinhadas ao CV em {jobs.cvLocation || 'Portugal'}</h2>
                <p>
                  {usesRemoteBoards(jobs.workMode)
                    ? 'ITJobs, Teamlyzer e Net-Empregos, mais boards remotos. A pesquisa usa o cargo e as skills do perfil, não uma lista fixa.'
                    : 'ITJobs, Teamlyzer e Net-Empregos. A pesquisa usa o cargo e as skills do perfil, não uma lista fixa.'}
                </p>
                <ul className="source-pills">
                  {['ITJobs', 'Teamlyzer', 'Net-Empregos', ...(usesRemoteBoards(jobs.workMode) ? ['We Work Remotely', 'Remotive', 'Remote OK'] : [])].map((source) => (
                    <li key={source}>{source}</li>
                  ))}
                </ul>
                <button className="button button-primary" type="button" disabled={jobs.isAnalyzingCv} onClick={() => void jobs.analyzeStoredCv()}>
                  {jobs.isAnalyzingCv ? <RefreshCw className="spin" size={16} /> : <Search size={16} />}
                  Procurar ofertas
                </button>
              </div>
            </div>
          ) : (
            <div className="empty-state jobs-empty">
              <div className="empty-icon"><Upload size={21} /></div>
              <h2>Começa pelo CV</h2>
              <p>Carrega o currículo. A pesquisa usa o cargo e as skills que lá estão, não uma lista fixa de profissões.</p>
            </div>
          )}
        </div>
      )}

      {jobs.cvAnalysis && (
        <div className="cv-results" aria-live="polite">
          <div className="result-filters">
            <h2>Ofertas</h2>
            {jobs.placeFacets.length > 1 && (
              <FilterSelect
                label="Sítio"
                value={jobs.placeFilter}
                allLabel="Todos os sítios"
                allCount={jobs.listedSuggestionCount}
                options={jobs.placeFacets}
                onChange={(value) => {
                  jobs.setPlaceFilter(value)
                  jobs.setSuggestionPage(1)
                }}
              />
            )}
            {jobs.sourceFacets.length > 1 && (
              <FilterSelect
                label="Fonte"
                value={jobs.sourceFilter}
                allLabel="Todas as fontes"
                allCount={jobs.listedSuggestionCount}
                options={jobs.sourceFacets}
                onChange={(value) => {
                  jobs.setSourceFilter(value)
                  jobs.setSuggestionPage(1)
                }}
              />
            )}
            {jobs.workModeFacets.length > 1 && (
              <FilterSelect
                label="Local"
                value={jobs.workModeFilter}
                allLabel="Todos os locais"
                allCount={jobs.listedSuggestionCount}
                options={jobs.workModeFacets}
                onChange={(value) => {
                  jobs.setWorkModeFilter(value)
                  jobs.setSuggestionPage(1)
                }}
              />
            )}
            {jobs.scheduleFacets.length > 1 && (
              <FilterSelect
                label="Horário"
                value={jobs.scheduleFilter}
                allLabel="Todos os horários"
                allCount={jobs.listedSuggestionCount}
                options={jobs.scheduleFacets}
                onChange={(value) => {
                  jobs.setScheduleFilter(value)
                  jobs.setSuggestionPage(1)
                }}
              />
            )}
            {(jobs.placeFilter || jobs.sourceFilter || jobs.workModeFilter || jobs.scheduleFilter) && (
              <button
                className="filter-clear"
                type="button"
                onClick={() => {
                  jobs.setPlaceFilter('')
                  jobs.setSourceFilter('')
                  jobs.setWorkModeFilter('')
                  jobs.setScheduleFilter('')
                  jobs.setSuggestionPage(1)
                }}
              >
                Limpar
              </button>
            )}
            <span>
              {jobs.visibleSuggestions.length} {jobs.visibleSuggestions.length === 1 ? 'anúncio' : 'anúncios'}
              {jobs.isAnalyzingCv ? ' · a procurar' : ''}
            </span>
          </div>
          {jobs.cvAnalysis.llm_used === false && (
            <p className="search-warning">A IA não respondeu: o perfil foi estimado pelo CV. Analisa de novo daqui a pouco.</p>
          )}
          {jobs.hiddenSuggestionCount > 0 && (
            <p className="search-warning">{jobs.hiddenSuggestionCount} {jobs.hiddenSuggestionCount === 1 ? 'empresa ocultada' : 'empresas ocultadas'}. <button type="button" className="button button-outline" onClick={() => jobs.updateIgnored([])}>Mostrar</button></p>
          )}
          {jobs.cvAnalysis.search_errors.length > 0 && (
            jobs.visibleSuggestions.length ? (
              <p className="search-note">{searchMissNote(jobs.cvAnalysis.search_errors)}</p>
            ) : (
              <p className="search-warning">A pesquisa falhou para: {jobs.cvAnalysis.search_errors.join(', ')}.</p>
            )
          )}
          {jobs.visibleSuggestions.length ? (
            <div className="suggestions-list">
              <div className="job-suggestions">
                {jobs.pagedSuggestions.map((suggestion) => (
                  <article
                    className={`job-suggestion ${jobs.selectedJobUrl === suggestion.url ? 'is-selected' : ''}`}
                    key={`${suggestion.company}-${suggestion.url}`}
                    role="button"
                    tabIndex={0}
                    aria-pressed={jobs.selectedJobUrl === suggestion.url}
                    onClick={() => jobs.openJob(suggestion)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        jobs.openJob(suggestion)
                      }
                    }}
                  >
                    <span className="job-mark" aria-hidden="true">{suggestion.company.slice(0, 1).toLocaleUpperCase('pt-PT')}</span>
                    <div className="suggestion-copy">
                      <strong>{suggestion.title}</strong>
                      <span className="suggestion-company">
                        {suggestion.company}
                        <span className={`job-rating ${suggestion.rating == null ? 'is-empty' : suggestion.rating >= 4 ? 'is-good' : ''}`}>
                          <Star size={12} /> {suggestion.rating != null ? ratingLabel(suggestion.rating, suggestion.review_count) : 'Sem opiniões'}
                        </span>
                      </span>
                      <div className="job-pills">
                        {jobPills(suggestion).map((pill, index) => (
                          <span key={`${pill}-${index}`}>{pill}</span>
                        ))}
                      </div>
                    </div>
                    <div className="job-card-actions">
                      <a className="button button-outline" href={suggestion.url} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()}>Ver vaga</a>
                      <JobActions suggestion={suggestion} />
                    </div>
                  </article>
                ))}
              </div>
              {jobs.suggestionPages > 1 && (
                <nav className="suggestion-pager" aria-label="Páginas de ofertas">
                  <button type="button" className="button button-outline" disabled={jobs.currentSuggestionPage <= 1} onClick={() => jobs.setSuggestionPage(jobs.currentSuggestionPage - 1)}>Anterior</button>
                  <span>{jobs.currentSuggestionPage} / {jobs.suggestionPages}</span>
                  <button type="button" className="button button-outline" disabled={jobs.currentSuggestionPage >= jobs.suggestionPages} onClick={() => jobs.setSuggestionPage(jobs.currentSuggestionPage + 1)}>Seguinte</button>
                </nav>
              )}
            </div>
          ) : !jobs.isAnalyzingCv ? (
            <div className="empty-state jobs-empty">
              <div className="empty-icon"><Search size={21} /></div>
              <h2>Sem ofertas desta vez</h2>
              <p>
                Não encontrámos vagas de {jobs.cvAnalysis.areas[0]?.name || 'esta profissão'} em {jobs.cvLocation || 'Portugal'}. Tenta outra localização ou um CV com o cargo mais explícito.
              </p>
            </div>
          ) : null}
        </div>
      )}
    </section>
  )
}

function searchMissNote(errors: string[]) {
  const names = [...new Set(errors.map((error) => error.match(/\(([^)]+)\)\s*$/)?.[1] || error))]
  if (names.length === 1) return `${names[0]} não respondeu desta vez. As outras fontes já estão na lista.`
  const last = names.pop()
  return `${names.join(', ')} e ${last} não responderam desta vez. As outras fontes já estão na lista.`
}

function FilterSelect({
  label,
  value,
  allLabel,
  allCount,
  options,
  onChange,
}: {
  label: string
  value: string
  allLabel: string
  allCount: number
  options: [string, number][]
  onChange: (value: string) => void
}) {
  return (
    <label className={`filter-select ${value ? 'is-active' : ''}`}>
      <span>{label}</span>
      <span className="filter-select-control">
        <select value={value} aria-label={label} onChange={(event) => onChange(event.target.value)}>
          <option value="">{allLabel} ({allCount})</option>
          {options.map(([name, count]) => (
            <option key={name} value={name}>{name} ({count})</option>
          ))}
        </select>
        <ChevronDown size={16} aria-hidden="true" />
      </span>
    </label>
  )
}

function ChoiceSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string
  options: [string, string][]
  onChange: (value: string) => void
}) {
  return (
    <label className={`filter-select ${value ? 'is-active' : ''}`}>
      <span>{label}</span>
      <span className="filter-select-control">
        <select value={value} aria-label={label} onChange={(event) => onChange(event.target.value)}>
          {options.map(([id, name]) => (
            <option key={id || 'all'} value={id}>{name}</option>
          ))}
        </select>
        <ChevronDown size={16} aria-hidden="true" />
      </span>
    </label>
  )
}

function JobActions({ suggestion }: { suggestion: JobSuggestion }) {
  const { jobs, saveJob, applyToJob, dismissJob } = useWorkspaceContext()
  const listed = jobs.listedContact(suggestion.company)
  const apply = applyJobAction(listed?.outreach_status)
  const busy = jobs.savingSuggestion === suggestion.url
  if (apply.done) {
    return <button className="button button-outline" type="button" disabled>{apply.label}</button>
  }
  return (
    <>
      <button className="button button-outline" type="button" disabled={busy || Boolean(listed)} onClick={(event) => { event.stopPropagation(); void saveJob(suggestion) }}>
        <Bookmark size={16} /> {listed ? 'Guardada' : 'Guardar'}
      </button>
      <button className="button button-primary" type="button" disabled={busy} onClick={(event) => { event.stopPropagation(); void applyToJob(suggestion) }}>
        {busy ? <RefreshCw className="spin" size={16} /> : <Send size={16} />}
        {busy ? 'A preparar…' : apply.label}
      </button>
      {!listed && (
        <button className="icon-button" type="button" title="Não me interessa" aria-label={`Não me interessa: ${suggestion.company}`} disabled={busy} onClick={(event) => { event.stopPropagation(); dismissJob(suggestion) }}>
          <X size={16} />
        </button>
      )}
    </>
  )
}
