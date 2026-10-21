import { useEffect, useState } from 'react'
import { RefreshCw, X } from 'lucide-react'
import { AppShell } from './components/AppShell'
import { WorkspaceProvider } from './context/WorkspaceContext'
import { useWorkspaceContext } from './hooks/useWorkspaceContext'
import { request } from './lib/api'
import { legalFromHash, loginNotice } from './lib/format'
import { ContactsPage } from './pages/ContactsPage'
import { JobsPage } from './pages/JobsPage'
import { LegalPage } from './pages/LegalPage'
import { LoginPage } from './pages/LoginPage'
import { ProfilePage } from './pages/ProfilePage'
import type { Session } from './types'
import './dashboard.css'

function AuthenticatedApp({ onLogout }: { onLogout: () => void }) {
  const { page, outreach } = useWorkspaceContext()

  return (
    <AppShell onLogout={onLogout}>
      {outreach.error && (page === 'vagas' || outreach.contacts.length > 0) && (
        <div className="notice notice-error" role="alert">
          <span><strong>Não foi possível concluir o pedido.</strong> {outreach.error}</span>
          <button className="icon-button" type="button" aria-label="Fechar aviso" onClick={() => outreach.setError(null)}><X size={16} /></button>
        </div>
      )}
      {page === 'vagas' ? <JobsPage /> : page === 'contactos' ? <ContactsPage /> : <ProfilePage />}
    </AppShell>
  )
}

function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [isChecking, setIsChecking] = useState(true)
  const [notice] = useState(loginNotice())
  const [legal, setLegal] = useState(legalFromHash())

  async function refreshSession() {
    setSession(await request<Session>('/auth/me'))
  }

  useEffect(() => {
    let isActive = true
    request<Session>('/auth/me')
      .then((data) => {
        if (!isActive) return
        setSession(data)
        if (window.location.search) {
          window.history.replaceState({}, '', window.location.pathname)
        }
      })
      .catch(() => undefined)
      .finally(() => { if (isActive) setIsChecking(false) })

    const expire = () => setSession(null)
    const syncLegal = () => setLegal(legalFromHash())
    window.addEventListener('ponto:unauthorized', expire)
    window.addEventListener('hashchange', syncLegal)
    return () => {
      isActive = false
      window.removeEventListener('ponto:unauthorized', expire)
      window.removeEventListener('hashchange', syncLegal)
    }
  }, [])

  async function logout() {
    await request('/auth/logout', { method: 'POST' }).catch(() => undefined)
    setSession(null)
  }

  if (legal) return <LegalPage kind={legal} />
  if (isChecking) return <main className="login-screen"><RefreshCw className="spin" size={22} /></main>
  if (!session) return <LoginPage notice={notice} />

  return (
    <WorkspaceProvider key={session.user.email} session={session} onSessionChange={refreshSession}>
      <AuthenticatedApp onLogout={() => void logout()} />
    </WorkspaceProvider>
  )
}

export default App
