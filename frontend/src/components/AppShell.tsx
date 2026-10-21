import { ClipboardList, Download, LogOut, Mail, UserRound, Users, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useWorkspaceContext } from '../hooks/useWorkspaceContext'
import { request } from '../lib/api'
import { contactKey } from '../lib/format'
import { DetailPanel } from './DetailPanel'
import { NewContactModal } from './NewContactModal'
import { ApplyLoader, SearchLoader } from './SearchLoader'
import { Toast } from './Toast'

export function AppShell({
  onLogout,
  children,
}: {
  onLogout: () => void
  children: ReactNode
}) {
  const { session, page, google, toast, jobs, composer, outreach } = useWorkspaceContext()
  const [accountOpen, setAccountOpen] = useState(false)
  const applyDraft = composer.contactDraft
  const applyContact = applyDraft
    ? outreach.contacts.find((contact) => contactKey(contact) === applyDraft.key)
    : null
  const isApplying = Boolean(applyDraft?.isLoading || composer.isSending)

  async function exportData() {
    try {
      const data = await request<unknown>('/auth/export')
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'ponto-dados.json'
      link.click()
      URL.revokeObjectURL(url)
      toast.showToast('success', 'Dados exportados.')
      setAccountOpen(false)
    } catch (error) {
      toast.showToast('error', error instanceof Error ? error.message : 'Não foi possível exportar os dados.')
    }
  }

  return (
    <div className="app-shell">
      <aside className="rail" aria-label="Navegação principal">
        <a className="brand-mark" href="#vagas" aria-label="Ponto">
          <span>p</span>
        </a>
        <nav className="rail-nav" aria-label="Páginas">
          <a className={`rail-link ${page === 'vagas' ? 'is-active' : ''}`} href="#vagas" title="Vagas" aria-label="Vagas" aria-current={page === 'vagas' ? 'page' : undefined}>
            <ClipboardList size={19} strokeWidth={1.8} />
          </a>
          <a className={`rail-link ${page === 'contactos' ? 'is-active' : ''}`} href="#contactos" title="Contactos" aria-label="Contactos" aria-current={page === 'contactos' ? 'page' : undefined}>
            <Users size={19} strokeWidth={1.8} />
          </a>
          <a className={`rail-link ${page === 'perfil' ? 'is-active' : ''}`} href="#perfil" title="Perfil" aria-label="Perfil" aria-current={page === 'perfil' ? 'page' : undefined}>
            <UserRound size={19} strokeWidth={1.8} />
          </a>
        </nav>
        <div className="rail-spacer" />
        <div className="rail-account">
          <button
            className={`rail-avatar ${accountOpen ? 'is-open' : ''}`}
            type="button"
            aria-label="Conta"
            aria-expanded={accountOpen}
            title={session.user.email}
            onClick={() => setAccountOpen((open) => !open)}
          >
            {(session.user.name || session.user.email).charAt(0).toUpperCase()}
          </button>
          {accountOpen && (
            <div className="account-panel" role="dialog" aria-label="Conta">
              <div className="google-panel-heading">
                <strong>{session.user.name || session.user.email}</strong>
                <button className="button button-quiet" type="button" aria-label="Fechar" onClick={() => setAccountOpen(false)}><X size={16} /></button>
              </div>
              <p>{session.user.email}</p>
              <p>
                <a href="#termos">Termos</a>
                {' · '}
                <a href="#privacidade">Privacidade</a>
              </p>
              <button className="button button-outline" type="button" onClick={() => void exportData()}>
                <Download size={16} />Exportar dados
              </button>
              <button
                className="button button-danger"
                type="button"
                onClick={() => toast.askConfirm(
                  'Isto apaga a conta, o CV, a lista de contactos e a sessão. Não dá para desfazer.',
                  'Apagar conta',
                  () => {
                    void request('/auth/account', { method: 'DELETE' })
                      .then(() => onLogout())
                      .catch((error: Error) => toast.showToast('error', error.message))
                  },
                )}
              >
                Apagar conta
              </button>
            </div>
          )}
        </div>
      </aside>

      <main className="workspace" id={page}>
        <header className="topbar">
          <div className="breadcrumb"><h1>{page === 'vagas' ? 'Vagas' : page === 'contactos' ? 'Contactos' : 'Perfil'}</h1></div>
          <div className="topbar-actions">
            <button className={`button button-outline ${google.googleStatus?.connected ? 'is-connected' : ''} ${google.needsReplyAccess ? 'needs-setup' : ''}`} type="button" aria-expanded={google.googlePanelOpen} onClick={() => google.setGooglePanelOpen((open) => !open)}>
              <Mail size={16} />{google.googleStatus?.connected ? (google.googleStatus.email || 'Gmail') : 'Ligar Gmail'}
            </button>
            {google.googlePanelOpen && (
              <div className="google-panel" role="dialog" aria-label="Conta Google">
                <div className="google-panel-heading"><strong>Gmail</strong><button className="button button-quiet" type="button" aria-label="Fechar" onClick={() => google.setGooglePanelOpen(false)}><X size={16} /></button></div>
                {!google.googleStatus ? <p>A API não respondeu.</p> : !google.googleStatus.configured ? (
                  <p>Define as credenciais Google no backend e reinicia o servidor.</p>
                ) : google.googleStatus.connected ? (
                  <>
                    {google.googleStatus.can_follow_replies ? (
                      <p>Ligado como <strong>{google.googleStatus.email || 'conta Google'}</strong>. As respostas da empresa passam para a lista de contactos.</p>
                    ) : (
                      <p>
                        Já podes enviar candidaturas com esta conta.
                        Para a app ver sozinha se a empresa respondeu, o Google pede uma permissão extra: ler o correio. O login normal não chega.
                      </p>
                    )}
                    {!google.googleStatus.can_follow_replies && (
                      <button className="button button-primary" type="button" onClick={() => void google.reconnectGoogle()}>Permitir ler respostas</button>
                    )}
                    <button className="button button-outline" type="button" onClick={() => void google.disconnectGoogle()}>Desligar Gmail</button>
                  </>
                ) : (
                  <>
                    <p>Liga a conta para enviar candidaturas e ver as respostas no Gmail.</p>
                    <button className="button button-primary" type="button" onClick={google.connectGoogle}>Ligar Google</button>
                  </>
                )}
              </div>
            )}
          </div>
          <button className="button button-outline" type="button" onClick={onLogout}><LogOut size={16} />Sair</button>
        </header>
        <div className="page-content">{children}</div>
      </main>

      <DetailPanel />
      {jobs.isAnalyzingCv && <SearchLoader analysis={jobs.cvAnalysis} location={jobs.cvLocation} />}
      {!jobs.isAnalyzingCv && isApplying && (
        <ApplyLoader
          company={applyContact?.name_company || 'a empresa'}
          role={applyContact?.job_title}
          sending={composer.isSending}
        />
      )}
      {toast.toast && <Toast toast={toast.toast} onClose={() => toast.setToast(null)} />}
      <NewContactModal />
    </div>
  )
}
