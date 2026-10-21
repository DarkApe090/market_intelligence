import { ChevronDown, CircleAlert, ExternalLink, Mail, Plus, RefreshCw, Search, Trash2, Users } from 'lucide-react'
import { useWorkspaceContext } from '../hooks/useWorkspaceContext'
import { contactKey, contactTypeLabels, daysAgo, statusLabels } from '../lib/format'
import type { OutreachStatus, StatusFilter } from '../types'

const FILTERS: [StatusFilter, string][] = [
  ['all', 'Todos'],
  ['to_contact', 'Por contactar'],
  ['sent', 'Enviados'],
  ['replied', 'Respostas'],
  ['rejected', 'Sem sucesso'],
  ['no_email', 'Sem email'],
]

export function ContactsPage() {
  const { google, outreach, jobs, removeFromList } = useWorkspaceContext()

  return (
    <section className="list-section" aria-label="Contactos de prospeção">
      <div className="page-intro">
        <div className="page-intro-lead">
          <span className="page-intro-mark" aria-hidden="true"><Users size={20} /></span>
          <p>Empresas da lista de prospeção, com o estado de cada candidatura.</p>
          <div className="list-heading-actions">
            <label className="search-field">
              <Search size={16} />
              <input
                type="search"
                placeholder="Pesquisar empresa ou email"
                value={outreach.search}
                onChange={(event) => outreach.setSearch(event.target.value)}
                aria-label="Pesquisar contactos"
              />
            </label>
            <button className="button button-primary" type="button" onClick={() => outreach.setFormOpen(true)}>
              <Plus size={16} /> Novo contacto
            </button>
          </div>
        </div>
        <div className="filter-tabs" role="tablist" aria-label="Filtrar por estado">
          {FILTERS.map(([filter, label]) => (
            <button
              className={`filter-tab ${outreach.activeFilter === filter ? 'is-selected' : ''}`}
              key={filter}
              type="button"
              role="tab"
              aria-selected={outreach.activeFilter === filter}
              onClick={() => outreach.setActiveFilter(filter)}
            >
              {label}<span>{outreach.counts[filter]}</span>
            </button>
          ))}
        </div>
      </div>

      {!google.googleStatus?.connected && (
        <p className="search-warning">Liga o Gmail no topo para enviar candidaturas e para a aba Respostas se preencher sozinha.</p>
      )}
      {google.googleStatus?.connected && google.googleStatus.can_follow_replies === false && (
        <p className="search-warning">O Gmail já envia. Para ver as respostas das empresas, abre Gmail no topo e permite ler o correio — sair e voltar a entrar não chega.</p>
      )}

      <div className="table-scroll">
        <table className="contact-table">
          <thead>
            <tr>
              <th scope="col">Empresa / contacto</th>
              <th scope="col">Email</th>
              <th scope="col">Tipo</th>
              <th scope="col">Estado</th>
              <th scope="col">Ações</th>
            </tr>
          </thead>
          <tbody>
            {outreach.visibleContacts.map((contact) => (
              <tr
                className={outreach.selectedKey === contactKey(contact) ? 'is-current' : ''}
                key={contactKey(contact)}
                onClick={() => {
                  jobs.setSelectedJobUrl(null)
                  outreach.setSelectedKey((current) => (current === contactKey(contact) ? null : contactKey(contact)))
                }}
              >
                <td>
                  <div className="company-copy">
                    <strong>
                      {contact.name_company}
                      {contact.id_jobPosting && !contact.job_seen_at ? <span className="job-unseen">Por ver</span> : null}
                    </strong>
                    <small>{contact.job_title || contact.name_contact || contact.role_contact || (contact.email ? 'Email disponível' : 'Contacto por identificar')}</small>
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
                    <span className="status-select-control">
                      <select
                        value={contact.outreach_status}
                        aria-label={`Estado de ${contact.name_company}`}
                        onChange={(event) => void outreach.updateStatus(contact, event.target.value as OutreachStatus)}
                      >
                        {Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                      </select>
                      <ChevronDown size={13} aria-hidden="true" />
                    </span>
                  </label>
                  {contact.sent_at && <small className="status-age">enviado {daysAgo(contact.sent_at)}</small>}
                </td>
                <td className="source-cell">
                  {contact.source_url ? (
                    <a
                      className="source-button"
                      href={contact.source_url}
                      target="_blank"
                      rel="noreferrer"
                      title="Abrir fonte"
                      aria-label={`Abrir fonte de ${contact.name_company}`}
                      onClick={(event) => {
                        event.stopPropagation()
                        if (contact.id_jobPosting) void outreach.markJobSeen(contact.id_jobPosting)
                      }}
                    >
                      <ExternalLink size={15} />
                    </a>
                  ) : <span className="source-missing">—</span>}
                  <button className="source-button write-button" type="button" title="Escrever email" aria-label={`Escrever email para ${contact.name_company}`} onClick={(event) => { event.stopPropagation(); jobs.setSelectedJobUrl(null); outreach.setSelectedKey(contactKey(contact)) }}>
                    <Mail size={15} />
                  </button>
                  <button className="source-button remove-button" type="button" title="Retirar da lista" aria-label={`Retirar ${contact.name_company} da lista`} onClick={(event) => { event.stopPropagation(); removeFromList(contact) }}>
                    <Trash2 size={15} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {outreach.isLoading && <div className="table-message"><RefreshCw className="spin" size={18} /> A carregar a lista...</div>}
        {!outreach.isLoading && outreach.error && outreach.contacts.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon"><CircleAlert size={21} /></div>
            <h2>Não foi possível ligar à API</h2>
            <p>Confirma se o backend está ativo em localhost:8000 e tenta novamente.</p>
            <button className="button button-outline" type="button" onClick={() => void outreach.loadContacts(true)} disabled={outreach.isRefreshing}>
              <RefreshCw size={15} className={outreach.isRefreshing ? 'spin' : ''} /> Tentar novamente
            </button>
          </div>
        )}
        {!outreach.isLoading && !outreach.error && outreach.visibleContacts.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon"><Users size={21} /></div>
            <h2>{outreach.contacts.length ? 'Sem resultados para esta pesquisa' : 'A lista começa aqui'}</h2>
            <p>{outreach.contacts.length ? 'Experimenta outro termo ou estado.' : 'Adiciona uma empresa e o respetivo contacto de carreiras.'}</p>
            {!outreach.contacts.length && <button className="button button-outline" type="button" onClick={() => outreach.setFormOpen(true)}><Plus size={16} /> Adicionar primeiro contacto</button>}
          </div>
        )}
      </div>
    </section>
  )
}
