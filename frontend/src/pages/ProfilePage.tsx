import { Search, Upload } from 'lucide-react'
import { ProfileCard } from '../components/ProfileCard'
import { useWorkspaceContext } from '../hooks/useWorkspaceContext'

export function ProfilePage() {
  const { session, jobs } = useWorkspaceContext()

  if (!session.cv) {
    return (
      <section className="profile-page" aria-label="Perfil">
        <div className="empty-state jobs-empty">
          <div className="empty-icon"><Upload size={21} /></div>
          <h2>Ainda não há perfil</h2>
          <p>O perfil nasce do CV: cargos e skills extraídos, usados na pesquisa de vagas.</p>
          <a className="button button-primary" href="#vagas"><Search size={16} /> Ir para Vagas</a>
        </div>
      </section>
    )
  }

  const areas = jobs.cvAnalysis?.areas.length ? jobs.cvAnalysis.areas : session.cv.areas
  const name = jobs.cvAnalysis?.candidate_name || session.cv.candidate_name || session.user.name || session.user.email

  return (
    <section className="profile-page" aria-label="Perfil">
      <ProfileCard
        name={name}
        email={session.user.email}
        filename={session.cv.filename}
        picture={session.user.picture}
        areas={areas}
      />
    </section>
  )
}
