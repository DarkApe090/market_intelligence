import type { CvAnalysis } from '../types'

function ProcessLoader({
  heading,
  detail,
  lines,
  variant = 'search',
}: {
  heading: string
  detail: string
  lines: [string, string, string]
  variant?: 'search' | 'apply'
}) {
  return (
    <div className="modal-backdrop search-loader-backdrop" role="status" aria-live="polite" aria-busy="true">
      <section className={`search-loader ${variant === 'apply' ? 'is-apply' : ''}`} aria-labelledby="search-loader-title">
        <div className="search-loader-scene" aria-hidden="true">
          <span className="search-loader-orb" />
          <span className="search-loader-card search-loader-card-1" />
          <span className="search-loader-card search-loader-card-2" />
          <span className="search-loader-card search-loader-card-3">
            {variant === 'apply' ? <span className="search-loader-stamp" /> : null}
          </span>
        </div>
        <h2 id="search-loader-title">{heading}</h2>
        <p>{detail}</p>
        <div className="search-loader-lines" aria-hidden="true">
          <span>{lines[0]}</span>
          <span>{lines[1]}</span>
          <span>{lines[2]}</span>
        </div>
        <div className="search-loader-dots" aria-hidden="true"><span /><span /><span /></div>
      </section>
    </div>
  )
}

export function SearchLoader({
  analysis,
  location,
}: {
  analysis: CvAnalysis | null
  location: string
}) {
  const area = analysis?.areas[0]?.name
  const found = analysis?.suggestions.length || 0
  const place = location.trim() || 'Portugal'
  const heading = area ? 'A procurar vagas' : 'A ler o currículo'
  const detail = found
    ? `${found} ${found === 1 ? 'oferta encontrada' : 'ofertas encontradas'} em ${place}.`
    : area
      ? `A cruzar ${area} com anúncios em ${place}.`
      : 'A extrair o perfil do currículo para procurar ofertas alinhadas.'

  return (
    <ProcessLoader
      heading={heading}
      detail={detail}
      lines={[
        'A consultar as fontes de emprego',
        'A filtrar por localização',
        'A escolher o melhor anúncio de cada empresa',
      ]}
    />
  )
}

export function ApplyLoader({
  company,
  role,
  sending,
}: {
  company: string
  role?: string | null
  sending: boolean
}) {
  const target = role ? `${company} · ${role}` : company
  const heading = sending ? 'A enviar a candidatura' : 'A escrever o rascunho'
  const detail = sending
    ? `A enviar o email para ${target}.`
    : `A IA está a escrever um rascunho para ${target}. Revês antes de enviar.`

  return (
    <ProcessLoader
      variant="apply"
      heading={heading}
      detail={detail}
      lines={sending
        ? ['A anexar o currículo', 'A enviar pelo Gmail', 'A confirmar a entrega']
        : ['A avaliar a afinidade com a vaga', 'A escrever o email com o CV', 'A preparar o rascunho']}
    />
  )
}
