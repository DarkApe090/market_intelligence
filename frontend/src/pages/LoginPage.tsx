import { useState } from 'react'
import { Mail } from 'lucide-react'
import { API_URL } from '../lib/api'

export function LoginPage({ notice }: { notice: string | null }) {
  const [accepted, setAccepted] = useState(false)
  const [error, setError] = useState<string | null>(notice)

  function signIn() {
    if (!accepted) {
      setError('Aceita os termos e a política de privacidade para entrar.')
      return
    }
    window.location.href = `${API_URL}/auth/login?accepted=1`
  }

  return (
    <main className="login-screen">
      <section className="login-card">
        <span className="brand-mark"><span>p</span></span>
        <h1>Ponto</h1>
        <p>Entra para ver a tua lista, o CV guardado e o Gmail.</p>
        <label className="login-consent">
          <input
            type="checkbox"
            checked={accepted}
            onChange={(event) => {
              setAccepted(event.target.checked)
              if (event.target.checked) setError(notice)
            }}
          />
          <span>
            Li e aceito os <a href="#termos">termos</a> e a <a href="#privacidade">política de privacidade</a>.
          </span>
        </label>
        <button className="button button-primary" type="button" disabled={!accepted} onClick={signIn}>
          <Mail size={16} />Entrar com Google
        </button>
        {error && <div className="notice notice-error" role="alert"><span>{error}</span></div>}
      </section>
    </main>
  )
}
