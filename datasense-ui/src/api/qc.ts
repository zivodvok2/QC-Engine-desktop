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
