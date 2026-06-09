import { client } from './client'
import type { JobStatus, QCConfig, QCResults, RunResponse } from '../types'

export async function runQC(fileId: string, config: QCConfig): Promise<RunResponse> {
  const { data } = await client.post<RunResponse>('/api/run', { file_id: fileId, config })
  return data
}

export async function getStatus(jobId: string): Promise<JobStatus> {
  const { data } = await client.get<JobStatus>(`/api/status/${jobId}`)
  return data
}

export async function getResults(jobId: string): Promise<QCResults> {
  const { data } = await client.get<QCResults>(`/api/results/${jobId}`)
  return data
}

export async function downloadReport(jobId: string): Promise<Blob> {
  const { data } = await client.get(`/api/report/${jobId}`, { responseType: 'blob' })
  return data
}

export interface SupplementalPayload {
  check_name: string
  issue_type?: string
  severity?: string
  flag_count?: number
  flagged_rows?: Record<string, unknown>[]
}

export async function addSupplemental(jobId: string, payload: SupplementalPayload): Promise<void> {
  await client.post(`/api/job/${jobId}/supplemental`, {
    check_name: payload.check_name,
    issue_type: payload.issue_type ?? 'Custom Check',
    severity: payload.severity ?? 'warning',
    flag_count: payload.flag_count ?? payload.flagged_rows?.length ?? 0,
    flagged_rows: payload.flagged_rows ?? [],
  })
}
