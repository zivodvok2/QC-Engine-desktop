import { client } from './client'

export interface Project {
  id: number
  name: string
  client: string | null
  status: string
  sample_target: number
  job_number: string | null
  column_config?: string | null
}

export interface SaveQCResult {
  status: string
  upload_id: string
  row_count: number
}

function authHeader(token: string) {
  return { Authorization: `Bearer ${token}` }
}

export async function getProjects(token: string): Promise<Project[]> {
  const { data } = await client.get<Project[]>('/api/projects', {
    headers: authHeader(token),
  })
  return data
}

export async function createProject(name: string, token: string): Promise<Project> {
  const { data } = await client.post<Project>(
    '/api/projects',
    { name },
    { headers: authHeader(token) },
  )
  return data
}

export async function saveQCResults(
  projectId: number,
  fileId: string,
  filename: string,
  token: string,
  waveLabel?: string,
  jobId?: string,
  columnConfig?: Record<string, string>,
): Promise<SaveQCResult> {
  const { data } = await client.post<SaveQCResult>(
    `/api/projects/${projectId}/qc-results`,
    {
      file_id: fileId, filename, wave_label: waveLabel || null, job_id: jobId || null,
      column_config: columnConfig || null,
    },
    { headers: authHeader(token) },
  )
  return data
}
