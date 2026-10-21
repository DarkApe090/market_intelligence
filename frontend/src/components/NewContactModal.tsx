import { Plus, RefreshCw, X } from 'lucide-react'
import { useWorkspaceContext } from '../hooks/useWorkspaceContext'

export function NewContactModal() {
  const { outreach } = useWorkspaceContext()
  if (!outreach.formOpen) return null

  return (
    <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) outreach.setFormOpen(false) }}>
      <section className="contact-modal" role="dialog" aria-modal="true" aria-labelledby="contact-form-title">
        <div className="modal-heading">
          <div><h2 id="contact-form-title">Adicionar contacto</h2></div>
          <button className="icon-button" type="button" aria-label="Fechar formulário" onClick={() => outreach.setFormOpen(false)}><X size={18} /></button>
        </div>
        <p className="modal-description">Liga uma pessoa ou equipa de recrutamento a uma empresa.</p>
        <form className="contact-form" onSubmit={(event) => void outreach.createContact(event)}>
          <label>Empresa <span>*</span><input required maxLength={150} value={outreach.form.name_company} onChange={(event) => outreach.setForm({ ...outreach.form, name_company: event.target.value })} placeholder="Nome da empresa" /></label>
          <div className="form-row">
            <label>Nome do contacto<input maxLength={150} value={outreach.form.name_contact} onChange={(event) => outreach.setForm({ ...outreach.form, name_contact: event.target.value })} placeholder="Pessoa ou equipa" /></label>
            <label>Função<input maxLength={150} value={outreach.form.role_contact} onChange={(event) => outreach.setForm({ ...outreach.form, role_contact: event.target.value })} placeholder="Ex.: Talent Acquisition" /></label>
          </div>
          <div className="form-row">
            <label>Email<input type="email" maxLength={320} value={outreach.form.email} onChange={(event) => outreach.setForm({ ...outreach.form, email: event.target.value })} placeholder="carreiras@empresa.pt" /></label>
            <label>Categoria<select value={outreach.form.contact_type} onChange={(event) => outreach.setForm({ ...outreach.form, contact_type: event.target.value })}><option value="careers">Carreiras</option><option value="recruitment">Recrutamento</option><option value="general">Geral</option></select></label>
          </div>
          <label>URL da fonte<input type="url" maxLength={1000} value={outreach.form.source_url} onChange={(event) => outreach.setForm({ ...outreach.form, source_url: event.target.value })} placeholder="https://empresa.pt/carreiras" /></label>
          <div className="modal-actions">
            <button className="button button-quiet" type="button" onClick={() => outreach.setFormOpen(false)}>Cancelar</button>
            <button className="button button-primary" type="submit" disabled={outreach.isSaving}>{outreach.isSaving ? <RefreshCw className="spin" size={16} /> : <Plus size={16} />}{outreach.isSaving ? 'A guardar...' : 'Guardar contacto'}</button>
          </div>
        </form>
      </section>
    </div>
  )
}
