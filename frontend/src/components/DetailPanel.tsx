import {
  ArrowUpRight,
  Bookmark,
  Building2,
  Copy,
  ExternalLink,
  FileText,
  Mail,
  MapPin,
  RefreshCw,
  Search,
  Send,
  Sparkles,
  Star,
  Trash2,
  X,
} from 'lucide-react'
import { useEffect } from 'react'
import { useWorkspaceContext } from '../hooks/useWorkspaceContext'
import { contactKey, contactTypeLabels, jobBlurb, jobFacts, ratingLabel, statusLabels } from '../lib/format'
import type { OutreachStatus } from '../types'

export function DetailPanel() {
  const {
    page,
    google,
    outreach,
    jobs,
    composer,
    selectedContact,
    selectedSuggestion,
    saveJob,
    applyToJob,
    dismissJob,
    closePanel,
    removeFromList,
  } = useWorkspaceContext()

  const showPanel = (page === 'contactos' && selectedContact) || (page === 'vagas' && selectedSuggestion)
  const selectedKey = selectedContact ? contactKey(selectedContact) : null
  const draft = composer.contactDraft?.key === selectedKey ? composer.contactDraft : null
  const emailFoundAt = selectedContact?.source_url ? new URL(selectedContact.source_url).hostname.replace(/^www\./, '') : null
  const draftReady = Boolean(draft && !draft.isLoading && draft.subject.trim() && draft.body.trim())
  const jobApplyBusy = selectedSuggestion ? jobs.savingSuggestion === selectedSuggestion.url : false

  useEffect(() => {
    if (page !== 'contactos' || !selectedContact) return
    void outreach.loadReply(selectedContact)
  }, [page, selectedContact?.id_company, selectedContact?.id_contact, selectedContact?.outreach_status])

  if (!showPanel) return null

  return (
    <aside className="detail-panel" aria-label={selectedContact ? 'Detalhes do contacto selecionado' : 'Detalhes da vaga'}>
      <div className="detail-topline">
        <span>{selectedContact ? 'Contacto' : 'Vaga'}</span>
        <button className="icon-button detail-close" type="button" onClick={closePanel} aria-label="Fechar detalhe"><X size={17} /></button>
      </div>
      {selectedContact ? (
        <>
          <div className="detail-company-mark">{selectedContact.name_company.slice(0, 1).toLocaleUpperCase('pt-PT')}</div>
          <h2>{selectedContact.name_company}</h2>
          <p className="detail-contact-name">{selectedContact.name_contact || (selectedContact.email ? 'Email disponível' : 'Contacto por identificar')}</p>
          {selectedContact.job_title && <p className="detail-role">{selectedContact.job_title}{selectedContact.job_seen_at ? '' : ' · por ver'}</p>}
          {selectedContact.role_contact && <p className="detail-role">{selectedContact.role_contact}</p>}

          <div className="detail-divider" />
          <div className="detail-field">
            <span className="detail-label"><Mail size={14} /> Email</span>
            {selectedContact.email ? (
              <>
                <div className="detail-email-row">
                  <a href={`mailto:${selectedContact.email}`}>{selectedContact.email}</a>
                  <button className="icon-button" type="button" title="Copiar email" aria-label="Copiar email" onClick={() => void composer.copyEmail(selectedContact.email!)}><Copy size={15} /></button>
                </div>
                {selectedContact.contact_type !== 'careers' && (
                  <p className="composer-hint">
                    Caixa geral{emailFoundAt ? `, encontrada em ${emailFoundAt}` : ''}. Confirma que é desta empresa antes de enviar.
                  </p>
                )}
              </>
            ) : (
              <span className="detail-empty">
                {selectedContact.outreach_status === 'no_email'
                  ? 'Não encontrado automaticamente. Cola o site da empresa ou o email de carreiras.'
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
            {selectedContact.source_url ? (
              <a
                className="source-detail-link"
                href={selectedContact.source_url}
                target="_blank"
                rel="noreferrer"
                onClick={() => {
                  if (selectedContact.id_jobPosting) void outreach.markJobSeen(selectedContact.id_jobPosting)
                }}
              >
                Abrir página de origem <ArrowUpRight size={14} />
              </a>
            ) : <span className="detail-empty">Fonte não registada</span>}
          </div>

          <form className="detail-website-form" key={selectedContact.id_company} onSubmit={(event) => void outreach.findEmail(selectedContact, event)}>
            <label className="detail-label" htmlFor="detail-website"><ExternalLink size={14} /> Site ou email</label>
            <input
              id="detail-website"
              type="text"
              inputMode="url"
              placeholder={selectedContact.website_url || 'exemplo.com ou carreiras@empresa.pt'}
              value={outreach.websiteDraft.idCompany === selectedContact.id_company ? outreach.websiteDraft.value : ''}
              onChange={(event) => outreach.setWebsiteDraft({ idCompany: selectedContact.id_company, value: event.target.value })}
            />
            <button className="button button-outline" type="submit" disabled={outreach.isSearchingEmail}>
              {outreach.isSearchingEmail ? <RefreshCw className="spin" size={14} /> : <Search size={14} />}
              {(outreach.websiteDraft.idCompany === selectedContact.id_company ? outreach.websiteDraft.value : '').includes('@') ? 'Guardar email' : 'Procurar email'}
            </button>
          </form>

          {(selectedContact.outreach_status === 'replied' || selectedContact.outreach_status === 'rejected') && (
            <>
              <div className="detail-divider" />
              <div className="reply-section">
                <span className="detail-label"><Mail size={14} /> Resposta</span>
                {outreach.mailReply?.key === selectedKey && outreach.mailReply.isLoading ? (
                  <p className="composer-hint"><RefreshCw className="spin" size={14} /> A ler o Gmail…</p>
                ) : outreach.mailReply?.key === selectedKey && outreach.mailReply.error ? (
                  <p className="composer-hint">{outreach.mailReply.error}</p>
                ) : outreach.mailReply?.key === selectedKey && outreach.mailReply.message ? (
                  <ReplyCard
                    sender={outreach.mailReply.message.sender}
                    subject={outreach.mailReply.message.subject}
                    body={outreach.mailReply.message.body}
                    sentAt={outreach.mailReply.message.sent_at}
                  />
                ) : (
                  <p className="composer-hint">Sem texto da resposta neste Gmail.</p>
                )}
              </div>
            </>
          )}

          <div className="detail-divider" />
          <div className="email-composer">
            <div className="composer-heading">
              <span className="detail-label"><Mail size={14} /> Email de candidatura</span>
              {selectedContact.outreach_status !== 'rejected' && (
                <div className="language-toggle" role="group" aria-label="Idioma do email">
                  <button type="button" className={composer.draftLanguage === 'pt' ? 'is-active' : ''} aria-pressed={composer.draftLanguage === 'pt'} onClick={() => composer.changeDraftLanguage('pt')}>PT</button>
                  <button type="button" className={composer.draftLanguage === 'en' ? 'is-active' : ''} aria-pressed={composer.draftLanguage === 'en'} onClick={() => composer.changeDraftLanguage('en')}>EN</button>
                </div>
              )}
            </div>
            {selectedContact.outreach_status === 'rejected' ? (
              <p className="composer-hint">Candidatura não selecionada. Enviar e gerar rascunho ficam desativados.</p>
            ) : !composer.profile ? (
              <p className="composer-hint">Analisa o teu CV primeiro para a IA redigir a candidatura.</p>
            ) : !draft ? (
              <button className="button button-primary composer-generate" type="button" onClick={() => void composer.draftForContact(selectedContact)}>
                <Sparkles size={14} /> Escrever candidatura
              </button>
            ) : draft.isLoading ? (
              <p className="composer-hint"><RefreshCw className="spin" size={14} /> A escrever o rascunho…</p>
            ) : (
              <>
                {draft.fitReason ? <p className="composer-fit"><strong>Afinidade {draft.fitScore}/100</strong> {draft.fitReason}</p> : null}
                {draft.skipped ? (
                  <p className="composer-hint">Afinidade baixa: não foi gerado email para esta vaga.</p>
                ) : (
                  <>
                    <input
                      className="composer-subject"
                      aria-label="Assunto"
                      value={draft.subject}
                      onChange={(event) => composer.setContactDraft({ ...draft, subject: event.target.value })}
                    />
                    <textarea
                      className="composer-body"
                      aria-label="Corpo do email"
                      rows={9}
                      value={draft.body}
                      onChange={(event) => composer.setContactDraft({ ...draft, body: event.target.value })}
                    />
                  </>
                )}
                <div className="composer-actions">
                  {google.googleStatus?.connected ? (
                    <button
                      className="button button-primary"
                      type="button"
                      disabled={!selectedContact.email || !draftReady || composer.isSending}
                      title={selectedContact.email ? `Enviar para ${selectedContact.email}` : 'Esta empresa ainda não tem email'}
                      onClick={() => composer.sendApplication(selectedContact)}
                    >
                      {composer.isSending ? <RefreshCw className="spin" size={14} /> : <Send size={14} />}
                      {composer.isSending ? 'A enviar…' : 'Enviar candidatura'}
                    </button>
                  ) : (
                    <button className="button button-primary" type="button" onClick={google.connectGoogle}>
                      <Mail size={14} /> Ligar Gmail para enviar
                    </button>
                  )}
                  <button className="button button-outline" type="button" disabled={composer.isSending} onClick={() => void composer.draftForContact(selectedContact)}>
                    <Sparkles size={14} /> Gerar de novo
                  </button>
                </div>
              </>
            )}
          </div>

          <div className="detail-divider" />
          <label className="detail-label status-detail-label" htmlFor="detail-status">Estado da prospeção</label>
          <select
            className="detail-status-control"
            id="detail-status"
            value={selectedContact.outreach_status}
            onChange={(event) => void outreach.updateStatus(selectedContact, event.target.value as OutreachStatus)}
          >
            {Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <button className="button button-outline detail-remove" type="button" onClick={() => removeFromList(selectedContact)}>
            <Trash2 size={14} /> Retirar da lista
          </button>
          <div className="detail-tip"><FileText size={15} /><span>{selectedContact.outreach_status === 'rejected' ? 'Esta vaga ficou na lista Sem sucesso. Podes voltar a movê-la no estado da prospeção.' : `A IA escreve um rascunho que podes editar. Só é enviado pelo Gmail para ${selectedContact.email || 'o contacto da empresa'}, com o CV anexado, quando carregares em Enviar.`}</span></div>
        </>
      ) : selectedSuggestion ? (
        <>
          <div className="detail-company-mark">{selectedSuggestion.company.slice(0, 1).toLocaleUpperCase('pt-PT')}</div>
          <h2>{selectedSuggestion.title}</h2>
          <p className="detail-role">{selectedSuggestion.company}</p>

          <dl className="job-facts">
            {jobFacts(selectedSuggestion).map((fact) => (
              <div className={fact.label === 'Salário' && selectedSuggestion.salary ? 'is-pay' : undefined} key={fact.label}>
                <dt>{fact.label}</dt>
                <dd>{fact.value}</dd>
              </div>
            ))}
          </dl>

          <div className="detail-field">
            <span className="detail-label"><FileText size={14} /> Sobre a vaga</span>
            <p className="detail-summary">{jobBlurb(selectedSuggestion) || 'Abre o anúncio para a descrição completa.'}</p>
          </div>

          <div className="company-insight">
            <p>
              <Star size={14} /> {selectedSuggestion.rating != null
                ? `${ratingLabel(selectedSuggestion.rating, selectedSuggestion.review_count)} no Teamlyzer`
                : 'Sem opiniões nesta fonte'}
            </p>
            <span>Opiniões de quem lá trabalha ou se candidatou — úteis antes de enviares o email.</span>
            {selectedSuggestion.company_url && (
              <a className="source-detail-link" href={selectedSuggestion.company_url} target="_blank" rel="noreferrer">
                Ler opiniões da empresa <ArrowUpRight size={14} />
              </a>
            )}
          </div>

          <div className="detail-divider" />
          <div className="detail-field">
            <span className="detail-label"><FileText size={14} /> No teu CV</span>
            {selectedSuggestion.matched_skills.length > 0 ? (
              <div className="skill-chips is-display">
                {selectedSuggestion.matched_skills.map((skill) => (
                  <span className="skill-chip" key={skill}>{skill}</span>
                ))}
              </div>
            ) : (
              <span className="detail-empty">Nenhuma skill desta vaga aparece no CV.</span>
            )}
          </div>
          <div className="detail-field">
            <span className="detail-label"><Mail size={14} /> Email</span>
            {selectedSuggestion.email ? (
              <div className="detail-email-row">
                <a href={`mailto:${selectedSuggestion.email}`}>{selectedSuggestion.email}</a>
                <button className="icon-button" type="button" title="Copiar email" aria-label="Copiar email" onClick={() => void composer.copyEmail(selectedSuggestion.email!)}><Copy size={15} /></button>
              </div>
            ) : <span className="detail-empty">Ainda não encontrado. Ao guardar ou candidatar, procuramos o email no site da empresa.</span>}
          </div>
          <div className="detail-field">
            <span className="detail-label"><ExternalLink size={14} /> Anúncio</span>
            <a className="source-detail-link" href={selectedSuggestion.url} target="_blank" rel="noreferrer">
              Abrir no {selectedSuggestion.source} <ArrowUpRight size={14} />
            </a>
          </div>

          <div className="detail-divider" />
          <div className="composer-actions">
            <button className="button button-primary" type="button" disabled={jobApplyBusy} onClick={() => void applyToJob(selectedSuggestion)}>
              {jobApplyBusy ? <RefreshCw className="spin" size={16} /> : <Send size={16} />}
              {jobApplyBusy ? 'A preparar…' : 'Candidatar'}
            </button>
            <button className="button button-outline" type="button" disabled={jobApplyBusy} onClick={() => void saveJob(selectedSuggestion)}>
              <Bookmark size={16} /> Guardar
            </button>
          </div>
          <button className="button button-quiet detail-remove" type="button" disabled={jobApplyBusy} onClick={() => dismissJob(selectedSuggestion)}>
            <X size={14} /> Não me interessa
          </button>
          <div className="detail-tip"><FileText size={15} /><span>A IA escreve um rascunho com base no teu CV. Revês e editas antes de o enviar pelo Gmail.</span></div>
        </>
      ) : null}
    </aside>
  )
}

function ReplyCard({ sender, subject, body, sentAt }: { sender: string, subject: string, body: string, sentAt: string | null }) {
  const from = senderParts(sender)
  const paragraphs = replyParagraphs(body)
  const when = formatReplyDate(sentAt)
  return (
    <article className="reply-card">
      <header className="reply-card-head">
        <div className="reply-from-row">
          <span className="reply-avatar" aria-hidden="true">{from.name.slice(0, 1).toLocaleUpperCase('pt-PT')}</span>
          <div>
            <p className="reply-from">{from.name}</p>
            {from.email ? <p className="reply-from-email">{from.email}</p> : null}
          </div>
        </div>
        {subject ? <p className="reply-subject">{subject}</p> : null}
        {when ? <p className="reply-date">{when}</p> : null}
      </header>
      <div className="reply-body">
        {paragraphs.length ? paragraphs.map((paragraph, index) => <p key={index}>{paragraph}</p>) : <p>A mensagem não tem texto visível.</p>}
      </div>
    </article>
  )
}

function senderParts(from: string): { name: string, email: string } {
  const match = from.match(/^(.*?)\s*<([^>]+)>\s*$/)
  if (!match) return { name: from, email: '' }
  return { name: match[1].replace(/^["']|["']$/g, '').trim() || match[2], email: match[2] }
}

function replyParagraphs(body: string): string[] {
  return body.split(/\n+/).map((line) => line.trim()).filter(Boolean)
}

function formatReplyDate(value: string | null): string | null {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleString('pt-PT', { dateStyle: 'medium', timeStyle: 'short' })
}
