import { useEffect, useState, type FormEvent, type KeyboardEvent } from 'react'
import { FileText, Pencil, Plus, RefreshCw, Trash2, X } from 'lucide-react'
import { useWorkspaceContext } from '../hooks/useWorkspaceContext'
import { MAX_PROFILE_AREAS, personInitials } from '../lib/format'
import type { CvArea } from '../types'

type AreaDraft = { name: string, skills: string[] }

type ProfileArea = Pick<CvArea, 'name' | 'matched_skills'> & { key?: string }

function toDraft(areas: ProfileArea[]): AreaDraft[] {
  return areas.map((area) => ({ name: area.name, skills: [...area.matched_skills] }))
}

function skillCount(areas: ProfileArea[]) {
  return areas.reduce((total, area) => total + area.matched_skills.length, 0)
}

function Avatar({ name, picture }: { name: string, picture: string | null }) {
  const [broken, setBroken] = useState(false)
  if (picture && !broken) {
    return <img className="profile-avatar" src={picture} alt="" referrerPolicy="no-referrer" onError={() => setBroken(true)} />
  }
  return <span className="profile-avatar">{personInitials(name)}</span>
}

export function ProfilePeek({ name, picture, areas }: { name: string, picture: string | null, areas: ProfileArea[] }) {
  const skills = areas.flatMap((area) => area.matched_skills)
  const uniqueSkills = [...new Set(skills)]
  return (
    <a className="jobs-stage-profile" href="#perfil">
      <Avatar name={name} picture={picture} />
      <p className="profile-kicker">O teu perfil</p>
      <strong>{name}</strong>
      <p>{areas.map((area) => area.name).join(' · ') || 'Perfil do CV'}</p>
      {uniqueSkills.length > 0 && (
        <div className="skill-chips is-display">
          {uniqueSkills.slice(0, 10).map((skill) => (
            <span className="skill-chip" key={skill}>{skill}</span>
          ))}
          {uniqueSkills.length > 10 && <span className="skill-chip">+{uniqueSkills.length - 10}</span>}
        </div>
      )}
      <span className="jobs-stage-link">{uniqueSkills.length} {uniqueSkills.length === 1 ? 'skill' : 'skills'} · Ver perfil</span>
    </a>
  )
}

export function ProfileCard({
  name,
  email,
  filename,
  picture,
  areas,
}: {
  name: string
  email: string
  filename: string
  picture: string | null
  areas: ProfileArea[]
}) {
  const { jobs } = useWorkspaceContext()
  const [draft, setDraft] = useState<AreaDraft[] | null>(null)
  const [skillDraft, setSkillDraft] = useState<Record<number, string>>({})
  const signature = areas.map((area) => `${area.name}:${area.matched_skills.join(',')}`).join('|')
  const skills = skillCount(areas)

  useEffect(() => {
    setDraft(null)
    setSkillDraft({})
  }, [signature])

  function updateArea(index: number, change: Partial<AreaDraft>) {
    setDraft((current) => current && current.map((area, position) => (position === index ? { ...area, ...change } : area)))
  }

  function excludeSkill(index: number, skill: string) {
    setDraft((current) => current && current.map((area, position) => (
      position === index ? { ...area, skills: area.skills.filter((item) => item !== skill) } : area
    )))
  }

  function clearSkills(index: number) {
    setDraft((current) => {
      if (!current) return current
      const area = current[index]
      if (area?.skills.length) {
        return current.map((item, position) => (position === index ? { ...item, skills: [] } : item))
      }
      if (current.length === 1) return current
      return current.filter((_, position) => position !== index)
    })
  }

  function addSkills(index: number, raw: string) {
    const pieces = raw.split(/[,;]+/).map((item) => item.trim()).filter(Boolean)
    if (!pieces.length) return
    setDraft((current) => current && current.map((area, position) => {
      if (position !== index) return area
      return { ...area, skills: [...area.skills, ...pieces.filter((item) => !area.skills.includes(item))] }
    }))
    setSkillDraft((current) => ({ ...current, [index]: '' }))
  }

  function onSkillKey(index: number, event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault()
      addSkills(index, event.currentTarget.value)
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!draft) return
    const saved = await jobs.saveProfile(draft.map((area) => ({
      name: area.name.trim(),
      skills: area.skills,
    })))
    if (saved) {
      setDraft(null)
      setSkillDraft({})
      window.location.hash = 'vagas'
    }
  }

  return (
    <div className="profile-page-layout">
      <header className="profile-hero">
        <Avatar name={name} picture={picture} />
        <div className="profile-hero-copy">
          <p className="profile-kicker">Perfil extraído do CV</p>
          <h2>{name}</h2>
          <p>{areas.map((area) => area.name).join(' · ') || 'Sem cargo ainda'}</p>
          <ul className="profile-meta">
            <li>{email}</li>
            <li><FileText size={14} /> {filename}</li>
            <li>{areas.length} {areas.length === 1 ? 'cargo' : 'cargos'}</li>
            <li>{skills} {skills === 1 ? 'skill' : 'skills'}</li>
          </ul>
        </div>
        {!draft && (
          <button className="button button-outline" type="button" disabled={jobs.isAnalyzingCv} onClick={() => setDraft(toDraft(areas))}>
            <Pencil size={15} /> Corrigir perfil
          </button>
        )}
      </header>

      {draft ? (
        <form className="profile-editor" onSubmit={(event) => void submit(event)}>
          <p>A IA tirou estes cargos do CV. Exclui skills ou cargos que não queres na pesquisa.</p>
          {draft.map((area, index) => (
            <div className="profile-editor-row" key={index}>
              <input
                value={area.name}
                onChange={(event) => updateArea(index, { name: event.target.value })}
                placeholder="Cargo extraído do CV"
                aria-label={`Cargo ${index + 1}`}
                maxLength={80}
              />
              <div className="skill-chips">
                {area.skills.map((skill) => (
                  <span className="skill-chip" key={skill}>
                    {skill}
                    <button type="button" aria-label={`Excluir ${skill}`} onClick={() => excludeSkill(index, skill)}>
                      <X size={12} />
                    </button>
                  </span>
                ))}
                <input
                  value={skillDraft[index] || ''}
                  onChange={(event) => setSkillDraft((current) => ({ ...current, [index]: event.target.value }))}
                  onKeyDown={(event) => onSkillKey(index, event)}
                  placeholder={area.skills.length ? 'Excluir acima, ou acrescentar' : 'Skill'}
                  aria-label={`Skills do cargo ${index + 1}`}
                />
              </div>
              <button
                className="icon-button"
                type="button"
                title={area.skills.length ? 'Limpar todas as skills' : draft.length === 1 ? 'Mantém pelo menos um cargo' : 'Excluir cargo'}
                aria-label={area.skills.length ? `Limpar skills do cargo ${index + 1}` : `Excluir cargo ${index + 1}`}
                disabled={!area.skills.length && draft.length === 1}
                onClick={() => clearSkills(index)}
              >
                <Trash2 size={15} />
              </button>
            </div>
          ))}
          <div className="profile-editor-actions">
            {draft.length < MAX_PROFILE_AREAS && (
              <button className="button button-quiet" type="button" onClick={() => setDraft([...draft, { name: '', skills: [] }])}>
                <Plus size={15} /> Adicionar cargo
              </button>
            )}
            <button className="button button-outline" type="button" onClick={() => { setDraft(null); setSkillDraft({}) }}>Cancelar</button>
            <button className="button button-primary" type="submit" disabled={jobs.isAnalyzingCv || draft.some((area) => area.name.trim().length < 2)}>
              {jobs.isAnalyzingCv && <RefreshCw className="spin" size={16} />} Guardar e procurar
            </button>
          </div>
        </form>
      ) : (
        <div className="profile-roles">
          {areas.map((area, index) => (
            <article className="profile-role" key={`${index}-${area.key || area.name}`}>
              <h3>{area.name}</h3>
              {area.matched_skills.length ? (
                <div className="skill-chips is-display">
                  {area.matched_skills.map((skill) => (
                    <span className="skill-chip" key={skill}>{skill}</span>
                  ))}
                </div>
              ) : (
                <p>Sem skills neste cargo.</p>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
