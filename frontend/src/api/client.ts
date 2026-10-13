// The dashboard only displays results. All logic lives in the Rozmarra Python
// package, which the API at /api serves.

import type {
  ApprovalResult,
  Comparison,
  FastTemplate,
  FastingPlan,
  History,
  IdfDar,
  ModelCard,
  PatientDetail,
  PatientRow,
  PlanOptions,
  ReplayMoment,
  ReplayOverview,
  SavedPlans,
  Timeseries,
  Twin,
} from './types'

export interface HealthResponse {
  status: string
  service: string
  version: string
  message: string
}

/** An error from the API. The message is the explanation that the API gave, if any. */
export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
  })
  if (!response.ok) {
    let message = `The Rozmarra service answered with status ${response.status}.`
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      // The answer had no JSON body, so the general message stays.
    }
    throw new ApiError(response.status, message)
  }
  return (await response.json()) as T
}

const post = <T>(path: string, body: unknown, method = 'POST') =>
  request<T>(path, { method, body: JSON.stringify(body) })

export const fetchHealth = () => request<HealthResponse>('/health')
export const fetchPatients = () => request<PatientRow[]>('/patients')
export const fetchPatient = (id: string) => request<PatientDetail>(`/patients/${id}`)
export const fetchIdfDar = (id: string) => request<IdfDar>(`/patients/${id}/idf-dar`)
export const fetchTwin = (id: string) => request<Twin>(`/patients/${id}/twin`)
export const fetchHistory = (id: string) => request<History>(`/patients/${id}/history`)
export const fetchTemplates = () => request<FastTemplate[]>('/templates')
export const fetchPlanOptions = () => request<PlanOptions>('/plan-options')
export const fetchDefaultPlan = (id: string) => request<FastingPlan>(`/patients/${id}/plans/default`)
export const fetchSavedPlans = (id: string) => request<SavedPlans>(`/patients/${id}/plans`)

export function fetchTimeseries(id: string, start: string, end: string) {
  const query = new URLSearchParams({ start, end })
  return request<Timeseries>(`/patients/${id}/timeseries?${query.toString()}`)
}

export const planFromTemplate = (id: string, templateId: string, date: string) =>
  post<FastingPlan>(`/patients/${id}/plans/from-template`, { template_id: templateId, date })

export const comparePlans = (id: string, planA: FastingPlan, planB: FastingPlan) =>
  post<Comparison>(`/patients/${id}/compare`, { plan_a: planA, plan_b: planB })

export const savePlan = (id: string, planId: string, plan: FastingPlan) =>
  post<FastingPlan>(`/patients/${id}/plans/${planId}`, plan, 'PUT')

export const approvePlan = (
  id: string,
  planId: string,
  plan: FastingPlan,
  doctorName: string,
  doctorContact = '',
) =>
  post<ApprovalResult>(`/patients/${id}/plans/${planId}/approve`, {
    doctor_name: doctorName,
    doctor_contact: doctorContact,
    plan,
  })

export const fetchReplay = (id: string) => request<ReplayOverview>(`/patients/${id}/replay`)

export function fetchReplayAt(id: string, at: string) {
  return request<ReplayMoment>(`/patients/${id}/replay?${new URLSearchParams({ at }).toString()}`)
}

export const fetchModelCard = () => request<ModelCard>('/model-card')

/** The address of the printable patient plan, which the API returns as an HTML page. */
export function documentUrl(id: string, planId: string, lang: string) {
  return `/api/patients/${id}/plans/${planId}/document?lang=${lang}`
}

export async function fetchPlanMessage(id: string, planId: string, lang: string) {
  const response = await fetch(`${documentUrl(id, planId, lang)}&format=text`)
  if (!response.ok) {
    throw new ApiError(response.status, `The Rozmarra service answered with status ${response.status}.`)
  }
  return response.text()
}
