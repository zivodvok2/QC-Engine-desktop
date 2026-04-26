import { client } from './client'

export interface RiskRow {
  [key: string]: unknown
  risk_score: number
  risk_level: 'HIGH' | 'MEDIUM' | 'LOW'
  total_interviews: number
  total_flags: number
  flag_rate_pct: number
  fabrication_flags: number
  duration_flags: number
  straightlining_flags: number
  productivity_flags: number
  verbatim_flags: number
}

export interface RiskResponse {
  rows: RiskRow[]
  interviewer_column: string
}

export async function computeRisk(
  fileId: string,
  jobId: string,
  interviewerColumn: string,
  redThreshold = 60,
  amberThreshold = 30,
): Promise<RiskResponse> {
  const { data } = await client.post<RiskResponse>('/api/interviewers/risk', {
    file_id: fileId,
    job_id: jobId,
    interviewer_column: interviewerColumn,
    red_threshold: redThreshold,
    amber_threshold: amberThreshold,
  })
  return data
}
