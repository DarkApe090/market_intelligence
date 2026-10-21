export type AppPage = 'vagas' | 'contactos' | 'perfil'
export type OutreachStatus = 'to_contact' | 'sent' | 'replied' | 'no_email' | 'rejected'
export type StatusFilter = 'all' | OutreachStatus
export type DraftLanguage = 'en' | 'pt'
export type ToastKind = 'success' | 'error' | 'warning' | 'confirm'

export interface MailReply {
  sender: string
  subject: string
  body: string
  sent_at: string | null
  outreach_status?: OutreachStatus | null
}

export interface OutreachContact {
  id_company: number
  name_company: string
  job_title: string | null
  id_jobPosting: number | null
  job_seen_at: string | null
  id_contact: number
  name_contact: string | null
  role_contact: string | null
  contact_type: string | null
  cellphone: string | null
  telephone: string | null
  email: string | null
  source_url: string | null
  website_url: string | null
  outreach_status: OutreachStatus
  sent_at: string | null
}

export interface Company {
  id_company: number
  name_company: string
}

export interface Contact {
  id_contact: number
}

export interface CvEvidence {
  text: string
  section: string
}

export interface CvArea {
  key: string
  name: string
  search_query: string
  matched_skills: string[]
  confidence: 'high' | 'medium' | 'low'
  evidence: CvEvidence[]
}

export interface ProfileAreaEdit {
  name: string
  skills: string[]
}

export type WorkMode = 'onsite' | 'hybrid' | 'remote'
export type Schedule = 'full_time' | 'part_time'

export interface JobSuggestion {
  company: string
  title: string
  location: string
  work_mode: WorkMode | null
  posted_at: string | null
  summary: string
  email: string | null
  location_priority: number
  url: string
  area: string
  source: string
  matched_skills: string[]
  rating?: number
  review_count?: number
  salary?: string
  seniority?: string
  company_url?: string
  schedule?: Schedule
  contract?: string
  tags?: string[]
}

export interface DraftResult {
  fit_score: number
  fit_reason: string
  subject: string | null
  body: string | null
  skipped: boolean
}

export interface CandidateProfile {
  name: string | null
  skills: string[]
}

export interface ContactDraft {
  key: string
  isLoading: boolean
  fitScore?: number
  fitReason?: string
  skipped?: boolean
  subject: string
  body: string
}

export interface GoogleStatus {
  configured: boolean
  connected: boolean
  email: string | null
  can_follow_replies: boolean
}

export interface StoredCv {
  filename: string
  candidate_name: string | null
  skills: string[]
  areas: { name: string, matched_skills: string[] }[]
  uploaded_at: string | null
}

export interface Session {
  user: { email: string, name: string | null, picture: string | null }
  cv: StoredCv | null
  google: GoogleStatus
}

export interface CvAnalysis {
  candidate_name: string | null
  areas: CvArea[]
  suggestions: JobSuggestion[]
  search_errors: string[]
  excluded_location_count: number
  cv_saved: boolean
  llm_used: boolean
  already_in_list_count: number
  location_priority_order: string[]
}

export interface ContactForm {
  name_company: string
  name_contact: string
  role_contact: string
  contact_type: string
  email: string
  source_url: string
}

export interface AppToast {
  kind: ToastKind
  message: string
  confirmLabel?: string
  onConfirm?: () => void
}
