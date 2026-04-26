import { client } from './client'

export interface WaveUploadResponse {
  file_id: string
  filename: string
  rows: number
  columns: number
  column_names: string[]
}

export interface DiffSummary {
  wave1_rows: number
  wave2_rows: number
  new_count: number
  removed_count: number
  common_count: number
  changed_count: number
}

export interface DiffResponse {
  summary: DiffSummary
  new_rows: Record<string, unknown>[]
  removed_rows: Record<string, unknown>[]
  changed_rows: Record<string, unknown>[]
  common_columns: string[]
}

export interface InterviewerShiftRow {
  [key: string]: unknown
  wave1_count: number
  wave2_count: number
  change: number
  change_pct: number
}

export interface InterviewerShiftResponse {
  rows: InterviewerShiftRow[]
  interviewer_column: string
}

export async function uploadWave2(file: File): Promise<WaveUploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await client.post<WaveUploadResponse>('/api/compare/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function computeDiff(
  fileId1: string,
  fileId2: string,
  idColumn: string,
  compareColumns: string[],
): Promise<DiffResponse> {
  const { data } = await client.post<DiffResponse>('/api/compare/diff', {
    file_id_1: fileId1,
    file_id_2: fileId2,
    id_column: idColumn,
    compare_columns: compareColumns,
  })
  return data
}

export async function computeInterviewerShift(
  fileId1: string,
  fileId2: string,
  interviewerColumn: string,
): Promise<InterviewerShiftResponse> {
  const { data } = await client.post<InterviewerShiftResponse>('/api/compare/interviewer-shift', {
    file_id_1: fileId1,
    file_id_2: fileId2,
    interviewer_column: interviewerColumn,
  })
  return data
}
