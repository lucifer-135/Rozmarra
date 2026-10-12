// The dashboard only displays results. All logic lives in the Rozmarra Python
// package, which the API at /api serves.

export interface HealthResponse {
  status: string
  service: string
  version: string
  message: string
}

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch('/api/health')
  if (!response.ok) {
    throw new Error(`The Rozmarra service answered with status ${response.status}.`)
  }
  return (await response.json()) as HealthResponse
}
